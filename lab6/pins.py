#!/usr/bin/env python3
# ===== pins.py — 실습 6 공통 핀 배정과 도우미 =====
# 목적: 핀 번호를 한 곳에 모아 두고, 모든 실습 코드가 import 해서 쓴다
#       (핀을 바꿔야 하면 이 파일만 고치면 됨)
# 번호 체계: 전부 BOARD 번호 (40핀 헤더에 인쇄된 물리 핀 번호) → GPIO.setmode(GPIO.BOARD)
# 실행: python3 pins.py   → 핀 배정표 + 이 장비의 pwmchip·I2C 버스 상태 출력
import glob
import os
import sys

# ---- 용도별 BOARD 핀 번호 ----
LED_L = 7        # 왼쪽 방향지시등 (330 Ω 직렬)
LED_R = 12       # 오른쪽 방향지시등
PWM_A = 15       # PWM A: 디밍 · 브레이크등 · 트리거 ch1  (3280000.pwm)
PWM_B = 18       # PWM B: 서보 · 트리거 ch2               (32c0000.pwm)
BTN_L = 22       # 버튼 L, 루프백/트리거 입력 (풀업, 누르면 LOW)
BTN_R = 16       # 버튼 R, 트리거 입력 2     (풀업, 누르면 LOW)
BUZZER = 13      # 부저 (2N2222 트랜지스터 경유)
US_TRIG = 29     # 초음파 TRIG
US_ECHO = 31     # 초음파 ECHO (1 kΩ : 2 kΩ 분압 후 연결)
I2C_SDA = 3      # I2C SDA
I2C_SCL = 5      # I2C SCL

POWER_3V3 = (1, 17)                      # 3.3 V 핀
POWER_5V = (2, 4)                        # 5 V 핀
GND_PINS = (6, 9, 14, 20, 25, 30, 34, 39)
SPARE_PINS = (32, 33, 35, 36, 37, 38, 40)  # 예비 핀 (오늘 쓰는 핀이 안 움직이면 교체)

# ---- BOARD 핀 → (gpiochip 번호, 라인 번호) ----
# 출처: Jetson.GPIO gpio_pin_data.py (Orin) · 확인: gpioinfo | grep PQ.06
PIN_LINES = {
    7: (0, 106),    # PQ.06  LED_L
    12: (0, 50),    # PH.07  LED_R
    13: (0, 108),   # PR.00  BUZZER (PWM 겸용)
    15: (0, 85),    # PN.01  PWM_A  (jetson-io로 PWM 설정하면 GPIO로는 못 씀)
    16: (1, 9),     # PBB.01 BTN_R  (gpiochip1 = tegra234-gpio-aon)
    18: (0, 43),    # PH.00  PWM_B
    22: (0, 96),    # PP.04  BTN_L
    29: (1, 1),     # PAA.01 US_TRIG (aon)
    31: (1, 0),     # PAA.00 US_ECHO (aon)
}
CHIP_LABEL = {0: "tegra234-gpio", 1: "tegra234-gpio-aon"}   # gpiodetect 에 보이는 이름

# ---- PWM 핀 → 컨트롤러 이름 (sysfs 에서 pwmchipN 을 찾는 열쇠) ----
PWM_ADDR = {BUZZER: "32f0000.pwm", PWM_A: "3280000.pwm", PWM_B: "32c0000.pwm"}

ADS1115_ADDR = 0x48    # ADDR 핀을 GND 에 연결했을 때


# ---------------------------------------------------------------
# 도우미 함수
# ---------------------------------------------------------------
def pwmchip_for(addr):
    """컨트롤러 이름(예: '3280000.pwm')을 가진 pwmchip 경로를 돌려준다. 없으면 None.
    /sys/class/pwm/pwmchipN 은 /sys/devices/platform/3280000.pwm/... 으로 연결된 링크다."""
    for chip in sorted(glob.glob("/sys/class/pwm/pwmchip*")):
        if addr in os.path.realpath(chip) or addr in os.path.realpath(chip + "/device"):
            return chip
    return None


def require_pwm(pin):
    """핀의 하드웨어 PWM 이 켜져 있는지 확인. 없으면 안내를 출력하고 종료."""
    addr = PWM_ADDR.get(pin)
    chip = pwmchip_for(addr) if addr else None
    if chip is None:
        sys.exit(
            f"[오류] 핀 {pin}의 하드웨어 PWM({addr})이 보이지 않음.\n"
            "  1) ls /sys/class/pwm      → pwmchip 이 3개 있어야 함\n"
            "  2) 없으면: sudo /opt/nvidia/jetson-io/jetson-io.py 에서 pwm 핀 활성화 → 재부팅"
        )
    return chip


def i2c_bus_guess(addr=None):
    """I2C 버스 번호 추측. 40핀 헤더 3·5번 핀은 보통 7번 버스, 안 되면 1번.
    addr 를 주면 7 → 1 순서로 그 주소에 응답하는 버스를 찾는다. 정답은 i2cdetect -l 로 확인."""
    buses = [b for b in (7, 1) if os.path.exists(f"/dev/i2c-{b}")]
    if addr is not None and buses:
        try:
            from smbus2 import SMBus
        except ImportError:
            return buses[0]
        for b in buses:
            try:
                with SMBus(b) as bus:
                    bus.read_byte(addr)
                return b
            except OSError:
                continue
    return buses[0] if buses else 7


