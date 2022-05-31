from amaranth import *
from structures import Coords, Color

class LineDrawer(Elaboratable):
	def __init__(self, max_x, max_y):
		self.max_x = max_x
		self.max_y = max_y

		self.endpoints = [Coords(Signal(range(max_x)), Signal(range(max_y))),
			Coords(Signal(range(max_x)), Signal(range(max_y)))]
		self.update = Signal()  # in
		self.enable = Signal()

		self.coords = Coords(Signal(range(max_x)), Signal(range(max_y)))
		self.write = Signal()  # out

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

		x = Signal(range(-self.max_x,self.max_x))
		y = Signal(range(-self.max_y,self.max_y))
		m.d.comb += self.coords.x.eq(x)
		m.d.comb += self.coords.y.eq(y)


		# pipeline that's syntactically easier to declare up here,
		# but it's used in the "draw" state below
		x_err = Signal()
		y_err = Signal()
		m.d.px += [
			y_err.eq(error<<1 >= dy),
			x_err.eq(error<<1 <= dx),
		]

		with m.FSM(domain="px", reset="wait"):
			with m.State("wait"):
				m.d.px += self.write.eq(0)
				with m.If(self.update & self.enable):
					m.next = "update"
			
			with m.State("update"):
				m.d.px += [
					endpoints_rect[0].x.eq(self.endpoints[0].x),
					endpoints_rect[0].y.eq(self.endpoints[0].y),
					endpoints_rect[1].x.eq(self.endpoints[1].x),
					endpoints_rect[1].y.eq(self.endpoints[1].y),
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
				m.next = "update_next"
			
			with m.State("update_next"):
				m.d.px += [
					error.eq(dx + dy),
					self.write.eq(1)
				]
				m.next = "draw"

			with m.State("draw"):
				m.d.px += self.write.eq(1)
				with m.If((x == endpoints_rect[1].x) & (y == endpoints_rect[1].y)):
					m.d.px += self.write.eq(0)
					m.next = "wait"

				with m.If((error<<1 >= dy) & (error<<1 <= dx)):
					m.d.px += error.eq(error + dy + dx)
					m.d.px += x.eq(x + sx)
					m.d.px += y.eq(y + sy)
				with m.Elif(error<<1 >= dy):
					with m.If(x == endpoints_rect[1].x):
						m.d.px += self.write.eq(0)
						m.next = "wait"
					m.d.px += error.eq(error + dy)
					m.d.px += x.eq(x + sx)
				with m.Elif(error<<1 <= dx):
					with m.If(y == endpoints_rect[1].y):
						m.d.px += self.write.eq(0)
						m.next = "wait"
					m.d.px += error.eq(error + dx)
					m.d.px += y.eq(y + sy)


		return m
