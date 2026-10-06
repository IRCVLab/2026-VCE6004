# 실습 6 — 트리거 신호 생성기: 원하는 주파수 · 펄스 폭을 PWM 으로 (★ 필수)

슬라이드 139~144 · HW #2 A-6 · 소요 25분

**목적**: 멀티센서 동기화용 트리거(예: 카메라 10 Hz · 펄스 1 ms)를 HW PWM 으로 만들고, 오실로스코프 없이 **`gpiomon` 커널 타임스탬프**로 주기 · 지터 · 위상차를 재서 품질을 숫자로 말한다. HW PWM(하한 · 양자화 · 위상)과 SW 토글(지터 · 부하 민감)을 같은 측정기로 비교.

| 파일 | 역할 |
|---|---|
| `trigger.sh` | sysfs 로 PWM 직접 설정: `주파수 펄스폭(µs) [컨트롤러] [--invert] [--no-enable]` / `--off`. 실패 시 원인 설명 출력 |
| `measure_period.sh` | `gpiomon` 으로 상승 에지 N 개를 커널 타임스탬프와 함께 파일로 (`-n 200 -o hw.txt [-c 칩 -l 라인]`) |
| `analyze.py` | 측정 파일 → 주기 평균 · 표준편차 · 최대 편차 표 (+ `--plot` 히스토그램). 실습 9 에서도 사용 |
| `sw_trigger.py` | 같은 10 Hz · 1 ms 를 Python 루프로 핀 7 에서 토글 (HW 와 비교용) |
| `trigger_phase.sh` / `trigger_phase.py` | 핀 15 · 18 두 채널을 동시에 켜고 위상차 측정 — 셸(enable 두 번) vs Python(연속 쓰기) |
| `phase_from_files.py` | gpiomon 파일 두 개 → 위상차 평균 · 표준편차 · 드리프트 (`trigger_phase.*` 가 내부에서 호출) |

컨트롤러 이름: 핀 15 = `3280000.pwm`(기본) · 핀 18 = `32c0000.pwm` · 핀 13 = `32f0000.pwm`. 어느 `pwmchipN` 인지는 `python3 ../pins.py`

## 배선 — 출력을 입력 핀으로 되돌리는 루프백

```
①② HW   : 핀 15(PWM A) ─ 330 Ω ─ 핀 22(BTN_L, gpiochip0 라인 96)
③  SW   : 핀 7 (LED_L) ─ 330 Ω ─ 핀 22                     ※ 핀 7/15 혼동 주의
④  위상 : 핀 15 ─ 330 Ω ─ 핀 22   +   핀 18(PWM B) ─ 330 Ω ─ 핀 16(BTN_R, gpiochip1 라인 9)
```

핀 22 · 16 에는 버튼 · 풀업이 병렬로 있어도 됨. 330 Ω 은 출력 단락 보호. 측정 중 버튼은 누르지 않기.

## 실행 순서 (이 폴더에서)

```bash
# ① 10 Hz · 1 ms 트리거 — sysfs 로 직접
./trigger.sh 10 1000                               # Invalid argument 면 20 → 50 Hz … 로 올려 '되는 최저 주파수' 찾기 (기록!)
cat /sys/class/pwm/pwmchip*/pwm0/period            # 쓰인 값 확인 (ns)

# ② 측정 — 커널 타임스탬프로 200 주기
./measure_period.sh -n 200 -o hw.txt               # 핀 22 상승 에지 200 개 (약 20 초)
python3 analyze.py hw.txt --nominal-ms 100         # 평균 · 표준편차 · 최대 편차 (명목 주기는 ① 에서 쓴 주파수에 맞춰)
./trigger.sh --off

# ③ 소프트웨어로 같은 신호 — 터미널 A 에서 측정을 먼저 켜고, 터미널 B 에서 생성
#   조건        터미널 A                                     터미널 B
#   SW          ./measure_period.sh -n 200 -o sw.txt          python3 sw_trigger.py --n 230
#   SW + chrt   ./measure_period.sh -n 200 -o sw_chrt.txt     sudo chrt -f 80 python3 sw_trigger.py --n 230
#   SW + 부하   ./measure_period.sh -n 200 -o sw_load.txt     (먼저 stress-ng -c $(nproc) --timeout 60s &) python3 sw_trigger.py --n 230
python3 analyze.py hw.txt sw.txt sw_chrt.txt sw_load.txt --nominal-ms 100 --plot period_hist.png

# ④ 두 채널 위상차 — 핀 15 · 18 동시 10 Hz
./trigger_phase.sh                                 # 셸: enable 을 두 번 연달아 (권한 없으면 sudo)
python3 trigger_phase.py --repeat 3                # Python: 시작할 때마다 위상차가 달라지나, 한 번 정해지면 유지되나

# ⑤ 사양 바꾸기 — 30 Hz · 100 µs · 액티브 로우, 펄스 폭 확인
./trigger.sh 30 100 --invert
gpiomon --num-events=20 --format="%e %s.%n" gpiochip0 96    # %e 1=상승 0=하강 → 인접 두 시각의 차 = 펄스 폭
./trigger.sh --off
```

