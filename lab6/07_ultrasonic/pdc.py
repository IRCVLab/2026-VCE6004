#!/usr/bin/env python3
# ===== 실습 7 — 초음파 주차보조 PDC (pdc.py) =====
# 목적: HC-SR04 의 ECHO 펄스 폭을 파이썬으로 재어 거리를 구하고, 거리에 따라 부저 간격을 바꾼다.
#       사용자 공간에서 µs 단위 펄스 폭을 재면 얼마나 흔들리는지(1 cm = 58 µs) 확인하는 실습.
# 배선: HC-SR04  VCC → 5 V(핀 2) · GND → 핀 6 · TRIG → 핀 29
#                ECHO → 1 kΩ ─┬─ 핀 31          (5 V 출력을 3.3 V 로 낮추는 분압:
#                              └─ 2 kΩ ─ GND      5 V × 2k/(1k+2k) = 3.3 V.  ECHO 를 핀에 직결 금지!)
#       부저  : 핀 13 ─ 10 kΩ ─ 2N2222 베이스, 이미터 ─ GND, 컬렉터 ─ 부저(−), 부저(+) ─ 5 V (실습 1 확장과 동일)
# 실행: python3 pdc.py                    주차보조 동작 (Ctrl-C 종료)
#       python3 pdc.py --log --dist 50    물체를 50 cm 에 고정해 두고 20 회 측정 → pdc_log_50cm.csv (보고서용)
# 거리 = ECHO 폭(µs) / 58 (cm).   부저: >100 cm 무음 · 50~100 cm 0.5 초 간격 · 20~50 cm 0.2 초 · <20 cm 연속
import argparse
import statistics
import time
from collections import deque

import Jetson.GPIO as GPIO
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import US_TRIG, US_ECHO, BUZZER, hint, all_off, stats, save_csv

ap = argparse.ArgumentParser()
ap.add_argument("--log", action="store_true", help="20 회 측정해 통계 + CSV 저장")
ap.add_argument("--dist", type=float, default=None, help="줄자로 잰 실제 거리(cm) — --log 와 함께")
args = ap.parse_args()

TIMEOUT = 0.030          # 30 ms 안에 안 오면 포기 (HC-SR04 최대 거리 약 4 m = 23 ms)


def measure_width_us():
    """TRIG 에 10 µs 펄스 → ECHO 가 HIGH 인 시간(µs). 응답이 없으면 None."""
    GPIO.output(US_TRIG, GPIO.HIGH)
    t = time.perf_counter()
    while time.perf_counter() - t < 10e-6:       # 10 µs 는 sleep 으로 못 잼 → 바쁜 대기
        pass
    GPIO.output(US_TRIG, GPIO.LOW)
    deadline = time.perf_counter() + TIMEOUT
    while GPIO.input(US_ECHO) == 0:              # ECHO 가 올라올 때까지
        if time.perf_counter() > deadline:
            return None
    t_rise = time.perf_counter()
    deadline = t_rise + TIMEOUT
    while GPIO.input(US_ECHO) == 1:              # ECHO 가 내려올 때까지 = 펄스 폭
        if time.perf_counter() > deadline:
            return None
    return (time.perf_counter() - t_rise) * 1e6


def beep_interval(cm):
    """거리 → 부저 간격(초). None = 무음, 0 = 연속음."""
    if cm is None or cm > 100:
        return None
    if cm >= 50:
        return 0.5
    if cm >= 20:
        return 0.2
    return 0


def buzzer_state(interval, now):
    """지금 부저를 울려야 하나? interval 초 울리고 interval 초 쉬기를 시간으로 계산."""
    if interval is None:
        return False
    if interval == 0:
        return True
    return (now % (2 * interval)) < interval


try:
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(US_TRIG, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(US_ECHO, GPIO.IN)
    GPIO.setup(BUZZER, GPIO.OUT, initial=GPIO.LOW)
    time.sleep(0.1)

    if args.log:
        print("20 회 측정 (물체를 고정해 두세요)")
        rows = []
        for i in range(1, 21):
            w = measure_width_us()
            if w is not None:
                rows.append((i, f"{w:.1f}", f"{w / 58.0:.2f}"))
                print(f"  {i:2d}: 폭 {w:7.1f} µs → {w / 58.0:6.2f} cm")
            else:
                print(f"  {i:2d}: 응답 없음 (배선·분압·물체 위치 확인)")
            time.sleep(0.1)                       # HC-SR04 는 측정 사이에 60 ms 이상 필요
        s = stats([float(r[2]) for r in rows])
        if s["n"]:
            print(f"\n거리(cm): 평균 {s['mean']:.2f} · 표준편차 {s['std']:.2f} · 최소 {s['min']:.2f} · 최대 {s['max']:.2f}  (유효 {s['n']}/20)")
            if args.dist:
                print(f"줄자 {args.dist:g} cm 와의 차이(평균): {s['mean'] - args.dist:+.2f} cm")
            name = f"pdc_log_{args.dist:g}cm.csv" if args.dist else "pdc_log.csv"
            save_csv(name, ["i", "width_us", "cm"], rows)
    else:
        print("주차보조 동작 중 — 손바닥을 센서 앞에서 움직여 보세요 (Ctrl-C 종료)")
        window = deque(maxlen=5)                  # 최근 5 개의 중앙값 → 튀는 값 제거
        misses = 0
        while True:
            w = measure_width_us()
            if w is None:
                misses += 1
                if misses >= 5:                   # 연속으로 응답이 없으면 '장애물 없음'
                    window.clear()
            else:
                misses = 0
                window.append(w / 58.0)
            cm = statistics.median(window) if window else None
            interval = beep_interval(cm)
            GPIO.output(BUZZER, int(buzzer_state(interval, time.monotonic())))
            msg = "무음" if interval is None else ("연속" if interval == 0 else f"{interval} 초 간격")
            print(f"\r거리 {'--' if cm is None else format(cm, '6.1f')} cm   부저: {msg:<8}", end="", flush=True)
            time.sleep(0.06)                      # 다음 측정까지 60 ms
except KeyboardInterrupt:
    print("\n종료")
except Exception as e:
    hint(e)
finally:
    all_off(GPIO, BUZZER, US_TRIG)
    GPIO.cleanup()
