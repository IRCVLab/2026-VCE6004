# 실습 3 — 인터럽트: 콜백과 반응속도 게임 (★ 필수)

슬라이드 95~101 · HW #2 A-3 · 소요 20분

**목적**: 이벤트의 두 가지 쓰임 — **기다리기**(`wait_for_edge`, 측정)와 **콜백**(`add_event_detect`, 병행 처리). 콜백은 다른 스레드에서 돌아가므로 "큐에 넣기만 하고 끝", 판단은 메인 루프에서.

| 파일 | 역할 |
|---|---|
| `event_callback.py` | 메인 루프는 LED L 을 느리게 깜빡이고(평소 일), 버튼 콜백 → 큐 → LED R 5 회 빠르게. 콜백-큐-메인 패턴 |
| `reaction.py` | 반응속도 게임 5 라운드. 랜덤 1~4 초 뒤 LED 점등 → 버튼까지 ms. 점등 전 누르면 부정 출발 +500 ms. → `reaction_log.csv` |
| `reaction_poll.py` | 같은 게임을 1 ms 폴링으로. 반응 시간 · CPU 사용(`process_time`)을 `reaction.py` 와 비교 |

## 배선 (실습 1·2 그대로 + LED R)

```
버튼: 3.3 V(핀 1) ─ 10 kΩ ─┬─ 핀 22 ─ 버튼 ─ GND
LED L: 핀 7  ─ 330 Ω ─ LED ─ GND
LED R: 핀 12 ─ 330 Ω ─ LED ─ GND        (event_callback.py)
```

## 실행 순서 (이 폴더에서)

```bash
python3 event_callback.py        # ① 버튼을 눌러 보기 — LED L 리듬이 깨지지 않으면서 LED R 이 반응하는지
python3 reaction.py              # ② 5 라운드. 결과 표 + reaction_log.csv (mode=wait_for_edge)
python3 reaction_poll.py         # ③ 폴링 버전. 같은 CSV 에 mode=poll 로 이어서 저장
cat reaction_log.csv             #    time, mode, round, wait_s, reaction_ms, false_start, result_ms, cpu_ms
```

- 두 버전 모두 라운드마다 `cpu_ms`(그 라운드에 CPU 가 실제로 돈 시간) 를 CSV 에 기록 → "CPU 사용" 비교는 이 열로. `top` 은 보조
- 한 핀에 `wait_for_edge` 와 `add_event_detect` 를 동시에 걸 수 없음 → `reaction.py` 는 부정 출발 감시(콜백) 를 `remove_event_detect` 한 뒤 측정(`wait_for_edge`) 으로 전환

## 기록 항목 (보고서)

- `reaction.py` 5 라운드 표 (라운드 · 대기 · 반응 ms · 부정 출발 · 최종) + 최고 · 평균
- `reaction_poll.py` 결과 표 + CPU 사용(`cpu_ms` 합계) 비교
- 두 방식 비교 1 문단 — 반응 시간 차이와 CPU 차이의 원인 (코드 복잡도 포함)
- 부정 출발 처리 화면 캡처 (일부러 먼저 눌러 보기)
- 질문: 같은 방법(Python 콜백)으로 100 µs 펄스를 잴 수 없는 이유

## 숫자 감각

사람 반응 200~250 ms · 버튼 바운스 ~5 ms · 커널 → Python 콜백 ~0.5 ms · 핀 전압 변화 µs 미만 — 측정값에 무엇이 섞여 있는지 생각하며 읽기

## 막히면

| 증상 | 확인 |
|---|---|
| 시간 초과가 안 일어남 | Jetson.GPIO `wait_for_edge(timeout=)` 는 **초 단위 정수** (`TIMEOUT_S = 3`) |
| 콜백이 두 번 불림 | 바운스. `event_callback.py` 는 `bouncetime` 사용 — 그래도 2 번이면 값을 늘리기 |
| `add_event_detect` 뒤 1 초쯤 멈춘 듯 | 정상 — 이 라이브러리는 등록에 약 1 초 걸림 |
| `Conflicting edge detection` | 같은 핀에 이벤트가 이미 등록됨 → 이전 프로그램 종료, 또는 `remove_event_detect` |
