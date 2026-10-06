#!/usr/bin/env python3
# ===== 실습 2 ② — 풀업이 없으면? 플로팅(floating) 관찰 (floating_demo.py) =====
# 목적: 아무것도 연결되지 않은(풀업·풀다운 없는) 입력 핀은 값이 정해지지 않음을 눈으로 확인
# 배선: ★ 핀 22 의 10 kΩ 풀업(3.3 V 쪽 저항)을 뺀다. 핀 22 는 버튼 한쪽만 연결하거나 점퍼 하나만 꽂는다.
#       (버튼 반대쪽 다리는 GND 에 연결하지 말 것 — 그러면 항상 0 이라 관찰이 안 됨)
# 실행: python3 floating_demo.py     손가락을 점퍼 끝에 가까이/닿게 해 보기 (Ctrl-C 종료)
# 출력: 10 ms 마다 읽은 값을 0/1 문자열로. 0 과 1 이 무작위로 섞이면 플로팅.
import time
import warnings

import Jetson.GPIO as GPIO
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import BTN_L, hint

try:
    GPIO.setmode(GPIO.BOARD)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")    # Jetson.GPIO 는 pull_up_down 을 무시한다는 경고를 낼 수 있음
        GPIO.setup(BTN_L, GPIO.IN, pull_up_down=GPIO.PUD_OFF)   # 풀업·풀다운 없음(OFF)
    print("값이 떠다니는지 보세요 (10 ms 간격, 한 줄 = 50 개)")
    line, changes, last = "", 0, None
    while True:
        v = GPIO.input(BTN_L)
        if last is not None and v != last:
            changes += 1                   # 값이 바뀐 횟수
        last = v
        line += str(v)
        if len(line) == 50:
            print(f"{line}   바뀐 횟수 {changes:2d}")
            line, changes = "", 0
        time.sleep(0.01)
except KeyboardInterrupt:
    print("\n종료")
except Exception as e:
    hint(e)
finally:
    GPIO.cleanup()
