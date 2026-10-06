#!/bin/bash
# ===== 실습 6 ④ — 두 PWM 채널의 위상차 (trigger_phase.sh, 셸 버전) =====
# 목적: 서로 독립인 PWM 컨트롤러 2 개(핀 15 · 핀 18)를 같은 주파수로 켜고, 두 입력 핀의 상승 에지 시각 차(위상차)를 잰다.
#       셸에서 enable 을 두 번 연달아 쓰면 두 채널 시작이 얼마나 어긋나는지 본다 (파이썬 버전 trigger_phase.py 와 비교)
# 배선: 핀 15 ─(330 Ω)─ 핀 22 (gpiochip0 라인 96),   핀 18 ─(330 Ω)─ 핀 16 (gpiochip1 라인 9)
# 실행: ./trigger_phase.sh [-f 10] [-u 1000] [-n 100]
#         -f 주파수(Hz, 기본 10) · -u 펄스 폭(µs, 기본 1000) · -n 채널마다 받을 에지 수(기본 100)
#       sysfs 쓰기 권한이 없으면: sudo ./trigger_phase.sh
# 흐름: ① 두 채널 설정(켜지 않음) ② gpiomon 2 개 백그라운드 시작 ③ enable 두 번 쓰기 ④ N 개 수집 ⑤ 끄기 ⑥ 위상차 분석
# 출력 파일: phase_a.txt (핀 22 쪽) · phase_b.txt (핀 16 쪽)
set -u
FREQ=10; PULSE=1000; N=100
while getopts "f:u:n:h" opt; do
  case "$opt" in
    f) FREQ=$OPTARG ;;
    u) PULSE=$OPTARG ;;
    n) N=$OPTARG ;;
    *) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  esac
done
DIR=$(cd "$(dirname "$0")" && pwd)
PWM_SYSFS=${PWM_SYSFS:-/sys/class/pwm}
ADDR_A=3280000.pwm     # 핀 15
ADDR_B=32c0000.pwm     # 핀 18

find_chip() {
  local c
  for c in "$PWM_SYSFS"/pwmchip*; do
    [ -e "$c" ] || continue
    case "$(readlink -f "$c")" in *"$1"*) echo "$c"; return 0 ;; esac
  done
  return 1
}

# ① 두 채널을 설정만 한다 (trigger.sh --no-enable 재사용)
"$DIR/trigger.sh" "$FREQ" "$PULSE" "$ADDR_A" --no-enable >/dev/null || { echo "[오류] 핀 15 설정 실패 → ./trigger.sh $FREQ $PULSE 로 원인 확인"; exit 1; }
"$DIR/trigger.sh" "$FREQ" "$PULSE" "$ADDR_B" --no-enable >/dev/null || { echo "[오류] 핀 18 설정 실패 → ./trigger.sh $FREQ $PULSE $ADDR_B 로 원인 확인"; exit 1; }
CHIP_A=$(find_chip "$ADDR_A")/pwm0
CHIP_B=$(find_chip "$ADDR_B")/pwm0
if [ ! -w "$CHIP_A/enable" ] || [ ! -w "$CHIP_B/enable" ]; then
  echo "[오류] enable 파일 쓰기 권한 없음 → sudo ./trigger_phase.sh"
  "$DIR/trigger.sh" --off "$ADDR_A" >/dev/null; "$DIR/trigger.sh" --off "$ADDR_B" >/dev/null
  exit 1
fi

# ② gpiomon 2 개를 백그라운드로 (measure_period.sh 재사용). 칩 이름은 gpiodetect 에서 라벨로 찾음 (기본 gpiochip0 / gpiochip1)
chip_of() { gpiodetect 2>/dev/null | awk -v l="[$1]" '$2 == l { print $1; exit }'; }
CH_A=$(chip_of tegra234-gpio);     CH_A=${CH_A:-gpiochip0}
CH_B=$(chip_of tegra234-gpio-aon); CH_B=${CH_B:-gpiochip1}
T=$(awk -v n="$N" -v f="$FREQ" 'BEGIN { printf "%d", n / f + 10 }')
"$DIR/measure_period.sh" -n "$N" -o phase_a.txt -c "$CH_A" -l 96 -t "$T" >/dev/null 2>&1 & PID_A=$!   # 핀 22 (라인 96)
"$DIR/measure_period.sh" -n "$N" -o phase_b.txt -c "$CH_B" -l 9  -t "$T" >/dev/null 2>&1 & PID_B=$!   # 핀 16 (aon 라인 9)
sleep 0.7      # gpiomon 이 준비될 시간

# ③ enable 을 연달아 쓴다. 셸 내장 echo 두 번 — 각각 open → write → close
#    (EPOCHREALTIME: 셸이 가진 현재 시각 변수, 프로그램을 새로 띄우지 않으므로 측정에 영향 없음)
T0=$EPOCHREALTIME
echo 1 > "$CHIP_A/enable"
T1=$EPOCHREALTIME
echo 1 > "$CHIP_B/enable"
echo "첫 번째 enable 쓰기에 걸린 시간(셸이 본 값, A→B 시작 간격의 대략치): $(awk -v a="$T0" -v b="$T1" 'BEGIN { printf "%.0f", (b - a) * 1e6 }') µs"
echo "${FREQ} Hz 로 핀 15·18 출력 중 — 에지 ${N}개 수집 (약 $(awk -v n="$N" -v f="$FREQ" 'BEGIN { printf "%.0f", n / f }') 초)"

# ④ 수집이 끝날 때까지 기다림
wait "$PID_A" "$PID_B"

# ⑤ 끄기
echo 0 > "$CHIP_A/enable"; echo 0 > "$CHIP_B/enable"
"$DIR/trigger.sh" --off "$ADDR_A" >/dev/null
"$DIR/trigger.sh" --off "$ADDR_B" >/dev/null

# ⑥ 분석
PERIOD_MS=$(awk -v f="$FREQ" 'BEGIN { printf "%.6f", 1000 / f }')
python3 "$DIR/phase_from_files.py" phase_a.txt phase_b.txt --period-ms "$PERIOD_MS"
