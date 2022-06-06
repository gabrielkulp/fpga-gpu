from amaranth import *
from structures import Coords, Color

class _LineDrawer(Elaboratable):
	def __init__(self, max_x, max_y):
		self.max_x = max_x
		self.max_y = max_y

		# in
		self.endpoints = [Coords(max_x, max_y), Coords(max_x, max_y)]
		self.start = Signal()

		# out
		self.coords = Coords(max_x, max_y)
		self.write = Signal()
		self.done = Signal()

	def elaborate(self, _platform):
		m = Module()

		end = Coords(self.max_x, self.max_y)

		dx = Signal(range(-self.max_x, self.max_x))
		sx = Signal(range(-self.max_x, self.max_x))
		dy = Signal(range(-self.max_y, self.max_y))
		sy = Signal(range(-self.max_y, self.max_y))
		error = Signal(range(-self.max_x<<1, self.max_x<<1))

		x = Signal(range(-self.max_x, self.max_x))
		y = Signal(range(-self.max_y, self.max_y))
		m.d.comb += self.coords.x.eq(x)
		m.d.comb += self.coords.y.eq(y)

		with m.FSM(domain="px", reset="wait"):
			with m.State("wait"):
				m.d.px += self.write.eq(0)
				m.d.px += self.done.eq(0)
				with m.If(self.start):
					m.d.px += [
						end.x.eq(self.endpoints[1].x),
						end.y.eq(self.endpoints[1].y),
						x.eq(self.endpoints[0].x),
						y.eq(self.endpoints[0].y),
					]
					with m.If(self.endpoints[0].x > self.endpoints[1].x):
						m.d.px += sx.eq(-1)
						m.d.px += dx.eq(self.endpoints[0].x - self.endpoints[1].x)
					with m.Else():
						m.d.px += sx.eq(1)
						m.d.px += dx.eq(self.endpoints[1].x - self.endpoints[0].x)
					
					with m.If(self.endpoints[0].y > self.endpoints[1].y):
						m.d.px += sy.eq(-1)
						m.d.px += dy.eq(self.endpoints[1].y - self.endpoints[0].y)
					with m.Else():
						m.d.px += sy.eq(1)
						m.d.px += dy.eq(self.endpoints[0].y - self.endpoints[1].y)
					m.next = "calculate"

			with m.State("calculate"):
				m.d.px += [
					error.eq(dx + dy),
					self.write.eq(1)
				]
				m.next = "draw"

			with m.State("draw"):
				m.d.px += self.write.eq(1)
				with m.If((x == end.x) & (y == end.y)):
					m.d.px += [self.write.eq(0), self.done.eq(1)]
					m.next = "wait"

				with m.If((error<<1 >= dy) & (error<<1 <= dx)):
					m.d.px += error.eq(error + dy + dx)
					m.d.px += [x.eq(x + sx), y.eq(y + sy)]
				with m.Elif(error<<1 >= dy):
					with m.If(x == end.x):
						m.d.px += [self.write.eq(0), self.done.eq(1)]
						m.next = "wait"
					m.d.px += error.eq(error + dy)
					m.d.px += x.eq(x + sx)
				with m.Elif(error<<1 <= dx):
					with m.If(y == end.y):
						m.d.px += [self.write.eq(0), self.done.eq(1)]
						m.next = "wait"
					m.d.px += error.eq(error + dx)
					m.d.px += y.eq(y + sy)

		return m


class _SegmentMemory(Elaboratable):
	def __init__(self, max_x, max_y):
		from math import log, ceil
		if ceil(log(max_x-1, 2)) + ceil(log(max_y-1, 2)) > 16:
			print("Coordinates are too large to fit in 1 line of SPRAM.")
			exit(1)
		
		# in
		self.index = Signal(14)
		self.endpoints_in = [Coords(max_x, max_y), Coords(max_x, max_y)]
		self.write = Signal()

		# out
		self.endpoints_out = [Coords(max_x, max_y), Coords(max_x, max_y)]
	
	def elaborate(self, _platform):
		m = Module()

		start_data_in_padded = Signal(16)
		start_data_out_padded = Signal(16)
		end_data_in_padded = Signal(16)
		end_data_out_padded = Signal(16)
		pad = C(0, 16-self.endpoints_in[0].width)

		m.d.comb += [
			start_data_in_padded.eq(Cat(self.endpoints_in[0].xy, pad)),
			self.endpoints_out[0].xy.eq(start_data_out_padded),
			end_data_in_padded.eq(Cat(self.endpoints_in[1].xy, pad)),
			self.endpoints_out[1].xy.eq(end_data_out_padded),
		]

		m.submodules.start = Instance(
			'SB_SPRAM256KA',
			i_ADDRESS = self.index,
			i_DATAIN = start_data_in_padded,
			i_MASKWREN = Const(0b1111, 4),
			i_WREN = self.write,
			i_CHIPSELECT = 1,
			i_CLOCK = ClockSignal("px"),
			i_STANDBY = 0,
			i_SLEEP = 0,
			i_POWEROFF = 1,
			o_DATAOUT = start_data_out_padded
		)

		m.submodules.end = Instance(
			'SB_SPRAM256KA',
			i_ADDRESS = self.index,
			i_DATAIN = end_data_in_padded,
			i_MASKWREN = Const(0b1111, 4),
			i_WREN = self.write,
			i_CHIPSELECT = 1,
			i_CLOCK = ClockSignal("px"),
			i_STANDBY = 0,
			i_SLEEP = 0,
			i_POWEROFF = 1,
			o_DATAOUT = end_data_out_padded
		)

		return m


