from amaranth import *
from structures import Coords, Color


class FrameBufferRAM(Elaboratable):
	def __init__(self, width, height, init):
		self.mem = Memory(width=3, depth=width*height, init=init)
		self.rp = self.mem.read_port(transparent=False, domain="px")
		self.wp = self.mem.write_port(domain="px")

	def elaborate(self, _platform):
		m = Module()
		m.submodules += self.rp
		m.submodules += self.wp
		return m


def pixels_to_fb(pix):
	init = []
	for x in range(160):
		for y in range(120):
			init += [pix[y][x]]
		init += [0]*8  # pad to width of 128
	return init


class FrameBuffer(Elaboratable):
	def __init__(self):
		self.width = 160
		self.height = 120
		self.fb_width  = 128
		self.fb_height = 160

		self.coords_r = Coords(self.width, self.height)
		self.coords_w = Coords(self.width, self.height)
		self.w_data = Signal(3)
		self.write = Signal()
		self.swap = Signal()
		self.read_fill = Signal()
		self.fill_data = Signal(3)
		self.palette = Array(Signal(12) for _ in range(16))
		self.color = Color(12)

	def elaborate(self, _platform):
		m = Module()


		pix = [[0]*160 for _ in range(120)]
		for i in range(7):
			for x in range(i*10,i*10+20):
				for y in range(i*10+20,i*10+40):
					pix[y-3][x+40] = i+1
		init0 = pixels_to_fb(pix)

		pix = [[0]*160 for _ in range(120)]
		for i in range(7):
			for x in range(i*10,i*10+20):
				for y in range(i*10+20,i*10+40):
					pix[y-3][x+40] = 7-i
		init1 = pixels_to_fb(pix)

		m.submodules.fb0 = fb0 = FrameBufferRAM(self.fb_width, self.fb_height, init0)
		m.submodules.fb1 = fb1 = FrameBufferRAM(self.fb_width, self.fb_height, init1)

		selected = Signal()  # selected fb is the one we write to
		with m.If(self.swap):
			m.d.px += selected.eq(~selected)

		m.d.px += [
			fb0.rp.en.eq(~selected),
			fb1.rp.en.eq(selected),
		]

		with m.If(selected):
			m.d.px += [
				fb0.wp.addr.eq(self.coords_w.xy),
				fb0.wp.data.eq(self.w_data),
				fb0.wp.en.eq(self.write),
				fb1.rp.addr.eq(self.coords_r.xy),
				fb1.wp.addr.eq(self.coords_r.xy),
				fb1.wp.data.eq(self.fill_data),
				fb1.wp.en.eq(self.read_fill),
				self.color.rgb.eq(self.palette[fb1.rp.data]),
			]
		with m.Else():
			m.d.px += [
				fb1.wp.addr.eq(self.coords_w.xy),
				fb1.wp.data.eq(self.w_data),
				fb1.wp.en.eq(self.write),
				fb0.rp.addr.eq(self.coords_r.xy),
				fb0.wp.addr.eq(self.coords_r.xy),
				fb0.wp.data.eq(self.fill_data),
				fb0.wp.en.eq(self.read_fill),
				self.color.rgb.eq(self.palette[fb0.rp.data]),
			]

		return m
