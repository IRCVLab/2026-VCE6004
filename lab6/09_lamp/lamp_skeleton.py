#!/usr/bin/env python3
# ===== 실습 9 — 차량 램프 컨트롤러 뼈대 (lamp_skeleton.py) =====
# ★ 학생용 뼈대: TODO ① 상태 전이표, TODO ② 점멸 타이밍 을 채우면 lamp.py 와 같은 동작.
#   (임포트·핀 설정·큐·짧게/길게 판정·정리 코드는 완성돼 있음. 아래 헤더는 lamp.py 와 동일)
# 목적: 이벤트 큐 + 상태기계 + 시간 기반 점멸로 방향지시등·비상등·브레이크등을 제어한다.
# 배선: LED L=핀 7 · LED R=핀 12 · 브레이크등=핀 15(PWM) (각각 330 Ω → LED → GND)
#       버튼 L=핀 22 · 버튼 R=핀 16 (각각 3.3 V ─ 10 kΩ ─ 핀 ─ 버튼 ─ GND, 누르면 LOW)
# 실행: python3 lamp.py                  (Ctrl-C 로 종료)
#       python3 lamp.py --period-log     LED L 점멸 시각을 log_period.txt 에 기록 → python3 ../06_trigger/analyze.py log_period.txt --nominal-ms 666.7
#                                        (한 상태, 예: 좌 점멸을 200 주기 ≈ 133 초 유지한 구간만 분석 의미 있음)
# 동작: 짧게(<1 s) L → 좌 점멸 켜기/끄기 · R → 우 점멸 (서로 배타) · 길게(≥1 s) → 비상등 켜기/끄기
#       두 버튼을 함께 누르는 동안 브레이크등 100 % (평소 미등 20 %)
# 구조: 콜백(다른 스레드) → 큐 → 메인 루프 10 ms 마다 ①큐 처리 ②상태 갱신 ③점멸 계산 ④출력.  블로킹(sleep) 없음
import argparse
import queue
import time

import Jetson.GPIO as GPIO
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import LED_L, LED_R, PWM_A, PWM_ADDR, BTN_L, BTN_R, hint, all_off, pwmchip_for

PERIOD = 1 / 1.5        # 점멸 1.5 Hz = 분당 90 회 (UN R48: 90±30), 켜짐 50 % → 주기 0.667 s
LONG_S = 1.0            # 이 시간 이상 누르면 LONG (비상등)
SETTLE = 0.035          # 에지 후 35 ms 지나 접점이 안정된 뒤에 핀을 읽는다 (> bouncetime 30 ms)
LOOP_S = 0.010          # 메인 루프 주기 10 ms

# 상태 전이표 {(현재 상태, 이벤트): 다음 상태}.  표에 없는 조합은 상태 유지 (예: 비상등 중 짧게 누름 = 무시)
# 상태: OFF · LEFT · RIGHT · HAZARD     이벤트: L_SHORT · R_SHORT · L_LONG · R_LONG
TRANS = {
    # TODO ①: 상태 전이표를 완성하세요.  키 = (현재 상태, 이벤트),  값 = 다음 상태
    #   · L_SHORT / R_SHORT : 해당 방향 점멸 켜기 · 같은 버튼이면 끄기 · 반대쪽이 켜져 있으면 그쪽으로 전환 (서로 배타)
    #   · L_LONG / R_LONG   : 비상등 켜기 · 비상등 중이면 끄기
    #   · 비상등 중 짧게 누름은 무시 (표에 없으면 상태 유지)
    ('OFF', 'L_SHORT'): 'LEFT',       # ← 예시 한 줄. 나머지를 채우세요 (총 14 줄 정도)
}
BLINK = {'OFF': (0, 0), 'LEFT': (1, 0), 'RIGHT': (0, 1), 'HAZARD': (1, 1)}   # 상태별 (LED L, LED R) 점멸 여부

q = queue.Queue()


def on_edge(pin):
    """콜백: 어느 핀에서 언제 에지가 났는지 큐에 넣고 바로 끝낸다. (sleep·print·판정 금지)"""
    q.put((pin, time.monotonic()))


