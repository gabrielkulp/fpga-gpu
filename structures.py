from amaranth import *

class Coords:
	def __init__(self, max_x, max_y):
		self.x = Signal(range(max_x))
		self.y = Signal(range(max_y))


class Color:
	def __init__(self, bits_per_channel):
		self.r = Signal(bits_per_channel)
		self.g = Signal(bits_per_channel)
		self.b = Signal(bits_per_channel)

	@property
	def rgb(self):
		return Cat(self.b, self.g, self.r)
