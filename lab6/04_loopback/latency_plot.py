#!/usr/bin/env python3
# ===== 실습 4 — 지연 분포 비교 (latency_plot.py) =====
# 목적: loopback_*.csv 여러 개를 읽어 요약표를 출력하고, 로그 x축 히스토그램 PNG 를 저장
# 실행: python3 latency_plot.py loopback_base.csv loopback_stress.csv loopback_fifo.csv
#       옵션: -o latency_hist.png (출력 파일)
# 참고: matplotlib 이 없으면 표만 출력 (pip3 install matplotlib, 또는 CSV 를 노트북으로 복사해서 실행)
#       Jetson 이 아니어도 실행됨 (Jetson.GPIO 를 쓰지 않음)
import argparse
import csv
import os
import sys


def load(path):
    """CSV 의 latency_us 열을 리스트로."""
    with open(path, newline="") as f:
        return [float(r["latency_us"]) for r in csv.DictReader(f)]


def pct(sorted_vals, p):
    k = (len(sorted_vals) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


ap = argparse.ArgumentParser()
ap.add_argument("files", nargs="+")
ap.add_argument("-o", "--out", default="latency_hist.png")
args = ap.parse_args()

data = {}
for path in args.files:
    try:
        data[os.path.splitext(os.path.basename(path))[0]] = sorted(load(path))
    except (OSError, KeyError, ValueError) as e:
        sys.exit(f"[오류] {path} 를 읽을 수 없음: {e}  (loopback.py 가 만든 CSV 인지 확인)")

print(f"{'조건':<22}{'n':>6}{'평균':>9}{'p50':>9}{'p99':>9}{'최대':>10}{'최대/평균':>10}   (단위 µs)")
for name, v in data.items():
    mean = sum(v) / len(v)
    print(f"{name:<22}{len(v):>6}{mean:>9.0f}{pct(v, 50):>9.0f}{pct(v, 99):>9.0f}{v[-1]:>10.0f}{v[-1] / mean:>10.1f}")

try:
    import matplotlib
    matplotlib.use("Agg")                    # 화면 없이 파일로만 저장
    import matplotlib.pyplot as plt
except ImportError:
    print("matplotlib 없음 → 그래프 생략 (pip3 install matplotlib)")
    sys.exit(0)

lo = min(v[0] for v in data.values())
hi = max(v[-1] for v in data.values())
bins = [lo * (hi / lo) ** (k / 60) for k in range(61)]       # 로그 간격 구간 60 개
fig, ax = plt.subplots(figsize=(8, 4.5))
for name, v in data.items():
    ax.hist(v, bins=bins, histtype="stepfilled", alpha=0.45, label=f"{name} (max {v[-1]:.0f} us)")
ax.set_xscale("log")                         # 꼬리가 보이도록 x 축을 로그로
ax.set_xlabel("latency (us, log scale)")     # 한글 폰트가 없어도 깨지지 않게 영어 라벨
ax.set_ylabel("count")
ax.set_title("Loopback latency: edge -> callback")
ax.legend()
fig.tight_layout()
fig.savefig(args.out, dpi=150)
print(f"저장: {args.out}")
