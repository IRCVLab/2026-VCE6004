#!/usr/bin/env python3
# ===== 실습 6 ④ — 두 gpiomon 파일에서 위상차 계산 (phase_from_files.py) =====
# 목적: 서로 독립인 두 PWM 채널(핀 15, 핀 18)의 상승 에지 시각을 비교해 위상차(B − A) 의 평균·표준편차·추세를 구한다
# 입력: gpiomon 출력 2 개 (A: 핀 22 쪽, B: 핀 16 쪽).  trigger_phase.sh / trigger_phase.py 가 만든다
# 실행: python3 phase_from_files.py phase_a.txt phase_b.txt --period-ms 100
# 읽는 법: 위상차 > 0 → B 가 A 보다 늦게 올라감.   '추세' 가 0 이 아니면 두 채널의 실제 주기가 서로 달라 위상차가 계속 변함
import argparse
import bisect
import statistics
import sys

from analyze import parse            # 같은 폴더의 analyze.py 재사용


def phase_offsets(a_ns, b_ns, period_ns):
    """A 의 각 에지에서 가장 가까운 B 에지까지의 시간차(µs). 한 주기 안(±T/2)으로 접는다."""
    b_sorted = sorted(b_ns)
    out = []
    for t in a_ns:
        i = bisect.bisect_left(b_sorted, t)
        near = [b_sorted[j] for j in (i - 1, i) if 0 <= j < len(b_sorted)]
        d = min((c - t for c in near), key=abs)
        d = (d + period_ns / 2) % period_ns - period_ns / 2
        out.append(d / 1000.0)
    return out


def mean_period_ms(times_ns):
    return (times_ns[-1] - times_ns[0]) / (len(times_ns) - 1) / 1e6


def analyze_phase(file_a, file_b, period_ms, quiet=False):
    """위상차 통계 dict 를 돌려주고, quiet 가 아니면 출력도 한다."""
    a, b = parse(file_a), parse(file_b)
    if len(a) < 3 or len(b) < 3:
        print(f"[경고] 에지가 부족함 (A {len(a)}개, B {len(b)}개) → 배선·gpiomon 확인")
        return None
    off = phase_offsets(a, b, period_ms * 1e6)
    n = len(off)
    mean = statistics.fmean(off)
    std = statistics.stdev(off) if n > 1 else 0.0
    # 최소제곱 직선: 위상차 = c + slope × (주기 번호)  → slope 가 µs/주기 단위 드리프트
    xs = list(range(n))
    xm = statistics.fmean(xs)
    slope = sum((x - xm) * (y - mean) for x, y in zip(xs, off)) / sum((x - xm) ** 2 for x in xs)
    res = {"n": n, "mean": mean, "std": std, "min": min(off), "max": max(off), "slope": slope,
           "period_a": mean_period_ms(a), "period_b": mean_period_ms(b)}
    if not quiet:
        print(f"A: {file_a} ({len(a)} 에지, 평균 주기 {res['period_a']:.4f} ms)")
        print(f"B: {file_b} ({len(b)} 에지, 평균 주기 {res['period_b']:.4f} ms)")
        print(f"위상차 B−A : 평균 {mean:+.1f} µs · 표준편차 {std:.1f} µs · 최소 {res['min']:+.1f} · 최대 {res['max']:+.1f}  (n={n})")
        print(f"추세(드리프트): {slope:+.3f} µs/주기  → {n} 주기 동안 약 {slope * n:+.1f} µs")
        if abs(slope * n) <= max(2 * std, 20.0):     # 총 변화량이 산포(2σ) 안이면 '일정'으로 본다
            print("→ 위상차가 일정: 시작 시점의 차이가 그대로 유지됨 (고정 오프셋 → 측정 후 보정 가능)")
        else:
            print("→ 위상차가 시간에 따라 변함: 두 채널의 실제 주기가 서로 다름 (주파수 양자화 차이)")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("file_a")
    ap.add_argument("file_b")
    ap.add_argument("--period-ms", type=float, default=100.0, help="명목 주기 ms (기본 100 = 10 Hz)")
    args = ap.parse_args()
    try:
        r = analyze_phase(args.file_a, args.file_b, args.period_ms)
    except OSError as e:
        sys.exit(f"[오류] 파일을 열 수 없음: {e}")
    sys.exit(0 if r else 1)
