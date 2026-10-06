#!/usr/bin/env python3
# ===== 실습 4 — 루프백 지연 측정 (loopback.py) =====
# 목적: "출력 명령 직전 시각(t0)" → "콜백이 시작된 시각(t1)" 까지의 지연을 1000 번 재서
#       평균이 아니라 꼬리(p99·최대)를 본다. 무부하 / 부하 / 실시간 우선순위를 비교.
# 배선: 핀 7(LED_L) ─ 1 kΩ ─ 핀 22(BTN_L) 점퍼 하나 (LED·버튼 배선은 그대로 둬도 됨)
# 실행: python3 loopback.py --tag base                      ① 무부하 (약 25 초)
#       stress-ng -c $(nproc) --timeout 90s &               ② 부하를 걸어 둔 채
#       python3 loopback.py --tag stress
#       sudo chrt -f 80 python3 loopback.py --tag fifo        ③ 실시간 우선순위 (root 로 실행 → 파일 소유자 root)
#       python3 latency_plot.py loopback_base.csv loopback_stress.csv loopback_fifo.csv
# 옵션: --n 1000 (측정 횟수)   --tag base (CSV 이름: loopback_<tag>.csv)
import argparse
import os
import random
import threading
import time

import Jetson.GPIO as GPIO
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import LED_L, BTN_L, hint, all_off, stats, save_csv

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=1000)
ap.add_argument("--tag", default="base")
args = ap.parse_args()

t1_ns = 0
got = threading.Event()


def on_rise(channel):
    """상승 에지 콜백 — 맨 첫 줄에서 시각만 기록한다 (이 시각이 '콜백 도착' 시각)."""
    global t1_ns
    t1_ns = time.monotonic_ns()
    got.set()


POLICY = {0: "SCHED_OTHER(보통)", 1: "SCHED_FIFO(실시간)", 2: "SCHED_RR(실시간)"}

try:
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(LED_L, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(BTN_L, GPIO.IN)
    GPIO.add_event_detect(BTN_L, GPIO.RISING, callback=on_rise)    # 등록에 약 1 초 걸림
    print(f"조건: tag={args.tag}  스케줄러={POLICY.get(os.sched_getscheduler(0), '?')}  "
          f"부하(1분 평균 load)={os.getloadavg()[0]:.2f}  코어={os.cpu_count()}")
    print(f"{args.n} 번 측정 시작 (점퍼 핀 7 ─ 핀 22 확인!)")

    lat, miss = [], 0
    for i in range(1, args.n + 1):
        GPIO.output(LED_L, GPIO.LOW)
        time.sleep(random.uniform(0.010, 0.030))   # 신호가 가라앉을 시간 (매번 조금씩 다르게)
        got.clear()
        t0 = time.monotonic_ns()                   # ① 출력 직전 시각
        GPIO.output(LED_L, GPIO.HIGH)              # ② 핀 7 을 HIGH → 점퍼 → 핀 22 에 상승 에지
        if got.wait(0.5) and t1_ns >= t0:          # ③ 콜백이 t1 을 기록할 때까지 최대 0.5 초 대기
            lat.append((t1_ns - t0) / 1000.0)      # ns → µs
        else:
            miss += 1                              # 이벤트를 못 받음 (배선 확인)
        if i % 100 == 0:
            print(f"  {i}/{args.n}")

    s = stats(lat)
    if s["n"] == 0:
        print("측정값 없음 → 핀 7 ─ 핀 22 점퍼가 꽂혔는지 확인")
    else:
        print(f"\n지연(µs): 평균 {s['mean']:.0f} · p50 {s['p50']:.0f} · p99 {s['p99']:.0f} · "
              f"최대 {s['max']:.0f} · 최소 {s['min']:.0f}   (유효 {s['n']}, 놓침 {miss})")
        save_csv(f"loopback_{args.tag}.csv", ["i", "latency_us"], [(k + 1, f"{v:.1f}") for k, v in enumerate(lat)])
except KeyboardInterrupt:
    print("\n중단")
except Exception as e:
    hint(e)
finally:
    all_off(GPIO, LED_L)
    GPIO.cleanup()
