# 실습 9 — 종합: 차량 램프 컨트롤러 (★ 필수 · HW #2 B 의 시작점)

슬라이드 169~177 · HW #2 A-9 + B · 소요 30분

**목적**: 오늘 배운 전부를 한 프로그램에 — GPIO 입출력(실습 1·2) · 콜백 → 큐 · 디바운스(실습 3) · 시간 기반 점멸과 PWM(실습 5) · 그리고 **측정으로 검증**(실습 6 의 도구). 방향지시등 · 비상등 · 브레이크등을 버튼 두 개로 제어하는 상태기계.

| 파일 | 역할 |
|---|---|
| `lamp_skeleton.py` | ★ 학생용 뼈대. **TODO ①** 상태 전이표 `TRANS`(슬라이드 170 의 전이도를 dict 로) · **TODO ②** 점멸 계산식 두 곳을 채우면 완성 |
| `lamp.py` | 정답. `--period-log` 로 LED L 점멸 시각을 `log_period.txt` 에 기록 (gpiomon 형식 → `analyze.py` 가 그대로 읽음) |

동작: 짧게(< 1 s) L → 좌 점멸 ON/OFF · R → 우 점멸 (서로 배타, 켜진 쪽에서 반대쪽 누르면 전환) · 길게(≥ 1 s) → 비상등(HAZARD, 양쪽 점멸) ON/OFF · 두 버튼 동시 누름 동안 브레이크등 100 % (평소 미등 20 %) · 점멸 1.5 Hz 듀티 50 %

구조: 콜백(다른 스레드) → `q.put((핀, 시각))` 한 줄 → 메인 루프 10 ms 마다 ① 큐 처리 ② 짧게/길게 판정 → 전이표 ③ `monotonic` 시계로 점멸 계산 ④ 출력. 블로킹 `sleep` 없음.

## 배선 — 버튼 2 + LED 3 (실습 1~3·5 의 부품 그대로)

```
LED L   핀 7  ─ 330 Ω ─ LED ─ GND          좌 방향지시등
LED R   핀 12 ─ 330 Ω ─ LED ─ GND          우 방향지시등
브레이크 핀 15(PWM A) ─ 330 Ω ─ LED ─ GND   미등 20 % ↔ 100 %   (jetson-io PWM 활성화 필요)
버튼 L  3.3 V ─ 10 kΩ ─┬─ 핀 22 ─ 버튼 ─ GND
버튼 R  3.3 V ─ 10 kΩ ─┬─ 핀 16 ─ 버튼 ─ GND
```

## 실행 순서 (이 폴더에서)

```bash
python3 lamp_skeleton.py                       # ① TODO 를 채우기 전: 버튼 이벤트는 들어오지만 상태가 안 바뀜
#   TODO ① TRANS: (현재 상태, 이벤트) → 다음 상태.  상태 OFF·LEFT·RIGHT·HAZARD, 이벤트 L_SHORT·R_SHORT·L_LONG·R_LONG (슬라이드 170 전이도 그대로)
#   TODO ② on = ((now - t_blink) % PERIOD) < PERIOD / 2     ← sleep 횟수로 세지 말고 '시계' 로 계산
python3 lamp_skeleton.py                       # ② 완성 후: 방향지시등 · 전환 · 비상등 · 브레이크 모두 확인

# ③ 검증 — 점멸 주기를 측정한다 (한 상태, 예: 좌 점멸을 200 주기 ≈ 133 초 유지. 상태를 바꾸지 말 것)
python3 lamp.py --period-log                   #    방법 A: 프로그램이 본 시각 → log_period.txt (소프트웨어 측정)
python3 ../06_trigger/analyze.py log_period.txt --nominal-ms 666.7
#    방법 B (더 정확): 핀 7 → 핀 31 점퍼 추가 후, 다른 터미널에서 커널 타임스탬프로
../06_trigger/measure_period.sh -c 1 -l 0 -n 200 -o lamp.txt      # gpiochip1 라인 0 = 핀 31
python3 ../06_trigger/analyze.py lamp.txt --nominal-ms 666.7
# ④ 부하 조건: stress-ng -c $(nproc) --timeout 150s &  를 켠 뒤 ③ 반복 → 무부하 / 부하 표
```

`lamp.py` 가 핀 7(라인 106)을 점유하므로 `gpiomon gpiochip0 106` 은 `busy` → 방법 A 또는 B 로.

## 기록 항목 (보고서 A-9 → HW #2 B 로 이어짐)

- 동작 영상 10 초 (방향지시등 · 비상등 · 브레이크 모두 보이게)
- 주기 측정 표: 무부하 / 부하 (평균 · 표준편차 · 최대 편차) — 1.5 Hz ± 5 % (633~700 ms) 안인지
- 상태 전이도 그림 (손그림 가능) — 코드의 `TRANS` 와 일치
- HW #2 B: 브레이크등 PWM(B-1) · `bouncetime` 없이 **직접 디바운스**(B-2) · 200 주기 로그 무부하/부하(B-3) · 전이도(B-4) → `../../docs/HW2_과제안내.md`

## 흔한 버그 — 증상에서 원인으로

| 증상 | 원인 | 수정 |
|---|---|---|
| 버튼 반응이 밀리거나 놓침 | 콜백 안에서 `sleep` · `print` | 콜백은 `q.put` 한 줄 |
| 가끔 상태가 꼬임 | 콜백과 메인이 전역 변수를 동시에 수정(경쟁) | 큐로만 전달, 판정은 메인 |
| 시간이 갈수록 점멸이 느려짐 | `sleep(0.333)` 누적 드리프트 | `monotonic` 기준 계산식 (TODO ②) |
| 다음 실행에서 `busy` | `cleanup` 없이 종료 | `try/finally cleanup` |
| 빠른 두 번 누름을 못 셈 / 한 번이 두 번 | `bouncetime` 과대 / 레벨 확정 없음 | 35 ms 레벨 확정(`SETTLE`) + 적절한 창 |
| 동시 누름이 방향지시등으로 오인 | 두 버튼의 눌림 순서만 봄 | 둘 다 눌린 상태인지(레벨) 확인 후 브레이크 판정 |
| 브레이크등이 안 켜짐 / 오류 | 핀 15 PWM 미활성화 | `python3 ../pins.py` → jetson-io (실습 5 README) |
