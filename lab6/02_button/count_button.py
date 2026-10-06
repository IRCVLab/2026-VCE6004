#!/usr/bin/env python3
# ===== 실습 2 ③④ — 바운스 관찰과 소프트웨어 디바운스 (count_button.py) =====
# 목적: 한 번 눌렀는데 몇 번으로 세어지는지(바운스) 보고, 직접 만든 디바운스로 1 번으로 세기
# 배선: 실습 2 ① 과 같음 (3.3 V ─ 10 kΩ ─ 핀 22 ─ 버튼 ─ GND)
# 실행: python3 count_button.py --raw        디바운스 없음: 하강 에지를 전부 센다
#       python3 count_button.py --debounce   디바운스 있음: 30 ms 뒤 다시 확인 + 50 ms 무시
#       (옵션) -n 10   몇 번 누를지 (기본 10).  버튼은 한 번씩 천천히 누르기
# 출력: 누를 때마다 에지 시각, 끝나면 "누름 번호 / 카운트" 표
import argparse
import time

import Jetson.GPIO as GPIO
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import BTN_L, hint

ap = argparse.ArgumentParser()
mode = ap.add_mutually_exclusive_group(required=True)
mode.add_argument("--raw", action="store_true", help="디바운스 없이 모든 하강 에지를 센다")
mode.add_argument("--debounce", action="store_true", help="소프트웨어 디바운스 적용")
ap.add_argument("-n", type=int, default=10, help="누를 횟수 (기본 10)")
args = ap.parse_args()
args.n = max(1, args.n)

edges = []              # 콜백이 본 모든 하강 에지의 시각 (s)
accepted = []           # 디바운스를 통과한 '진짜 누름'의 시각
ignore_until = 0.0      # 이 시각 전의 에지는 무시 (디바운스 무시 구간)


def on_falling(channel):
    """하강 에지마다 호출됨 (별도 스레드).  ※ 일부러 콜백 안에서 처리 — 실습 3 에서 큐 방식과 비교."""
    global ignore_until
    t = time.monotonic()
    edges.append(t)                         # 원시 에지는 항상 기록 (디바운스 모드는 sleep 때문에 줄 서 있던 에지의 시각 = 처리 시각)
    if args.raw:
        return                              # --raw: 여기서 끝. 바운스도 전부 셈
    if t < ignore_until:                    # 무시 구간 안의 에지 = 바운스
        return
    time.sleep(0.030)                       # ① 30 ms 기다려서 접점이 안정되길 기다림
    if GPIO.input(BTN_L) == GPIO.LOW:       # ② 아직 눌려 있으면 진짜 누름  (장비에서 확인: 콜백 안 input)
        accepted.append(t)
        ignore_until = time.monotonic() + 0.050   # ③ 이후 50 ms 는 무시


def group(times, gap=0.3):
    """0.3 초 이상 떨어진 에지는 '다른 누름'으로 묶는다."""
    groups = []
    for t in times:
        if groups and t - groups[-1][-1] < gap:
            groups[-1].append(t)
        else:
            groups.append([t])
    return groups


try:
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(BTN_L, GPIO.IN)
    # bouncetime 을 주지 않음 → 라이브러리가 걸러주지 않고 모든 에지가 콜백으로 옴
    GPIO.add_event_detect(BTN_L, GPIO.FALLING, callback=on_falling)   # (등록에 약 1 초 걸림)
    name = "raw(디바운스 없음)" if args.raw else "debounce(30 ms 확인 + 50 ms 무시)"
    print(f"모드: {name} — 버튼을 {args.n} 번 누르세요 (한 번씩 천천히)")
    shown = 0
    while True:
        time.sleep(0.05)
        while shown < len(edges):           # 새 에지 출력
            gap = (edges[shown] - edges[shown - 1]) * 1000 if shown else 0.0
            print(f"  에지 {shown + 1:3d}  (직전과의 간격 {gap:8.2f} ms)")
            shown += 1
        done = len(group(edges)) >= args.n and time.monotonic() - edges[-1] > 0.6
        if done:
            break
except KeyboardInterrupt:
    print("\n중단 — 지금까지의 결과를 표로 출력")
except Exception as e:
    hint(e)
finally:
    GPIO.cleanup()

# ---- 결과 표 ----
groups = group(edges)
print("\n누름 번호 | 원시 에지 수 | 이 모드의 카운트")
total = 0
for i, g in enumerate(groups, 1):
    if args.raw:
        count = len(g)                                          # 에지 하나하나가 카운트
    else:
        count = sum(1 for t in accepted if g[0] <= t <= g[-1])  # 인정된 누름 수 (보통 1)
    total += count
    print(f"{i:9d} | {len(g):12d} | {count:5d}")
print(f"실제 누름 {len(groups)} 번 → 프로그램이 센 값 {total}  "
      f"({'바운스가 그대로 카운트됨' if args.raw else '디바운스 후'})")
