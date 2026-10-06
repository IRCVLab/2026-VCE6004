#!/usr/bin/env python3
# ===== 실습 3 ③④⑤ — 반응속도 게임 (reaction.py) =====
# 목적: wait_for_edge(블로킹)로 버튼 반응 시간을 재고, add_event_detect(콜백)로 부정 출발을 잡는다
# 규칙: 5 라운드. 랜덤 1~4 초 기다림 → LED L 켜짐 → 버튼! (LED 켜지기 전에 누르면 부정 출발 +500 ms)
# 배선: 버튼(핀 22, 10 kΩ 풀업, GND) · LED L(핀 7 ─ 330 Ω ─ LED ─ GND)
# 실행: python3 reaction.py          결과는 화면 + reaction_log.csv(이어서 저장)
# 참고: Jetson.GPIO 의 wait_for_edge timeout 은 '초' 단위 정수 (RPi.GPIO 는 ms) → 3 = 3 초
import random
import time

import Jetson.GPIO as GPIO
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import BTN_L, LED_L, hint, all_off, reaction_report

ROUNDS = 5
PENALTY_MS = 500          # 부정 출발 페널티
TIMEOUT_S = 3             # LED 켜진 뒤 3 초 안에 안 누르면 시간 초과 (단위: 초!)
CSV_FILE = "reaction_log.csv"

false_start = False


def on_early_press(channel):
    """대기 중 버튼이 눌리면 표시만 한다 (콜백은 짧게)."""
    global false_start
    false_start = True


def wait_release():
    """버튼에서 손을 뗄 때까지 기다림 (장비에서 확인: 이벤트 등록 뒤 input)."""
    while GPIO.input(BTN_L) == GPIO.LOW:
        time.sleep(0.01)
    time.sleep(0.05)      # 뗄 때 바운스가 가라앉을 시간


def play_round():
    """한 라운드: (대기 시간, 반응 ms 또는 None, 부정출발 여부, CPU ms) 를 돌려준다."""
    global false_start
    wait_release()
    false_start = False
    cpu0 = time.process_time()
    # ① 대기 구간: 콜백 방식으로 '미리 누름'을 감시 (등록에 약 1 초 걸림)
    GPIO.add_event_detect(BTN_L, GPIO.FALLING, callback=on_early_press, bouncetime=50)
    wait_s = random.uniform(1.0, 4.0)
    time.sleep(wait_s)
    GPIO.remove_event_detect(BTN_L)          # wait_for_edge 와 동시에 쓸 수 없음 → 감시 해제
    if false_start:
        print("  부정 출발! (+500 ms)")
        if GPIO.input(BTN_L) == GPIO.LOW:
            print("  버튼에서 손을 떼세요")
        wait_release()
    # ② 측정 구간: LED 켜고 바로 시각 기록 → 블로킹으로 버튼 기다림
    GPIO.output(LED_L, GPIO.HIGH)
    t0 = time.monotonic()                    # monotonic: 시스템 시계가 바뀌어도 안 흔들리는 시계
    result = GPIO.wait_for_edge(BTN_L, GPIO.FALLING, timeout=TIMEOUT_S, bouncetime=50)
    t1 = time.monotonic()
    GPIO.output(LED_L, GPIO.LOW)
    cpu_ms = (time.process_time() - cpu0) * 1000
    reaction = None if result is None else (t1 - t0) * 1000      # None = 시간 초과
    return wait_s, reaction, false_start, cpu_ms


try:
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(BTN_L, GPIO.IN)
    GPIO.setup(LED_L, GPIO.OUT, initial=GPIO.LOW)
    print(f"반응속도 게임 — {ROUNDS} 라운드. LED 가 켜지면 버튼을 최대한 빨리! (켜지기 전에 누르면 +{PENALTY_MS} ms)")
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

    reaction_report(rows, "wait_for_edge", CSV_FILE)      # 결과 표 + CSV 저장 (pins.py)
except KeyboardInterrupt:
    print("\n중단")
except Exception as e:
    hint(e)
finally:
    all_off(GPIO, LED_L)
    GPIO.cleanup()
