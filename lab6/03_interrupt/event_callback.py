#!/usr/bin/env python3
# ===== 실습 3 ①② — 콜백은 짧게, 일은 메인 루프가 (event_callback.py) =====
# 목적: add_event_detect 의 콜백은 "다른 스레드"에서 실행됨 → 큐에 넣기만 하고 끝낸다.
#       메인 루프는 LED L 을 느리게 깜빡이면서(평소 일), 큐에서 이벤트가 나오면 LED R 을 5 번 빠르게 깜빡임
# 배선: 버튼(핀 22, 10 kΩ 풀업, GND) · LED L(핀 7 ─ 330 Ω ─ LED ─ GND) · LED R(핀 12 ─ 330 Ω ─ LED ─ GND)
# 실행: python3 event_callback.py     (버튼 누르기, Ctrl-C 종료)
import queue
import time

import Jetson.GPIO as GPIO
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import BTN_L, LED_L, LED_R, hint, all_off

q = queue.Queue()                      # 스레드 사이에서 안전하게 물건을 넘기는 줄(큐)


def on_button(channel):
    """콜백: 시각만 큐에 넣고 바로 끝낸다. (sleep·print·긴 계산 금지!)"""
    q.put(time.monotonic())


try:
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(BTN_L, GPIO.IN)
    GPIO.setup([LED_L, LED_R], GPIO.OUT, initial=GPIO.LOW)
    # bouncetime=50: 첫 에지 후 50 ms 안의 에지는 라이브러리가 버림 (등록에 약 1 초 걸림)
    # 버튼을 뗄 때의 바운스가 한 번 더 이벤트가 될 수 있음 → 실습 2 에서 본 현상
    GPIO.add_event_detect(BTN_L, GPIO.FALLING, callback=on_button, bouncetime=50)
    print("LED L 이 천천히 깜빡입니다. 버튼을 누르면 LED R 이 5 번 깜빡입니다 (Ctrl-C 종료)")

    t0 = time.monotonic()
    r_left, r_next, r_level = 0, 0.0, 0    # LED R: 남은 토글 횟수, 다음 토글 시각, 현재 값
    while True:
        now = time.monotonic()
        # (1) 평소 일: LED L 을 1 초 주기로 점멸 — 시간으로 계산 (sleep 으로 세지 않음)
        GPIO.output(LED_L, int((now - t0) % 1.0 < 0.5))
        # (2) 큐 확인: 이벤트가 있으면 LED R 5 회 깜빡임 시작 (10 번 토글 × 0.2 s)
        try:
            t_event = q.get_nowait()
            print(f"이벤트 처리 (콜백 이후 {(now - t_event) * 1000:.1f} ms 뒤)")
            r_left, r_next = 10, now
        except queue.Empty:
            pass
        # (3) LED R 을 0.2 초마다 토글 — 이 동안에도 LED L 은 계속 깜빡임
        if r_left > 0 and now >= r_next:
            r_level ^= 1
            GPIO.output(LED_R, r_level)
            r_left -= 1
            r_next = now + 0.2
        time.sleep(0.01)                   # 메인 루프 10 ms 주기
except KeyboardInterrupt:
    print("\n종료")
except Exception as e:
    hint(e)
finally:
    all_off(GPIO, LED_L, LED_R)
    GPIO.cleanup()
