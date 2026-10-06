#!/bin/bash
# shellcheck disable=SC2015
# ===== pincheck.sh — 실습 핀 사전 점검 =====
# 목적: 쓸 핀이 실제로 움직이는지 확인 (JetPack 일부 버전은 특정 핀이 HIGH 가 안 나옴 → 안 되는 핀은 예비 핀으로 교체)
#       ① 출력 핀 5개: 1 초 HIGH  ② 입력 핀 3개: 값 읽기  ③ PWM: 주기 100 ms(10 Hz)·20 ms(50 Hz) 수용 여부 + pwmchip ↔ 핀
#       ④ I2C: 버스 목록과 0x48(ADS1115) 확인
# 준비: LED + 330 Ω 의 GND 쪽은 고정해 두고, '+ 쪽 점퍼'만 핀에 옮겨 꽂는다. (배선은 전원 끄고!)
# 실행: bash pincheck.sh             LED 를 옮겨 가며 확인 (Enter 로 진행)
#       bash pincheck.sh --auto      질문 없이 명령 성공 여부만 확인 (LED 없이도 가능)
#       bash pincheck.sh --sudo      그룹 권한이 아직 없을 때 gpioset/gpioget/i2cdetect 를 sudo 로 실행
#       bash pincheck.sh --only out|in|pwm|i2c   한 부분만 다시 점검
# 참고: PWM 은 /sys 에 쓰므로 권한이 없으면 sudo 비밀번호를 물음. 결과는 마지막 표를 핀 배정표에 반영
set -u
AUTO=0; SUDO=""; ONLY="all"
while [ $# -gt 0 ]; do
  case "$1" in
    --auto) AUTO=1 ;;
    --sudo) SUDO="sudo" ;;
    --only) shift; ONLY=${1:-all} ;;
    -h|--help) sed -n '3,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "알 수 없는 옵션: $1 (-h 로 도움말)"; exit 1 ;;
  esac
  shift
done
PWM_SYSFS=${PWM_SYSFS:-/sys/class/pwm}

for c in gpiodetect gpioset gpioget; do
  command -v "$c" >/dev/null || { echo "[오류] $c 없음 → bash setup_lab6.sh 먼저 실행"; exit 1; }
done

# 핀:칩 라벨:라인:이름  (pins.py 의 PIN_LINES 와 같은 값 — 바꾸면 양쪽을 함께 고칠 것)
OUT_PINS=("7:tegra234-gpio:106:LED_L" "12:tegra234-gpio:50:LED_R" "13:tegra234-gpio:108:BUZZER(PWM 겸용)"
          "15:tegra234-gpio:85:PWM_A(PWM 핀)" "18:tegra234-gpio:43:PWM_B(PWM 핀)")
IN_PINS=("22:tegra234-gpio:96:BTN_L" "16:tegra234-gpio-aon:9:BTN_R" "31:tegra234-gpio-aon:0:US_ECHO")

RES=()      # 결과 표 (판정|항목|설명)
res() { RES+=("$1|$2|$3"); }
ERR=""

chip_of() {   # chip_of <라벨> : gpiodetect 에서 실제 이름(gpiochipN)을 찾음. 못 찾으면 기본 번호
  local name
  name=$(gpiodetect 2>/dev/null | awk -v l="[$1]" '$2 == l { print $1; exit }')
  if [ -n "$name" ]; then echo "$name"; else case "$1" in tegra234-gpio) echo gpiochip0 ;; *) echo gpiochip1 ;; esac; fi
}

ask() {   # ask <질문> : 자동 모드가 아니면 Enter 를 기다림
  [ "$AUTO" = 1 ] && return 0
  read -r -p "$1 " _ || true
}
yesno() {   # yesno <질문> → 0(예) / 1(아니오) / 2(건너뜀). 자동 모드는 건너뜀(2)
  [ "$AUTO" = 1 ] && return 2
  local a; read -r -p "$1 [y/n/s=건너뜀] " a || a=s
  case "$a" in y|Y) return 0 ;; n|N) return 1 ;; *) return 2 ;; esac
}

echo "================ 핀 사전 점검 (pincheck.sh) ================"
echo "gpiochip 목록:"; gpiodetect
echo

