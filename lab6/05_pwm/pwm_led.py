#!/usr/bin/env python3
# ===== 실습 5 ②③ — PWM 으로 LED 밝기 조절 (pwm_led.py) =====
# 목적: 듀티 사이클(켜진 시간 비율)로 밝기를 바꾼다. 같은 듀티라도 주파수가 낮으면(5 Hz) 깜빡임이 보인다.
# 배선: 핀 15(PWM A) ─ 330 Ω ─ LED(긴 다리 +) ─ GND        (소프트웨어 모드는 핀 7 에 LED)
# 준비: jetson-io 로 PWM 활성화 + 재부팅이 끝나 있어야 함 → ls /sys/class/pwm
# 실행: python3 pwm_led.py              200 Hz, 듀티 0 → 100 → 0 % 를 반복 (2 초 주기)
#       python3 pwm_led.py --freq 5     5 Hz → 깜빡임이 눈에 보임 (슬로모션 영상도 찍어 보기)
#       python3 pwm_led.py --soft       PWM 이 안 될 때 대체: 핀 7 에서 소프트웨어 PWM (sleep 으로 토글, 지터 큼)
import argparse
import time

import Jetson.GPIO as GPIO
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import PWM_A, LED_L, hint, all_off, require_pwm

ap = argparse.ArgumentParser()
ap.add_argument("--freq", type=float, default=200.0, help="PWM 주파수 Hz (기본 200)")
ap.add_argument("--soft", action="store_true", help="소프트웨어 PWM (핀 7)")
args = ap.parse_args()

# 듀티 삼각파: 0, 2, 4 ... 100, 98 ... 2  (% 단위)
DUTIES = list(range(0, 101, 2)) + list(range(98, 0, -2))
STEP_S = 0.02            # 듀티를 20 ms 마다 바꿈


def soft_pwm(pin, freq, duty, seconds):
    """소프트웨어 PWM: 켜고 sleep, 끄고 sleep 을 seconds 동안 반복."""
    period = 1.0 / freq
    on = period * duty / 100.0
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if on > 0:
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(on)
        if period - on > 0:
            GPIO.output(pin, GPIO.LOW)
            time.sleep(period - on)


pwm = None
try:
    GPIO.setmode(GPIO.BOARD)
    if args.soft:
        GPIO.setup(LED_L, GPIO.OUT, initial=GPIO.LOW)
        print(f"소프트웨어 PWM {args.freq:g} Hz (핀 7). Ctrl-C 종료")
    else:
        require_pwm(PWM_A)                        # PWM 이 안 켜져 있으면 여기서 안내하고 종료
        pwm = GPIO.PWM(PWM_A, args.freq)          # 핀 15 를 하드웨어 PWM 으로
        pwm.start(0)                              # 듀티 0 % 로 출력 시작
        print(f"하드웨어 PWM {args.freq:g} Hz (핀 15). 밝기가 선형으로 안 느껴지는 점도 관찰. Ctrl-C 종료")
    while True:
        for duty in DUTIES:
            if args.soft:
                soft_pwm(LED_L, args.freq, duty, STEP_S)
            else:
                pwm.ChangeDutyCycle(duty)         # 듀티 변경 → 평균 전압 = 3.3 V × 듀티
                time.sleep(STEP_S)
except KeyboardInterrupt:
    print("\n종료")
except Exception as e:
    hint(e)
finally:
    if pwm is not None:
        pwm.stop()                                # PWM 출력 멈춤
    all_off(GPIO, LED_L)
    GPIO.cleanup()
