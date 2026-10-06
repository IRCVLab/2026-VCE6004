# 실습 5 — PWM 디밍 · 서보 (★ 필수)

슬라이드 134~138 · HW #2 A-5 · 소요 15분

**목적**: PWM 은 **주파수 + 듀티** 두 숫자. 듀티로 LED 밝기를 바꾸고(200 Hz), 주파수를 5 Hz 로 낮추면 같은 듀티가 깜빡임으로 보임을 확인. 서보는 "펄스 폭 = 각도" — 개체마다 끝점이 달라 캘리브레이션이 필요.

| 파일 | 역할 |
|---|---|
| `pwm_led.py` | 핀 15 HW PWM, 듀티 0 → 100 → 0 % 삼각파 (2 초 주기). `--freq 5` 로 깜빡임, `--soft` 는 핀 7 소프트웨어 PWM 대체 |
| `servo.py` | 핀 18 50 Hz. `--cal` 로 0° · 180° 듀티 실측 → 상단 `DUTY_0` · `DUTY_180` 에 기록 → 0→90→180→90 왕복. 실습 8 `steer.py` 가 이 값을 그대로 가져다 씀 |

## 준비 확인 — jetson-io 로 PWM 핀이 켜져 있어야 함 (재부팅 1 회)

```bash
ls /sys/class/pwm/                     # pwmchip 이 (보통 3 개) 보여야 함. 없으면 ↓
sudo /opt/nvidia/jetson-io/jetson-io.py   # Configure Jetson 40pin Header → Configure header pins manually → pwm(13·15·18) → Save and reboot
python3 ../pins.py                     # 재부팅 후: 어느 pwmchipN 이 핀 15(3280000.pwm) · 18(32c0000.pwm) · 13(32f0000.pwm) 인지
```

핀 13 · 15 · 18 은 기본이 GPIO. pinmux 를 PWM 으로 바꿔야 `/sys/class/pwm` 에 나타남 (슬라이드 28 · `../README.md` 2 절). 끝내 안 되면 `pwm_led.py --soft` 로 진행하고, 서보는 핀 7 소프트웨어 PWM 으로 떨림을 관찰하는 것으로 대체.

## 배선

```
LED : 핀 15(PWM A) ─ 330 Ω ─ LED ─ GND        (--soft 는 핀 7 의 LED)
서보: 갈색 ─ GND · 빨강 ─ 5 V(핀 2) · 주황(신호) ─ 핀 18(PWM B)
```

서보가 움직일 때 접속이 끊기거나 보드가 리셋되면 기동 전류 때문 → 외부 5 V 어댑터(GND 는 보드와 공통)

## 실행 순서 (이 폴더에서)

```bash
python3 pwm_led.py                 # ① 200 Hz 디밍 — 밝기가 듀티에 비례해 보이나?
python3 pwm_led.py --freq 5        # ② 5 Hz → 깜빡임. 깜빡임이 사라지는 주파수를 10 → 20 → 50 Hz 로 찾아 보기
python3 servo.py --cal             # ③ 듀티(%) 를 직접 입력해 0° · 180° 끝점 찾기 (예 2.5 · 12.5) → servo.py 상단에 기록
python3 servo.py                   # ④ 0 → 90 → 180 → 90 왕복 3 회 (--loops 0 이면 Ctrl-C 까지)
```

## 기록 항목 (보고서)

- `python3 ../pins.py` 출력 캡처 (pwmchip ↔ 핀 대응)
- 서보 캘리브레이션 표: 0° · 90° · 180° 실측 듀티(%) + 펄스 폭(ms) 환산 (50 Hz → 주기 20 ms × 듀티)
- 5 Hz 깜빡임 캡처 또는 10 초 영상 링크 · 깜빡임이 사라지는 주파수(개인별)
- 질문 ① 듀티 50 % 가 '절반 밝기' 로 안 보이는 이유 2 문장 (눈의 감도 · 감마)
- 질문 ② 서보 신호를 핀 7(SW PWM) 로 주면 어떤 현상이 예상되나

## 막히면

| 증상 | 확인 |
|---|---|
| `pwmchip` 이 없음 | jetson-io 미설정 또는 재부팅 전 → 위 '준비 확인' |
| `GPIO.PWM` 에서 오류 / `Invalid argument` | 핀 15 · 18 이 아닌 핀에 PWM · jetson-io 전 · 주파수가 장비 범위 밖 → `../pins.py` 로 확인 |
| 서보가 끝에서 떨림(버징) | 끝점을 넘어간 듀티 → `--cal` 로 범위를 안쪽으로 |
| 서보가 아예 안 움직임 | 5 V 전원 · GND 공통 · 신호선이 핀 18 인지 · PWM B 가 활성화됐는지 |
| 밝기가 안 변하고 켜져만 있음 | 핀 15 가 아직 GPIO 모드 — `/sys/class/pwm` 확인 |
