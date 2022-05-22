#!/usr/bin/env python3

from time import sleep

from amaranth import *
from amaranth_boards.icebreaker import ICEBreakerPlatform

from dvi import DVI, DVI_Timing, dvi_resource

class Top(Elaboratable):
	def __init__(self):
		self.what = Signal()
	def elaborate(self, platform):
		m = Module()

		dvi = DVI()
		m.submodules += [dvi]

		m.d.comb += dvi.red.eq(dvi.x)
		m.d.comb += dvi.green.eq(dvi.x)
		m.d.comb += dvi.blue.eq(dvi.y)
		#m.d.comb += dvi.px_clk.eq(ClockSignal())

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
	s.add_clock(1.0 / 1000000)

	def out_proc():
		for _ in range(500):
			yield
	
	s.add_sync_process(out_proc)
	with s.write_vcd("dvi.vcd", "dvi.gtkw", traces=dvi.signals):
		s.run()

import sys
if __name__ == "__main__":
	if "-s" in sys.argv:
		_sim()
	else:
		_flash()
