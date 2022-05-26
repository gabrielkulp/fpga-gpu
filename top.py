#!/usr/bin/env python3
from amaranth import *
from amaranth_boards.icebreaker import ICEBreakerPlatform

from structures import Color, Coords
from vga import VGA, vga_resource
from lines import LineCalculator

class Top(Elaboratable):
	def __init__(self):
		self.what = Signal()
	def elaborate(self, _platform):
		m = Module()

		m.submodules.vga = vga = VGA(delay=3)

		sign = Signal(shape=signed(2), reset=1)
		counter = Signal(range(128))
		with m.If(vga.frame):# & (pre==0)
			m.d.px += counter.eq(counter+sign)
		with m.If(counter == 127):
			m.d.px += sign.eq(-1)
		with m.Elif(counter == 0):
			m.d.px += sign.eq(1)

		sign_2 = Signal(shape=signed(2), reset=1)
		counter_2 = Signal(range(128))
		pre = Signal(2)
		m.d.px += pre.eq(pre+vga.frame)
		with m.If(vga.frame & (pre==0)):
			m.d.px += counter_2.eq(counter_2+sign_2)
		with m.If(counter_2 == 100):
			m.d.px += sign_2.eq(-1)
		with m.Elif(counter_2 == 0):
			m.d.px += sign_2.eq(1)
		
		red_next = Signal(4)
		red_nn = Signal(4)
		green_next = Signal(4)
		green_nn = Signal(4)
		blue_next = Signal(4)
		blue_nn = Signal(4)
		m.d.px += [
			vga.red.eq(red_nn),
			red_nn.eq(red_next),
			vga.blue.eq(blue_nn),
			blue_nn.eq(blue_next),
			vga.green.eq(green_nn),
			green_nn.eq(green_next),
		]

		m.d.px += red_next.eq(0) # just a nice dot grid
		m.d.px += green_next.eq((vga.x[0]^vga.y[0])<<2)
		m.d.px += blue_next.eq((vga.x[0]^vga.y[0])<<2)
#
		with m.If(vga.y == 598):
			m.d.px += blue_next.eq(15)
		with m.If(vga.y == 599):
			m.d.px += red_next.eq(15)
#
		with m.If(vga.y == 1):
			m.d.px += blue_next.eq(15)
		with m.If(vga.y == 0):
			m.d.px += red_next.eq(15)
#
		with m.If(vga.x == 798):
			m.d.px += blue_next.eq(15)
		with m.If(vga.x == 799):
			m.d.px += red_next.eq(15)
#
		with m.If(vga.x == 1):
			m.d.px += blue_next.eq(15)
		with m.If(vga.x == 0):
			m.d.px += red_next.eq(15)
#
		#with m.If((vga.x == 0) | (vga.x == 799) | (vga.y == 0) | (vga.y == 599)):
		#	m.d.px += vga.green.eq(counter[-4:])

		m.submodules.line_a = line_a = LineCalculator(800, 600)
		m.d.px += [
			line_a.coords.x.eq(vga.x),
			line_a.coords.y.eq(vga.y),
			line_a.endpoints[1].x.eq(400),
			line_a.endpoints[1].y.eq(300),
			line_a.endpoints[0].x.eq(400-64+counter),
			line_a.endpoints[0].y.eq(300-50+counter_2),
			line_a.row_strobe.eq(vga.line),
			line_a.update.eq(vga.frame),
			line_a.enable.eq(vga.in_bounds)
		]

		with m.If(line_a.is_on_line):
			m.d.px += Cat(vga.red, vga.green, vga.blue).eq(0xfff)
		#with m.Else():
		#	m.d.px += Cat(vga.red, vga.blue, vga.green).eq(0x111)

		#size = 4
		#for (x,y) in zip(
		#	[0,1,2,1,1,1,0,1,2 , 5,4,5,6,5,5,5,6,7 , 9,10,8,9,10,11,9,10 , 15,15,15,15,16,17,17,16 , 20,21,19,22,19,20,21,22,19,20,21 , 26,26,26,26,25,24,24,25 , 29,28,29,30,29,29,29,30 , 32,32,32,32,33 , 35,36,38,35,35,37,37,39,39 , 42,43,41,44,41,42,43,44,41,42,43],
		#	[1,1,1,2,3,4,5,5,5 , 1,2,2,2,3,4,5,5,0 , 1,1,2,3,3,4,5,5     , 1,2,3,4,3,4,5,5         , 1,1,2,2,3,3,3,3,4,5,5            , 1,2,3,4,3,4,5,5         , 1,2,2,2,3,4,5,5         , 1,3,4,5,5      , 3,3,3,4,5,4,5,4,5          , 1,1,2,2,3,3,3,3,4,5,5]
		#):
		#	with m.If((vga.x>>size == x+1) & (vga.y>>size == y+1)):
		#		m.d.px += vga.red.eq(15)

		return m


from amaranth.build import *
if __name__ == "__main__":
	board = ICEBreakerPlatform()
	board.add_resources([vga_resource])
	board.build(Top(), do_program=True, nextpnr_opts="--timing-allow-fail")
