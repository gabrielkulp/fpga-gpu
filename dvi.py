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
		self.h_counter = Signal(11)
		self.v_counter = Signal(10)
		self.px_clk = Signal()
		self.signals = [self.x, self.y, self.v_sync, self.h_sync, self.data_enable, self.h_counter, self.v_counter]
	
	def elaborate(self, _platform):
		m = Module()
		
		h_bp    = 88
		h_actv  = 800
		h_fp    = 40
		h_sync  = 128
		h_total = 1056

		v_bp    = 23
		v_actv  = 600
		v_fp    = 1
		v_sync  = 4
		v_total = 628

		y_strobe = Signal()
		m.d.px += y_strobe.eq(0)

		v_enable = Signal()
		h_enable = Signal()

		m.d.px += self.h_counter.eq(self.h_counter + 1)
		with m.FSM(name="horizontal_state", reset="BACK_PORCH"):
			with m.State("BACK_PORCH"):
				with m.If(self.h_counter == h_bp-1):
					m.d.px += self.h_counter.eq(0)
					m.next = "ACTIVE"
					m.d.px += h_enable.eq(1)

			with m.State("ACTIVE"):
				m.d.px += self.x.eq(self.x + 1)
				with m.If(self.h_counter == h_actv-1):
					m.d.px += self.h_counter.eq(0)
					m.d.px += self.x.eq(0)
					m.next = "FRONT_PORCH"
					m.d.px += self.h_sync.eq(0)
					m.d.px += h_enable.eq(0)

			with m.State("FRONT_PORCH"):
				with m.If(self.h_counter == h_fp-1):
					m.d.px += self.h_counter.eq(0)
					m.next = "SYNC"

			with m.State("SYNC"):
				with m.If(self.h_counter == h_sync-1):
					m.d.px += self.h_counter.eq(0)
					m.d.px += y_strobe.eq(1)
					m.d.px += self.h_sync.eq(1)
					m.next = "BACK_PORCH"
		
		with m.If(y_strobe):
			m.d.px += self.v_counter.eq(self.v_counter + 1)
			with m.FSM(name="vertical_state", reset="BACK_PORCH"):
				with m.State("BACK_PORCH"):
					with m.If(self.v_counter == v_bp-1):
						m.d.px += self.v_counter.eq(0)
						m.next = "ACTIVE"
						m.d.px += v_enable.eq(1)

				with m.State("ACTIVE"):
					m.d.px += self.y.eq(self.y + 1)
					with m.If(self.v_counter == v_actv-1):
						m.d.px += self.v_counter.eq(0)
						m.d.px += self.y.eq(0)
						m.next = "FRONT_PORCH"
						m.d.px += self.v_sync.eq(0)
						m.d.px += v_enable.eq(0)

				with m.State("FRONT_PORCH"):
					with m.If(self.v_counter == v_fp-1):
						m.d.px += self.v_counter.eq(0)
						m.next = "SYNC"

				with m.State("SYNC"):
					with m.If(self.v_counter == v_sync-1):
						m.d.px += self.y.eq(0)
						m.d.px += self.v_sync.eq(1)
						m.d.px += self.v_counter.eq(0)
						m.next = "BACK_PORCH"
		
		m.d.comb += self.data_enable.eq(v_enable & h_enable)

		return m


# 40MHz clock for 60Hz display.
# also still outputs 12MHz for running main logic
class DVI_PLL(Elaboratable):
	def __init__(self):
		self.clk39_750 = Signal(attrs = {"keep": "true"})  # out
		self.clk12 = Signal(attrs = {"keep": "true"})  # out
	
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


class DVI(Elaboratable):
	def __init__(self):
		self.red = Signal(4)
		self.green = Signal(4)
		self.blue = Signal(4)

		# outputs
		self.drawing = Signal()
		self.x = Signal(10)
		self.y = Signal(10)
		self.clk_px = Signal(attrs = {"keep": "true"})
		self.clk_sync = Signal(attrs = {"keep": "true"})

	def elaborate(self, platform):
		m = Module()

		dvi_clock = DVI_PLL()
		m.submodules += dvi_clock

		dvi_timing = DVI_Timing()
		m.submodules += dvi_timing

		# connect to the physical pins
		# xdr assigns 1 for buffered and 2 for DDR
		dvi_pins = platform.request("dvi", xdr = {
			"red": 1, "green": 1, "blue": 1,
			"v_sync": 1, "h_sync": 1, "enable": 1,
			"px_clk": 2
		})
		m.d.comb += [
			dvi_pins.red.eq(self.red), 
			dvi_pins.green.eq(self.green), 
			dvi_pins.blue.eq(self.blue), 
			dvi_pins.v_sync.eq(dvi_timing.v_sync), 
			dvi_pins.h_sync.eq(dvi_timing.h_sync), 
			dvi_pins.enable.eq(dvi_timing.data_enable), 
			dvi_pins.px_clk.o0.eq(0),
			dvi_pins.px_clk.o1.eq(1),
			dvi_pins.px_clk.o_clk.eq(dvi_clock.clk39_750),
			dvi_timing.px_clk.eq(dvi_clock.clk39_750)
		]

		# connect this module's outputs
		m.d.comb += self.drawing.eq(dvi_timing.data_enable)
		m.d.comb += self.x.eq(dvi_timing.x)
		m.d.comb += self.y.eq(dvi_timing.y)
		m.d.comb += self.clk_px.eq(dvi_clock.clk39_750)
		m.d.comb += self.clk_sync.eq(dvi_clock.clk12)
		
		return m
