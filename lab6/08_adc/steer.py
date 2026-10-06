#!/usr/bin/env python3
# ===== 실습 8 — 가변저항으로 서보 조향: "핸들 → 바퀴" (steer.py) =====
# 목적: 아날로그 입력(가변저항)을 I2C ADC 로 읽어 각도로 바꾸고 서보(PWM)를 돌린다. 20 Hz 로 갱신.
# 배선: 가변저항 → ADS1115 A0 (ADS1115 배선은 ads1115.py 참고) · 서보 신호 → 핀 18, 전원 5 V(핀 2), GND
# 실행: python3 steer.py             (가변저항을 돌려 보기, Ctrl-C 종료)
#       python3 steer.py --bus 1     (I2C 버스 번호 지정)
# 매핑: 각도 = 전압 / 3.3 V × 180°   (전압 0 ~ 3.3 V → 0° ~ 180°)
import argparse
import time

import Jetson.GPIO as GPIO
from ads1115 import ADS1115
import os, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)                          # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
sys.path.insert(0, os.path.join(_ROOT, '05_pwm'))  # 실습 5 의 servo.py (angle_to_duty) 재사용
from pins import PWM_B, hint, require_pwm
from servo import angle_to_duty            # servo.py 의 캘리브레이션 값을 그대로 사용

ap = argparse.ArgumentParser()
ap.add_argument("--bus", type=int, default=None)
args = ap.parse_args()

VREF = 3.3                # 가변저항 양끝 전압
PERIOD = 0.05             # 20 Hz

adc, pwm = None, None
try:
    adc = ADS1115(args.bus)                       # I2C 연결 확인 (실패하면 안내 후 종료)
    GPIO.setmode(GPIO.BOARD)
    require_pwm(PWM_B)
    pwm = GPIO.PWM(PWM_B, 50)
    pwm.start(angle_to_duty(90))
    print(f"조향 시작 (ADS1115 버스 {adc.busno}). 가변저항을 돌려 보세요 — Ctrl-C 종료")
    last_angle = None
    nxt = time.monotonic()
    while True:
        v = adc.read_single(0)                                    # A0 전압 (V)
        angle = max(0.0, min(180.0, v / VREF * 180.0))            # 전압 → 각도 (범위 제한)
        if last_angle is None or abs(angle - last_angle) >= 1.0:  # 1° 이상 바뀔 때만 서보 갱신 (떨림 방지)
            pwm.ChangeDutyCycle(angle_to_duty(angle))
            last_angle = angle
        print(f"\rA0 = {v:5.3f} V → 각도 {angle:6.1f}°", end="", flush=True)
        nxt += PERIOD                                             # 절대 시각으로 20 Hz 유지
        time.sleep(max(0.0, nxt - time.monotonic()))
except KeyboardInterrupt:
    print("\n종료")
except Exception as e:
    hint(e)
finally:
    if pwm is not None:
        pwm.ChangeDutyCycle(0)
        pwm.stop()
    if adc is not None:
        adc.close()
    GPIO.cleanup()