# ---------------- ① 출력 핀 ----------------
if [ "$ONLY" = all ] || [ "$ONLY" = out ]; then
  echo "== ① 출력 핀: gpioset --mode=time --sec=1  (1 초 HIGH)"
  echo "   ※ PWM 핀(13·15·18)은 jetson-io 로 PWM 설정을 했다면 GPIO 로는 HIGH 가 안 나올 수 있음 → ③ PWM 점검 결과를 따른다"
  for e in "${OUT_PINS[@]}"; do
    IFS=: read -r pin lbl line name <<<"$e"
    chip=$(chip_of "$lbl")
    ask "LED를 핀 $pin ($name)에 연결했는지 확인 후 Enter  →"
    echo "   $SUDO gpioset --mode=time --sec=1 $chip $line=1"
    out=$($SUDO gpioset --mode=time --sec=1 "$chip" "$line=1" 2>&1); rc=$?
    if [ "$rc" -ne 0 ]; then
      why="gpioset 실패: $out"
      case "$out" in *busy*) why="$why → 그 라인을 쓰는 프로그램 종료 (gpioinfo 의 [used])" ;;
                     *ermission*) why="$why → --sudo 로 다시 실행하거나 setup_lab6.sh 후 재로그인" ;; esac
      echo "   ✗ $why"; res "FAIL" "핀 $pin $name" "$why"
      continue
    fi
    yesno "   LED 가 1 초 켜졌나요? (멀티미터면 3.3 V)"; a=$?
    case "$a" in
      0) echo "   ✓ HIGH 확인"; res "PASS" "핀 $pin $name" "$chip 라인 $line HIGH 확인" ;;
      1) echo "   ✗ 켜지지 않음 — 핀 번호·LED 극성·저항·GND 확인. PWM 핀이면 정상일 수 있음"
         res "FAIL" "핀 $pin $name" "명령은 성공했지만 LED 안 켜짐 (PWM 핀이면 ③ 확인, 아니면 예비 핀 32·33·35·36·37·38·40 으로 교체)" ;;
      *) echo "   - 명령 성공 (실제 전압은 확인 안 함)"; res "PASS?" "핀 $pin $name" "$chip 라인 $line 명령 성공 (전압 미확인)" ;;
    esac
  done
  echo
fi

# ---------------- ② 입력 핀 ----------------
if [ "$ONLY" = all ] || [ "$ONLY" = in ]; then
  echo "== ② 입력 핀: gpioget"
  for e in "${IN_PINS[@]}"; do
    IFS=: read -r pin lbl line name <<<"$e"
    chip=$(chip_of "$lbl")
    v1=$($SUDO gpioget "$chip" "$line" 2>&1); rc=$?
    if [ "$rc" -ne 0 ]; then
      echo "   ✗ 핀 $pin $name: gpioget 실패: $v1"; res "FAIL" "핀 $pin $name" "gpioget 실패: $v1"; continue
    fi
    if [ "$pin" = 31 ]; then
      echo "   핀 31 ($name) 현재값 = $v1   (초음파가 연결돼 있으면 보통 0)"
      if [ "$AUTO" = 1 ]; then res "PASS?" "핀 $pin $name" "읽기 성공 (값 $v1)"; continue; fi
      ask "   점퍼로 핀 31 을 3.3 V(핀 1)에 연결하고 Enter  →"; h=$($SUDO gpioget "$chip" "$line" 2>&1)
      ask "   점퍼를 GND(핀 6)로 옮기고 Enter  →";             l=$($SUDO gpioget "$chip" "$line" 2>&1)
      echo "   3.3 V 연결 → $h,  GND 연결 → $l"
      [ "$h" = 1 ] && [ "$l" = 0 ] && { echo "   ✓"; res "PASS" "핀 $pin $name" "3.3 V→1, GND→0"; } \
                                    || { echo "   ✗ 기대: 1 / 0"; res "FAIL" "핀 $pin $name" "3.3 V→$h, GND→$l (기대 1/0)"; }
      continue
    fi
    echo "   핀 $pin ($name) 안 누름 = $v1   (10 kΩ 풀업이면 1)"
    if [ "$AUTO" = 1 ]; then
      [ "$v1" = 1 ] && res "PASS?" "핀 $pin $name" "안 누름 1 (누름 미확인)" || res "FAIL" "핀 $pin $name" "안 누름인데 0 → 10 kΩ 풀업(3.3 V) 확인"
      continue
    fi
    ask "   버튼을 누른 채로 Enter  →"; v2=$($SUDO gpioget "$chip" "$line" 2>&1)
    echo "   누름 = $v2"
    if [ "$v1" = 1 ] && [ "$v2" = 0 ]; then echo "   ✓"; res "PASS" "핀 $pin $name" "안 누름 1 / 누름 0"
    else echo "   ✗ 기대: 1 / 0  (항상 1 이면 버튼-GND 연결, 항상 0 이면 풀업 저항 확인)"; res "FAIL" "핀 $pin $name" "안 누름 $v1 / 누름 $v2 (기대 1/0)"; fi
  done
  echo
