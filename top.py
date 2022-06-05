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
		
		divider = Signal(range(16))
		with m.If(vga.frame & play):
			m.d.px += divider.eq(divider+1)
		sign_3 = Signal(shape=signed(2), reset=1)
		counter_z = Signal(range(-5,5))
		with m.If(vga.frame & play & (divider == 0)):
			m.d.px += counter_z.eq(counter_z+sign_3)
		with m.If(counter_z == 3):
			m.d.px += sign_3.eq(-1)
		with m.Elif(counter_z == -3):
			m.d.px += sign_3.eq(1)

		m.submodules.fb = fb = FrameBuffer()
		
		# colors are:  black  red    green  yellow blue   purple cyan   white
		colorscheme = [0x000, 0xb44, 0x9b6, 0xfc7, 0x7ab, 0xb7a, 0x7ba, 0xfff] # terminal
		#colorscheme = [0x000, 0x111, 0x222, 0x333, 0x555, 0x888, 0xbbb, 0xfff] # gamma
		#colorscheme = [0xfff, 0x000, 0x9b6, 0xfc7, 0x7ab, 0xb7a, 0x7ba, 0xfff] # inverse

		for i, color in enumerate(colorscheme):
			m.d.comb += fb.palette[i].eq(color)
		m.d.px += vga.color.rgb.eq(fb.color.rgb)

		m.d.comb += [
			fb.coords_r.x.eq(vga.coords.x>>2),
			fb.coords_r.y.eq(vga.coords.y>>2),
			fb.read_fill.eq((vga.coords.x[:2] == 3) & (vga.coords.y[:2] == 3)),
			fb.swap.eq(vga.frame),
		]

		m.submodules.line = line = LineSet(160,120, 8)
		m.d.comb += [
			line.segments[0][0].x.eq(20),
			line.segments[0][0].y.eq(20),
			line.segments[0][1].x.eq(80-40-5+counter_x+counter_z),
			line.segments[0][1].y.eq(60-30-5+counter_y+counter_z),

			line.segments[1][0].x.eq(140),
			line.segments[1][0].y.eq(20),
			line.segments[1][1].x.eq(80-40+5+counter_x+counter_z),
			line.segments[1][1].y.eq(60-30-5+counter_y-counter_z),

			line.segments[2][0].x.eq(20),
			line.segments[2][0].y.eq(100),
			line.segments[2][1].x.eq(80-40-5+counter_x-counter_z),
			line.segments[2][1].y.eq(60-30+5+counter_y+counter_z),

			line.segments[3][0].x.eq(140),
			line.segments[3][0].y.eq(100),
			line.segments[3][1].x.eq(80-40+5+counter_x-counter_z),
			line.segments[3][1].y.eq(60-30+5+counter_y-counter_z),
			# inner square
			line.segments[4][0].x.eq(80-40-5+counter_x+counter_z),
			line.segments[4][0].y.eq(60-30-5+counter_y+counter_z),
			line.segments[4][1].x.eq(80-40-5+counter_x-counter_z),
			line.segments[4][1].y.eq(60-30+5+counter_y+counter_z),

			line.segments[5][0].x.eq(80-40-5+counter_x-counter_z),
			line.segments[5][0].y.eq(60-30+5+counter_y+counter_z),
			line.segments[5][1].x.eq(80-40+5+counter_x-counter_z),
			line.segments[5][1].y.eq(60-30+5+counter_y-counter_z),

			line.segments[6][0].x.eq(80-40+5+counter_x-counter_z),
			line.segments[6][0].y.eq(60-30+5+counter_y-counter_z),
			line.segments[6][1].x.eq(80-40+5+counter_x+counter_z),
			line.segments[6][1].y.eq(60-30-5+counter_y-counter_z),

			line.segments[7][0].x.eq(80-40+5+counter_x+counter_z),
			line.segments[7][0].y.eq(60-30-5+counter_y-counter_z),
			line.segments[7][1].x.eq(80-40-5+counter_x+counter_z),
			line.segments[7][1].y.eq(60-30-5+counter_y+counter_z),

			fb.coords_w.xy.eq(line.coords.xy),
			fb.write.eq(line.write),
			fb.fill_data.eq(0), # background color
		]

		color_counter = Signal(range(7))
		with m.If(vga.frame & (divider==0) & play):
			with m.If(color_counter == 7):
				m.d.px += color_counter.eq(1)
			with m.Else():
				m.d.px += color_counter.eq(color_counter+1)
		m.d.comb += fb.w_data.eq(color_counter) # line color

		# do this one step after updating the counters
		m.d.px += line.start.eq(vga.frame)

		return m


def build_and_run():
	board = ICEBreakerPlatform()
	board.add_resources([vga_resource])
	board.build(Top(), do_program=True)

from amaranth.build import *
if __name__ == "__main__":
	build_and_run()