#!/usr/bin/env python3
# ===== 실습 6·9 — 주기 분석 (analyze.py) =====
# 목적: gpiomon 출력(또는 lamp.py 가 쓴 log_period.txt)에서 에지 시각을 읽어
#       주기의 평균 · 표준편차 · 최소/최대 · 명목값과의 최대 편차를 표로 출력
# 입력 형식 (둘 다 읽음):
#       event: RISING EDGE offset: 96 timestamp: [  1234.567890123]     ← libgpiod v1 gpiomon
#       1234.567890123                                                  ← 시각만 있는 줄
# 실행: python3 analyze.py hw.txt sw.txt --nominal-ms 100
#       python3 analyze.py hw.txt sw.txt --nominal-ms 100 --plot period_hist.png
#       옵션: --edge rising|falling|any (기본 rising) · --skip N (처음 N 개 에지 버림, 기본 0)
#             --offset N (파일에 여러 라인이 섞여 있을 때 그 라인만)
# 참고: Jetson 이 아니어도 실행됨 (노트북에서 분석 가능)
import argparse
import os
import re
import statistics
import sys

NUM = re.compile(r"(\d+)\.(\d+)")            # 12345.678901234 형태
OFFSET = re.compile(r"offset:\s*(\d+)")


def parse(path, edge="rising", offset=None):
    """파일에서 에지 시각(ns, 정수) 리스트를 만든다."""
    times = []
    with open(path) as f:
        for line in f:
            up = line.upper()
            if edge == "rising" and "FALLING" in up:
                continue
            if edge == "falling" and "RISING" in up:
                continue
            if offset is not None:
                m = OFFSET.search(line)
                if m and int(m.group(1)) != offset:
                    continue
            found = NUM.findall(line)
            if not found:
                continue
            sec, frac = found[-1]                       # 줄의 마지막 소수 = 타임스탬프
            times.append(int(sec) * 10 ** 9 + int(frac[:9].ljust(9, "0")))
    return times


def summarize(times_ns, nominal_ms=None):
    """에지 시각 → 주기 통계 dict (주기 단위 ms, 편차 단위 µs)."""
    diffs = [(b - a) / 1e6 for a, b in zip(times_ns, times_ns[1:])]
    if len(diffs) < 2:
        return None
    mean = statistics.fmean(diffs)
    ref = nominal_ms if nominal_ms else mean            # 명목값이 없으면 평균 기준
    dev = [abs(d - ref) * 1000 for d in diffs]          # |주기 − 명목| (µs)
    return {
        "n": len(times_ns), "mean": mean, "std_us": statistics.stdev(diffs) * 1000,
        "min": min(diffs), "max": max(diffs), "maxdev_us": max(dev),
        "bias_us": (mean - ref) * 1000,
        "outliers": sum(1 for d in diffs if d > 1.5 * ref),     # 에지 누락이 의심되는 긴 주기
        "diffs": diffs, "ref": ref,
    }


def main():
    ap = argparse.ArgumentParser(description="gpiomon 에지 시각 → 주기 통계")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--nominal-ms", type=float, default=None, help="명목 주기 (ms), 예: 10 Hz → 100")
    ap.add_argument("--edge", choices=["rising", "falling", "any"], default="rising")
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--offset", type=int, default=None)
    ap.add_argument("--plot", default=None, help="히스토그램 PNG 저장 경로 (matplotlib 필요)")
    args = ap.parse_args()

    results = {}
    for path in args.files:
        try:
            t = parse(path, args.edge, args.offset)[args.skip:]
        except OSError as e:
            sys.exit(f"[오류] {path} 를 열 수 없음: {e}")
        r = summarize(t, args.nominal_ms)
        if r is None:
            print(f"[경고] {path}: 에지가 3 개 미만 ({len(t)} 개) → 건너뜀")
            continue
        results[os.path.basename(path)] = r

    if not results:
        sys.exit("분석할 데이터가 없음")
    ref_txt = f"명목 {args.nominal_ms:g} ms" if args.nominal_ms else "명목값 없음 → 평균 기준"
    print(f"\n주기 분석 ({ref_txt})")
    print(f"{'파일':<18}{'에지':>6}{'평균(ms)':>11}{'표준편차(µs)':>14}{'최소(ms)':>11}{'최대(ms)':>11}"
          f"{'최대편차(µs)':>14}{'평균-명목(µs)':>15}{'긴주기':>7}")
    for name, r in results.items():
        print(f"{name[:17]:<18}{r['n']:>6}{r['mean']:>11.4f}{r['std_us']:>14.1f}{r['min']:>11.4f}"
              f"{r['max']:>11.4f}{r['maxdev_us']:>14.1f}{r['bias_us']:>15.1f}{r['outliers']:>7}")
    if any(r["outliers"] for r in results.values()):
        print("※ '긴주기' > 0: 주기가 1.5 배 이상인 구간 = 에지를 놓쳤을 수 있음 (통계가 부풀려짐)")
    print("※ 평균-명목: 요청한 주기와 실제 평균의 차이 = 주파수 양자화 오차  /  표준편차·최대편차: 지터")

    if args.plot:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib 없음 → 그래프 생략")
            return
        fig, ax = plt.subplots(figsize=(8, 4.5))
        for name, r in results.items():
            ax.hist([(d - r["ref"]) * 1000 for d in r["diffs"]], bins=60, alpha=0.5, label=name)
        ax.set_xlabel("period - nominal (us)")        # 한글 폰트 없이도 깨지지 않게 영어 라벨
        ax.set_ylabel("count")
        ax.set_title("Period deviation histogram")
        ax.legend()
        fig.tight_layout()
        fig.savefig(args.plot, dpi=150)
        print(f"저장: {args.plot}")


if __name__ == "__main__":
    main()
