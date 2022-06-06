#!/usr/bin/env python3
from amaranth import *
from amaranth_boards.icebreaker import ICEBreakerPlatform
from structures import Coords

from uart import UART
from vga import VGA, vga_resource
from framebuffer import FrameBuffer
from lines import LineSet

class Top(Elaboratable):
	def __init__(self):
		self.what = Signal()

	def elaborate(self, platform):
		m = Module()

		m.submodules.vga = vga = VGA(delay=2)

		btn = platform.request("button")
		last = Signal()
		step = Signal()
		play = Signal(reset=1)
		m.d.px += play.eq(play+step)
		m.d.px += step.eq(0)
		with m.If(vga.frame):
			m.d.px += last.eq(btn.i)
			with m.If(btn.i & ~last):
				m.d.px += step.eq(1)

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
			fb.read_fill.eq(vga.valid_data & (vga.coords.x[:2] == 3) & (vga.coords.y[:2] == 3)),
			fb.swap.eq(vga.frame)
		]

		m.submodules.uart = uart = UART(platform.request("uart"))
		#led = platform.request("led")
		#m.d.comb += led.o.eq(uart.rx_error)

		# auto-reply with data immediately
		empty = Signal(reset=1)
		m.d.comb += [
			uart.rx_ack.eq(1), # mark received to not enter error state;
			uart.tx_data.eq(~uart.rx_data),
			uart.tx_ready.eq(1)
		]

		m.submodules.line = line = LineSet(160,120)
		m.d.comb += [
			fb.coords_w.xy.eq(line.coords.xy),
			fb.write.eq(line.write),
			fb.fill_data.eq(4), # background color
			fb.w_data.eq(1), # line color
		]

		m.d.px += line.length.eq(1)
		index_write = Signal(16)

		plat_leds = [platform.request("led_g", n+1).o for n in range(4)]
		leds = Signal(4)
		m.d.comb += Cat(*plat_leds).eq(leds)

		endpoints = [Coords(160, 120), Coords(160, 120)]
		m.d.px += line.request_write.eq(0)
		with m.FSM(reset="IDLE", domain="px"):
			with m.State("IDLE"):
				m.d.px += leds.eq(0)
				with m.If(uart.rx_ready):
					m.d.px += endpoints[0].x.eq(uart.rx_data)
					m.next = "Y0"
			with m.State("Y0"):
				m.d.px += leds.eq(1)
				with m.If(uart.rx_ready):
					m.d.px += endpoints[0].y.eq(uart.rx_data)
					m.next = "X1"
			with m.State("X1"):
				m.d.px += leds.eq(2)
				with m.If(uart.rx_ready):
					m.d.px += endpoints[1].x.eq(uart.rx_data)
					m.next = "Y1"
			with m.State("Y1"):
				m.d.px += leds.eq(3)
				with m.If(uart.rx_ready):
					m.d.px += line.endpoints_in[0].xy.eq(endpoints[0].xy)
					m.d.px += line.endpoints_in[1].x.eq(endpoints[1].x)
					m.d.px += line.endpoints_in[1].y.eq(uart.rx_data)
					m.d.px += endpoints[1].y.eq(uart.rx_data)
					m.d.px += line.index_write.eq(index_write)
					m.d.px += line.request_write.eq(1)
					m.next = "IDLE"
		#m.d.comb += line.endpoints_in[0].x.eq(20)
		#m.d.comb += line.endpoints_in[0].y.eq(30)
		#m.d.comb += line.endpoints_in[1].x.eq(110)
		#m.d.comb += line.endpoints_in[1].y.eq(90)
		#with m.If(uart.rx_ready):
		#	m.d.px += line.index_write.eq(0)
		#	m.d.px += line.request_write.eq(1)

		# do this one step after updating the counters
		m.d.px += line.start.eq(vga.frame)

		return m


def build_and_run():
	board = ICEBreakerPlatform()
	board.add_resources([vga_resource])
	board.add_resources(board.break_off_pmod)
	from subprocess import CalledProcessError
	try:
		board.build(Top(), do_program=True)
	except CalledProcessError:
		print("Can't find iCE FTDI USB device")

from amaranth.build import *
if __name__ == "__main__":
	build_and_run()