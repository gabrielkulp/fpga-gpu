from amaranth import *
from structures import Coords, Color

class LineCalculator(Elaboratable):
	def __init__(self, max_x, max_y):
		self.max_x = max_x
		self.max_y = max_y

		self.coords = Coords(Signal(range(max_x)), Signal(range(max_y)))
		self.endpoints = [Coords(Signal(range(max_x)), Signal(range(max_y))),
			Coords(Signal(range(max_x)), Signal(range(max_y)))]
		self.row_strobe = Signal()  # in
		self.update = Signal()  # in
		self.enable = Signal()

		self.is_on_line = Signal()  # out

	def elaborate(self, _platform):
		m = Module()

		#line_mem = Memory(width=1, depth=self.max_x, init=[0]*self.max_x)
		endpoints_rect = [Coords(Signal(range(self.max_x)), Signal(range(self.max_y))),
			Coords(Signal(range(self.max_x)), Signal(range(self.max_y)))]

		dx = Signal(range(-self.max_x, self.max_x))
		sx = Signal(range(-self.max_x,self.max_x))
		dy = Signal(range(-self.max_y, self.max_y))
		sy = Signal(range(-self.max_y,self.max_y))
		error = Signal(range(-self.max_x<<9, self.max_x<<9))

		m.d.comb += sy.eq(1) # points are swapped so this is always 1

		

		curr_x = Signal(range(-self.max_x,self.max_x))
		curr_y = Signal(range(-self.max_y,self.max_y))
		done = Signal()
		update_n = Signal()  # second cycle of update
		update_nn = Signal()  # third cycle of update
		m.d.px += update_n.eq(self.update)
		m.d.px += update_nn.eq(self.update)

		with m.If(self.update):
			# swap endpoints so line always has the first point above the second
			with m.If(self.endpoints[0].y > self.endpoints[1].y):
				m.d.px += [
					endpoints_rect[0].x.eq(self.endpoints[1].x),
					endpoints_rect[0].y.eq(self.endpoints[1].y),
					endpoints_rect[1].x.eq(self.endpoints[0].x),
					endpoints_rect[1].y.eq(self.endpoints[0].y),
				]
			with m.Else():
				m.d.px += [
					endpoints_rect[0].x.eq(self.endpoints[0].x),
					endpoints_rect[0].y.eq(self.endpoints[0].y),
					endpoints_rect[1].x.eq(self.endpoints[1].x),
					endpoints_rect[1].y.eq(self.endpoints[1].y),
				]

		with m.If(update_n):
			m.d.px += [
				error.eq(dx + dy),
				curr_x.eq(endpoints_rect[0].x),
				curr_y.eq(endpoints_rect[0].y),
				self.is_on_line.eq(0),
				dy.eq(endpoints_rect[0].y - endpoints_rect[1].y),
				done.eq(0)
			]
			with m.If(endpoints_rect[0].x > endpoints_rect[1].x):
				m.d.px += sx.eq(-1)
				m.d.px += dx.eq(endpoints_rect[0].x - endpoints_rect[1].x)
			with m.Else():
				m.d.px += sx.eq(1)
				m.d.px += dx.eq(endpoints_rect[1].x - endpoints_rect[0].x)
		
		inverted = Signal()
		with m.If(update_nn):
				m.d.px += inverted.eq((sx < 0) & (-dy < dx))

		with m.If((self.coords.x == endpoints_rect[1].x) & (self.coords.y == endpoints_rect[1].y)):
			m.d.px += done.eq(1)
			m.d.px += self.is_on_line.eq(1)

		x_err = Signal()
		y_err = Signal()
		m.d.comb += [
			y_err.eq(error<<1 >= dy),
			x_err.eq(error<<1 <= dx),
		]

		with m.If(self.enable & (curr_x == self.coords.x) & (curr_y == self.coords.y)):
			m.d.px += self.is_on_line.eq(~done)
			with m.If(y_err & x_err):
				m.d.px += error.eq(error + dy + dx)
				m.d.px += curr_x.eq(curr_x + sx)
				m.d.px += curr_y.eq(curr_y + sy)
			with m.Elif(y_err):
				with m.If(curr_x == endpoints_rect[1].x):
					m.d.px += done.eq(1)
				m.d.px += error.eq(error + dy)
				m.d.px += curr_x.eq(curr_x + sx)
			with m.Elif(x_err):
				with m.If(curr_y == endpoints_rect[1].y):
					m.d.px += done.eq(1)
				m.d.px += error.eq(error + dx)
				m.d.px += curr_y.eq(curr_y + sy)
		with m.Else():
			m.d.px += self.is_on_line.eq(0)
		
		#steps_left = Signal(range(-self.max_x, self.max_x))
		with m.If(inverted): # special case that doesn't work normally
			with m.If((self.coords.x == endpoints_rect[0].x) & (self.coords.y == endpoints_rect[0].y)):
				m.d.px += self.is_on_line.eq(1)
			with m.If((self.coords.x == endpoints_rect[1].x) & (self.coords.y == endpoints_rect[1].y)):
				m.d.px += self.is_on_line.eq(1)


		return m





#	def elaborate(self, _platform):
#		m = Module()
#
#		# Stage 1
#
#		is_in_x = Signal()
#		is_in_y = Signal()
#
#		#m.d.comb += [
#		#	is_in_x.eq(self.coords.x <= Mux(self.endpoints[0].x > self.endpoints[1].x, self.endpoints[0].x, self.endpoints[1].x)
#		#			& (self.coords.x >= Mux(self.endpoints[0].x > self.endpoints[1].x, self.endpoints[1].x, self.endpoints[0].x))),
#		#	is_in_y.eq(self.coords.y <= Mux(self.endpoints[0].y > self.endpoints[1].y, self.endpoints[0].y, self.endpoints[1].y)
#		#			& (self.coords.y >= Mux(self.endpoints[0].y > self.endpoints[1].y, self.endpoints[1].y, self.endpoints[0].y))),
#		#]
#		m.d.comb += [
#			is_in_x.eq((self.coords.x <= self.endpoints[1].x) & (self.coords.x >= self.endpoints[0].x)),
#			is_in_y.eq((self.coords.y <= self.endpoints[1].y) & (self.coords.y >= self.endpoints[0].y))
#		]
#		in_bounds = [Signal(), Signal(), Signal()]
#		m.d.px += in_bounds[0].eq(is_in_x & is_in_y)
#
#		diff_a = Signal(range(max(self.max_x, self.max_y)))
#		diff_b = Signal(range(max(self.max_x, self.max_y)))
#		diff_c = Signal(range(max(self.max_x, self.max_y)))
#		diff_d = Signal(range(max(self.max_x, self.max_y)))
#		
#		m.d.px += [
#			diff_a.eq(self.endpoints[1].x - self.endpoints[0].x),
#			diff_b.eq(self.endpoints[1].y - self.endpoints[0].y),
#			diff_c.eq(self.endpoints[0].y - self.coords.y),
#			diff_d.eq(self.endpoints[0].x - self.coords.x)
#		]
#
#		# Stage 2
#		m.d.px += in_bounds[1].eq(in_bounds[0])
#
#		numerator = Signal(11)
#		denominator = Signal(11)
#
#		m.d.px += [
#			numerator.eq((diff_a * diff_c) - (diff_d * diff_b)),
#			denominator.eq((diff_a * diff_a) + (diff_b * diff_b)),
#		]
#
#		# Stage 3
#		#m.d.px += in_bounds[2].eq(in_bounds[1])
#		m.d.px += self.is_on_line.eq(in_bounds[0] & (numerator < denominator))
#		return m