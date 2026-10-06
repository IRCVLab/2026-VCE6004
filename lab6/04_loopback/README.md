# 실습 4 — 루프백 지연 측정: 평균이 아니라 꼬리 (○ 시간 되면 · 과제 필수)

슬라이드 102~104 · HW #2 A-4 · 소요 15분 (측정 3 회 × 25 초 + 그래프)

**목적**: 출력 명령을 내린 시각(t0)부터 그 변화가 입력 핀 인터럽트 → 커널 → Python 콜백으로 돌아온 시각(t1)까지를 1000 번 재서, 평균 대신 **p99 · 최대** 를 본다. 무부하 / CPU 부하 / 실시간 우선순위(SCHED_FIFO) 세 조건을 비교 — "리눅스 사용자 공간은 어디까지 믿을 수 있나".

| 파일 | 역할 |
|---|---|
| `loopback.py` | 핀 7 을 올리고 핀 22 콜백까지의 지연(µs) 1000 회 → `loopback_<tag>.csv` + 요약(평균 · p50 · p99 · 최대) |
| `latency_plot.py` | CSV 여러 개 → 요약표 + 로그 x축 히스토그램 PNG. Jetson 이 아니어도 실행됨(노트북에서 그려도 됨) |

## 배선

```
핀 7(LED_L) ─ 1 kΩ ─ 핀 22(BTN_L)      점퍼 하나 추가 (LED · 버튼 · 풀업 배선은 그대로 둬도 됨)
```

- 1 kΩ 은 두 핀이 동시에 출력으로 잡히는 실수에 대비한 보호 저항
- 측정 중 버튼을 누르지 않기 (핀 22 를 GND 로 떨어뜨려 '놓침' 이 늘어남)

## 실행 순서 (이 폴더에서)

```bash
python3 loopback.py --tag base                        # ① 무부하 (약 25 초)
stress-ng -c $(nproc) --timeout 120s &                # ② 전 코어 부하 (120 초 뒤 자동 종료)
python3 loopback.py --tag stress                      #    부하 속에서
sudo chrt -f 80 python3 loopback.py --tag fifo        # ③ 같은 부하 속에서 실시간 우선순위 SCHED_FIFO 80
sudo chown $USER *.csv                                #    (sudo 로 만든 CSV 소유자 정리)
python3 latency_plot.py loopback_base.csv loopback_stress.csv loopback_fifo.csv   # → latency_hist.png
```

더 해보기: `taskset -c 11 python3 loopback.py --tag core11` (코어 고정) · `sudo nvpmodel -m 0 && sudo jetson_clocks` (주파수 고정) → 꼬리가 어떻게 변하나

## 기록 항목 (보고서)

- `latency_plot.py` 가 만든 히스토그램 PNG (base · stress · fifo, 로그 x축)
- 조건별 평균 / p50 / p99 / 최대 표 (µs) — 스크립트 출력 그대로
- 부하(stress-ng) 시 꼬리(최대)가 몇 배 길어졌는지
- SCHED_FIFO 가 평균 · 최대 중 어느 쪽을 더 줄였는지
- "왜 평균이 아니라 최대값을 보는가" 2 문장 (차량 예 포함 — 에어백 · 브레이크 신호에서 평균은 의미가 없는 이유)
- (선택) 보호 저항 없이 직결하면 결과가 달라지는가 — 이유

## 막히면

| 증상 | 확인 |
|---|---|
| '놓침' 카운트 증가 | 점퍼 빠짐 · 버튼이 눌린 상태 · 다른 프로그램이 핀 22 사용 중 |
| `chrt: failed to set pid ... Operation not permitted` | `sudo` 필요 (실시간 우선순위는 root) |
| CSV 를 열 수 없음 (Permission) | `sudo` 로 만든 파일 → `sudo chown $USER *.csv` |
| `latency_plot.py` 가 표만 출력 | matplotlib 없음 → `pip3 install matplotlib` 또는 CSV 를 노트북으로 복사해 실행 |
