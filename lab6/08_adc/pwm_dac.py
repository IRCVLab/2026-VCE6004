#!/usr/bin/env python3
# ===== 실습 8 선택 — PWM + RC 필터 = 싸구려 DAC, ADS1115 로 확인 (pwm_dac.py) =====
# 목적: PWM 듀티 0~100 % 를 RC 저역 필터에 통과시켜 평균 전압을 만들고, 듀티-전압이 선형인지 ADS1115 로 측정
# 배선: 핀 15(PWM A) ─ 10 kΩ ─┬─ ADS1115 A1
#                              └─ 10 µF ─ GND        (RC 시정수 = 10 kΩ × 10 µF = 100 ms)
#       (ADS1115 배선은 ads1115.py 참고. 10 µF 가 없으면 이 실습은 건너뛰어도 됨)
# 실행: python3 pwm_dac.py        듀티 0 → 100 % (10 % 간격) → 표 출력 + pwm_dac.csv
#       python3 pwm_dac.py --bus 1 --freq 20000
# 주의: 전해 커패시터는 극성(긴 다리 +) — + 를 A1 쪽, − 를 GND 쪽에
import argparse
import time

import Jetson.GPIO as GPIO
from ads1115 import ADS1115
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import PWM_A, hint, require_pwm, save_csv

ap = argparse.ArgumentParser()
ap.add_argument("--bus", type=int, default=None)
ap.add_argument("--freq", type=float, default=20000.0, help="PWM 주파수 Hz (기본 20 kHz)")
args = ap.parse_args()

VCC = 3.3
adc, pwm = None, None
try:
    adc = ADS1115(args.bus)
    GPIO.setmode(GPIO.BOARD)
    require_pwm(PWM_A)
    pwm = GPIO.PWM(PWM_A, args.freq)          # 20 kHz: RC 필터가 걸러내기 쉬울 만큼 빠르게
    pwm.start(0)
    print(f"PWM {args.freq:g} Hz → RC 필터 → ADS1115 A1")
    print("듀티(%) | 이론 전압(V) | 측정 전압(V) | 오차(mV)")
    rows = []
    for duty in range(0, 101, 10):
        pwm.ChangeDutyCycle(duty)
        time.sleep(1.0)                        # 시정수 100 ms 의 10 배 기다려 전압이 안정되게
        v = sum(adc.read_single(1) for _ in range(8)) / 8      # 8 번 평균
        ideal = VCC * duty / 100.0
        rows.append((duty, f"{ideal:.3f}", f"{v:.3f}", f"{(v - ideal) * 1000:.0f}"))
        print(f"{duty:7d} | {ideal:12.3f} | {v:12.3f} | {(v - ideal) * 1000:8.0f}")
    save_csv("pwm_dac.csv", ["duty_percent", "ideal_v", "measured_v", "error_mv"], rows)
    print("→ 듀티-전압 그래프를 그려 선형인지 확인 (130 번 슬라이드의 실측)")
except KeyboardInterrupt:
    print("\n중단")
except Exception as e:
    hint(e)
finally:
    if pwm is not None:
        pwm.ChangeDutyCycle(0)
        pwm.stop()
    if adc is not None:
        adc.close()
    GPIO.cleanup()
