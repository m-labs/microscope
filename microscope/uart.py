from migen import *


class UART(Module):
	def __init__(self, pads, tuning_word):
		self.rx_data = Signal(8)
        self.rx_stb = Signal()

        self.tx_data = Signal(8)
        self.tx_stb = Signal()
        self.tx_ack = Signal()

		# # #

		#
		# RX
		#

		uart_clk_rxen = Signal()
        phase_accumulator_rx = Signal(32)

        rx = Signal()
        self.specials += MultiReg(pads.rx, rx)
        rx_r = Signal()
        rx_reg = Signal(8)
        rx_bitcount = Signal(4)
        rx_busy = Signal()
        rx_done = self.rx_stb
        rx_data = self.rx_data
        self.sync += [
            rx_done.eq(0),
            rx_r.eq(rx),
            If(~rx_busy,
                If(~rx & rx_r,  # look for start bit
                    rx_busy.eq(1),
                    rx_bitcount.eq(0),
                )
            ).Else(
                If(uart_clk_rxen,
                    rx_bitcount.eq(rx_bitcount + 1),
                    If(rx_bitcount == 0,
                        If(rx,  # verify start bit
                            rx_busy.eq(0)
                        )
                    ).Elif(rx_bitcount == 9,
                        rx_busy.eq(0),
                        If(rx,  # verify stop bit
                            rx_data.eq(rx_reg),
                            rx_done.eq(1)
                        )
                    ).Else(
                        rx_reg.eq(Cat(rx_reg[1:], rx))
                    )
                )
            )
        ]
        self.sync += \
            If(rx_busy,
                Cat(phase_accumulator_rx, uart_clk_rxen).eq(phase_accumulator_rx + tuning_word)
            ).Else(
                Cat(phase_accumulator_rx, uart_clk_rxen).eq(2**31)
            )

        #
        # TX
        #
        uart_clk_txen = Signal()
        phase_accumulator_tx = Signal(32)

        pads.tx.reset = 1

        tx_reg = Signal(8)
        tx_bitcount = Signal(4)
        tx_busy = Signal()
        self.sync += [
            self.tx_ack.eq(0),
            If(self.tx_stb & ~tx_busy & ~self.tx_ack,
                tx_reg.eq(self.sink.data),
                tx_bitcount.eq(0),
                tx_busy.eq(1),
                pads.tx.eq(0)
            ).Elif(uart_clk_txen & tx_busy,
                tx_bitcount.eq(tx_bitcount + 1),
                If(tx_bitcount == 8,
                    pads.tx.eq(1)
                ).Elif(tx_bitcount == 9,
                    pads.tx.eq(1),
                    tx_busy.eq(0),
                    self.tx_ack.eq(1),
                ).Else(
                    pads.tx.eq(tx_reg[0]),
                    tx_reg.eq(Cat(tx_reg[1:], 0))
                )
            )
        ]
        self.sync += \
            If(tx_busy,
                Cat(phase_accumulator_tx, uart_clk_txen).eq(phase_accumulator_tx + tuning_word)
            ).Else(
                Cat(phase_accumulator_tx, uart_clk_txen).eq(0)
            )
