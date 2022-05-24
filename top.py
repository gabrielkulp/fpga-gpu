#!/usr/bin/env python3
from amaranth import *
from amaranth_boards.icebreaker import ICEBreakerPlatform

from vga import VGA, vga_resource


class Top(Elaboratable):
	def __init__(self):
		self.what = Signal()
	def elaborate(self, _platform):
		m = Module()

		vga = VGA()
		m.submodules += vga

		counter = Signal(32)
		with m.If(vga.frame == 1):
			m.d.px += counter.eq(counter+1)

		m.d.comb += vga.red.eq(vga.x[:4]-counter)
		m.d.comb += vga.green.eq(vga.x[2:6])
		m.d.comb += vga.blue.eq(vga.y[:4]-counter)

		return m


from amaranth.build import *
if __name__ == "__main__":
	board = ICEBreakerPlatform()
	board.add_resources([vga_resource])
	board.build(Top(), do_program=True)
