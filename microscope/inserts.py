from migen import *
from migen.genlib.cdc import PulseSynchronizer, MultiReg


__all__ = ["InsertRegistry", "ProbeAsync", "ProbeSingle", "ProbeBuffer"]


class InsertRegistry:
    def __init__(self):
        self.filter = None
        self.inserts = []

    def is_enabled(self, insert):
        if self.filter is None:
            return True
        else:
            return insert.group in self.filter

    def register(self, insert):
        self.inserts.append(insert)


class Insert(Module):
    def __init__(self, registry, group, name):
        self.group = group
        self.name = name
        registry.register(self)

    def create_insert_logic(self):
        raise NotImplementedError


class ProbeAsync(Insert):
    def __init__(self, registry, group, name, target):
        Insert.__init__(self, registry, group, name)
        self.target = target

    def create_insert_logic(self):
        self.data = Signal.like(self.target)
        self.specials += MultiReg(self.target, self.data, "microscope")


class ProbeSingle(Insert):
    def __init__(self, registry, group, name, target, clock_domain="sys"):
        Insert.__init__(self, registry, group, name)
        self.target = target
        self.clock_domain = clock_domain

    def create_insert_logic(self):
        self.arm = Signal()
        self.pending = Signal()
        self.data = Signal.like(self.target)

        buf = Signal.like(self.target)
        buf.attr.add("no_retiming")
        self.specials += MultiReg(buf, self.data, "microscope")

        ps_arm = PulseSynchronizer("microscope", self.clock_domain)
        ps_done = PulseSynchronizer(self.clock_domain, "microscope")
        self.submodules += ps_arm, ps_done
        self.comb += ps_arm.i.eq(self.arm)
        self.sync.microscope += [
            If(ps_done.o, self.pending.eq(0)),
            If(self.arm, self.pending.eq(1))
        ]

        sync = getattr(self.sync, self.clock_domain)
        sync += [
            ps_done.i.eq(0),
            If(ps_arm.o,
                buf.eq(self.target),
                ps_done.i.eq(1)
            )
        ]


class ProbeBuffer(Insert):
    def __init__(self, registry, group, name, target, trigger=1, depth=256, clock_domain="sys"):
        Insert.__init__(self, registry, group, name)
        self.target = target
        self.trigger = trigger
        self.depth = depth
        self.clock_domain = clock_domain

    def create_insert_logic(self):
        self.arm = Signal()
        self.pending = Signal()
        self.address = Signal(max=self.depth)
        self.data = Signal(len(self.target))
        self.specials.memory = Memory(len(self.target), self.depth)

        rdport = self.memory.get_port(clock_domain="microscope")
        self.specials += rdport
        self.comb += [
            rdport.adr.eq(self.address),
            self.data.eq(rdport.dat_r)
        ]

        ps_arm = PulseSynchronizer("microscope", self.clock_domain)
        ps_done = PulseSynchronizer(self.clock_domain, "microscope")
        self.submodules += ps_arm, ps_done
        self.comb += ps_arm.i.eq(self.arm)
        self.sync.microscope += [
            If(ps_done.o, self.pending.eq(0)),
            If(self.arm, self.pending.eq(1))
        ]

        port = self.memory.get_port(write_capable=True,
                                    clock_domain=self.clock_domain)
        self.specials += port

        running = Signal()
        wait_trigger = Signal()
        sync = getattr(self.sync, self.clock_domain)
        sync += [
            ps_done.i.eq(0),
            If(running,
                port.adr.eq(port.adr + 1),
                If(port.adr == self.depth-1,
                    running.eq(0),
                    ps_done.i.eq(1)
                )
            ),
            If(wait_trigger & self.trigger,
                running.eq(1),
                wait_trigger.eq(0)
            ),
            If(ps_arm.o,
                wait_trigger.eq(1)
            )
        ]
        self.comb += [
            port.we.eq(running),
            port.dat_w.eq(self.target)
        ]
