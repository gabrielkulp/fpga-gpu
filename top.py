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

		sign = Signal(shape=signed(2), reset=1)
		counter = Signal(range(32))
		with m.If(vga.frame == 1):
			m.d.px += counter.eq(counter+sign)
		with m.If(counter == 30):
			m.d.px += sign.eq(-1)
		with m.Elif(counter == 1):
			m.d.px += sign.eq(1)
		
		m.d.px += vga.red.eq(0) # just a nice dot grid
		m.d.px += vga.green.eq((vga.x[0]^vga.y[0])<<2)
		m.d.px += vga.blue.eq((vga.x[0]^vga.y[0])<<2)

		with m.If(vga.y == 598):
			m.d.px += vga.blue.eq(15)
		with m.If(vga.y == 597):
			m.d.px += vga.red.eq(15)

		with m.If(vga.y == 1):
			m.d.px += vga.blue.eq(15)
		with m.If(vga.y == 2):
			m.d.px += vga.red.eq(15)

		with m.If(vga.x == 798):
			m.d.px += vga.blue.eq(15)
		with m.If(vga.x == 797):
			m.d.px += vga.red.eq(15)

		with m.If(vga.x == 1):
			m.d.px += vga.blue.eq(15)
		with m.If(vga.x == 2):
			m.d.px += vga.red.eq(15)

		with m.If((vga.x == 0) | (vga.x == 799) | (vga.y == 0) | (vga.y == 599)):
			m.d.px += vga.green.eq(counter[-4:])

		return m


from amaranth.build import *
if __name__ == "__main__":
	board = ICEBreakerPlatform()
	board.add_resources([vga_resource])
	board.build(Top(), do_program=True)
