#!/bin/bash
# ===== 실습 6 ②③ — gpiomon 으로 신호 주기 측정 (measure_period.sh) =====
# 목적: 입력 핀의 상승 에지를 "커널 타임스탬프"와 함께 N 개 받아 파일로 저장 (분석은 analyze.py)
#       커널이 에지 순간에 찍는 시각이라, 파이썬으로 재는 것보다 훨씬 정확함
# 배선: 측정할 신호를 입력 핀으로 루프백
#         HW PWM : 핀 15 ─(330 Ω)─ 핀 22        SW 트리거 : 핀 7 ─(330 Ω)─ 핀 22
#       ※ 핀 22 에는 버튼이 병렬로 연결돼 있음 → 측정 중 버튼을 누르지 말 것 (출력 단락)
# 실행: ./measure_period.sh [-n 200] [-o hw.txt] [-c 0] [-l 96] [-t 120]
#         -n 에지 개수 · -o 저장 파일 · -c gpiochip 번호(또는 이름) · -l 라인 번호 · -t 제한 시간(초)
#       기본값 = BTN_L 입력 (gpiochip0 라인 96).  핀 16 은 -c 1 -l 9,  핀 31 은 -c 1 -l 0
#       이어서: python3 analyze.py hw.txt --nominal-ms 100
# 주의: 같은 라인을 다른 프로그램이 잡고 있으면 'Device or resource busy'
#       (예: lamp.py 가 쓰는 핀 7(라인 106) 은 gpiomon 으로 직접 못 봄 → 핀 31 에 점퍼 후 -c 1 -l 0)
set -u
N=200; OUT=hw.txt; CHIP=0; LINE=96; TMO=120

while getopts "n:o:c:l:t:h" opt; do
  case "$opt" in
    n) N=$OPTARG ;;
    o) OUT=$OPTARG ;;
    c) CHIP=$OPTARG ;;
    l) LINE=$OPTARG ;;
    t) TMO=$OPTARG ;;
    *) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  esac
done

command -v gpiomon >/dev/null || { echo "[오류] gpiomon 없음 → bash setup_lab6.sh (gpiod 설치)"; exit 1; }
case "$CHIP" in ''|*[!0-9]*) CHIP_ARG=$CHIP ;; *) CHIP_ARG="gpiochip$CHIP" ;; esac   # 숫자면 gpiochipN, 아니면 이름 그대로

# 파일로 저장할 때 출력이 버퍼에 갇히지 않게: --line-buffered 가 있으면 쓰고, 없으면 stdbuf
CMD=(gpiomon --rising-edge --num-events="$N")
PRE=()
if gpiomon --help 2>&1 | grep -q -- '--line-buffered'; then
  CMD+=(--line-buffered)
else
  PRE=(stdbuf -oL)                      # (장비에서 확인: libgpiod v1 옵션 이름)
fi
CMD+=("$CHIP_ARG" "$LINE")

ERRF=$(mktemp)
echo "측정 시작: ${PRE[*]-} ${CMD[*]}  → $OUT  (최대 ${TMO}초, 에지 ${N}개)"
echo "  (신호가 안 오면 배선·trigger.sh 실행 여부 확인. Ctrl-C 로 중단해도 받은 만큼 저장됨)"
timeout --signal=INT --kill-after=3 "$TMO" "${PRE[@]+"${PRE[@]}"}" "${CMD[@]}" > "$OUT" 2> "$ERRF"
rc=$?

COUNT=$(grep -c "EDGE" "$OUT" 2>/dev/null || true)
if [ "$rc" -ne 0 ] && [ "$rc" -ne 124 ] && [ "$rc" -ne 130 ]; then
  echo "[오류] gpiomon 종료 코드 $rc:"; cat "$ERRF"
  grep -qi "busy" "$ERRF" && echo "  → 그 라인을 쓰는 프로그램을 먼저 끝내세요 (gpioinfo 에서 [used] 확인)"
  grep -qi "permission" "$ERRF" && echo "  → gpio 그룹 필요: bash setup_lab6.sh 후 재로그인 (임시: sudo ./measure_period.sh ...)"
  rm -f "$ERRF"; exit 2
fi
rm -f "$ERRF"
[ "$rc" -eq 124 ] && echo "[알림] 제한 시간(${TMO}초) 도달 — 에지를 ${COUNT:-0}개만 받음"
echo "저장: $OUT  (에지 ${COUNT:-0}개)"
head -3 "$OUT"
[ "${COUNT:-0}" -lt 2 ] && { echo "[경고] 에지가 2개 미만 → 분석 불가. 신호가 입력 핀에 연결됐는지 확인"; exit 3; }
echo "다음: python3 analyze.py $OUT --nominal-ms 100     (명목 주기에 맞게 바꾸기)"
