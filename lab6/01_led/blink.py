#!/usr/bin/env python3
# ===== 실습 1 — LED 깜빡이기 (blink.py) =====
# 목적: GPIO 출력 한 줄로 핀 전압을 바꿔 LED를 켜고 끈다. 종료 시 cleanup 으로 핀을 원상복구
# 배선: 핀 7 ─ 330 Ω ─ LED(긴 다리 +, 짧은 다리 −) ─ GND(핀 6)   (배선은 전원 끄고!)
# 실행: python3 blink.py        (Ctrl-C 로 종료 → LED 꺼지는지 확인)
import time

import Jetson.GPIO as GPIO           # RPi.GPIO 와 같은 사용법의 Jetson 라이브러리
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import LED_L, hint, all_off   # 핀 번호·도우미는 pins.py 에 모아 둠

try:
    GPIO.setmode(GPIO.BOARD)                          # ① 핀 번호 = 보드에 인쇄된 물리 번호
    GPIO.setup(LED_L, GPIO.OUT, initial=GPIO.LOW)     # ② 핀 7 을 출력으로, 처음엔 꺼 둠
    print("깜빡임 시작 (Ctrl-C 로 종료)")
    while True:
        GPIO.output(LED_L, GPIO.HIGH)                 # ③ 핀 전압 3.3 V → LED 켜짐
        time.sleep(0.5)                               # ④ 0.5 초 기다림 (소프트웨어 타이밍)
        GPIO.output(LED_L, GPIO.LOW)                  #    핀 전압 0 V → LED 꺼짐
        time.sleep(0.5)
except KeyboardInterrupt:
    print("\n종료")
except Exception as e:
    hint(e)                                           # 오류 원인을 한국어로 안내
finally:
    all_off(GPIO, LED_L)                              # 안전하게 LOW 로 내린 뒤
    GPIO.cleanup()                                    # ⑤ 핀을 되돌리고 라인 반납
