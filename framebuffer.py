from amaranth import *


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

		# this isn't quite the right calculation, but it works for 160x120
		self.r_x = Signal(range(self.width))
		self.r_y = Signal(range(self.height))
		self.w_x = Signal(range(self.width))
		self.w_y = Signal(range(self.height))
		self.r_data = Signal(3)
		self.w_data = Signal(3)
		self.write = Signal()
		self.swap = Signal()
		self.read_erase = Signal()
		self.palette = Array(Signal(12) for _ in range(16))
		self.color = Signal(12)

	def elaborate(self, _platform):
		m = Module()


		pix = [[0]*160 for _ in range(120)]
		for i in range(7):
			for x in range(i*10,i*10+20):
				for y in range(i*10+20,i*10+40):
					pix[y-3][x+40] = i+1
		init0 = pixels_to_fb(pix)

		pix = [[i for i in range(16)]*10]
		for i in range(119):
			if i%2:
				pix.append([2]*160)
			else:
				pix.append([3]*160)
		init1 = pixels_to_fb(pix)

		m.submodules.fb0 = fb0 = FrameBufferRAM(self.fb_width, self.fb_height, init0)
		m.submodules.fb1 = fb1 = FrameBufferRAM(self.fb_width, self.fb_height, init1)

		r_addr = Signal(self.r_x.width + self.r_y.width)
		w_addr = Signal(r_addr.width)
		m.d.comb += [
			r_addr.eq(Cat(self.r_y, self.r_x)),
			w_addr.eq(Cat(self.w_y, self.w_x)),
		]

		selected = Signal()  # selected fb is the one we write to
		with m.If(self.swap):
			m.d.px += selected.eq(~selected)

		m.d.px += [
			fb0.rp.en.eq(~selected),
			fb1.rp.en.eq(selected),
		]

		with m.If(selected):
			m.d.px += [
				fb0.wp.addr.eq(w_addr),
				fb0.wp.data.eq(self.w_data),
				fb0.wp.en.eq(self.write),
				fb1.rp.addr.eq(r_addr),
				fb1.wp.addr.eq(r_addr),
				fb1.wp.data.eq(0),
				fb1.wp.en.eq(self.read_erase),
				self.color.eq(self.palette[fb1.rp.data]),
			]
		with m.Else():
			m.d.px += [
				fb1.wp.addr.eq(w_addr),
				fb1.wp.data.eq(self.w_data),
				fb1.wp.en.eq(self.write),
				fb0.rp.addr.eq(r_addr),
				fb0.wp.addr.eq(r_addr),
				fb0.wp.data.eq(0),
				fb0.wp.en.eq(self.read_erase),
				self.color.eq(self.palette[fb0.rp.data]),
			]

		return m
