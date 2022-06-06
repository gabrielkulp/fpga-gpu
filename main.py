#!/usr/bin/env python3
from serial import Serial
from typing import Tuple
from time import sleep
from struct import pack
from top import build_and_run

import uart


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
		self.conn.write(uart.commands["ping"].to_bytes(1, 'big'))
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


def main():
	print("Starting build...")
	build_and_run()

	sleep(2)

	gpu = GPUConnection("/dev/ttyUSB1")
	print("connected")
	input()
	assert gpu.send_segment(0, (30, 50, 100, 90))
	input()
	assert gpu.send_segment(1, (30, 50, 110, 80))
	input()
	assert gpu.send_segment(2, (30, 50, 80, 80))
	input()
	assert gpu.send_segment(3, (30, 50, 60, 80))
	input()
	assert gpu.set_bounds(2, 3)
	gpu.close()
	print("done!")


if __name__ == "__main__":
	main()