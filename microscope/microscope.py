#!/usr/bin/env python3

import sys
import argparse
import struct

import serial
import msgpack
import prettytable


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
        return struct.unpack("?", self.ser.read(1))[0]

    def data(self, length):
        self.ser.write(Comm.magic + b"\x04")
        return self.ser.read(length)


def display_inserts(comm):
    config = comm.get_config()
    table = prettytable.PrettyTable(["Group", "Name", "Width", "Depth"])
    for group, name, width, depth in config["ins"]:
        group = config["grp"][group]
        table.add_row([group, name, width, depth])
    print(table)


def display_singles(comm):
    config = comm.get_config()
    table = prettytable.PrettyTable(["Group", "Name", "Value"])
    for i, (group, name, width, depth) in enumerate(config["ins"]):
        if depth == 1:
            comm.select(i)
            comm.arm()
            while comm.pending():
                pass
            data = comm.data((width+7)//8)
            value = int.from_bytes(data, "little")
            group = config["grp"][group]
            table.add_row([group, name, hex(value)])
    print(table)


def monitor_single(comm, q_group, q_name, q_n):
    config = comm.get_config()
    try:
        q_group = config["grp"].index(q_group)
    except IndexError:
        raise SystemExit("Group not found")
    found = None
    n = 0
    for i, (group, name, width, depth) in enumerate(config["ins"]):
        if group == q_group and name == q_name and depth == 1:
            if q_n is None or n == q_n:
                if found is not None:
                    raise SystemExit("More than one insert matches")
                found = i
    if found is None:
        raise SystemExit("Insert not found")

    _, _, width, _ = config["ins"][found]
    fmtstring = "{:0" + str((width+3)//4) + "x}"
    toggle = False
    comm.select(found)
    while True:
        comm.arm()
        while comm.pending():
            pass
        data = comm.data((width+7)//8)
        value = int.from_bytes(data, "little")
        print(("/ " if toggle else "\\ ") + fmtstring.format(value),
              end="\r", flush=True)
        toggle = not toggle


def display_buffer(comm, q_group, q_name, q_n):
    config = comm.get_config()
    try:
        q_group = config["grp"].index(q_group)
    except IndexError:
        raise SystemExit("Group not found")
    found = False
    n = 0
    for i, (group, name, width, depth) in enumerate(config["ins"]):
        if group == q_group and name == q_name:
            if q_n is None or n == q_n:
                found = True
                comm.select(i)
                comm.arm()
                print("waiting for trigger...", file=sys.stderr)
                while comm.pending():
                    pass
                print("done", file=sys.stderr)

                word_len = (width+7)//8
                data = comm.data(depth*word_len)
                print("[")
                for j in range(depth):
                    print(hex(int.from_bytes(data[j*word_len:(j+1)*word_len], "little")) + ",")
                print("]")
            n += 1
    if not found:
        raise SystemExit("Insert not found")


def main():
    parser = argparse.ArgumentParser(description="Microscope FPGA logic analyzer client")
    parser.add_argument("port", help="serial port URL (see open_for_url in pyserial)")
    subparsers = parser.add_subparsers(dest="action")
    subparsers.add_parser("inserts", help="list inserts available on the target device")
    subparsers.add_parser("singles", help="show current values of single-value inserts")
    parser_monitor = subparsers.add_parser("monitor", help="continously monitor the value of a single-value insert")
    parser_monitor.add_argument("group", metavar="GROUP")
    parser_monitor.add_argument("name", metavar="NAME")
    parser_monitor.add_argument("-n", type=int, default=None,
                                help="index (in case of multiple matches)")
    parser_buffer = subparsers.add_parser("buffer", help="show values of a buffering insert")
    parser_buffer.add_argument("group", metavar="GROUP")
    parser_buffer.add_argument("name", metavar="NAME")
    parser_buffer.add_argument("-n", type=int, default=None,
                               help="index (in case of multiple matches)")
    args = parser.parse_args()

    comm = Comm(args.port)
    try:
        if args.action is None or args.action == "inserts":
            display_inserts(comm)
        elif args.action == "singles":
            display_singles(comm)
        elif args.action == "monitor":
            monitor_single(comm, args.group, args.name, args.n)
        elif args.action == "buffer":
            display_buffer(comm, args.group, args.name, args.n)
    finally:
        comm.close()


if __name__ == "__main__":
    main()
