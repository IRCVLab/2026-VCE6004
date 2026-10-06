#!/usr/bin/env python3
# ===== 실습 5 ④ — 서보 모터 (servo.py) =====
# 목적: 50 Hz PWM 의 펄스 폭이 곧 각도. 0 → 90 → 180 → 90 도를 반복하고, 실제 0°·180° 듀티를 찾는다.
# 배선: SG90 서보 3선 — 갈색(GND) → 핀 6, 빨강(5 V) → 핀 2, 주황(신호) → 핀 18(PWM B)
#       (서보가 움직일 때 보드가 리셋/끊기면 외부 5 V 전원 사용, GND 는 반드시 공통)
# 준비: jetson-io 로 PWM 활성화 + 재부팅 (ls /sys/class/pwm)
# 실행: python3 servo.py            0 → 90 → 180 → 90 도를 3 번 반복  (--loops N, 0 이면 계속)
#       python3 servo.py --cal      캘리브레이션: 듀티(%)를 직접 입력해 0°·180° 끝점 찾기
# 원리: SG90 은 20 ms 주기에서 펄스 0.5 ms = 0°, 1.5 ms = 90°, 2.5 ms = 180°  (약 2.5 % ~ 12.5 %)
#       (교재의 1.0~2.0 ms 는 일반 규격. SG90 은 실제로 0.5~2.5 ms 까지 움직이는 제품이 많음)
import argparse
import time

import Jetson.GPIO as GPIO
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import PWM_B, hint, require_pwm

DUTY_0 = 2.5       # 0° 듀티(%)    ← --cal 로 실측한 값으로 바꾸면 steer.py 도 같이 좋아짐
DUTY_180 = 12.5    # 180° 듀티(%)


def angle_to_duty(a):
    """각도(0~180) → 듀티(%)."""
    a = max(0.0, min(180.0, a))
    return DUTY_0 + a / 180.0 * (DUTY_180 - DUTY_0)      # 기본값이면 2.5 + a/180*10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cal", action="store_true", help="듀티를 직접 입력하는 캘리브레이션 모드")
    ap.add_argument("--loops", type=int, default=3, help="왕복 횟수 (0 이면 Ctrl-C 까지)")
    args = ap.parse_args()

    pwm = None
    try:
        GPIO.setmode(GPIO.BOARD)
        require_pwm(PWM_B)
        pwm = GPIO.PWM(PWM_B, 50)                 # 서보는 50 Hz (주기 20 ms)
        pwm.start(angle_to_duty(90))              # 먼저 가운데(90°)
        time.sleep(1.0)
        if args.cal:
            print("듀티(%)를 입력하면 그 펄스로 서보가 움직임. 예: 2.5  7.5  12.5   (q = 종료)")
            print("0°·180° 끝에서 서보가 '윙—' 소리를 내며 밀면 한계를 넘은 것 → 값을 조금 줄이기")
            tried = []
            while True:
                text = input("듀티(%)> ").strip()
                if text.lower() in ("q", "quit", ""):
                    break
                try:
                    duty = max(0.0, min(100.0, float(text)))
                except ValueError:
                    print("숫자를 입력하세요")
                    continue
                pwm.ChangeDutyCycle(duty)
                tried.append(duty)
            print("시도한 값:", tried, "→ 0° 와 180° 에 해당하는 값을 보고서에 기록")
        else:
            n = 0
            while args.loops == 0 or n < args.loops:
                for a in (0, 90, 180, 90):
                    duty = angle_to_duty(a)
                    pwm.ChangeDutyCycle(duty)
                    print(f"{a:3d}°  듀티 {duty:5.2f} %  (펄스 {duty / 100 * 20:.2f} ms)")
                    time.sleep(1.0)
                n += 1
    except KeyboardInterrupt:
        print("\n종료")
    except Exception as e:
        hint(e)
    finally:
        if pwm is not None:
            pwm.ChangeDutyCycle(0)                # 펄스를 멈춰 서보 떨림 방지
            pwm.stop()
        GPIO.cleanup()


if __name__ == "__main__":
    main()
