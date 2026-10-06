#!/bin/bash
# ===== setup_lab6.sh — 6주차 실습 환경 준비 (Jetson 1대당 한 번) =====
# 목적: 필요한 패키지 설치 · Jetson.GPIO 확인 · gpio/i2c 그룹과 udev 규칙 설정 · 결과를 ✓/✗ 표로 요약
# 실행: bash setup_lab6.sh                (sudo 비밀번호를 물어봄. 인터넷 필요, 3~5분)
#       bash setup_lab6.sh --save-debs    설치 후 받은 .deb 를 lab6/deb/ 에 복사 → 인터넷 없는 Jetson 에서 재사용
#                                         (패키지를 처음 설치하는 '깨끗한' Jetson 에서 실행해야 의존 패키지까지 담김)
# 특징: 여러 번 실행해도 안전 (이미 된 것은 건너뜀). 일부가 실패해도 끝까지 진행하고 마지막에 표로 알려 줌.
# 끝난 뒤: ① 로그아웃/재로그인 (그룹 반영)  ② PWM 핀은 jetson-io 로 활성화 + 재부팅
# shellcheck disable=SC2012,SC2015   # ls 로 개수·목록만 세는 용도, row() 는 항상 성공을 돌려줌
set -u      # (-e 는 쓰지 않음: 한 단계가 실패해도 계속 진행)

DIR=$(cd "$(dirname "$0")" && pwd)
SAVE_DEBS=0; [ "${1:-}" = "--save-debs" ] && SAVE_DEBS=1
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
ME=${SUDO_USER:-${USER:-$(id -un)}}          # 그룹에 넣을 사용자 (sudo 로 실행해도 원래 사용자)
APT_PKGS=(gpiod python3-libgpiod i2c-tools stress-ng python3-pip)

# ---------- 결과 표 ----------
ROWS=(); FAILS=0
row() {   # row <ok|bad|warn> <항목> <설명>
  local mark="✓"
  case "$1" in bad) mark="✗"; FAILS=$((FAILS + 1)) ;; warn) mark="△" ;; esac
  ROWS+=("$mark|$2|$3")
}

echo "================ 6주차 실습 환경 준비 ================"
echo "사용자: $ME   (이 스크립트는 여러 번 실행해도 안전합니다)"

# ---------- 1. 버전 정보 ----------
echo
echo "== 1. JetPack / L4T 버전"
if [ -r /etc/nv_tegra_release ]; then head -1 /etc/nv_tegra_release; else echo "/etc/nv_tegra_release 없음 — Jetson 이 아닐 수 있음"; fi
apt show nvidia-jetpack 2>/dev/null | grep -m1 '^Version' || echo "nvidia-jetpack 패키지 정보 없음 (정상일 수 있음)"
python3 --version

# ---------- 2. apt 패키지 ----------
echo
echo "== 2. 패키지 설치: ${APT_PKGS[*]}"
missing=()
for p in "${APT_PKGS[@]}"; do dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p"); done
if [ "${#missing[@]}" -eq 0 ]; then
  echo "모두 설치돼 있음 — 건너뜀"
