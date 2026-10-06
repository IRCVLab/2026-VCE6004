#!/usr/bin/env python3
# ===== 실습 2 ① — 버튼을 폴링으로 읽기 (poll_button.py) =====
# 목적: 입력 핀 값을 주기적으로 읽는 가장 단순한 방법(폴링)과 CPU 사용량 확인
# 배선: 3.3 V(핀 1) ─ 10 kΩ ─┬─ 핀 22        (풀업: 안 누르면 1)
#                            └─ 버튼 ─ GND(핀 6)   (누르면 0)
#       ※ Jetson.GPIO 는 setup() 의 pull_up_down 을 무시함 → 외부 10 kΩ 풀업이 필요
# 실행: python3 poll_button.py             50 ms 마다 읽기
#       python3 poll_button.py --nosleep   sleep 없이 읽기 → 다른 터미널에서 top 으로 CPU 확인
import argparse
import time

import Jetson.GPIO as GPIO
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import BTN_L, hint

ap = argparse.ArgumentParser()
ap.add_argument("--nosleep", action="store_true", help="sleep 없이 최대 속도로 읽기 (CPU 100 %)")
args = ap.parse_args()

try:
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(BTN_L, GPIO.IN)             # 입력 핀 (기본값은 외부 풀업이 정함)
    print("버튼을 눌러 보세요 (Ctrl-C 종료)  — 다른 터미널: top -p $(pgrep -f poll_button)")
    loops, t_report = 0, time.monotonic()
    while True:
        value = GPIO.input(BTN_L)          # 핀 전압 → 1(HIGH) 또는 0(LOW)
        if args.nosleep:
            loops += 1
            if time.monotonic() - t_report >= 1.0:   # 1 초에 한 번만 출력
                print(f"초당 {loops} 회 읽는 중 (top 에서 CPU 약 100 %)  BTN_L = {value}")
                loops, t_report = 0, time.monotonic()
        else:
            print(f"\rBTN_L = {value}  {'눌림 ' if value == 0 else '안 눌림'}", end="", flush=True)
            time.sleep(0.05)               # 50 ms 마다 → 1 초에 20 번 (이 사이에 눌렀다 떼면 놓침!)
except KeyboardInterrupt:
    print("\n종료")
except Exception as e:
    hint(e)
finally:
    GPIO.cleanup()
