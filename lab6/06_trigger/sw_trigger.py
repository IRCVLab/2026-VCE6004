#!/usr/bin/env python3
# ===== 실습 6 ③ — 소프트웨어로 만드는 트리거 신호 (sw_trigger.py) =====
# 목적: HW PWM 없이 파이썬 루프로 10 Hz · 1 ms 펄스를 만들고, 주기 지터를 HW PWM 과 비교한다.
# 배선: 핀 7(LED_L) ─(330 Ω)─ 핀 22(BTN_L) 점퍼.   ※ 핀 15 가 아님! (핀 7/15 혼동 주의)
# 실행: python3 sw_trigger.py                         10 Hz · 펄스 1000 µs · 200 개
#       (측정 쪽 gpiomon 을 먼저 켜 두고 시작하므로 약간 넉넉히: --n 230 으로 200 에지 수집)
#       python3 sw_trigger.py --freq 20 --pulse-us 500 --n 400
#       (다른 터미널) ./measure_period.sh -n 200 -o sw.txt  →  python3 analyze.py sw.txt --nominal-ms 100
# 비교 조건 (같은 측정을 조건만 바꿔 반복):
#       SW           python3 sw_trigger.py
#       SW + chrt    sudo chrt -f 80 python3 sw_trigger.py        (실시간 우선순위 SCHED_FIFO)
#       SW + 부하    stress-ng -c $(nproc) --timeout 120s &  를 먼저 실행한 뒤 sw_trigger.py
#       (옵션) --spin  마지막 0.3 ms 를 바쁜 대기 → 지터 ↓, 대신 CPU 100 %
import argparse
import time

import Jetson.GPIO as GPIO
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import LED_L, hint, all_off, stats

ap = argparse.ArgumentParser()
ap.add_argument("--freq", type=float, default=10.0, help="주파수 Hz (기본 10)")
ap.add_argument("--pulse-us", type=int, default=1000, help="펄스 폭 µs (기본 1000). sleep 한계로 약 1.1 ms 미만은 부정확")
ap.add_argument("--n", type=int, default=200, help="펄스 개수 (0 이면 Ctrl-C 까지)")
ap.add_argument("--spin", action="store_true", help="마지막 0.3 ms 바쁜 대기")
args = ap.parse_args()


def wait_until(t):
    """perf_counter 시각 t 까지 기다린다."""
    rest = t - time.perf_counter()
    if args.spin:
        if rest > 0.0003:
            time.sleep(rest - 0.0003)         # 대부분은 잠자고
        while time.perf_counter() < t:        # 마지막 구간만 계속 확인 (CPU 사용)
            pass
    elif rest > 0:
        time.sleep(rest)


period = 1.0 / args.freq
pulse = args.pulse_us / 1e6
late = []                                    # 코드가 본 지연: (실제 시각 − 예정 시각) µs

try:
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(LED_L, GPIO.OUT, initial=GPIO.LOW)
    start = time.perf_counter() + 0.5        # 0.5 초 뒤에 시작
    print(f"{args.freq:g} Hz · 펄스 {args.pulse_us} µs · {args.n or '무한'} 개 출력 중 (핀 7).  Ctrl-C 로 중단")
    k = 0
    while args.n == 0 or k < args.n:
        t_rise = start + k * period          # ★ 절대 시각 = 시작 + k × 주기 → sleep 오차가 쌓이지 않음(드리프트 없음)
        wait_until(t_rise)
        t_now = time.perf_counter()
        GPIO.output(LED_L, GPIO.HIGH)        # 펄스 시작
        late.append((t_now - t_rise) * 1e6)
        wait_until(time.perf_counter() + pulse)
        GPIO.output(LED_L, GPIO.LOW)         # 펄스 끝
        k += 1
except KeyboardInterrupt:
    print("\n중단")
except Exception as e:
    hint(e)
finally:
    all_off(GPIO, LED_L)
    GPIO.cleanup()

s = stats(late)
if s["n"]:
    print(f"코드가 본 지연(예정 시각 → 출력 직전, µs): 평균 {s['mean']:.0f} · p99 {s['p99']:.0f} · 최대 {s['max']:.0f}")
    print("※ 진짜 지터는 gpiomon 으로 잰다 (출력 명령 자체의 지연이 이 값에 안 들어 있음)")
