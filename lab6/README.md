# lab6 — 6주차 Embedded I/O 실습 코드

차량용 임베디드 시스템 설계 · 6주차 (Basics SW | Embedded I/O) · Jetson AGX Orin Developer Kit (JetPack 6.x · Ubuntu 22.04 · Python 3.10)

- 핀 번호는 전부 **BOARD 번호**(40핀 헤더에 인쇄된 물리 번호). 코드는 `GPIO.setmode(GPIO.BOARD)` + `try/finally: GPIO.cleanup()`
- 핀 배정은 `pins.py` 한 곳에 모아 둠 → 핀을 바꿀 때는 이 파일만 수정. 각 실습 폴더의 코드는 상위 폴더의 `pins.py` 를 자동으로 찾음
- 이 폴더는 Jetson 에서 실행하는 코드. 장비가 없는 곳에서는 `python3 -m py_compile */*.py` 문법 검사까지만 가능
- **실습 폴더마다 `README.md` 가 있음** — 배선 · 실행 순서 · 보고서 기록 항목 · 막힐 때 볼 곳. 실습은 그 폴더로 `cd` 해서 진행

## 1. 폴더 구조 — 실습 번호 = 폴더 번호

```
lab6/
├── README.md          ← 이 파일 (전체 안내 · 핀 배정표 · 문제 해결)
├── pins.py            ← 공통: 핀 상수 · 핀→(gpiochip, 라인) 표 · pwmchip_for() · 오류 안내 hint().  python3 pins.py 로 장비 상태 확인
├── setup_lab6.sh      ← 준비: 패키지 설치 · 그룹 · udev (Jetson 1대당 한 번)
├── pincheck.sh        ← 준비: 핀 사전 점검 (출력·입력·PWM·I2C)
├── requirements.txt   ← 파이썬 패키지 (smbus2 · matplotlib 선택)
│
├── 01_led/            ★ 실습 1  LED — gpioset → Python            blink.py · buzzer.py
├── 02_button/         ★ 실습 2  버튼 — 플로팅·바운스·디바운스      poll_button.py · floating_demo.py · count_button.py · wait_button.py
├── 03_interrupt/      ★ 실습 3  인터럽트 — 반응속도 게임            event_callback.py · reaction.py · reaction_poll.py
├── 04_loopback/       ○ 실습 4  루프백 지연 측정                    loopback.py · latency_plot.py
├── 05_pwm/            ★ 실습 5  PWM 디밍 · 서보                     pwm_led.py · servo.py
├── 06_trigger/        ★ 실습 6  트리거 신호 생성기 (+ 측정 도구)     trigger.sh · measure_period.sh · analyze.py · sw_trigger.py · trigger_phase.sh · trigger_phase.py · phase_from_files.py
├── 07_ultrasonic/     ○ 실습 7  초음파 주차보조(PDC)                pdc.py
├── 08_adc/            ○ 실습 8  ADS1115 가변저항 → 서보 조향         ads1115.py · steer.py · pwm_dac.py
└── 09_lamp/           ★ 실습 9  종합 — 램프 컨트롤러                lamp_skeleton.py (뼈대) · lamp.py (정답)
```

