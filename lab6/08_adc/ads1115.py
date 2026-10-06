#!/usr/bin/env python3
# ===== 실습 8 — ADS1115 최소 드라이버 (ads1115.py) =====
# 목적: I2C 레지스터 두 개(설정 0x01 · 변환 0x00)만으로 16 비트 ADC 값을 읽는다. (steer.py · pwm_dac.py 가 import)
# 배선: ADS1115 VDD → 3.3 V(핀 1) · GND → 핀 6 · SCL → 핀 5 · SDA → 핀 3 · ADDR → GND (주소 0x48)
#       A0 ← 가변저항 가운데 단자 (양끝: 3.3 V 와 GND)
#       ※ VDD 가 3.3 V 이므로 입력은 0 ~ 3.3 V 를 넘기면 안 됨
# 실행: python3 ads1115.py                  A0~A3 전압을 1 초마다 출력 (자체 시험)
#       python3 ads1115.py --bus 7 --ch 0   버스 번호 지정 (i2cdetect -l 로 확인), 채널 하나만
# 바이트 순서: ADS1115 레지스터는 상위 바이트(MSB)가 먼저 온다 (big-endian).
#       smbus 의 read_word_data() 는 하위 바이트 먼저라 값이 뒤집힘 → 여기서는 바이트 2 개를 직접 읽어 합친다.
import argparse
import time

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 공통 pins.py 는 한 단계 위 폴더(lab6/)에 있음
from pins import ADS1115_ADDR, hint, i2c_bus_guess

try:
    from smbus2 import SMBus
except ImportError:
    SMBus = None

REG_CONV = 0x00       # 변환 결과 레지스터 (읽기)
REG_CONFIG = 0x01     # 설정 레지스터 (읽기/쓰기)
PGA_BITS = {6.144: 0b000, 4.096: 0b001, 2.048: 0b010, 1.024: 0b011, 0.512: 0b100, 0.256: 0b101}


class ADS1115:
    def __init__(self, bus=None, addr=ADS1115_ADDR):
        if SMBus is None:
            raise RuntimeError("smbus2 가 없음 → bash setup_lab6.sh 또는 pip3 install smbus2")
        self.addr = addr
        self.busno = i2c_bus_guess(addr) if bus is None else bus
        try:
            self.bus = SMBus(self.busno)
        except FileNotFoundError:
            raise RuntimeError(f"No such file: /dev/i2c-{self.busno} — i2cdetect -l 로 버스 번호 확인 후 --bus 로 지정")
        try:
            self.bus.read_byte(addr)                 # 장치가 응답하는지 확인
        except OSError:
            self.bus.close()
            raise RuntimeError(f"Remote I/O error: 버스 {self.busno} 에서 0x{addr:02X} 응답 없음 "
                               "(배선 SDA/SCL·전원·ADDR 확인, i2cdetect -y N)")

    def read_single(self, channel, pga=4.096):
        """단일 종단 입력 AINx(0~3) 를 한 번 변환해 전압(V)으로 돌려준다."""
        if channel not in (0, 1, 2, 3) or pga not in PGA_BITS:
            raise ValueError("channel 은 0~3, pga 는 6.144/4.096/2.048/1.024/0.512/0.256 중 하나")
        config = (1 << 15) \
            | ((0b100 + channel) << 12) \
            | (PGA_BITS[pga] << 9) \
            | (1 << 8) \
            | (0b100 << 5) \
            | 0b00011
        # 비트: [15] OS=1 변환 시작 · [14:12] MUX=100+ch (AINx 대 GND) · [11:9] PGA(±4.096 V=001)
        #       [8] MODE=1 단발 · [7:5] DR=100 (128 SPS) · [4:2]=000 비교기 기본값 · [1:0]=11 비교기 끔
        self.bus.write_i2c_block_data(self.addr, REG_CONFIG, [config >> 8, config & 0xFF])   # MSB 먼저
        deadline = time.monotonic() + 0.1
        while True:                                   # 변환이 끝나면 OS 비트(최상위)가 1 로 돌아옴
            msb, _ = self.bus.read_i2c_block_data(self.addr, REG_CONFIG, 2)
            if msb & 0x80:
                break
            if time.monotonic() > deadline:
                raise RuntimeError("ADS1115 변환 시간 초과 — 배선·전원 확인")
            time.sleep(0.001)
        msb, lsb = self.bus.read_i2c_block_data(self.addr, REG_CONV, 2)   # 변환 결과 (MSB 먼저)
        raw = (msb << 8) | lsb
        if raw >= 0x8000:                             # 부호 있는 16 비트 (음수 처리)
            raw -= 0x10000
        return raw * pga / 32768.0                    # 1 LSB = pga/32768 (±pga 범위가 −32768~32767)

    def close(self):
        self.bus.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bus", type=int, default=None, help="I2C 버스 번호 (기본: 7 → 1 순서로 찾음)")
    ap.add_argument("--ch", type=int, default=None, help="채널 하나만 (기본 전부)")
    args = ap.parse_args()
    try:
        adc = ADS1115(args.bus)
        print(f"ADS1115 연결됨: 버스 {adc.busno}, 주소 0x{adc.addr:02X}  (Ctrl-C 종료)")
        while True:
            chans = [args.ch] if args.ch is not None else [0, 1, 2, 3]
            print("  ".join(f"A{c} = {adc.read_single(c):6.3f} V" for c in chans))
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n종료")
    except Exception as e:
        hint(e)
