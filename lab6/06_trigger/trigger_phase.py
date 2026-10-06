#!/usr/bin/env python3
# ===== 실습 6 ④ — 두 PWM 채널의 위상차 (trigger_phase.py, 파이썬 버전) =====
# 목적: 서로 독립인 PWM 컨트롤러 2 개(핀 15 · 핀 18)를 같은 주파수로 켜고 위상차를 잰다.
#       enable 파일을 미리 열어 두고 연달아 써서 두 채널의 시작 시각 차이를 줄인다 (셸 버전과 비교).
# 배선: 핀 15 ─(330 Ω)─ 핀 22 (gpiochip0 라인 96),   핀 18 ─(330 Ω)─ 핀 16 (gpiochip1 라인 9)
# 실행: python3 trigger_phase.py [--freq 10] [--pulse-us 1000] [--events 100] [--repeat 3]
#       (sysfs 쓰기 권한이 없으면 sudo python3 ...)
# 흐름: ① 두 채널 설정(켜지 않음) ② gpiomon 2 개 시작 ③ enable 연속 쓰기 ④ N 개 수집 ⑤ 위상차 분석 ⑥ 끄기
#       --repeat: 켜고 끄기를 반복해 '시작 때마다 위상차가 얼마나 달라지는지' 확인
# 주의: PWM 하한 때문에 10 Hz 가 안 되는 장비면 --freq 20 또는 50 으로 (실습 6 ① 결과)
import argparse
import os
import subprocess
import time

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import PWM_ADDR, PWM_A, PWM_B, CHIP_LABEL, PIN_LINES, BTN_L, BTN_R, hint, pwmchip_for, stats
from phase_from_files import analyze_phase

ap = argparse.ArgumentParser()
ap.add_argument("--freq", type=float, default=10.0)
ap.add_argument("--pulse-us", type=int, default=1000)
ap.add_argument("--events", type=int, default=100, help="채널마다 받을 에지 수")
ap.add_argument("--repeat", type=int, default=1)
args = ap.parse_args()

period_ns = round(1e9 / args.freq)
duty_ns = args.pulse_us * 1000


def sysfs_write(path, value):
    with open(path, "w") as f:
        f.write(str(value))


