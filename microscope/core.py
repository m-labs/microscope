from migen import *
from migen.genlib.fsm import *

from microscope.globals import registry as global_registry
from microscope.config import *
from microscope.uart import UART


class ConfigROM(Module):
    def __init__(self, data):
        self.data = Signal(8)
        self.next = Signal()
        self.reset = Signal()
        self.last = Signal()

        mem = Memory(8, len(data), init=data)
        port = mem.get_port()
        self.specials += mem, port

        current_address = Signal(max=len(data))
        self.sync += current_address.eq(port.adr)
        self.comb += [
            self.data.eq(port.dat_r),
            port.adr.eq(current_address),
            If(self.next,
                port.adr.eq(current_address + 1)
            ),
            If(self.reset,
                port.adr.eq(0)
            ),
            self.last.eq(current_address == len(data)-1)
        ]


class InsertMux(Module):
    def __init__(self, inserts):
        max_depth = max(getattr(insert, "depth", 1) for insert in inserts)
        max_width = max(len(insert.data) for insert in inserts)

        self.sel = Signal(max=len(inserts))
        self.arm = Signal()
        self.pending = Signal()
        self.address = Signal(max=max_depth)
        self.data = Signal(max_width)

        self.last_address = Signal(max=max(max_depth, 1))
        self.last_byte = Signal(max=max((max_width+7)//8, 1))

        # # #

        sel = self.sel
        self.comb += [
            self.pending.eq(Array(getattr(insert, "pending", 0) for insert in inserts)[sel]),
            self.data.eq(Array(insert.data for insert in inserts)[sel])
        ]
        for n, insert in enumerate(inserts):
            if hasattr(insert, "arm"):
                self.comb += insert.arm.eq(self.arm & (sel == n))
            if hasattr(insert, "address"):
                self.comb += insert.address.eq(self.address)
        self.comb += [
            self.last_address.eq(Array(getattr(insert, "depth", 1)-1 for insert in inserts)[sel]),
            self.last_byte.eq(Array((len(insert.data)+7)//8-1 for insert in inserts)[sel])
        ]


class SerialProtocolEngine(Module):
    def __init__(self, config_rom, imux, timeout_cycles):
        self.rx_data = Signal(8)
        self.rx_stb = Signal()

        self.tx_data = Signal(8)
        self.tx_stb = Signal()
        self.tx_ack = Signal()

        # # #

        timeout = Signal()
        timeout_counter = Signal(max=timeout_cycles + 1, reset=timeout_cycles)
        self.sync += [
            timeout.eq(0),
            If(self.tx_stb | self.rx_stb,
                timeout_counter.eq(timeout_cycles)
            ).Else(
                If(timeout_counter == 0,
                    timeout.eq(1),
                    timeout_counter.eq(timeout_cycles)
                ).Else(
                    timeout_counter.eq(timeout_counter - 1)
                )
            )
        ]
        
        next_address = Signal()
        reset_address = Signal()
        last_address = Signal()
        current_address = Signal.like(imux.address)
        self.sync += current_address.eq(imux.address)
        self.comb += [
            imux.address.eq(current_address),
            If(next_address,
                imux.address.eq(current_address + 1)
            ),
            If(reset_address,
                imux.address.eq(0)
            ),
            last_address.eq(current_address == imux.last_address)
        ]

        next_byte = Signal()
        reset_byte = Signal()
        last_byte = Signal()
        current_byte = Signal.like(imux.last_byte)
        data = Signal(8)
        nbytes = (len(imux.data)+7)//8
        self.sync += [
            If(next_byte,
                Case(current_byte, {
                    i: data.eq(imux.data[((i+1)*8):]) for i in range(nbytes-1)
                }),
                current_byte.eq(current_byte + 1)
            ),
            If(reset_byte,
                data.eq(imux.data),
                current_byte.eq(0)
            )
        ]
        self.comb += last_byte.eq(current_byte == imux.last_byte)

        imux_sel_load = Signal()
        self.sync += If(imux_sel_load, imux.sel.eq(self.rx_data))

        fsm = ResetInserter()(FSM())
        self.submodules += fsm
        self.comb += fsm.reset.eq(timeout)

        fsm.act("MAGIC1",
            If(self.rx_stb,
                If(self.rx_data == 0x1a,
                    NextState("MAGIC2")
                ).Else(
                    NextState("MAGIC1")
                )
            )
        )
        fsm.act("MAGIC2",
            If(self.rx_stb,
                If(self.rx_data == 0xe5,
                    NextState("MAGIC3")
                ).Else(
                    NextState("MAGIC1")
                )
            )
        )
        fsm.act("MAGIC3",
            If(self.rx_stb, 
                If(self.rx_data == 0x52,
                    NextState("MAGIC4")
                ).Else(
                    NextState("MAGIC1")
                )
            )
        )
        fsm.act("MAGIC4",
            If(self.rx_stb,
                If(self.rx_data == 0x9c,
                    NextState("COMMAND")
                ).Else(
                    NextState("MAGIC1")
                )
            )
        )
        fsm.act("COMMAND",
            config_rom.reset.eq(1),
            reset_address.eq(1),
            reset_byte.eq(1),
            If(self.rx_stb,
                Case(self.rx_data, {
                    0x00: NextState("SEND_CONFIG"),
                    0x01: NextState("SET_SEL"),
                    0x02: imux.arm.eq(1),
                    0x03: NextState("SEND_PENDING"),
                    0x04: NextState("SEND_DATA")
                })
            )
        )
        fsm.act("SEND_CONFIG",
            self.tx_stb.eq(1),
            self.tx_data.eq(config_rom.data),
            If(self.tx_ack,
                config_rom.next.eq(1),
                If(config_rom.last, NextState("MAGIC1"))
            )
        )
        fsm.act("SET_SEL",
            If(self.rx_stb,
                imux_sel_load.eq(1),
                NextState("MAGIC1")
            )
        )
        fsm.act("SEND_PENDING",
            self.tx_stb.eq(1),
            self.tx_data.eq(imux.pending),
            If(self.tx_ack, NextState("MAGIC1"))
        )
        fsm.act("SEND_DATA",
            self.tx_stb.eq(1),
            self.tx_data.eq(data),
            If(self.tx_ack,
                next_byte.eq(1),
                If(last_byte,
                    next_address.eq(1),
                    If(last_address,
                        NextState("MAGIC1")
                    ).Else(
                        NextState("RESET_BYTE")
                    )
                )
            )
        )
        fsm.act("RESET_BYTE",
            reset_byte.eq(1),
            NextState("SEND_DATA")
        )


class Microscope(Module):
    def __init__(self, serial_pads, sys_clk_freq, registry=None):
        self.serial_pads = serial_pads
        self.sys_clk_freq = sys_clk_freq
        if registry is None:
            registry = global_registry
        self.registry = registry

        self.clock_domains.cd_microscope = ClockDomain(reset_less=True)
        self.comb += self.cd_microscope.clk.eq(ClockSignal())

    def do_finalize(self):
        inserts = [insert for insert in self.registry.inserts
                   if self.registry.is_enabled(insert)]
        if not inserts:
            return
        for insert in inserts:
            insert.create_insert_logic()

        config_rom = ConfigROM(list(get_config_from_inserts(inserts)))
        imux = InsertMux(inserts)
        spe = SerialProtocolEngine(config_rom, imux, round(self.sys_clk_freq*50e-3))
        uart = UART(self.serial_pads, round((115200/self.sys_clk_freq)*2**32))
        self.submodules += config_rom, imux, spe, uart

        self.comb += [
            spe.rx_data.eq(uart.rx_data),
            spe.rx_stb.eq(uart.rx_stb),
            uart.tx_data.eq(spe.tx_data),
            uart.tx_stb.eq(spe.tx_stb),
            spe.tx_ack.eq(uart.tx_ack)
        ]
