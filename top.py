#!/usr/bin/env python3
from amaranth import *
from amaranth_boards.icebreaker import ICEBreakerPlatform

from vga import VGA, VGA_Timing, vga_resource


class Top(Elaboratable):
	def __init__(self):
		self.what = Signal()
	def elaborate(self, _platform):
		m = Module()

		vga = VGA()
		m.submodules += vga

		m.d.comb += vga.red.eq(vga.x[:4])
		m.d.comb += vga.green.eq(vga.x[:4])
		m.d.comb += vga.blue.eq(vga.y[:4])

		# blink LED every second to verify clock speed is actually 40MHz
		led = _platform.request("led_r")
		counter = Signal(range(39750000))
		m.d.px += counter.eq(counter+1)
		with m.If(counter == 39750000-1):
			m.d.px += counter.eq(0)
			m.d.px += led.o.eq(~led.o)

		return m


from amaranth.build import *
if __name__ == "__main__":
	board = ICEBreakerPlatform()
	board.add_resources([vga_resource])
	board.build(Top(), do_program=True)
