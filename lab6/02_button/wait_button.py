#!/usr/bin/env python3
# ===== 실습 2 ⑤ — 기다리기: wait_for_edge (wait_button.py) =====
# 목적: 폴링 없이 "버튼이 눌릴 때까지 잠자기" → CPU 0 %. 누를 때마다 LED 1 초
# 배선: 버튼(핀 22, 10 kΩ 풀업, GND)  +  LED(핀 7 ─ 330 Ω ─ LED ─ GND)
# 실행: python3 wait_button.py       (다른 터미널에서 top 으로 CPU 확인, Ctrl-C 종료)
import time

import Jetson.GPIO as GPIO
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import BTN_L, LED_L, hint, all_off

try:
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(BTN_L, GPIO.IN)
    GPIO.setup(LED_L, GPIO.OUT, initial=GPIO.LOW)
    print("버튼을 누르면 LED 가 1 초 켜집니다 (Ctrl-C 종료)")
    while True:
        # 눌림(하강 에지)이 올 때까지 여기서 잠잔다 → CPU 를 쓰지 않음
        GPIO.wait_for_edge(BTN_L, GPIO.FALLING, bouncetime=50)
        # 주의: Jetson.GPIO 의 wait_for_edge 는 bouncetime 을 적용하지 않을 수 있음 (장비에서 확인)
        #       → 직접 기다린다: 50 ms 대기 후, 손을 뗄 때까지 대기
        time.sleep(0.05)
        print("눌림!")
        GPIO.output(LED_L, GPIO.HIGH)
        time.sleep(1.0)
        GPIO.output(LED_L, GPIO.LOW)
        while GPIO.input(BTN_L) == GPIO.LOW:    # 아직 누르고 있으면 뗄 때까지 (장비에서 확인)
            time.sleep(0.01)
        time.sleep(0.05)                        # 뗄 때의 바운스가 가라앉을 시간
except KeyboardInterrupt:
    print("\n종료")
except Exception as e:
    hint(e)
finally:
    all_off(GPIO, LED_L)
    GPIO.cleanup()
