Microscope
==========

A simple FPGA logic analyzer for Migen designs.

Microscope only requires two RS232 UART pins and a clock to work, and is highly
portable. It is the tool of choice when everything else in your FPGA is falling
apart. It is more feature-limited than C...scope, but it uses kilobytes instead
of gigabytes, and it will work without involving Intellectual Poverty (IP) or
drivers with more bugs than a rain forest.

Probes can be inserted anywhere in the target design using the ``add_probe_*``
global functions. Those functions return submodules that you must add to the
current module (this enables the probes to see the clock domains of the current
module).

The logic analyzer component ``Microscope`` can be instantiated anywhere in
the design, typically at the top-level. If ``Microscope`` is not instantiated,
or the probes are filtered out, then the probes generate no logic and can be
left in their respective cores without consuming FPGA resources.

Use the communication program ``microscope.py`` to read back data from the
probes.

See ``demo.py`` for an example design.
