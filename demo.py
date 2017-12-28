#!/usr/bin/env python3

from migen import *
from migen.build.platforms import kc705
from migen.genlib.io import CRG

from microscope import *


class MicroscopeDemo(Module):
    def __init__(self, serial_pads, sys_clk_freq):
        counter = Signal(32)
        toggle1 = Signal()
        toggle2 = Signal()
        self.comb += [
            toggle1.eq(counter[29]),
            toggle2.eq(counter[28])
        ]
        self.sync += counter.eq(counter + 1)

        self.submodules += [
            add_probe_single("demo", "toggle1", toggle1),
            add_probe_single("demo", "toggle2", toggle2),
            add_probe_buffer("demo", "counter", counter)
        ]

        self.submodules += Microscope(serial_pads, sys_clk_freq)


def main():
    platform = kc705.Platform()
    top = MicroscopeDemo(platform.request("serial"), 1e9/platform.default_clk_period)
    clock = platform.request(platform.default_clk_name)
    top.submodules += CRG(clock)
    platform.build(top)


if __name__ == "__main__":
    main()
