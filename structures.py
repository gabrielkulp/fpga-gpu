from amaranth import *

class Coords:
	def __init__(self, x, y):
		self.x = x
		self.y = y
	
	def eq(self, rhs, y=None):
		if y:
			return (self.x == rhs) & (self.y == y)
		else:
			return (self.x == rhs.x) & (self.y == rhs.y)


class Color:
	def __init__(self, r : Signal, g : Signal, b : Signal):
		self.r = r
		self.g = g
		self.b = b
		self.rgb = Cat(self.r, self.g, self.b)