else
  echo "설치할 패키지: ${missing[*]}"
  $SUDO apt-get update || echo "[경고] apt-get update 실패 (인터넷 확인) — 계속 진행"
  if ! $SUDO apt-get install -y "${missing[@]}"; then
    echo "[경고] 한 번에 설치 실패 → 하나씩 다시 시도"
    for p in "${missing[@]}"; do $SUDO apt-get install -y "$p" || echo "[실패] $p"; done
  fi
  # 아직 빠진 게 있고 미리 받아 둔 .deb 가 있으면 그걸로 설치
  still=()
  for p in "${APT_PKGS[@]}"; do dpkg -s "$p" >/dev/null 2>&1 || still+=("$p"); done
  if [ "${#still[@]}" -gt 0 ] && ls "$DIR"/deb/*.deb >/dev/null 2>&1; then
    echo "[알림] 인터넷 설치 실패 → $DIR/deb/ 의 .deb 로 설치 시도"
    $SUDO dpkg -i "$DIR"/deb/*.deb || echo "[경고] dpkg 설치 중 오류"
  fi
fi

# smbus2: apt 에 있으면 apt, 없으면 pip
if ! python3 -c "import smbus2" 2>/dev/null; then
  echo "smbus2 설치 시도 (apt → pip 순서)"
  $SUDO apt-get install -y python3-smbus2 2>/dev/null || pip3 install --user smbus2 || $SUDO pip3 install smbus2
fi

if [ "$SAVE_DEBS" = 1 ]; then
  mkdir -p "$DIR/deb" && cp /var/cache/apt/archives/*.deb "$DIR/deb/" 2>/dev/null \
    && echo "받은 .deb $(ls "$DIR"/deb/*.deb 2>/dev/null | wc -l) 개를 $DIR/deb/ 에 복사함" \
    || echo "[경고] 복사할 .deb 없음 (이미 설치돼 있었거나 apt 캐시가 비어 있음)"
fi

# ---------- 3. Jetson.GPIO ----------
echo
echo "== 3. Jetson.GPIO 확인"
if python3 -c "import Jetson.GPIO" 2>/dev/null; then
  echo "이미 있음: Jetson.GPIO $(python3 -c 'import Jetson.GPIO as G; print(G.VERSION)')"
else
  echo "없음 → pip 로 설치"
  $SUDO pip3 install Jetson.GPIO
fi

# ---------- 4. 그룹과 udev 규칙 ----------
echo
echo "== 4. gpio · i2c 그룹과 udev 규칙"
$SUDO groupadd -f -r gpio && $SUDO usermod -aG gpio "$ME" && echo "gpio 그룹에 $ME 추가(또는 이미 있음)"
$SUDO groupadd -f -r i2c  && $SUDO usermod -aG i2c  "$ME" && echo "i2c 그룹에 $ME 추가(또는 이미 있음)"

RULES_CHANGED=0
PKGDIR=$(python3 -c "import Jetson.GPIO, os; print(os.path.dirname(Jetson.GPIO.__file__))" 2>/dev/null || true)
if [ -n "$PKGDIR" ] && [ -r "$PKGDIR/99-gpio.rules" ]; then
  if ! cmp -s "$PKGDIR/99-gpio.rules" /etc/udev/rules.d/99-gpio.rules; then
    $SUDO cp "$PKGDIR/99-gpio.rules" /etc/udev/rules.d/99-gpio.rules && RULES_CHANGED=1 && echo "99-gpio.rules 설치 (gpiochip·PWM sysfs 를 gpio 그룹에 허용)"
  else
    echo "99-gpio.rules 이미 설치됨"
  fi
else
  echo "[경고] Jetson.GPIO 패키지에서 99-gpio.rules 를 찾지 못함"
fi
I2C_RULE='SUBSYSTEM=="i2c-dev", GROUP="i2c", MODE="0660"'
if ! grep -qsF "$I2C_RULE" /etc/udev/rules.d/99-i2c-lab.rules; then
  echo "$I2C_RULE" | $SUDO tee /etc/udev/rules.d/99-i2c-lab.rules >/dev/null && RULES_CHANGED=1 && echo "99-i2c-lab.rules 설치 (/dev/i2c-* 를 i2c 그룹에 허용)"
else
  echo "99-i2c-lab.rules 이미 설치됨"
fi
if [ "$RULES_CHANGED" = 1 ]; then
  $SUDO udevadm control --reload-rules
  $SUDO udevadm trigger
  $SUDO udevadm trigger --action=add --subsystem-match=gpio --subsystem-match=pwm --subsystem-match=i2c-dev   # 장비에서 확인
  echo "udev 규칙 다시 읽음 (완전히 적용되려면 재부팅·재로그인)"
fi

# ---------- 5. 결과 확인 ----------
echo
echo "== 5. 결과 확인"
if command -v gpiodetect >/dev/null && command -v gpioset >/dev/null && command -v gpioget >/dev/null \
   && command -v gpiomon >/dev/null && command -v gpioinfo >/dev/null; then
  row ok "gpiod 도구" "$(gpiodetect --version 2>&1 | head -1)"
else
  row bad "gpiod 도구" "gpioset/gpioget/gpiomon/gpioinfo 없음 → sudo apt-get install gpiod"
fi
python3 -c "import gpiod" 2>/dev/null && row ok "python3-libgpiod" "import gpiod 성공" || row warn "python3-libgpiod" "import 실패 (실습에서 필수는 아님)"
if python3 -c "import Jetson.GPIO" 2>/dev/null; then
  row ok "Jetson.GPIO" "버전 $(python3 -c 'import Jetson.GPIO as G; print(G.VERSION)')"
else
  row bad "Jetson.GPIO" "import 실패 → sudo pip3 install Jetson.GPIO (Jetson 장비인지도 확인)"
fi
python3 -c "import smbus2" 2>/dev/null && row ok "smbus2" "import 성공" || row bad "smbus2" "없음 → pip3 install --user smbus2"
command -v i2cdetect >/dev/null && row ok "i2c-tools" "$(command -v i2cdetect)" || row bad "i2c-tools" "i2cdetect 없음"
command -v stress-ng >/dev/null && row ok "stress-ng" "$(stress-ng --version 2>&1 | head -1)" || row bad "stress-ng" "없음 (실습 4·6 부하 실험에 필요)"

for g in gpio i2c; do
  if getent group "$g" | grep -qw "$ME"; then
    if id -nG "$ME" | grep -qw "$g"; then
      row ok "그룹 $g" "$ME 가 $g 그룹 (현재 세션에 반영됨)"
    else
      row warn "그룹 $g" "추가됨 — 재로그인(또는 재부팅) 후 적용"
    fi
  else
    row bad "그룹 $g" "$ME 가 $g 그룹에 없음"
  fi
done
[ -e /etc/udev/rules.d/99-gpio.rules ] && row ok "udev 규칙" "99-gpio.rules" || row bad "udev 규칙" "99-gpio.rules 없음 → Jetson.GPIO 설치 확인 후 다시 실행"

chips=$(ls /dev/gpiochip* 2>/dev/null | tr '\n' ' ')
if [ -n "$chips" ]; then
  row ok "/dev/gpiochip*" "$chips($(stat -c '%U:%G %a' /dev/gpiochip0 2>/dev/null))"
else
  row bad "/dev/gpiochip*" "없음 (Jetson 이 맞나요?)"
fi
pwms=""
for c in /sys/class/pwm/pwmchip*; do
  [ -e "$c" ] || continue
  dev=$(basename "$(readlink -f "$c/device" 2>/dev/null)")
  case "$dev" in *.pwm) ;; *) dev=$(basename "$(dirname "$(dirname "$(readlink -f "$c")")")") ;; esac   # device 링크가 없으면 경로에서
  pwms="$pwms$(basename "$c")→$dev "
done
if [ -n "$pwms" ]; then
  row ok "/sys/class/pwm" "$pwms"
else
  row warn "/sys/class/pwm" "pwmchip 없음 → jetson-io 로 PWM 활성화 후 재부팅 필요 (아래 '다음 할 일' 2번)"
fi
buses=$(ls /dev/i2c-* 2>/dev/null | tr '\n' ' ')
[ -n "$buses" ] && row ok "I2C 버스" "$buses(40핀 3·5번 핀 = 보통 7번, i2cdetect -l 로 확인)" || row bad "I2C 버스" "/dev/i2c-* 없음"

echo
echo "------------------------------------------------------------"
echo "  | 항목 | 상태"
for r in "${ROWS[@]}"; do
  IFS='|' read -r mark name detail <<<"$r"
  echo "$mark | $name | $detail"
done
echo "------------------------------------------------------------"
echo "✓ 정상   △ 아래 '다음 할 일' 을 하면 해결   ✗ 문제 (위 설명 확인 후 이 스크립트를 다시 실행)"

echo
echo "== 다음 할 일"
echo " 1) 로그아웃 후 다시 로그인 (또는 재부팅) — gpio·i2c 그룹이 적용됨. 확인: groups"
echo " 2) PWM 핀 활성화(실습 5·6): sudo /opt/nvidia/jetson-io/jetson-io.py"
echo "      → Configure Jetson 40pin Header → Configure header pins manually → pwm(핀 13·15·18) 체크"
echo "      → Save pin changes → Save and reboot      (재부팅 후 ls /sys/class/pwm 에 pwmchip 3개)"
echo " 3) 핀 점검: bash pincheck.sh"
[ "$FAILS" -gt 0 ] && echo "※ ✗ 항목이 $FAILS 개 있습니다. 인터넷 연결을 확인하고 이 스크립트를 다시 실행하세요."
[ "$FAILS" -eq 0 ]
