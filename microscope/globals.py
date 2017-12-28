from microscope.inserts import *


registry = InsertRegistry()


def add_probe_async(*args, **kwargs):
    return ProbeAsync(registry, *args, **kwargs)


def add_probe_single(*args, **kwargs):
    return ProbeSingle(registry, *args, **kwargs)


def add_probe_buffer(*args, **kwargs):
    return ProbeBuffer(registry, *args, **kwargs)
