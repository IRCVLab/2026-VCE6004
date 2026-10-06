#!/usr/bin/env python3
# ===== 실습 3 비교용 — 폴링 버전 반응속도 게임 (reaction_poll.py) =====
# 목적: reaction.py 와 같은 게임을 "1 ms 마다 핀을 읽는 폴링"으로 만들어 비교
#       (반응 시간 숫자 · CPU 사용량 · 코드 복잡도). 비교 1 문단은 보고서에.
# 배선·규칙: reaction.py 와 동일
# 실행: python3 reaction_poll.py     결과는 화면 + reaction_log.csv(이어서 저장, mode=poll)
import random
import time

import Jetson.GPIO as GPIO
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import BTN_L, LED_L, hint, all_off, reaction_report

ROUNDS = 5
PENALTY_MS = 500
TIMEOUT_S = 3.0
POLL_S = 0.001            # 1 ms 마다 읽기
CSV_FILE = "reaction_log.csv"


def wait_release():
    while GPIO.input(BTN_L) == GPIO.LOW:
        time.sleep(0.01)
    time.sleep(0.05)


def play_round():
    wait_release()
    cpu0 = time.process_time()
    # ① 대기 구간: 1 ms 마다 읽으며 '미리 누름' 감시
    wait_s = random.uniform(1.0, 4.0)
    t_end = time.monotonic() + wait_s
    early = False
    while time.monotonic() < t_end:
        if GPIO.input(BTN_L) == GPIO.LOW:
            early = True
        time.sleep(POLL_S)
    if early:
        print("  부정 출발! (+500 ms)")
        if GPIO.input(BTN_L) == GPIO.LOW:
            print("  버튼에서 손을 떼세요")
        wait_release()
    # ② 측정 구간: LED 켜고 1 ms 마다 읽는다 → 반응 시간은 최대 1 ms 늦게 잡힘
    GPIO.output(LED_L, GPIO.HIGH)
    t0 = time.monotonic()
    reaction = None
    while time.monotonic() - t0 < TIMEOUT_S:
        if GPIO.input(BTN_L) == GPIO.LOW:
            reaction = (time.monotonic() - t0) * 1000
            break
        time.sleep(POLL_S)
    GPIO.output(LED_L, GPIO.LOW)
    return wait_s, reaction, early, (time.process_time() - cpu0) * 1000


try:
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(BTN_L, GPIO.IN)
    GPIO.setup(LED_L, GPIO.OUT, initial=GPIO.LOW)
    print(f"[폴링 버전] 반응속도 게임 — {ROUNDS} 라운드. LED 가 켜지면 버튼!")
    rows = []
    for r in range(1, ROUNDS + 1):
        print(f"[라운드 {r}/{ROUNDS}] 준비...")
        wait_s, reaction, fs, cpu_ms = play_round()
        if reaction is None:
            print("  시간 초과")
            final = None
        else:
            final = reaction + (PENALTY_MS if fs else 0)
            print(f"  반응 {reaction:6.1f} ms" + (f" + 페널티 {PENALTY_MS} = {final:.1f} ms" if fs else ""))
        rows.append((r, wait_s, reaction, fs, final, cpu_ms))

    reaction_report(rows, "poll", CSV_FILE)      # 결과 표 + CSV 저장 (pins.py)
except KeyboardInterrupt:
    print("\n중단")
except Exception as e:
    hint(e)
finally:
    all_off(GPIO, LED_L)
    GPIO.cleanup()
