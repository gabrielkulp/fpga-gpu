#!/usr/bin/env python3
from amaranth import *
from amaranth_boards.icebreaker import ICEBreakerPlatform

from dvi import DVI, DVI_Timing, dvi_resource


class Top(Elaboratable):
	def __init__(self):
		self.what = Signal()
	def elaborate(self, _platform):
		m = Module()

		dvi = DVI()
		m.submodules += dvi

		m.d.comb += dvi.red.eq(dvi.x[:4])
		m.d.comb += dvi.green.eq(dvi.x[:4])
		m.d.comb += dvi.blue.eq(dvi.y[:4])

		# blink LED every second to verify clock speed is actually 40MHz
		led = _platform.request("led_r")
		counter = Signal(range(39750000))
		m.d.px += counter.eq(counter+1)
		with m.If(counter == 39750000-1):
			m.d.px += counter.eq(0)
			m.d.px += led.o.eq(~led.o)

		return m


from amaranth.build import *
def _flash():
	board = ICEBreakerPlatform()
	board.add_resources([dvi_resource])
	board.build(Top(), do_program=True)

from amaranth import sim
def _sim():
	dvi = DVI_Timing()
	s = sim.Simulator(dvi)
	s.add_clock(1.0 / 40000000, domain="px")

	def out_proc():
		# two frames
		for _ in range(10000):
			yield
	
	s.add_sync_process(out_proc, domain="px")
	with s.write_vcd("dvi.vcd", "dvi.gtkw", traces=[dvi.x, dvi.y, dvi.h_sync, dvi.v_sync]):
		s.run()

import sys
if __name__ == "__main__":
	if "-s" in sys.argv:
		_sim()
	else:
		_flash()
