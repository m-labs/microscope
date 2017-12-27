import msgpack

from microscope.inserts import *


__all__ = ["get_config_from_inserts"]


def get_config_from_inserts(inserts):
    config_groups = []
    for insert in inserts:
        if insert.group not in config_groups:
            config_groups.append(insert.group)

    config_inserts = []
    for insert in inserts:
        element = [config_groups.index(insert.group),
                   insert.name]
        if isinstance(insert, ProbeSingle):
            element += [len(insert.data), 1]
        elif isinstance(insert, ProbeBuffer):
            element += [len(insert.data), insert.depth]
        else:
            raise ValueError
        config_inserts.append(element)

    config = {
        "grp": config_groups,
        "ins": config_inserts
    }
    return msgpack.packb(config)