# 오류 메시지 조각 → 한국어 안내
_HINTS = [
    ("Permission denied", "권한 없음 → groups 에 gpio 가 있나? 없으면 bash setup_lab6.sh 후 재로그인 (임시: sudo 로 실행)"),
    ("busy", "핀을 다른 프로그램이 쓰는 중 → ps -ef | grep python 으로 찾아 종료 (gpioinfo 에서 [used] 표시 확인)"),
    ("Invalid argument", "PWM 값 거부 → 이 장비 PWM 은 낮은 주파수(5·10 Hz 등)가 안 될 수 있음 (실습 6 참고). 대체: pwm_led.py --soft / jetson-io 설정도 확인"),
    ("No such file", "장치 파일 없음 → PWM 은 jetson-io 설정 + 재부팅, I2C 는 i2cdetect -l 로 버스 번호 확인"),
    ("Could not determine Jetson model", "Jetson 장비가 아님 → Jetson 에서 실행"),
    ("Remote I/O error", "I2C 장치가 응답 안 함 → 배선(SDA/SCL 바뀜?)·전원·주소(0x48) 확인: i2cdetect -y 7"),
    ("is not a PWM", "이 핀은 PWM 핀이 아님 → PWM 핀은 13 · 15 · 18"),
]


def hint(err):
    """예외를 한국어로 설명하고 종료 코드 1 로 끝낸다. (finally 의 cleanup 은 그대로 실행됨)"""
    msg = str(err)
    print(f"\n[오류] {type(err).__name__}: {msg}", file=sys.stderr)
    for key, text in _HINTS:
        if key.lower() in msg.lower():
            print(f"  → {text}", file=sys.stderr)
            break
    else:
        print("  → 원인 불명: README.md '문제 해결' 표 확인, 오류 메시지 전체를 복사해 질문", file=sys.stderr)
    sys.exit(1)


def all_off(GPIO, *pins):
    """종료 직전에 출력 핀을 LOW 로 내린다 (설정이 안 된 핀이면 조용히 무시).
    cleanup() 만으로 출력이 꺼진다고 가정하지 않기 위한 안전장치."""
    for p in pins:
        try:
            GPIO.output(p, GPIO.LOW)
        except Exception:
            pass


def percentile(sorted_vals, p):
    """정렬된 리스트의 p 퍼센타일 (선형 보간)."""
    if not sorted_vals:
        return float("nan")
    k = (len(sorted_vals) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def stats(values):
    """평균·표준편차·최소·p50·p99·최대를 dict 로."""
    v = sorted(values)
    n = len(v)
    if n == 0:
        return {"n": 0}
    mean = sum(v) / n
    std = (sum((x - mean) ** 2 for x in v) / (n - 1)) ** 0.5 if n > 1 else 0.0
    return {"n": n, "mean": mean, "std": std, "min": v[0],
            "p50": percentile(v, 50), "p99": percentile(v, 99), "max": v[-1]}


def save_csv(path, header, rows):
    """CSV 저장 (엑셀로 열림)."""
    import csv
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"저장: {path}")


def reaction_report(rows, mode, csv_file="reaction_log.csv"):
    """반응속도 게임 결과를 표로 출력하고 CSV 에 이어서 저장 (reaction.py · reaction_poll.py 공용).
    rows: (라운드, 대기 s, 반응 ms 또는 None, 부정출발 여부, 기록 ms 또는 None, CPU ms)"""
    import csv
    import time
    print("\n라운드 | 대기(s) | 반응(ms) | 부정출발 | 기록(ms)")
    for r, w, rt, fs, fin, _ in rows:
        print(f"{r:6d} | {w:7.2f} | {'-' if rt is None else format(rt, '8.1f'):>8} | "
              f"{'예' if fs else '-':>6} | {'시간초과' if fin is None else format(fin, '8.1f'):>8}")
    valid = [x[4] for x in rows if x[4] is not None]
    if valid:
        print(f"최고 {min(valid):.1f} ms · 평균 {sum(valid) / len(valid):.1f} ms · "
              f"CPU 사용 합계 {sum(x[5] for x in rows):.0f} ms (라운드 전체)")
    new = not os.path.exists(csv_file)
    with open(csv_file, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "mode", "round", "wait_s", "reaction_ms", "false_start", "result_ms", "cpu_ms"])
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        for r, wt, rt, fs, fin, cpu in rows:
            w.writerow([stamp, mode, r, f"{wt:.3f}", "" if rt is None else f"{rt:.2f}",
                        int(fs), "" if fin is None else f"{fin:.2f}", f"{cpu:.1f}"])
    print(f"저장: {csv_file}")


if __name__ == "__main__":
    print("핀 배정표 (BOARD 번호)")
    names = {LED_L: "LED_L", LED_R: "LED_R", PWM_A: "PWM_A", PWM_B: "PWM_B", BTN_L: "BTN_L",
             BTN_R: "BTN_R", BUZZER: "BUZZER", US_TRIG: "US_TRIG", US_ECHO: "US_ECHO"}
    for pin, (chip, line) in sorted(PIN_LINES.items()):
        print(f"  핀 {pin:2d}  {names.get(pin, ''):8s}  gpiochip{chip} ({CHIP_LABEL[chip]}) 라인 {line}")
    print("\nPWM 컨트롤러 → pwmchip")
    for pin, addr in sorted(PWM_ADDR.items()):
        print(f"  핀 {pin:2d}  {addr:14s}  {pwmchip_for(addr) or '없음 (jetson-io 설정 필요)'}")
    print(f"\nI2C 버스 추측: {i2c_bus_guess(ADS1115_ADDR)}  (정답은 i2cdetect -l)")
