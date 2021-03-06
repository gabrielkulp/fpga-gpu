#!/usr/bin/env python3
# https://github.com/icebreaker-fpga/icebreaker-amaranth-examples/blob/master/icebreaker/uart/uart.py
from ctypes import ArgumentError
from amaranth import *
from amaranth.build import *

baud = 115200
ping_res = 0x42
ack = 0xbd

commands = {
	"ping": 0,
	"write": 1,
	"set_bounds": 2,
	"vsync": 3
}

def _divisor(freq_in, freq_out, max_ppm=None):
	divisor = freq_in // freq_out
	if divisor <= 0:
		raise ArgumentError("Output frequency is too high.")

	ppm = 100000 * ((freq_in / divisor) - freq_out) / freq_out
	if max_ppm is not None and ppm > max_ppm:
		raise ArgumentError("Output frequency deviation is too high.")

	return divisor


class UART(Elaboratable):
	def __init__(self, serial, clk_freq=25125000, baud_rate=baud):
		self.rx_data = Signal(8)
		self.rx_ready = Signal()
		self.rx_ack = Signal()
		self.rx_error = Signal()
		self.rx_strobe = Signal()
		self.rx_bitno = None
		self.rx_fsm = None

		self.tx_data = Signal(8)
		self.tx_ready = Signal()
		self.tx_ack = Signal()
		self.tx_strobe = Signal()
		self.tx_bitno = None
		self.tx_latch = None
		self.tx_fsm = None

		self.serial = serial

		self.divisor = _divisor(
			freq_in=clk_freq, freq_out=baud_rate, max_ppm=50000)

	def elaborate(self, _platform: Platform) -> Module:
		m = Module()

		# RX

		rx_counter = Signal(range(self.divisor))
		m.d.comb += self.rx_strobe.eq(rx_counter == 0)
		with m.If(rx_counter == 0):
			m.d.px += rx_counter.eq(self.divisor - 1)
		with m.Else():
			m.d.px += rx_counter.eq(rx_counter - 1)

		self.rx_bitno = rx_bitno = Signal(3)
		with m.FSM(reset="IDLE", domain="px") as self.rx_fsm:
			with m.State("IDLE"):
				with m.If(~self.serial.rx):
					m.d.px += rx_counter.eq(self.divisor // 2)
					m.next = "START"

			with m.State("START"):
				with m.If(self.rx_strobe):
					m.next = "DATA"

			with m.State("DATA"):
				with m.If(self.rx_strobe):
					m.d.px += [
						self.rx_data.eq(
							Cat(self.rx_data[1:8], self.serial.rx)),
						rx_bitno.eq(rx_bitno + 1)
					]
					with m.If(rx_bitno == 7):
						m.next = "STOP"

			with m.State("STOP"):
				with m.If(self.rx_strobe):
					with m.If(~self.serial.rx):
						m.next = "ERROR"
					with m.Else():
						m.next = "FULL"

			with m.State("FULL"):
				m.d.comb += self.rx_ready.eq(1)
				with m.If(self.rx_ack):
					m.next = "IDLE"
				with m.Elif(~self.serial.rx):
					m.next = "ERROR"

			with m.State("ERROR"):
				m.d.comb += self.rx_error.eq(1)

		# TX

		tx_counter = Signal(range(self.divisor))
		m.d.comb += self.tx_strobe.eq(tx_counter == 0)
		with m.If(tx_counter == 0):
			m.d.px += tx_counter.eq(self.divisor - 1)
		with m.Else():
			m.d.px += tx_counter.eq(tx_counter - 1)

		self.tx_bitno = tx_bitno = Signal(3)
		self.tx_latch = tx_latch = Signal(8)
		with m.FSM(reset="IDLE", domain="px") as self.tx_fsm:
			with m.State("IDLE"):
				m.d.comb += self.tx_ack.eq(1)
				with m.If(self.tx_ready):
					m.d.px += [
						tx_counter.eq(self.divisor - 1),
						tx_latch.eq(self.tx_data)
					]
					m.next = "START"
				with m.Else():
					m.d.px += self.serial.tx.eq(1)

			with m.State("START"):
				with m.If(self.tx_strobe):
					m.d.px += self.serial.tx.eq(0)
					m.next = "DATA"

			with m.State("DATA"):
				with m.If(self.tx_strobe):
					m.d.px += [
						self.serial.tx.eq(tx_latch[0]),
						tx_latch.eq(Cat(tx_latch[1:8], 0)),
						tx_bitno.eq(tx_bitno + 1)
					]
					with m.If(self.tx_bitno == 7):
						m.next = "STOP"

			with m.State("STOP"):
				with m.If(self.tx_strobe):
					m.d.px += self.serial.tx.eq(1)
					m.next = "IDLE"

		return m