#!/bin/bash
# ===== 실습 6 ① — sysfs 로 PWM 트리거 신호 만들기 (trigger.sh) =====
# 목적: 주파수와 펄스 폭을 주면 period / duty_cycle(ns)을 계산해 /sys/class/pwm 에 직접 쓴다
#       (Jetson.GPIO 없이 커널 PWM 인터페이스를 직접 다루는 실습)
# 배선: 핀 15 (3280000.pwm) 또는 핀 18 (32c0000.pwm) → LED 또는 루프백 점퍼 → 핀 22 (실습 6 ②)
# 준비: jetson-io 로 PWM 활성화 + 재부팅 완료 (ls /sys/class/pwm)
# 실행: ./trigger.sh FREQ_HZ PULSE_US [CHIP_ADDR] [--invert] [--no-enable]
#         ./trigger.sh 10 1000                  10 Hz, 펄스 1 ms, 핀 15 (3280000.pwm 기본)
#         ./trigger.sh 30 100 32c0000.pwm       30 Hz, 펄스 100 µs, 핀 18
#         ./trigger.sh 30 100 --invert          액티브 로우 (펄스 구간이 LOW): 듀티를 보수로
#         ./trigger.sh 10 1000 --no-enable      설정만 하고 켜지 않음 (trigger_phase.sh 가 사용)
#       ./trigger.sh --off [CHIP_ADDR]          끄기 (disable + unexport)
# 쓰기 순서: duty_cycle 은 period 보다 클 수 없다 (넘으면 Invalid argument)
#   · 주기를 줄일 때는 duty 를 먼저 0 으로 내린 뒤 period → duty 순서로 쓴다
#   · 처음(period=0) 에는 period 부터 써야 한다  (장비에서 확인: 커널 버전별 차이)
set -u
PWM_SYSFS=${PWM_SYSFS:-/sys/class/pwm}     # 테스트용으로 바꿀 수 있음 (보통 그대로)
ERR=""

usage() { sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; }

# ---- 인자 읽기 ----
FREQ=""; PULSE_US=""; ADDR=""; INVERT=0; OFF=0; NO_ENABLE=0
pos=()
for a in "$@"; do
  case "$a" in
    --invert)    INVERT=1 ;;
    --off)       OFF=1 ;;
    --no-enable) NO_ENABLE=1 ;;
    -h|--help)   usage; exit 0 ;;
    -*)          echo "[오류] 알 수 없는 옵션: $a"; usage; exit 1 ;;
    *)           pos+=("$a") ;;
  esac
done
if [ "$OFF" = 1 ]; then
  ADDR=${pos[0]:-3280000.pwm}
else
  [ "${#pos[@]}" -ge 2 ] || { usage; exit 1; }
  FREQ=${pos[0]}; PULSE_US=${pos[1]}; ADDR=${pos[2]:-3280000.pwm}
fi

pin_of() {   # 컨트롤러 → 40핀 번호 (안내용)
  case "$1" in 3280000.pwm) echo 15 ;; 32c0000.pwm) echo 18 ;; 32f0000.pwm) echo 13 ;; *) echo "?" ;; esac
}

find_chip() {   # find_chip <addr> : /sys/class/pwm/pwmchipN 중 addr 를 가진 것을 출력
  local c
  for c in "$PWM_SYSFS"/pwmchip*; do
    [ -e "$c" ] || continue
    case "$(readlink -f "$c")" in *"$1"*) echo "$c"; return 0 ;; esac
  done
  return 1
}

wr() {   # wr <파일> <값> : 쓰기. 쓸 권한이 없으면 sudo tee. 실패하면 오류 문장이 ERR 에 남는다
  local f=$1 v=$2
  if [ -w "$f" ]; then
    ERR=$( { echo "$v" > "$f"; } 2>&1 )
  else
    ERR=$( echo "$v" | sudo tee "$f" 2>&1 >/dev/null )
  fi
}

rd() { cat "$1" 2>/dev/null || echo 0; }   # 값 읽기 (없으면 0)

explain_einval() {   # $1 = 실패한 단계 이름
  cat <<MSG
[오류] $1 쓰기가 'Invalid argument' 로 거부됨
       요청: ${FREQ} Hz → period ${PERIOD} ns, 펄스 ${PULSE_NS} ns, duty_cycle ${DUTY} ns

왜 그럴까?
 · Jetson PWM(pwm-tegra)은 소스 클록을 256 으로 나눈 뒤, 13 비트 분주기(PFM)로 한 번 더 나눠 주파수를 만든다.
     출력 f = 클록 / (256 × (PFM+1)),  PFM = 0 ~ 8191
 · 낮은 주파수를 만들려면 소스 클록 자체를 낮춰야 한다 (드라이버가 f × 256 Hz 로 요청).
   그런데 클록 트리가 내려갈 수 있는 하한이 있어서, 그보다 낮은 주파수는 거부된다 = 이 장비 PWM 의 주파수 하한.
 · 반대로 주기가 너무 짧거나, 펄스 폭이 주기보다 길어도 같은 오류가 난다.

해 보기:
 · 주파수를 올려 가며 되는 최저 주파수를 찾는다:
     ./trigger.sh 20 1000      ./trigger.sh 50 1000      (결과를 보고서에 기록)
 · 10 Hz 가 안 되는 장비라면 정상일 수 있음 → 소프트웨어 방식(sw_trigger.py)과 비교하는 것이 이 실습의 요점
MSG
}

cleanup_export() {   # 이번 실행에서 export 한 채널이면 되돌린다
  if [ "${EXPORTED_NOW:-0}" = 1 ]; then wr "$CHIP/unexport" 0; fi
}