★ 수업 중 필수 6개 · ○ 시간이 되면 3개 (못 하면 과제에서). 과제(HW #2)는 **9개 전부** → `../docs/HW2_과제안내.md`

| # | 폴더 | 실습 | 핵심 관찰 | 슬라이드 |
|---|---|---|---|---|
| 1 | `01_led` | LED — gpioset → Python | 라이브러리 없이 핀 켜기, cleanup | 63~68 |
| 2 | `02_button` | 버튼 — 플로팅·바운스·디바운스 | 풀업 제거 시 값이 떠다님, 한 번 눌러도 에지 여러 개 | 69~75 |
| 3 | `03_interrupt` | 인터럽트 — 반응속도 게임 | wait_for_edge vs 콜백 vs 폴링, 부정 출발 | 95~101 |
| 4 | `04_loopback` | 루프백 지연 측정 | 무부하/부하/SCHED_FIFO 지연의 꼬리 | 102~104 |
| 5 | `05_pwm` | PWM 디밍 · 서보 | 200 Hz vs 5 Hz, 각도↔듀티 캘리브레이션 | 134~138 |
| 6 | `06_trigger` | 트리거 신호 생성기 | HW PWM 하한·양자화, SW 지터, 2채널 위상차 | 139~144 |
| 7 | `07_ultrasonic` | 초음파 주차보조(PDC) | 사용자 공간 펄스 폭 측정의 산포 | 145~148 |
| 8 | `08_adc` | ADS1115 가변저항 → 서보 조향 | I2C 레지스터 읽기, 아날로그 → 각도 | 164~167 |
| 9 | `09_lamp` | 종합 — 램프 컨트롤러 | 상태기계 · 이벤트 큐 · 주기 검증 | 169~177 |

(슬라이드 번호는 2026-10-06 배포판 기준)

### 폴더를 넘어 쓰는 파일
- 실습 9 의 주기 분석과 커널 타임스탬프 측정은 **실습 6 의 도구**를 그대로 씀: `python3 ../06_trigger/analyze.py …`, `../06_trigger/measure_period.sh …`
- 실습 8 의 `steer.py` 는 실습 5 `servo.py` 의 각도→듀티 변환(캘리브레이션 값)을 import 함 → `servo.py --cal` 로 맞춘 값이 그대로 반영됨
- 실습 7 의 부저 회로는 실습 1 확장(`buzzer.py`)과 동일

## 2. 실행 순서 — 준비 (Jetson 1대당 한 번)

```bash
# 0) 코드 받기 (노트북에서):  scp -r lab6/ user@192.168.55.1:~/
cd ~/lab6
chmod +x *.sh */*.sh                          # 복사 과정에서 실행 권한이 빠졌을 때 (./trigger.sh 가 Permission denied 면)

# 1) 환경 준비 (인터넷 필요 3~5분) → 끝나면 재로그인
bash setup_lab6.sh

# 2) PWM 핀 활성화 (한 번, 재부팅 필요) — 실습 5·6·8·9 에 필요
sudo /opt/nvidia/jetson-io/jetson-io.py     # Configure Jetson 40pin Header → Configure header pins manually → pwm(13·15·18)
ls /sys/class/pwm                            # pwmchip 3개가 보여야 함
python3 pins.py                              # 어느 pwmchip 이 핀 15·18·13 인지

# 3) 핀 점검 (LED 를 옮겨 가며) → 결과를 핀 배정표에 반영
bash pincheck.sh
```

## 3. 실행 순서 — 실습별 (각 폴더의 README.md 에 같은 내용 + 배선 + 기록 항목)

```bash
cd ~/lab6/01_led                                          # 실습 1
gpioinfo gpiochip0 | grep PQ.06                          #   핀 7 = 라인 106
gpioset --mode=time --sec=3 gpiochip0 106=1               #   라이브러리 없이 켜기
python3 blink.py                                          #   Ctrl-C 로 종료
python3 buzzer.py                                         #   (확장) 트랜지스터로 부저

cd ~/lab6/02_button                                       # 실습 2
python3 poll_button.py                                    #   --nosleep 으로 CPU 비교 (top)
python3 floating_demo.py                                  #   ★ 10 kΩ 풀업을 뺀 상태에서
gpiomon --num-events=20 gpiochip0 96                      #   한 번 누르면 에지가 몇 개?
python3 count_button.py --raw                             #   바운스가 그대로 카운트됨
python3 count_button.py --debounce                        #   디바운스 후 1번
python3 wait_button.py                                    #   wait_for_edge, CPU 0 %

cd ~/lab6/03_interrupt                                    # 실습 3
python3 event_callback.py
python3 reaction.py                                       #   → reaction_log.csv
python3 reaction_poll.py                                  #   비교용 (같은 CSV 에 mode=poll 로 이어서 저장)

cd ~/lab6/04_loopback                                     # 실습 4 (핀 7 ─ 1 kΩ ─ 핀 22 점퍼)
python3 loopback.py --tag base                            #   ① 무부하
stress-ng -c $(nproc) --timeout 120s &                    #   ② 부하를 걸어 둔 채로
python3 loopback.py --tag stress
sudo chrt -f 80 python3 loopback.py --tag fifo            #   ③ 같은 부하 속에서 실시간 우선순위 (SCHED_FIFO)
python3 latency_plot.py loopback_base.csv loopback_stress.csv loopback_fifo.csv

cd ~/lab6/05_pwm                                          # 실습 5
python3 pwm_led.py                                        #   200 Hz
python3 pwm_led.py --freq 5                               #   5 Hz → 깜빡임 (안 되면 --soft)
python3 servo.py --cal                                    #   0°·180° 듀티 실측
python3 servo.py                                          #   0→90→180→90

cd ~/lab6/06_trigger                                      # 실습 6 ①② HW PWM (핀 15 ─ 330 Ω ─ 핀 22 점퍼)
./trigger.sh 10 1000                                      #   10 Hz · 1 ms.  Invalid argument 면 20 → 50 Hz … 로 올려 하한 찾기
./measure_period.sh -n 200 -o hw.txt                      #   커널 타임스탬프로 200 에지 수집
python3 analyze.py hw.txt --nominal-ms 100                #   평균·표준편차·최대 편차
./trigger.sh --off
#   ③ SW 트리거 (핀 7 ─ 330 Ω ─ 핀 22 점퍼). 터미널 A 에서 측정을 먼저 켜 두고, 터미널 B 에서 생성
#   조건        터미널 A                                   터미널 B
#   SW          ./measure_period.sh -n 200 -o sw.txt        python3 sw_trigger.py --n 230
#   SW + chrt   ./measure_period.sh -n 200 -o sw_chrt.txt   sudo chrt -f 80 python3 sw_trigger.py --n 230
#   SW + 부하   ./measure_period.sh -n 200 -o sw_load.txt   (먼저 stress-ng -c $(nproc) --timeout 60s &)  python3 sw_trigger.py --n 230
python3 analyze.py hw.txt sw.txt sw_chrt.txt sw_load.txt --nominal-ms 100 --plot period_hist.png
#   ④ 2채널 위상차 (핀 15 ─ 330 Ω ─ 핀 22,  핀 18 ─ 330 Ω ─ 핀 16)
./trigger_phase.sh                                        #   셸 버전 (권한이 없으면 sudo)
python3 trigger_phase.py --repeat 3                       #   파이썬 버전: 시작할 때마다 위상차가 얼마나 달라지나
./trigger.sh 30 100 --invert                              #   ⑤ 사양 바꾸기: 30 Hz · 100 µs · 액티브 로우

cd ~/lab6/07_ultrasonic                                   # 실습 7
python3 pdc.py
python3 pdc.py --log --dist 50                            #   20·50·100 cm 에서 각각 → pdc_log_*.csv

cd ~/lab6/08_adc                                          # 실습 8
i2cdetect -l ; i2cdetect -y 7                             #   0x48 이 보이는지
python3 ads1115.py                                        #   A0~A3 전압 (자체 시험)
python3 steer.py                                          #   가변저항 → 서보
python3 pwm_dac.py                                        #   (선택) PWM + RC → ADS1115

cd ~/lab6/09_lamp                                         # 실습 9
python3 lamp_skeleton.py                                  #   TODO 2곳을 채워서 완성
python3 lamp.py --period-log                              #   정답 (LED L 점멸 시각 → log_period.txt)
python3 ../06_trigger/analyze.py log_period.txt --nominal-ms 666.7
```

측정 결과 파일(`*.csv` `*.txt` `*.png`)은 실행한 폴더에 생김 → 보고서에 그대로 붙이기.

## 4. 핀 배정표 (BOARD)

| 용도 | BOARD | 신호 · gpiochip 라인 | 실습 | 비고 |
|---|---|---|---|---|
| LED L (좌 방향지시등) | 7 | PQ.06 · gpiochip0 106 | 1·3·4·6·9 | 330 Ω 직렬 |
| LED R (우 방향지시등) | 12 | PH.07 · gpiochip0 50 | 3·9 | 330 Ω |
| PWM A (디밍·브레이크등·트리거 ch1) | 15 | PN.01 · 3280000.pwm | 5·6·8·9 | jetson-io PWM |
| PWM B (서보·트리거 ch2) | 18 | PH.00 · 32c0000.pwm | 5·6·8 | jetson-io PWM |
| 버튼 L · 루프백/트리거 입력 | 22 | PP.04 · gpiochip0 96 | 2·3·4·6·9 | **외부 10 kΩ 풀업**, 누르면 LOW |
| 버튼 R · 트리거 입력 2 | 16 | PBB.01 · gpiochip1(aon) 9 | 6·9 | 외부 10 kΩ 풀업 |
| 부저 (2N2222 경유) | 13 | PR.00 · gpiochip0 108 · 32f0000.pwm | 1(확장)·7 | PWM 겸용 핀 |
| 초음파 TRIG / ECHO | 29 / 31 | gpiochip1 1 / 0 | 7 | ECHO 는 1 kΩ : 2 kΩ 분압 |
| I2C SDA / SCL | 3 / 5 | I2C 버스(번호는 `i2cdetect -l`, 보통 7) | 8 | ADS1115 주소 0x48 |
| 전원 · GND | 3.3 V: 1·17 / 5 V: 2·4 / GND: 6·9·14·20·25·30·34·39 | | | 서보·초음파는 5 V |
| 예비 핀 | 32·33·35·36·37·38·40 | | | 점검에서 안 움직이는 핀 대체 |

`gpiochip0` = `tegra234-gpio`(메인), `gpiochip1` = `tegra234-gpio-aon`(상시 전원). 번호가 다르게 보이면 `gpiodetect` 의 이름으로 확인 (`pincheck.sh`·`trigger_phase.*` 는 이름으로 찾음).

## 5. 배선 메모

- **버튼 (핀 22, 핀 16)**: `3.3 V(핀 1) ─ 10 kΩ ─┬─ 핀 ─ 버튼 ─ GND`. Jetson.GPIO 는 `setup()` 의 `pull_up_down` 을 **무시**하므로 외부 풀업이 필수 (플로팅 실험은 이 저항을 뺌)
- **LED**: `핀 ─ 330 Ω ─ LED(긴 다리 +) ─ GND`
- **루프백 점퍼**: 핀 22 에는 버튼이 병렬이므로 점퍼에 330 Ω 을 직렬로 넣고, 측정 중 버튼을 누르지 않기 (출력 단락 방지). 실습 4 는 1 kΩ
- **초음파 ECHO**: 5 V 출력 → `1 kΩ ─┬─ 핀 31`, `└─ 2 kΩ ─ GND` (직결하면 핀 손상)
- **서보**: 갈색 GND · 빨강 5 V(핀 2) · 주황 신호(핀 18). 움직일 때 접속이 끊기면 외부 5 V (GND 공통)
- **ADS1115**: VDD 3.3 V(핀 1) · GND · SCL 핀 5 · SDA 핀 3 · ADDR → GND. 입력은 3.3 V 를 넘기지 말 것
- **lamp.py 주기 측정**: 실행 중인 lamp.py 가 핀 7(라인 106)을 점유 → `gpiomon` 으로 바로 못 봄. ① `--period-log` 를 쓰거나 ② 핀 7 → 핀 31 점퍼를 추가하고 `../06_trigger/measure_period.sh -c 1 -l 0 -n 200 -o lamp.txt`

## 6. 안전 수칙

- 배선·변경은 **전원을 끄고** (`sudo poweroff`) 한 뒤, 사진을 찍어 옆 조와 교차 확인
- 5 V 를 GPIO 에 직접 연결 금지 · 3.3 V/5 V 와 GND 단락 금지
- LED 는 반드시 저항과 함께 · 출력 핀끼리 연결 금지
- 서보·초음파는 5 V 핀. 서보 기동 전류로 접속이 끊기면 외부 5 V
- 공용 장비: 끝나면 프로그램을 종료(Ctrl-C → `cleanup`)하고 `pwm`을 `./trigger.sh --off` 로 해제

## 7. Jetson.GPIO 주의점 (라이브러리 2.1.13 소스로 확인 — 장비 버전은 `pip3 show Jetson.GPIO`)

| 항목 | 내용 |
|---|---|
| `pull_up_down` | `setup()` 에 넘겨도 **무시**됨(경고). 풀업은 외부 저항으로 |
| `wait_for_edge(timeout=)` | 단위가 **초(정수)**. RPi.GPIO 의 ms 와 다름 → 3 초 = `timeout=3` |
| `wait_for_edge(bouncetime=)` | 블로킹 호출에서는 적용되지 않을 수 있음 → 반환 뒤 직접 대기 (`wait_button.py`) |
| `add_event_detect` | 등록에 약 1 초 걸림. 콜백은 채널마다 스레드 1개에서 순서대로 실행, 콜백에는 **채널 번호만** 전달(에지 방향·시각 없음). 채널당 이벤트 1개 (`wait_for_edge` 와 동시 사용 불가) |
| `GPIO.BOTH` | 지원됨 (`lamp.py`). 방향은 콜백 안에서 알 수 없으므로 핀을 다시 읽어 판정 |
| 이벤트 등록 뒤 `GPIO.input()` | 동작은 하지만 라이브러리 내부 사정에 기댄 것 → 장비에서 확인 (`# 장비에서 확인` 표시) |
| PWM | `GPIO.PWM()` 은 `/sys/class/pwm` 을 감쌈. PWM 핀(13·15·18)이 아니거나 jetson-io 설정 전이면 오류 |

## 8. 문제 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| `ModuleNotFoundError: No module named 'Jetson'` | Jetson.GPIO 없음 | `bash setup_lab6.sh` 또는 `sudo pip3 install Jetson.GPIO` |
| `Permission denied` (`/dev/gpiochip*`, `/dev/i2c-*`, `/sys/class/pwm/...`) | gpio/i2c 그룹 미적용 | `groups` 에 gpio·i2c 가 있나? 없으면 `bash setup_lab6.sh` 후 **재로그인**(또는 재부팅). 급하면 `sudo` 로 실행 |
| `Device or resource busy` | 그 핀(라인)을 다른 프로세스가 잡고 있음 | `ps -ef \| grep -E "python\|gpio"` 로 찾아 종료, `gpioinfo` 에서 `[used]` 확인. `gpioset --mode=wait/signal` 은 끝낼 때까지 라인을 점유 |
| PWM 이 `Invalid argument` | 주파수가 이 장비 PWM 범위 밖 · 펄스 폭 > 주기 · 쓰기 순서 | `./trigger.sh 20 1000` → `50 1000` 으로 올려 보기 (하한 기록). `trigger.sh` 가 원인 설명을 출력 |
| `pwmchip` 이 없음 / PWM 핀 오류 | jetson-io 에서 PWM 미설정 | `sudo /opt/nvidia/jetson-io/jetson-io.py` → pwm(13·15·18) → 저장·재부팅. 급하면 `pwm_led.py --soft` |
| `[WARNING] ... set to input/output in pinmux` | 핀 멀티플렉서(pinmux)가 방향을 막고 있음 | 경고에 나온 `busybox devmem ...` 명령으로 임시 해결(재부팅 시 초기화) 또는 예비 핀으로 교체 |
| LED 안 켜짐 | 극성 · 저항 · GND · 핀 번호 | 긴 다리가 +, GND 연결, **BOARD 번호**인지, `pincheck.sh` 결과 |
| 버튼이 항상 1 | 풀업만 있고 버튼-GND 연결 없음 | 버튼 한쪽을 GND 에 |
| 버튼이 항상 0 | 풀업 저항 없음 (플로팅 실험 상태 그대로) | 10 kΩ → 3.3 V 복구 |
| I2C `Remote I/O error` / 0x48 안 보임 | 버스 번호 · SDA/SCL 바뀜 · 전원 · ADDR | `i2cdetect -l` 로 버스 확인 → `python3 steer.py --bus N`, 배선 점검 |
| `gpiomon` 이 아무것도 안 찍음 | 신호가 입력 핀에 없음 · 점퍼 빠짐 | `trigger.sh` 가 켜져 있는지, 핀 15 → 핀 22 점퍼 확인 |
| `gpiomon` busy | 그 라인을 쓰는 Python 이 살아 있음 | Python 종료 후 측정 (핀 7 은 출력 중이면 못 봄 → 핀 22/31 로 루프백) |

## 9. 장비에서 확인이 필요한 부분 (코드에 `# 장비에서 확인` 표시)

- PWM 10 Hz 가능 여부 · `Invalid argument` 가 나는 시점(period/duty/enable) — 커널·드라이버 의존
- libgpiod v1 `gpiomon --line-buffered` 옵션 이름 (없으면 `stdbuf -oL` 로 대체하도록 작성)
- 이벤트 등록(`add_event_detect`/`wait_for_edge`) 뒤의 `GPIO.input()` 동작
- `udevadm trigger` 로 권한 규칙이 즉시 적용되는지 (안 되면 재부팅)
- ADS1115 변환 완료 대기와 I2C 버스 번호(7 → 1 순서로 탐색)