def sysfs_read(path):
    try:
        with open(path) as f:
            return int(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0


def configure(chip):
    """채널을 export 하고 period/duty 를 쓴다 (켜지는 않음). 반환: pwm0 폴더 경로."""
    pwm = chip + "/pwm0"
    if not os.path.isdir(pwm):
        sysfs_write(chip + "/export", 0)
    for _ in range(100):                                  # udev 가 권한을 줄 때까지 최대 2 초
        if os.access(pwm + "/enable", os.W_OK):
            break
        time.sleep(0.02)
    if sysfs_read(pwm + "/enable") == 1:
        sysfs_write(pwm + "/enable", 0)
    if sysfs_read(pwm + "/period") > 0 and sysfs_read(pwm + "/duty_cycle") > 0:
        sysfs_write(pwm + "/duty_cycle", 0)               # 주기를 줄이기 전에 duty 부터 0
    sysfs_write(pwm + "/period", period_ns)
    sysfs_write(pwm + "/duty_cycle", duty_ns)
    return pwm


def line_buffer_flag():
    """gpiomon 이 --line-buffered 옵션을 지원하면 그 옵션 목록, 아니면 빈 리스트 (장비에서 확인)."""
    try:
        r = subprocess.run(["gpiomon", "--help"], capture_output=True, text=True)
        return ["--line-buffered"] if "--line-buffered" in r.stdout + r.stderr else []
    except OSError:
        return []


def chip_name(n):
    """gpiochip 번호 n 의 실제 이름. gpiodetect 에서 라벨로 찾고, 못 찾으면 gpiochipN."""
    try:
        out = subprocess.run(["gpiodetect"], capture_output=True, text=True).stdout
        for ln in out.splitlines():
            parts = ln.split()
            if len(parts) >= 2 and parts[1] == f"[{CHIP_LABEL[n]}]":
                return parts[0]
    except OSError:
        pass
    return f"gpiochip{n}"


def start_gpiomon(pin, out_file):
    """pin 에 해당하는 라인의 상승 에지 N 개를 out_file 로 저장하는 gpiomon 시작."""
    chip, line = PIN_LINES[pin]
    cmd = ["gpiomon", "--rising-edge", f"--num-events={args.events}"] + line_buffer_flag() + [chip_name(chip), str(line)]
    return subprocess.Popen(cmd, stdout=open(out_file, "w"), stderr=subprocess.PIPE, text=True)


def one_run(a_dir, b_dir, run_no):
    pa = start_gpiomon(BTN_L, f"phase_a{run_no}.txt")     # A: 핀 15 → 핀 22
    pb = start_gpiomon(BTN_R, f"phase_b{run_no}.txt")     # B: 핀 18 → 핀 16
    time.sleep(0.5)                                       # gpiomon 이 준비될 시간
    fd_a = os.open(a_dir + "/enable", os.O_WRONLY)        # enable 파일을 미리 열어 둔다 (open 시간 제거)
    fd_b = os.open(b_dir + "/enable", os.O_WRONLY)
    try:
        t0 = time.perf_counter_ns()
        os.write(fd_a, b"1")                              # 채널 A 시작
        t1 = time.perf_counter_ns()
        os.write(fd_b, b"1")                              # 채널 B 시작 — A 시작 직후
        print(f"  enable 쓰기 간격(소프트웨어가 본 값): {(t1 - t0) / 1000:.0f} µs")
        limit = args.events / args.freq + 10
        for p in (pa, pb):
            try:
                p.wait(timeout=limit)
            except subprocess.TimeoutExpired:
                p.terminate()
                print("  [경고] 제한 시간 초과 — 신호가 입력 핀에 오는지 확인")
    finally:
        os.write(fd_a, b"0")
        os.write(fd_b, b"0")
        os.close(fd_a)
        os.close(fd_b)
    for name, p in (("A", pa), ("B", pb)):
        if p.returncode not in (0, None, -15):
            print(f"  [오류] gpiomon {name}: {p.stderr.read().strip()}")
    return analyze_phase(f"phase_a{run_no}.txt", f"phase_b{run_no}.txt", 1000.0 / args.freq)


chips = {}
try:
    for pin in (PWM_A, PWM_B):
        chip = pwmchip_for(PWM_ADDR[pin])
        if chip is None:
            raise FileNotFoundError(f"No such file: 핀 {pin} 의 PWM {PWM_ADDR[pin]} 없음 (jetson-io 설정 필요)")
        chips[pin] = chip
    print(f"{args.freq:g} Hz · 펄스 {args.pulse_us} µs 로 핀 15 와 핀 18 을 {args.repeat} 번 시작해 위상차 측정")
    dirs = {pin: configure(chip) for pin, chip in chips.items()}
    means = []
    for r in range(1, args.repeat + 1):
        print(f"[{r}/{args.repeat}]")
        res = one_run(dirs[PWM_A], dirs[PWM_B], r)
        if res:
            means.append(res["mean"])
        time.sleep(0.5)
    if len(means) > 1:
        s = stats(means)
        print(f"\n반복별 평균 위상차(µs): {[round(m, 1) for m in means]}")
        print(f"→ 시작할 때마다 위상차가 {s['std']:.1f} µs (표준편차) 만큼 달라짐 — 셸 버전(trigger_phase.sh)과 비교")
except KeyboardInterrupt:
    print("\n중단")
except FileNotFoundError as e:
    if "gpiomon" in str(e):
        print("[오류] gpiomon 없음 → bash setup_lab6.sh")
    else:
        hint(e)
except Exception as e:
    hint(e)
finally:
    for pin, chip in chips.items():                        # 정리: 끄고 해제
        try:
            if sysfs_read(chip + "/pwm0/enable") == 1:
                sysfs_write(chip + "/pwm0/enable", 0)
            sysfs_write(chip + "/unexport", 0)
        except OSError:
            pass
