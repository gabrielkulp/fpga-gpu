#!/usr/bin/env python3
from amaranth import *
from amaranth.build import *

from structures import Coords, Color

vga_resource = Resource(
	"dvi", 0,
	Subsignal("red",    Pins("8 2 7 1",  dir="o", conn=("pmod", 0))),
	Subsignal("green",  Pins("10 4 9 3", dir="o", conn=("pmod", 0))),
	Subsignal("blue",   Pins("3 8 7 1",  dir="o", conn=("pmod", 1))),
	Subsignal("v_sync", Pins("10",  dir="o", conn=("pmod", 1))),
	Subsignal("h_sync", Pins("4", dir="o", conn=("pmod", 1))),
	Subsignal("px_clk", Pins("2",  dir="o", conn=("pmod", 1))),
	Subsignal("enable", Pins("9",  dir="o", conn=("pmod", 1)))
)


# 40MHz clock for 60Hz display.
# also still outputs 12MHz for running main logic
class VGA_PLL(Elaboratable):
	def __init__(self):
		self.clk39_750 = Signal(attrs = {"keep": "true"})
		self.clk12 = Signal(attrs = {"keep": "true"})
	
	def elaborate(self, platform):
		m = Module()
		platform.lookup(platform.default_clk).attrs['GLOBAL'] = False
		m.submodules.pll = Instance(
			'SB_PLL40_2_PAD',
			i_PACKAGEPIN = platform.request('clk12').i,
			i_RESETB = Const(1),
			i_BYPASS = Const(0),

			o_PLLOUTGLOBALA = self.clk12,
			o_PLLOUTGLOBALB = self.clk39_750,

			p_FEEDBACK_PATH = 'SIMPLE',
			p_PLLOUT_SELECT_PORTB = 'GENCLK',

			p_DIVR = 0,
			p_DIVF = 52,
			p_DIVQ = 4,
			p_FILTER_RANGE = 1
		)

		# redefine sync domain to be driven by this 12MHz output and
		# add a new px domain. Both domains will be available everywhere
		platform.add_clock_constraint(self.clk12, 12e6)
		platform.add_clock_constraint(self.clk39_750, 39.750e6)
		m.domains += [
			ClockDomain('sync'),
			ClockDomain('px')
		]
		m.d.comb += [
			ClockSignal('sync').eq(self.clk12),
			ClockSignal('px').eq(self.clk39_750)
		]
		return m


class VGA_Timing(Elaboratable):
	def __init__(self, lengths, coord_delay):
		self.lengths = lengths
		self.coord_delay = coord_delay
		# coord_delay = 1 means that coordinates are supplied 1 clock cycle
		#   before the corresponding pixel is drawn

		# inputs
		self.increment = Signal()

		# outputs:
		self.coord = Signal(range(self.lengths["active"]))
		self.drawing = Signal()  # if coordinates are in drawing range
		self.sync = Signal(reset=1)
		self.valid_data = Signal()  # for "data enable" pin
		self.overflow = Signal()
	
	def elaborate(self, _platform):
		m = Module()

		width = range(max([self.lengths[i] for i in self.lengths]))
		counter = Signal(width, reset=self.lengths["sync"]-1)

		m.d.px += self.overflow.eq(0)
		already_overflowed = Signal()

		with m.If(self.increment):
			m.d.px += counter.eq(counter - 1)
			m.d.px += self.coord.eq(self.coord+1)

			with m.FSM(name="state", reset="SYNC", domain="px"):
				with m.State("SYNC"):
					with m.If(counter == 1):
						# one cycle early so chained state updates in sync
						m.d.px += self.overflow.eq(~already_overflowed)
						m.d.px += already_overflowed.eq(1)
					with m.Elif(counter == 0):
						m.d.px += already_overflowed.eq(0)
						m.d.px += self.sync.eq(0)
						m.d.px += counter.eq(self.lengths["bp"] - 1)
						m.next = "BACK_PORCH"

				with m.State("BACK_PORCH"):
					with m.If(counter == self.coord_delay):
						m.d.px += self.coord.eq(0)
						m.d.px += self.drawing.eq(1)
					with m.If(counter == 0):
						m.d.px += self.valid_data.eq(1)
						m.d.px += counter.eq(self.lengths["active"] - 1)
						m.next = "ACTIVE"

				with m.State("ACTIVE"):
					with m.If(counter == self.coord_delay):
						m.d.px += self.drawing.eq(0)
					with m.If(counter == 0):
						m.d.px += self.valid_data.eq(0)
						m.d.px += counter.eq(self.lengths["fp"] - 1)
						m.next = "FRONT_PORCH"

				with m.State("FRONT_PORCH"):
					with m.If(counter == 0):
						m.d.px += counter.eq(self.lengths["sync"] - 1)
						m.d.px += self.sync.eq(1)
						m.next = "SYNC"

		return m


