from amaranth import *

class Coords:
	def __init__(self, max_x, max_y):
		self.max_x = max_x
		self.max_y = max_y
		self.x = Signal(range(max_x))
		self.y = Signal(range(max_y))
		self.width = self.x.width + self.y.width

	@property
	def xy(self):
		return Cat(self.y, self.x)


class Color:
	def __init__(self, bits_per_channel):
		self.width = bits_per_channel*3
		self.r = Signal(bits_per_channel)
		self.g = Signal(bits_per_channel)
		self.b = Signal(bits_per_channel)

	@property
	def rgb(self):
		return Cat(self.b, self.g, self.r)
