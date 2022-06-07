class Point():
	def __init__(self, x=0, y=0):
		self.x = x
		self.y = y
	
	@property
	def xy(self):
		return (self.x, self.y)


class Segment():
	def __init__(self, start:Point, end:Point):
		self.start = start
		self.end = end
	
	def serialize(self):
		return (*self.start.xy, *self.end.xy)


class Mesh():
	def __init__(self, points=[], edges=[]):
		self.points = points
		self.edges = edges
	
	def serialize(self):
		segments = []
		for edge in self.edges:
			segments.append(Segment(self.points[edge[0]], self.points[edge[1]]))
		return [s.serialize() for s in segments]
