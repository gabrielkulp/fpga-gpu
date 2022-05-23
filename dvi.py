from amaranth import *
from amaranth.build import *

dvi_resource = Resource(
	"dvi", 0,
	Subsignal("red",    Pins("2 8 1 7",  dir="o", conn=("pmod", 0))),
	Subsignal("green",  Pins("4 10 3 9", dir="o", conn=("pmod", 0))),
	Subsignal("blue",   Pins("9 2 1 7",  dir="o", conn=("pmod", 1))),
	Subsignal("v_sync", Pins("4",  dir="o", conn=("pmod", 1))),
	Subsignal("h_sync", Pins("10", dir="o", conn=("pmod", 1))),
	Subsignal("px_clk", Pins("8",  dir="o", conn=("pmod", 1))),
	Subsignal("enable", Pins("3",  dir="o", conn=("pmod", 1)))
)


class DVI_Timing(Elaboratable):
	def __init__(self):
		# all are outputs
		self.x = Signal(10)
		self.y = Signal(10)
		self.v_sync = Signal(reset=1)
		self.h_sync = Signal(reset=1)
		self.data_enable = Signal()
	
	def elaborate(self, _platform):
		m = Module()

		# 800x600, 60Hz -> 40MHz px clock
		h_bp, h_actv, h_fp, h_sync = 88, 800, 40, 128
		v_bp, v_actv, v_fp, v_sync = 23, 600, 1, 4

		# simulation logic: less scrolling through waveforms
		if _platform == None:
			h_bp, h_actv, h_fp, h_sync = 10, 20, 5, 15
			v_bp, v_actv, v_fp, v_sync = 4, 8, 1, 2

		h_counter = Signal(range(max(h_bp, h_actv, h_fp, h_sync)))
		v_counter = Signal(range(max(v_bp, v_actv, v_fp, v_sync)))

		line_done = Signal()
		m.d.px += line_done.eq(0)

		v_enable = Signal()
		h_enable = Signal()

		m.d.px += h_counter.eq(h_counter + 1)
		with m.FSM(name="horizontal_state", reset="BACK_PORCH", domain="px"):
			with m.State("BACK_PORCH"):
				with m.If(h_counter == h_bp-1):
					m.d.px += h_counter.eq(0)
					m.next = "ACTIVE"
					m.d.px += h_enable.eq(1)

			with m.State("ACTIVE"):
				with m.If(h_counter == h_actv-1):
					m.d.px += h_counter.eq(0)
					m.next = "FRONT_PORCH"
					m.d.px += h_enable.eq(0)

			with m.State("FRONT_PORCH"):
				with m.If(h_counter == h_fp-1):
					m.d.px += self.h_sync.eq(0)
					m.d.px += h_counter.eq(0)
					m.next = "SYNC"

			with m.State("SYNC"):
				with m.If(h_counter == h_sync-1):
					m.d.px += h_counter.eq(0)
					m.d.px += self.h_sync.eq(1)
					m.next = "BACK_PORCH"
				with m.Elif(h_counter == h_sync-2):
					m.d.px += line_done.eq(1)
		
		with m.If(line_done):
			m.d.px += v_counter.eq(v_counter + 1)
			with m.FSM(name="vertical_state", reset="BACK_PORCH", domain="px"):
				with m.State("BACK_PORCH"):
					with m.If(v_counter == v_bp-1):
						m.d.px += v_counter.eq(0)
						m.next = "ACTIVE"
						m.d.px += v_enable.eq(1)

				with m.State("ACTIVE"):
					with m.If(v_counter == v_actv-1):
						m.d.px += v_counter.eq(0)
						m.next = "FRONT_PORCH"
						m.d.px += v_enable.eq(0)

				with m.State("FRONT_PORCH"):
					with m.If(v_counter == v_fp-1):
						m.d.px += self.v_sync.eq(0)
						m.d.px += v_counter.eq(0)
						m.next = "SYNC"

				with m.State("SYNC"):
					with m.If(v_counter == v_sync-1):
						m.d.px += self.v_sync.eq(1)
						m.d.px += v_counter.eq(0)
						m.next = "BACK_PORCH"
		
		m.d.comb += self.data_enable.eq(v_enable & h_enable)
		m.d.comb += self.x.eq(Mux(self.data_enable, h_counter, 0))
		m.d.comb += self.y.eq(Mux(self.data_enable, v_counter, 0))

		return m


# 40MHz clock for 60Hz display.
# also still outputs 12MHz for running main logic
class DVI_PLL(Elaboratable):
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


# instantiates the PLL and sets up chip IO for you
class DVI(Elaboratable):
	def __init__(self):
		self.red   = Signal(4)
		self.green = Signal(4)
		self.blue  = Signal(4)

		# outputs
		self.drawing = Signal()
		self.x = Signal(10)
		self.y = Signal(10)

	def elaborate(self, platform):
		m = Module()

		dvi_clock = DVI_PLL()
		dvi_timing = DVI_Timing()
		m.submodules += [dvi_clock, dvi_timing]

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
			dvi_pins.v_sync.o.eq(dvi_timing.v_sync),
			dvi_pins.h_sync.o.eq(dvi_timing.h_sync), 
			dvi_pins.enable.o.eq(dvi_timing.data_enable),

			# buffered and DDR pins require a clock
			dvi_pins.red.o_clk.eq(ClockSignal("px")),
			dvi_pins.blue.o_clk.eq(ClockSignal("px")),
			dvi_pins.green.o_clk.eq(ClockSignal("px")),
			dvi_pins.v_sync.o_clk.eq(ClockSignal("px")),
			dvi_pins.h_sync.o_clk.eq(ClockSignal("px")),
			dvi_pins.enable.o_clk.eq(ClockSignal("px")),
			dvi_pins.px_clk.o_clk.eq(ClockSignal("px")),

			# non-inverting DDR output?
			dvi_pins.px_clk.o0.eq(1),
			dvi_pins.px_clk.o1.eq(0),
		]

		# connect this module's outputs
		m.d.comb += [
			self.drawing.eq(dvi_timing.data_enable),
			self.x.eq(dvi_timing.x),
			self.y.eq(dvi_timing.y),
		]

		return m