class _SegmentAccessArbiter(Elaboratable):
	def __init__(self, max_x, max_y):
		self.max_x = max_x
		self.max_y = max_y

		# line renderer in
		self.index_read = Signal(14)
		self.request_read = Signal()

		# UART in
		self.index_write = Signal(14)
		self.request_write = Signal()
		self.endpoints_in = [Coords(max_x, max_y), Coords(max_x, max_y)]

		# out
		self.endpoints_out = [Coords(max_x, max_y), Coords(max_x, max_y)]
		self.write_done = Signal()
	
	def elaborate(self, _platform):
		m = Module()
		m.submodules.memory = mem = _SegmentMemory(self.max_x, self.max_y)

		pending_write = Signal()
		pending_index = Signal(14)
		pending_data = [Coords(self.max_x, self.max_y), Coords(self.max_x, self.max_y)]

		led = _platform.request("led_r")

		# reading gets priority in the edge case that both happen simultaneously
		m.d.px += self.write_done.eq(0)
		m.d.px += mem.write.eq(0)
		with m.If(self.request_read):
			m.d.px += mem.index.eq(self.index_read)
		with m.Elif(pending_write):
			m.d.px += [
				led.o.eq(~led.o),
				pending_write.eq(0),
				self.write_done.eq(1),
				mem.write.eq(1),
				mem.index.eq(pending_index),
				mem.endpoints_in[0].xy.eq(pending_data[0].xy),
				mem.endpoints_in[1].xy.eq(pending_data[1].xy),
			]
		m.d.px += mem.index.eq(0)
		
		m.d.comb += self.endpoints_out[0].xy.eq(mem.endpoints_out[0].xy)
		m.d.comb += self.endpoints_out[1].xy.eq(mem.endpoints_out[1].xy)

		with m.If(self.request_write):
			m.d.px += pending_write.eq(1)
			m.d.px += pending_index.eq(self.index_write)
			m.d.px += pending_data[0].xy.eq(self.endpoints_in[0].xy)
			m.d.px += pending_data[1].xy.eq(self.endpoints_in[1].xy)

		return m


class LineSet(Elaboratable):
	def __init__(self, max_x, max_y):
		self.max_x = max_x
		self.max_y = max_y

		# UART in
		self.length = Signal(14)
		self.index_write = Signal(14)
		self.request_write = Signal()
		self.endpoints_in = [Coords(max_x, max_y), Coords(max_x, max_y)]

		# vga in
		self.start = Signal()

		# out
		self.write_done = Signal()  # uart out
		self.coords = Coords(max_x, max_y)  # fb out
		self.write = Signal()  # fb out
	
	def elaborate(self, _platform):
		m = Module()
		counter = Signal(self.length.width)

		m.submodules.mem = arb = _SegmentAccessArbiter(self.max_x, self.max_y)

		m.submodules.line = line = _LineDrawer(self.max_x, self.max_y)
		m.d.comb += [
			self.coords.xy.eq(line.coords.xy),
			self.write.eq(line.write),
			line.endpoints[0].xy.eq(arb.endpoints_out[0].xy),
			line.endpoints[1].xy.eq(arb.endpoints_out[1].xy),
			#line.endpoints[0].xy.eq(self.endpoints_in[0].xy),
			#line.endpoints[1].xy.eq(self.endpoints_in[1].xy),

			arb.index_write.eq(self.index_write),
			arb.request_write.eq(self.request_write),
			arb.endpoints_in[0].xy.eq(self.endpoints_in[0].xy),
			arb.endpoints_in[1].xy.eq(self.endpoints_in[1].xy),
			self.write_done.eq(arb.write_done)
		]

		m.d.px += line.start.eq(0)
		m.d.px += arb.request_read.eq(0)
		with m.FSM(reset="IDLE", domain="px"):
			with m.State("IDLE"):
				with m.If(self.start):
					m.d.px += arb.index_read.eq(counter)
					m.d.px += arb.request_read.eq(1)  # how many cycles until the result is available?
					m.next = "START"
			#with m.State("WAIT"):
			#	m.next = "START"
			with m.State("START"):
				#m.d.px += line.endpoints[0].xy.eq(mem.endpoints_out[0].xy)
				#m.d.px += line.endpoints[1].xy.eq(mem.endpoints_out[1].xy)
				m.d.px += line.start.eq(1)
				m.next = "DRAW"
			with m.State("DRAW"):
				with m.If(line.done):
					m.d.px += counter.eq(0)
					m.next = "IDLE"
		
		return m