def main(period_log):
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup([LED_L, LED_R], GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup([BTN_L, BTN_R], GPIO.IN)
    brake = None
    if pwmchip_for(PWM_ADDR[PWM_A]):                      # 하드웨어 PWM 이 켜져 있을 때만 브레이크등 사용
        brake = GPIO.PWM(PWM_A, 200)
        brake.start(20)                                   # 미등 20 %
    else:
        print("[알림] 핀 15 PWM 이 없어 브레이크등 없이 실행 (jetson-io 설정 확인)")
    for b in (BTN_L, BTN_R):                              # 눌림·뗌 모두 감지, 30 ms 안의 바운스는 라이브러리가 버림
        GPIO.add_event_detect(b, GPIO.BOTH, callback=on_edge, bouncetime=30)
    log = open("log_period.txt", "w") if period_log else None
    state, t_blink = 'OFF', time.monotonic()              # t_blink: 점멸 주기의 기준 시각
    down, pending, combo = {}, {}, set()                  # 눌린 버튼 {핀: 누른 시각} · 판정 대기 {핀: 에지 시각} · 동시 누름에 쓰인 버튼
    out, duty = (0, 0), 20
    nxt = time.monotonic()
    print("램프 컨트롤러 시작: 버튼 L/R 짧게 = 방향지시등, 길게 = 비상등, 둘 다 = 브레이크 (Ctrl-C 종료)")
    try:
        while True:
            now = time.monotonic()
            # ① 큐 처리: 에지가 난 핀을 '판정 대기'에 넣고, 35 ms 지나 안정된 핀의 레벨을 읽어 눌림/뗌을 정한다
            while not q.empty():
                pin, t = q.get()
                pending[pin] = t                              # 같은 핀에서 에지가 또 오면 시각을 갱신 (마지막 에지 기준)
            for pin in [p for p, t in pending.items() if now - t >= SETTLE]:
                t_edge = pending.pop(pin)
                pressed = GPIO.input(pin) == GPIO.LOW         # 눌림 = LOW (풀업)  (장비에서 확인: 이벤트 등록 뒤 input)
                if pressed and pin not in down:
                    down[pin] = t_edge
                    if len(down) == 2:
                        combo.update(down)                    # 두 버튼 동시 = 브레이크. 이 누름들은 방향지시등 판정에서 제외
                elif not pressed and pin in down:
                    held = t_edge - down.pop(pin)             # 누른 시간
                    if pin in combo:
                        combo.discard(pin)
                        continue
                    # ② 짧게/길게 판정 → 이벤트 → 전이표로 다음 상태
                    event = ('L' if pin == BTN_L else 'R') + ('_LONG' if held >= LONG_S else '_SHORT')
                    new = TRANS.get((state, event), state)
                    print(f"{event:8s} {state} → {new}")
                    if state == 'OFF' and new != 'OFF':
                        t_blink = now                         # 점멸을 켬 구간부터 시작
                    state = new
            # ③ 점멸: sleep 횟수가 아니라 시계로 계산 → 오차가 쌓이지 않음 (켜짐 = 주기의 앞 절반)
            on = False        # TODO ②: 1.5 Hz · 켜짐 50 % 점멸을 '시계'로 계산 (힌트: (now - t_blink) % PERIOD 와 PERIOD / 2 비교. sleep 횟수로 세지 말 것)
            want = tuple(int(on and f) for f in BLINK[state])
            # ④ 출력: 바뀔 때만 쓴다
            if want != out:
                GPIO.output([LED_L, LED_R], want)
                if log and want[0] != out[0]:                 # gpiomon 과 같은 형식으로 기록 → analyze.py 가 그대로 읽음
                    log.write(f"event: {'RISING' if want[0] else 'FALLING'} EDGE offset: 106 timestamp: [{time.monotonic():.9f}]\n")
                out = want
            want_duty = 100 if len(down) == 2 else 20         # 두 버튼을 누르는 동안 브레이크등 100 %
            if brake and want_duty != duty:
                brake.ChangeDutyCycle(want_duty)
                duty = want_duty
            nxt += LOOP_S                                     # 다음 깨어날 시각 = 절대 시각 (루프 주기 유지)
            time.sleep(max(0.0, nxt - time.monotonic()))
    finally:                                              # 어떻게 끝나든 PWM·로그 파일 정리
        if brake:
            brake.stop()
        if log:
            log.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--period-log", action="store_true", help="LED L 점멸 시각을 log_period.txt 에 기록")
    args = ap.parse_args()
    try:
        main(args.period_log)
    except KeyboardInterrupt:
        print("\n종료")
    except Exception as e:
        hint(e)
    finally:
        all_off(GPIO, LED_L, LED_R)
        GPIO.cleanup()