fail() {   # fail <단계>
  if echo "$ERR" | grep -qi "invalid argument"; then
    explain_einval "$1"
  else
    echo "[오류] $1 쓰기 실패: $ERR"
    echo "  권한 문제면 sudo 로 다시 실행하거나 bash setup_lab6.sh 후 재부팅/재로그인"
  fi
  cleanup_export
  exit 2
}

# ---- 컨트롤러 찾기 ----
CHIP=$(find_chip "$ADDR") || {
  echo "[오류] '$ADDR' 컨트롤러를 찾지 못함."
  # shellcheck disable=SC2012
  echo "  현재 pwmchip: $(ls "$PWM_SYSFS" 2>/dev/null | tr '\n' ' ')"
  echo "  없으면: sudo /opt/nvidia/jetson-io/jetson-io.py 에서 pwm 활성화 → 재부팅"
  exit 1
}
P="$CHIP/pwm0"

# ---- 끄기 ----
if [ "$OFF" = 1 ]; then
  if [ -d "$P" ]; then
    if [ "$(rd "$P/enable")" = 1 ]; then wr "$P/enable" 0 || echo "[경고] disable 실패: $ERR"; fi
    wr "$CHIP/unexport" 0 || echo "[경고] unexport 실패: $ERR"
    echo "[완료] $ADDR (핀 $(pin_of "$ADDR")) 끔 + 해제"
  else
    echo "이미 해제됨: $ADDR"
  fi
  exit 0
fi

# ---- 값 검사와 계산 ----
awk -v f="$FREQ" 'BEGIN { exit !(f ~ /^[0-9]+(\.[0-9]+)?$/ && f > 0) }' || { echo "[오류] FREQ_HZ 는 0 보다 큰 숫자: '$FREQ'"; exit 1; }
case "$PULSE_US" in ''|*[!0-9]*) echo "[오류] PULSE_US 는 0 이상의 정수(µs): '$PULSE_US'"; exit 1 ;; esac

PERIOD=$(awk -v f="$FREQ" 'BEGIN { printf "%.0f", 1e9 / f }')   # 주기(ns) = 1e9 / 주파수
PULSE_NS=$(( PULSE_US * 1000 ))                                  # 펄스 폭(ns)
if [ "$PULSE_NS" -gt "$PERIOD" ]; then
  echo "[오류] 펄스 폭(${PULSE_US} µs)이 주기(${PERIOD} ns)보다 김"; exit 1
fi
if [ "$INVERT" = 1 ]; then DUTY=$(( PERIOD - PULSE_NS )); else DUTY=$PULSE_NS; fi   # 액티브 로우 = 듀티 보수

# ---- export ----
EXPORTED_NOW=0
if [ ! -d "$P" ]; then
  wr "$CHIP/export" 0 || { echo "[오류] export 실패: $ERR"; exit 2; }
  EXPORTED_NOW=1
fi
for _ in $(seq 1 50); do [ -w "$P/enable" ] && break; sleep 0.02; done   # udev 가 권한을 줄 때까지 최대 1 초

# ---- 설정 (순서 중요) ----
if [ "$(rd "$P/enable")" = 1 ]; then wr "$P/enable" 0 || fail enable; fi          # 켜져 있으면 먼저 끔
if [ "$(rd "$P/period")" -gt 0 ] && [ "$(rd "$P/duty_cycle")" -gt 0 ]; then
  wr "$P/duty_cycle" 0 || fail duty_cycle                                          # 주기 줄이기 전에 duty 부터 0
fi
wr "$P/period" "$PERIOD" || fail period
wr "$P/duty_cycle" "$DUTY" || fail duty_cycle
if [ "$NO_ENABLE" = 0 ]; then
  wr "$P/enable" 1 || fail enable      # Tegra 드라이버는 켤 때 하드웨어 한계를 검사함 (장비에서 확인)
fi

# ---- 결과 출력 ----
case "$ADDR" in
  3280000.pwm) LOOP="핀 15 → 핀 22 점퍼 (330 Ω 직렬 권장)"; MEAS="./measure_period.sh -n 200 -o hw.txt" ;;
  32c0000.pwm) LOOP="핀 18 → 핀 16 점퍼 (330 Ω 직렬 권장)"; MEAS="./measure_period.sh -n 200 -o hw18.txt -c 1 -l 9" ;;
  *)           LOOP="(이 핀은 루프백 입력이 배정되지 않음)"; MEAS="" ;;
esac
awk -v d="$DUTY" -v p="$PERIOD" -v pu="$PULSE_US" -v inv="$INVERT" -v f="$FREQ" -v chip="$CHIP" -v addr="$ADDR" -v pin="$(pin_of "$ADDR")" -v ne="$NO_ENABLE" 'BEGIN {
  printf "[완료] %s (핀 %s, %s/pwm0)  %s\n", addr, pin, chip, (ne ? "설정만 함(꺼진 상태)" : "출력 중")
  printf "  요청 주파수 %s Hz → period     %d ns\n", f, p
  printf "  펄스 폭   %d µs → duty_cycle %d ns (%.3f %%)\n", pu, d, 100.0 * d / p
  printf "  극성: %s\n", (inv ? "액티브 로우 (펄스 구간 LOW, 평상시 HIGH). 주의: disable 하면 출력이 LOW 가 됨" : "펄스 구간 HIGH, 평상시 LOW")
}'
echo "  측정: $LOOP"
[ -n "$MEAS" ] && echo "        $MEAS  →  python3 analyze.py <파일> --nominal-ms $(awk -v p="$PERIOD" 'BEGIN { printf "%g", p / 1e6 }')"
echo "  끄기: ./trigger.sh --off $ADDR"
