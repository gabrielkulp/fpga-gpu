#!/usr/bin/env python3
from amaranth import *
from amaranth_boards.icebreaker import ICEBreakerPlatform

from structures import Color, Coords
from vga import VGA, vga_resource
from framebuffer import FrameBuffer
from lines import LineSet

class Top(Elaboratable):
	def __init__(self):
		self.what = Signal()

	def elaborate(self, _platform):
		m = Module()

		m.submodules.vga = vga = VGA(delay=4)

		btn = _platform.request("button")
		last = Signal()
		step = Signal()
		play = Signal(reset=1)
		m.d.px += play.eq(play+step)
		m.d.px += step.eq(0)
		with m.If(vga.frame):
			m.d.px += last.eq(btn.i)
			with m.If(btn.i & ~last):
				m.d.px += step.eq(1)
		

		sign = Signal(shape=signed(2), reset=1)
		counter_y = Signal(range(60))
		with m.If(vga.frame & play):
			m.d.px += counter_y.eq(counter_y+sign)
		with m.If(counter_y == 59):
			m.d.px += sign.eq(-1)
		with m.Elif(counter_y == 0):
			m.d.px += sign.eq(1)

		sign_2 = Signal(shape=signed(2), reset=1)
		counter_x = Signal(range(80))
		with m.If(vga.frame & play):
			m.d.px += counter_x.eq(counter_x+sign_2)
		with m.If(counter_x == 79):
			m.d.px += sign_2.eq(-1)
		with m.Elif(counter_x == 0):
			m.d.px += sign_2.eq(1)

		m.submodules.fb = fb = FrameBuffer()
		
		# colors are:  black  red    green  yellow blue   purple cyan   white
		colorscheme = [0x000, 0xb44, 0x9b6, 0xfc7, 0x7ab, 0xb7a, 0x7ba, 0xfff] # terminal
		#colorscheme = [0x000, 0x111, 0x222, 0x333, 0x555, 0x888, 0xbbb, 0xfff] # gamma

		for i, color in enumerate(colorscheme):
			m.d.comb += fb.palette[i].eq(color)
		m.d.px += vga.color.rgb().eq(fb.color)

		m.d.comb += [
			fb.r_x.eq(vga.coords.x>>2),
			fb.r_y.eq(vga.coords.y>>2),
			fb.read_erase.eq((vga.coords.x[:2] == 3) & (vga.coords.y[:2] == 3)),
			fb.swap.eq(vga.frame),
		]

		m.submodules.line = line = LineSet(160,120, 8)
		m.d.comb += [
			line.segments[0][0].x.eq(20),
			line.segments[0][0].y.eq(20),
			line.segments[0][1].x.eq(80-40-5+counter_x),
			line.segments[0][1].y.eq(60-30-5+counter_y),

			line.segments[1][0].x.eq(140),
			line.segments[1][0].y.eq(20),
			line.segments[1][1].x.eq(80-40+5+counter_x),
			line.segments[1][1].y.eq(60-30-5+counter_y),

			line.segments[2][0].x.eq(20),
			line.segments[2][0].y.eq(100),
			line.segments[2][1].x.eq(80-40-5+counter_x),
			line.segments[2][1].y.eq(60-30+5+counter_y),

			line.segments[3][0].x.eq(140),
			line.segments[3][0].y.eq(100),
			line.segments[3][1].x.eq(80-40+5+counter_x),
			line.segments[3][1].y.eq(60-30+5+counter_y),
			# inner square
			line.segments[4][0].x.eq(80-40-5+counter_x),
			line.segments[4][0].y.eq(60-30-5+counter_y),
			line.segments[4][1].x.eq(80-40-5+counter_x),
			line.segments[4][1].y.eq(60-30+5+counter_y),

			line.segments[5][0].x.eq(80-40-5+counter_x),
			line.segments[5][0].y.eq(60-30+5+counter_y),
			line.segments[5][1].x.eq(80-40+5+counter_x),
			line.segments[5][1].y.eq(60-30+5+counter_y),

			line.segments[6][0].x.eq(80-40+5+counter_x),
			line.segments[6][0].y.eq(60-30+5+counter_y),
			line.segments[6][1].x.eq(80-40+5+counter_x),
			line.segments[6][1].y.eq(60-30-5+counter_y),

			line.segments[7][0].x.eq(80-40+5+counter_x),
			line.segments[7][0].y.eq(60-30-5+counter_y),
			line.segments[7][1].x.eq(80-40-5+counter_x),
			line.segments[7][1].y.eq(60-30-5+counter_y),

			fb.w_x.eq(line.coords.x),
			fb.w_y.eq(line.coords.y),
			fb.write.eq(line.write),
			fb.w_data.eq(4)
		]

		# do this one step after updating the counters
		m.d.px += line.start.eq(vga.frame)

		return m


from amaranth.build import *
if __name__ == "__main__":
	board = ICEBreakerPlatform()
	board.add_resources([vga_resource])
	board.build(Top(), do_program=True, nextpnr_opts="--timing-allow-fail")
