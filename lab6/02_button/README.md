# 실습 2 — 버튼: 플로팅 · 바운스 · 디바운스 (★ 필수)

슬라이드 69~75 · HW #2 A-2 · 소요 15분

**목적**: 입력 핀의 세 가지 함정을 직접 본다 — ① 기본값이 없으면 값이 떠다닌다(플로팅) ② 한 번 눌러도 에지가 여러 개(바운스) ③ 기다릴 때 폴링은 CPU 를 태운다.

| 파일 | 역할 |
|---|---|
| `poll_button.py` | 50 ms 마다 읽기(폴링). `--nosleep` 으로 CPU 100 % 확인 |
| `floating_demo.py` | ★ 풀업 저항을 뺀 상태에서 실행 — 0/1 이 무작위로 섞임 |
| `count_button.py` | `--raw` 하강 에지 전부 카운트 / `--debounce` 30 ms 뒤 재확인 + 50 ms 무시 |
| `wait_button.py` | `wait_for_edge` 로 잠들어 기다림 → CPU 0 %. 누를 때마다 LED 1 초 |

## 배선 (전원 끄고)

```
3.3 V(핀 1) ─ 10 kΩ ─┬─ 핀 22 (BTN_L)      안 누름 = 1 (풀업)
                     └─ 버튼 ─ GND(핀 6)     누름   = 0
LED: 핀 7 ─ 330 Ω ─ LED ─ GND  (실습 1 그대로, wait_button.py 가 사용)
```

- Jetson.GPIO 는 `setup()` 의 `pull_up_down` 을 **무시**함 → 외부 10 kΩ 풀업이 필수
- 플로팅 실험(②)만 10 kΩ 을 뺀다. 버튼 반대쪽 다리는 GND 에서 떼어 둠(연결돼 있으면 항상 0). 끝나면 **복구**

## 실행 순서 (이 폴더에서)

```bash
python3 poll_button.py                       # ① 폴링. 다른 터미널 top 으로 CPU 확인
python3 poll_button.py --nosleep             #    sleep 없이 → CPU 가 어떻게 되나
python3 floating_demo.py                     # ② ★ 풀업 뺀 상태. 손가락을 점퍼 끝에 가까이/닿게
gpiomon --num-events=20 gpiochip0 96         # ③ 한 번 누르면 에지가 몇 개? (핀 22 = 라인 96)
python3 count_button.py --raw                # ④ 바운스가 그대로 카운트됨 (10 회 누르기)
python3 count_button.py --debounce           #    디바운스 후 1 번 = 1 (10 회 누르기)
python3 wait_button.py                       # ⑤ wait_for_edge. top 에서 CPU 0 % 확인
```

## 기록 항목 (보고서)

- 플로팅 관찰 캡처 (풀업 제거 전 / 후)
- 바운스: 한 번 누름당 `gpiomon` 이벤트 수 — 5 회 측정 → 평균
- 디바운스 전 / 후 카운트 표 (10 회 누름, `--raw` vs `--debounce`)
- `top` CPU 비교: 폴링(sleep 유 / 무) vs `wait_for_edge`
- 질문: "30 ms 뒤 재확인" 방식이 놓칠 수 있는 입력은? (어떤 누름을 못 세는가)

## 라이브러리 제약 (Jetson.GPIO 2.1.13)

| 항목 | 내용 |
|---|---|
| `pull_up_down` | 무시됨 → 외부 저항 |
| `wait_for_edge(timeout=)` | 단위가 **초(정수)** (RPi.GPIO 는 ms) |
| `bouncetime` | `add_event_detect` 에서만 동작. `wait_for_edge` 의 bouncetime 은 적용 안 될 수 있음 → `wait_button.py` 는 반환 뒤 직접 대기 |

## 막히면

| 증상 | 확인 |
|---|---|
| 버튼이 항상 1 | 버튼 한쪽이 GND 에 안 붙음 |
| 버튼이 항상 0 | 풀업 저항이 없음 (플로팅 실험 상태 그대로) → 10 kΩ → 3.3 V 복구 |
| `gpiomon` 이 `busy` | 그 라인을 쓰는 Python 이 살아 있음 → 종료 후 실행 |
| 디바운스 후에도 2 로 셈 | 접점이 특히 나쁜 버튼 → `count_button.py` 의 `0.030`(재확인) · `0.050`(무시) 초를 늘려 보기 |