## 결과 읽는 법

- **평균 − 명목** = 체계적 오차 (PWM 클럭 분주 · 8 비트 듀티 양자화) → 센서 사이의 누적 드리프트의 원인
- **표준편차** = 지터, **최대 편차** = 최악의 한 번 (동기화 요구는 보통 최악값으로 말함)
- `gpiomon` 으로 잰 µs 지터는 "GPIO 인터럽트 → 커널 타임스탬프" 측정 경로의 것 — HW PWM 자체는 더 좋음. **측정 하한을 알고 읽기**. SW 트리거의 ms 지터는 하한보다 훨씬 커서 SW 자체의 것
- 위상차: 독립 컨트롤러 두 개는 "누가 먼저 시작했나" 가 남음 → 같은 카운터의 다중 비교 채널(MCU 타이머) 또는 PPS 재동기(입력 캡처 필요)가 답

## 기록 항목 (보고서)

1. 되는 최저 HW PWM 주파수(Hz) 와 그때의 오류 메시지 캡처 (`trigger.sh` 설명 포함)
2. HW 10 Hz(또는 대체 주파수) 주기 통계 표: 평균 · 표준편차 · 최대 편차 + 히스토그램
3. SW / SW+chrt / SW+부하 같은 표 — HW 와 비교 1 문단
4. 2 채널 위상차: Python 3 회 · 셸 1 회 값, '유지되는가'
5. 30 Hz · 100 µs 펄스 폭 측정값 · `--invert` 캡처
6. "이 Jetson 으로 10 Hz 카메라 트리거를 PPS 에 맞추려면 무엇이 더 필요한가" 3 문장

## 막히면

| 증상 | 확인 |
|---|---|
| `pwmchip` 이 없음 | jetson-io 미설정 → `../05_pwm/README.md` 준비 확인 (재부팅 필요) |
| `Invalid argument` (enable 시) | 주파수가 이 장비 PWM 하한 밖 · 펄스 폭 > 주기 · 쓰기 순서 → 주파수를 올려 보기. **10 Hz 가 안 되는 장비는 정상일 수 있음** — 되는 값을 기록하고 이후 단계는 그 주파수로 (`--nominal-ms` 도 맞춰) |
| `Permission denied` (`/sys/class/pwm`) | `sudo ./trigger.sh …` 또는 `bash ../setup_lab6.sh` 후 재부팅 |
| `gpiomon` 이 아무것도 안 찍음 | `trigger.sh` 가 켜져 있나 · 점퍼(핀 15 → 22) · SW 는 핀 **7** 인지 |
| `gpiomon` busy | 그 라인을 쓰는 Python 이 살아 있음 → 종료 후 측정 |
| 측정 파일이 비어 있음 | 터미널 A(측정)를 먼저 켜고 B(생성)를 시작했는지 · `--n 230` 으로 넉넉히 |
| 끝낸 뒤 | `./trigger.sh --off` (핀 18 은 `./trigger.sh --off 32c0000.pwm`) — 공용 장비 핀 상태 원복 |
