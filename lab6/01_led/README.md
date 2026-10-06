# 실습 1 — LED: gpioset → Python (★ 필수)

슬라이드 63~68 · HW #2 A-1 · 소요 10분

**목적**: 핀 하나를 출력으로 잡아 전압을 바꾸는 가장 작은 일. 라이브러리 없이(`gpioset`) 한 번, Python(`blink.py`)으로 한 번 — 같은 일이 어떻게 커널까지 내려가는지 본다.

| 파일 | 역할 |
|---|---|
| `blink.py` | 핀 7 LED 0.5 초 간격 깜빡임. `setmode → setup → output → finally cleanup` 의 기본 패턴 |
| `buzzer.py` | (확장) 핀 13 → 트랜지스터 → 부저. "핀은 전원이 아니다" — 큰 부하는 스위치로 |

## 배선 (전원 끄고)

```
핀 7 ─ 330 Ω ─ LED(긴 다리 +) ─ LED(짧은 다리 −) ─ GND(핀 6)
```

확장(부저): `핀 13 ─ 10 kΩ ─ 2N2222 베이스` · `이미터 ─ GND` · `컬렉터 ─ 부저(−)` · `부저(+) ─ 5 V(핀 2)`

## 실행 순서 (이 폴더에서)

```bash
gpioinfo gpiochip0 | grep PQ.06                 # ① 핀 7 의 라인 번호 찾기 → 106
gpioset --mode=time --sec=3 gpiochip0 106=1     # ② 라이브러리 없이 3 초 켜기
python3 blink.py                                # ③ Python 으로 깜빡임, Ctrl-C → LED 가 꺼지는지(cleanup)
python3 buzzer.py                               # ④ (확장) 삐-삐-삐—— 3 회
```

## 기록 항목 (보고서)

- 회로 사진 (LED · 확장했으면 트랜지스터 배선)
- `gpioinfo` 로 찾은 핀 7 의 라인 번호 캡처
- `blink.py` 실행 캡처 (시작 · Ctrl-C · 종료 메시지)
- 질문 ① 저항을 330 Ω → 1 kΩ 으로 바꾸면 밝기는? — 전류 계산 (3.3 V − LED 전압) / R 으로 답
- 질문 ② `cleanup()` 을 빼고 종료한 뒤 다시 실행하면 어떤 오류가 나는가 (직접 해 보고 메시지 붙이기)

## 막히면

| 증상 | 확인 |
|---|---|
| LED 안 켜짐 | 긴 다리가 + 쪽인지 · 저항 · GND 연결 · **BOARD 번호**(7)인지 · `bash ../pincheck.sh --only out` |
| `Device or resource busy` | 이전 프로그램이 핀을 잡고 있음 → `ps -ef \| grep python` 으로 종료 |
| `Permission denied` | `bash ../setup_lab6.sh` 후 재로그인. 급하면 `sudo python3 blink.py` |
| `No module named 'Jetson'` | `bash ../setup_lab6.sh` 또는 `sudo pip3 install Jetson.GPIO` |
