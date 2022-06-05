from amaranth import *
from structures import Coords, Color

class LineDrawer(Elaboratable):
	def __init__(self, max_x, max_y):
		self.max_x = max_x
		self.max_y = max_y

		# in
		self.endpoints = Array([Coords(max_x, max_y), Coords(max_x, max_y)])
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
	def __init__(self, max_x, max_y, max_count):
		from math import log, ceil
		if ceil(log(max_x-1, 2)) + ceil(log(max_y-1, 2)) > 16:
			print("Coordinates are too large to fit in 1 line of SPRAM.")
			exit(1)
		if max_count >= 2**14:
			print("Line count is too large to fit in 2 SPRAMs")
		
		# in
		self.index = Signal(range(max_count))
		self.endpoints_in = Array([Coords(max_x, max_y), Coords(max_x, max_y)])
		self.write = Signal()

		# out
		self.endpoints_out = Array([Coords(max_x, max_y), Coords(max_x, max_y)])
	
	def elaborate(self, _platform):
		m = Module()

		m.submodules.start = Instance(
			'SB_SPRAM256KA',
			i_ADDRESS = self.index,
			i_DATAIN = self.endpoints_in[0].xy,
			i_MASKWREN = Const(0b1111, 4),
			i_WREN = self.write,
			i_CHIPSELECT = 1,
			i_CLOCK = ClockSignal("px"),
			i_STANDBY = 0,
			i_SLEEP = 0,
			i_POWEROFF = 0,
			o_DATAOUT = self.endpoints_out[0].xy
		)

		m.submodules.end = Instance(
			'SB_SPRAM256KA',
			i_ADDRESS = self.index,
			i_DATAIN = self.endpoints_in[1].xy,
			i_MASKWREN = Const(0b1111, 4),
			i_WREN = self.write,
			i_CHIPSELECT = 1,
			i_CLOCK = ClockSignal("px"),
			i_STANDBY = 0,
			i_SLEEP = 0,
			i_POWEROFF = 0,
			o_DATAOUT = self.endpoints_out[1].xy
		)

		return m


class _SegmentAccessArbiter(Elaboratable):
	def __init__(self, max_x, max_y, max_count):
		self.max_x = max_x
		self.max_y = max_y
		self.max_count = max_count

		# line renderer in
		self.index_read = Signal(range(max_count))
		self.request_read = Signal()

		# UART in
		self.index_write = Signal(range(max_count))
		self.request_write = Signal()
		self.endpoints_in = Array([Coords(max_x, max_y), Coords(max_x, max_y)])

		# out
		self.endpoints_out = Array([Coords(max_x, max_y), Coords(max_x, max_y)])
		self.write_done = Signal()
	
	def elaborate(self, _platform):
		m = Module()
		m.submodules.memory = mem = _SegmentMemory(self.max_x, self.max_y, self.max_count)

		pending_write = Signal()
		pending_data = Array([Coords(self.max_x, self.max_y), Coords(self.max_x, self.max_y)])

		# reading gets priority in the edge case that both happen simultaneously
		with m.If(self.request_read):
			m.d.px += mem.write.eq(0)
			m.d.px += mem.index.eq(self.index_read)
		with m.Else():
			with m.If(pending_write):
				pending_write.eq(0)
				m.d.px += [
					self.write_done.eq(1),
					mem.write.eq(1),
					mem.index.eq(self.index_write),
					mem.endpoints_in.eq(pending_data)
				]
		
		m.d.comb += self.endpoints_out.eq(mem.endpoints_out)

		with m.If(self.request_write):
			m.d.px += pending_write.eq(1)
			m.d.px += pending_data.eq(self.endpoints_in)

		return m


class LineSet(Elaboratable):
	def __init__(self, max_x, max_y, length):
		self.length = length
		self.max_x = max_x
		self.max_y = max_y

		# in
		self.segments = Array([
			Array([Coords(max_x, max_y), Coords(max_x, max_y)])
			for _ in range(length)
		])
		self.start = Signal()

		# out
		self.done = Signal()
		self.coords = Coords(max_x, max_y)
		self.write = Signal()
	
	def elaborate(self, _platform):
		m = Module()
		counter = Signal(range(self.length))

		m.submodules.line = line = LineDrawer(self.max_x, self.max_y)
		m.d.comb += [
			self.coords.x.eq(line.coords.x),
			self.coords.y.eq(line.coords.y),
			self.write.eq(line.write)
		]

		m.d.px += self.done.eq(0)
		m.d.px += line.start.eq(0)
		with m.If((counter == 0) & self.start):
			m.d.px += [
				line.endpoints[0].x.eq(self.segments[0][0].x),
				line.endpoints[0].y.eq(self.segments[0][0].y),
				line.endpoints[1].x.eq(self.segments[0][1].x),
				line.endpoints[1].y.eq(self.segments[0][1].y),
				line.start.eq(1),
				counter.eq(counter+1)
			]
		with m.If((counter != 0) & line.done):
			m.d.px += [
				line.endpoints[0].x.eq(self.segments[counter][0].x),
				line.endpoints[0].y.eq(self.segments[counter][0].y),
				line.endpoints[1].x.eq(self.segments[counter][1].x),
				line.endpoints[1].y.eq(self.segments[counter][1].y),
				line.start.eq(1)
			]
			with m.If(counter != self.length-1):
				m.d.px += counter.eq(counter+1)
			with m.Else():
				m.d.px += counter.eq(0)
		
		return m