fi

# ---------------- ③ PWM ----------------
wr() {   # wr <파일> <값> : 쓰기 (권한이 없으면 sudo tee). 실패하면 ERR 에 오류 문장
  local f=$1 v=$2
  if [ -w "$f" ]; then ERR=$( { echo "$v" > "$f"; } 2>&1 )
  else ERR=$( echo "$v" | sudo tee "$f" 2>&1 >/dev/null ); fi
}
rd() { cat "$1" 2>/dev/null || echo 0; }

pwm_try() {   # pwm_try <pwmchip 경로> <period_ns> [유지 시간 초] → 0 성공 / 1 실패 (사유 PWM_ERR)
  local c=$1 per=$2 p="$1/pwm0" newly=0 rc=0
  PWM_ERR=""
  if [ ! -d "$p" ]; then wr "$c/export" 0 || true; [ -d "$p" ] || { PWM_ERR="export 실패: $ERR"; return 1; }; newly=1; fi
  for _ in $(seq 1 50); do [ -w "$p/enable" ] && break; sleep 0.02; done
  if [ "$(rd "$p/enable")" = 1 ]; then wr "$p/enable" 0 || true; fi
  if [ "$(rd "$p/period")" -gt 0 ] && [ "$(rd "$p/duty_cycle")" -gt 0 ]; then wr "$p/duty_cycle" 0 || true; fi
  # 쓰기 순서: duty 를 먼저 0 → period → duty → enable (Tegra 는 켤 때 하드웨어 한계를 검사할 수 있음: 장비에서 확인)
  wr "$p/period" "$per";              if [ -n "$ERR" ]; then PWM_ERR="period: $ERR"; rc=1; fi
  if [ "$rc" = 0 ]; then wr "$p/duty_cycle" $((per / 2)); [ -n "$ERR" ] && { PWM_ERR="duty_cycle: $ERR"; rc=1; }; fi
  if [ "$rc" = 0 ]; then wr "$p/enable" 1;  [ -n "$ERR" ] && { PWM_ERR="enable: $ERR"; rc=1; }; fi
  sleep "${3:-0.3}"
  if [ "$(rd "$p/enable")" = 1 ]; then wr "$p/enable" 0 || true; fi
  if [ "$newly" = 1 ]; then wr "$c/unexport" 0 || true; fi
  return "$rc"
}

pin_of() { case "$1" in 3280000.pwm) echo "15 (PWM A)" ;; 32c0000.pwm) echo "18 (PWM B)" ;; 32f0000.pwm) echo "13 (부저)" ;; *) echo "?" ;; esac; }

