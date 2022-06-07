#!/usr/bin/env python3
from operator import ge
from serial import Serial
from typing import Tuple
from time import sleep
from struct import pack
from top import build_and_run

import uart
import geometry

class GPUConnection():
	coord_max = 0xff
	index_max = 2**14
	baud = 115200

	def __init__(self, serial_device="/dev/ttyUSB1"):
		self.conn = Serial(serial_device, self.baud)
		if not self.alive:
			raise ConnectionError("Could not establish serial connection")
	
	def close(self):
		self.conn.close()

	@property
	def alive(self):
		self.conn.write(pack('B', uart.commands["ping"]))
		res = self.conn.read(1)
		return res == pack('B', uart.ping_res)
	
	def send_segment(self, index, coords: Tuple[int, int, int, int]):  # x y x y
		if any([c > self.coord_max and c >= 0 for c in coords]):
			raise ValueError(f"Coordinates must be in the range of 0 to {self.coord_max}")

		index %= self.index_max  # sure, why not wrap around?

		msg = pack('<BH4B', uart.commands["write"], index, *coords)
		self.conn.write(msg)
		res = self.conn.read(1)
		return res == pack('B', uart.ack)
	
	def set_bounds(self, start_index, end_index):
		start_index %= self.index_max
		end_index %= self.index_max

		msg = pack('<B2H', uart.commands["set_bounds"], start_index, end_index)
		self.conn.write(msg)
		res = self.conn.read(1)
		return res == pack('B', uart.ack)
	
	def v_sync(self):
		self.conn.write(pack('B', uart.commands["vsync"]))
		res = self.conn.read(1)
		return res == pack('B', uart.ack)
	
	def blank(self):
		return self.set_bounds(0, 0)


def transform(segment):
	(xs, ys, xe, ye) = segment
	xs += 160//2
	ys += 120//2
	xe += 160//2
	ye += 120//2
	return (xs, ys, xe, ye)


def main(flash=True):
	if flash:
		print("Starting build...")
		build_and_run()
		sleep(2)

	gpu = GPUConnection("/dev/ttyUSB1")
	print("connected")

	points = [
		geometry.Point(20, 20),
		geometry.Point(20, -20),
		geometry.Point(-20, -20),
		geometry.Point(-20, 20),
	]
	edges = [
		(0,1),
		(1,2),
		(2,3),
		(3,0)
	]
	square = geometry.Mesh(points, edges)
	points = [
		geometry.Point(0, 25),
		geometry.Point(25, 0),
		geometry.Point(0, -25),
		geometry.Point(-25, 0),
	]
	square2 = geometry.Mesh(points, edges)


	gpu.blank()
	for i, seg in enumerate(square.serialize()):
		gpu.send_segment(i+1, transform(seg))

	for i, seg in enumerate(square2.serialize()):
		gpu.send_segment(i+1+len(edges), transform(seg))

	for _ in range(300):
		gpu.set_bounds(1, len(edges))
		gpu.set_bounds(len(edges)+1, len(edges)*2)
	
	gpu.blank()
	gpu.close()
	print("done!")


import sys
if __name__ == "__main__":
	if "--flash" in sys.argv:
		main(flash=True)
	else:
		main(flash=False)