# instantiates the PLL and sets up chip IO for you
class VGA(Elaboratable):
	def __init__(self, delay=0):
		# 800x600, 60Hz -> 40MHz px clock
		# sync width, back porch, active region, front porch
		self.delay = delay
		self.h_timing = {"sync": 128, "bp": 88, "active": 800, "fp": 40}
		self.v_timing = {"sync":   4, "bp": 23, "active": 600, "fp":  1}

		# inputs
		self.red   = Signal(4)
		self.green = Signal(4)
		self.blue  = Signal(4)
		self.rgb = Color(self.red, self.green, self.blue)

		# outputs
		self.in_bounds = Signal()
		self.valid_data = Signal()
		self.line  = Signal()
		self.frame = Signal()
		self.x = Signal(range(self.h_timing["active"]))
		self.y = Signal(range(self.v_timing["active"]))
		self.coords = Coords(self.x, self.y)

	def elaborate(self, platform):
		m = Module()

		m.submodules.clock = VGA_PLL()
		m.submodules.timing_h = VGA_Timing_h = VGA_Timing(self.h_timing, self.delay)
		m.submodules.timing_v = VGA_Timing_v = VGA_Timing(self.v_timing, 0)

		# connect submodules together
		m.d.comb += [
			VGA_Timing_h.increment.eq(1),
		]

		# connect this module's outputs
		m.d.comb += [
			VGA_Timing_v.increment.eq(VGA_Timing_h.overflow),
			self.line.eq(VGA_Timing_h.overflow),
			self.frame.eq(VGA_Timing_v.overflow),
			self.valid_data.eq(VGA_Timing_v.valid_data & VGA_Timing_h.valid_data),
			self.x.eq(VGA_Timing_h.coord),
			self.y.eq(VGA_Timing_v.coord),
			self.in_bounds.eq(VGA_Timing_h.drawing)
		]

		# xdr: 1 for buffered, 2 for DDR
		dvi_pins = platform.request("dvi", xdr = {
			"red": 1, "green": 1, "blue": 1,
			"v_sync": 1, "h_sync": 1, "enable": 1,
			"px_clk": 2
		})

		# connect to the physical pins
		m.d.comb += [
			dvi_pins.red.o.eq(self.red),
			dvi_pins.blue.o.eq(self.blue),
			dvi_pins.green.o.eq(self.green),
			dvi_pins.enable.o.eq(self.valid_data),
			dvi_pins.v_sync.o.eq(VGA_Timing_v.sync),
			dvi_pins.h_sync.o.eq(VGA_Timing_h.sync), 

			# buffered and DDR pins require a clock
			dvi_pins.red.o_clk.eq(ClockSignal("px")),
			dvi_pins.blue.o_clk.eq(ClockSignal("px")),
			dvi_pins.green.o_clk.eq(ClockSignal("px")),
			dvi_pins.enable.o_clk.eq(ClockSignal("px")),
			dvi_pins.v_sync.o_clk.eq(ClockSignal("px")),
			dvi_pins.h_sync.o_clk.eq(ClockSignal("px")),
			dvi_pins.px_clk.o_clk.eq(ClockSignal("px")),

			# set phase of DDR output
			dvi_pins.px_clk.o0.eq(0),
			dvi_pins.px_clk.o1.eq(1),
		]

		return m


class TopSim(Elaboratable):
	def __init__(self):
		# sync width, back porch, active, front porch
		self.h_timing = {"sync": 15, "bp": 10, "active": 20, "fp": 5}
		self.v_timing = {"sync":  2, "bp":  4, "active":  8, "fp": 1}

		self.x = Signal(range(self.h_timing["active"]))
		self.y = Signal(range(self.v_timing["active"]))
		self.h_sync = Signal()
		self.v_sync = Signal()
		self.data_enable = Signal()

	def elaborate(self, _plat):
		m = Module()
		vga_h = VGA_Timing(self.h_timing, 0)
		vga_v = VGA_Timing(self.v_timing, 0)
		m.submodules.horizontal = vga_h
		m.submodules.vertical = vga_v

		m.d.px += [
			vga_h.increment.eq(1),
		]

		m.d.comb += [
			vga_v.increment.eq(vga_h.overflow),
			self.x.eq(vga_h.coord),
			self.y.eq(vga_v.coord),
			self.h_sync.eq(vga_h.sync),
			self.v_sync.eq(vga_v.sync),
			self.data_enable.eq(vga_h.valid_data & vga_v.valid_data),
		]

		return m


from amaranth import sim
if __name__ == "__main__":
	top = TopSim()
	s = sim.Simulator(top)
	s.add_clock(1.0 / 40000000, domain="px")

	def out_proc():
		for _ in range(10000):
			yield
	
	s.add_sync_process(out_proc, domain="px")
	with s.write_vcd("vga.vcd", "vga.gtkw",
			traces=[top.x, top.y, top.h_sync, top.v_sync, top.data_enable]):
		s.run()