if [ "$ONLY" = all ] || [ "$ONLY" = pwm ]; then
  echo "== ③ PWM: pwmchip ↔ 핀, 주기 100 ms(10 Hz) / 20 ms(50 Hz) 수용 여부"
  shopt -s nullglob
  chips=("$PWM_SYSFS"/pwmchip*)
  shopt -u nullglob
  if [ "${#chips[@]}" -eq 0 ]; then
    echo "   pwmchip 없음 → sudo /opt/nvidia/jetson-io/jetson-io.py 로 pwm(13·15·18) 활성화 후 재부팅"
    res "WARN" "PWM" "pwmchip 없음 (jetson-io 설정 + 재부팅 필요)"
  fi
  for c in "${chips[@]}"; do
    dev=$(basename "$(readlink -f "$c/device" 2>/dev/null)")
    case "$dev" in *.pwm) ;; *) dev=$(basename "$(dirname "$(dirname "$(readlink -f "$c")")")") ;; esac   # device 링크가 없으면 경로에서
    echo "   $(basename "$c") → $dev  = 핀 $(pin_of "$dev")"
    summary=""
    for spec in "100000000:10 Hz" "20000000:50 Hz"; do
      per=${spec%%:*}; hz=${spec#*:}
      if pwm_try "$c" "$per"; then
        echo "      $hz (period $per ns): OK"; summary="$summary$hz OK / "
      else
        case "$PWM_ERR" in
          *"Invalid argument"*) why="Invalid argument — 이 컨트롤러가 거부 (주파수 하한? 실습 6 ① 참고)" ;;
          *ermission*) why="권한 없음 → sudo 로 실행하거나 setup_lab6.sh 후 재부팅" ;;
          *busy*) why="사용 중 (다른 프로그램이 export 해 둠)" ;;
          *) why="$PWM_ERR" ;;
        esac
        echo "      $hz (period $per ns): 실패 — $why"; summary="$summary$hz 실패($why) / "
      fi
    done
    case "$summary" in *실패*) res "WARN" "PWM $(basename "$c") $dev (핀 $(pin_of "$dev"))" "${summary% / }" ;;
                       *)      res "PASS" "PWM $(basename "$c") $dev (핀 $(pin_of "$dev"))" "${summary% / }" ;; esac
    # 사람이 있으면: PWM 으로 실제 핀이 움직이는지 LED 로 확인 (jetson-io 로 PWM 이 된 핀은 GPIO 점검 대신 이것으로)
    if [ "$AUTO" = 0 ]; then
      hz=""
      case "$summary" in *"10 Hz OK"*) hz="10 Hz"; per=100000000 ;; *"50 Hz OK"*) hz="50 Hz"; per=20000000 ;; esac
      if [ -n "$hz" ]; then
        ask "   핀 $(pin_of "$dev") 에 LED 를 연결하고 Enter → $hz PWM 을 2 초 출력  →"
        pwm_try "$c" "$per" 2 || true
        yesno "   LED 가 깜빡이거나(10 Hz) 어렴풋이 켜졌나요(50 Hz)?"; a=$?
        case "$a" in
          0) res "PASS" "PWM 출력 핀 $(pin_of "$dev")" "LED 로 확인" ;;
          1) res "FAIL" "PWM 출력 핀 $(pin_of "$dev")" "PWM 은 설정되지만 핀에서 신호 없음 (배선·핀 번호·jetson-io 확인)" ;;
        esac
      fi
    fi
  done
  echo "   → 위 pwmchip 번호 ↔ 핀 대응을 기록해 두세요 (실습 5·6 에서 사용)"
  echo
fi

# ---------------- ④ I2C ----------------
if [ "$ONLY" = all ] || [ "$ONLY" = i2c ]; then
  echo "== ④ I2C 버스와 ADS1115(0x48)"
  if command -v i2cdetect >/dev/null; then
    i2cdetect -l
    found=""
    for b in 7 1; do
      [ -e "/dev/i2c-$b" ] || continue
      out=$($SUDO i2cdetect -y "$b" 0x48 0x48 2>&1)
      if echo "$out" | grep -qw -e 48 -e UU; then found=$b; break; fi
    done
    if [ -n "$found" ]; then
      echo "   ✓ 버스 $found 에서 0x48 감지  → steer.py 등은 --bus $found (자동 탐색도 됨)"; res "PASS" "I2C ADS1115" "버스 $found, 주소 0x48"
    else
      echo "   0x48 응답 없음 → ADS1115 를 아직 안 달았다면 정상. 달았다면 SDA(핀 3)·SCL(핀 5)·3.3 V·GND·ADDR→GND 확인"
      res "WARN" "I2C ADS1115" "0x48 없음 (미연결이면 정상). 버스 번호는 위 i2cdetect -l 참고"
    fi
  else
    echo "   i2cdetect 없음 → bash setup_lab6.sh"; res "FAIL" "I2C" "i2c-tools 없음"
  fi
  echo
fi

# ---------------- 결과 표 ----------------
echo "================ 결과 요약 ================"
fails=0
for r in "${RES[@]}"; do
  IFS='|' read -r st name detail <<<"$r"
  echo "[$st] $name — $detail"
  [ "$st" = FAIL ] && fails=$((fails + 1))
done
echo "PASS 확인됨 · PASS? 명령만 성공(전압 미확인) · WARN 확인 필요 · FAIL 문제"
[ "$fails" -gt 0 ] && echo "※ FAIL 핀은 예비 핀(32·33·35·36·37·38·40)으로 바꾸고, 바꾼 핀 번호를 pins.py 와 핀 배정표에 기록하세요."
[ "$fails" -eq 0 ]
