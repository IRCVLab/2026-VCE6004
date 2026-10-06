#!/usr/bin/env python3
# ===== 실습 1 확장 — 트랜지스터로 부저 울리기 (buzzer.py) =====
# 목적: GPIO 핀은 전류가 약함 → 트랜지스터(2N2222)를 스위치로 써서 부저를 구동
# 배선: 핀 13 ─ 10 kΩ ─ 2N2222 베이스(B)
#       2N2222 이미터(E) ─ GND(핀 6)
#       부저(−) ─ 2N2222 컬렉터(C),  부저(+) ─ 5 V(핀 2)
#       (전자식 코일 부저면 1N4148 다이오드를 부저와 병렬로: 띠 쪽이 + 쪽)
# 실행: python3 buzzer.py        (삐-삐-삐—— 패턴 3회 반복, Ctrl-C 종료)
# 주의: 핀 13 을 jetson-io 에서 PWM 으로 바꿨다면 GPIO 출력이 안 될 수 있음
#       → pincheck.sh 결과 확인 (장비에서 확인)
import time

import Jetson.GPIO as GPIO
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import BUZZER, hint, all_off

PATTERN = [(0.1, 0.1), (0.1, 0.1), (0.4, 0.5)]   # (울림 초, 쉼 초): 짧게 · 짧게 · 길게

try:
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(BUZZER, GPIO.OUT, initial=GPIO.LOW)
    for round_no in range(3):
        print(f"{round_no + 1}회째")
        for on, off in PATTERN:
            GPIO.output(BUZZER, GPIO.HIGH)    # 베이스에 전류 → 트랜지스터 ON → 부저 울림
            time.sleep(on)
            GPIO.output(BUZZER, GPIO.LOW)
            time.sleep(off)
        time.sleep(0.5)
    print("끝")
except KeyboardInterrupt:
    print("\n종료")
except Exception as e:
    hint(e)
finally:
    all_off(GPIO, BUZZER)      # 울리는 중에 끝나도 부저를 확실히 끔
    GPIO.cleanup()
