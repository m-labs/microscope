#!/usr/bin/env python3

import argparse
import serial
import msgpack
import struct


class Comm:
    magic = b"\x1a\xe5\x52\x9c"

    def __init__(self, port_url):
        self.ser = serial.serial_for_url(port_url, baudrate=115200)

    def close(self):
        self.ser.close()

    def get_config(self):
        self.ser.write(Comm.magic + b"\x00")
        return next(msgpack.Unpacker(self.ser, read_size=1))

    def select(self, insert):
        self.ser.write(Comm.magic + b"\x01" + struct.pack("B", insert))

    def arm(self):
        self.ser.write(Comm.magic + b"\x02")

    def pending(self):
        self.ser.write(Comm.magic + b"\x03")
        return struct.unpack("?", ser.read(1))[0]

    def data(self, len):
        self.ser.write(Comm.magic + b"\x04")
        return ser.read(len)


def main():
    parser = argparse.ArgumentParser(description="Microscope FPGA logic analyzer client")
    parser.add_argument("port", help="serial port")
    args = parser.parse_args()

    comm = Comm(args.port)
    try:
        print(comm.get_config())
    finally:
        comm.close()


if __name__ == "__main__":
    main()
