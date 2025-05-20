from migen import *
from migen.genlib.cdc import MultiReg

from artiq.gateware.rtio import rtlink


class PmtSimTriggerGenerator(Module):
    def __init__(self, trigger_in, primary_triggers_out):
        # Address mapping:
        # a[0]: write not read
        # a[1..2] == 00: output trigger mask, 1 - trigger enabled, 0 - trigger disabled
        # a[1..2] == 01: trigger pulse length

        # Data width not less than 16
        data_width = max(16, len(primary_triggers_out))
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(
                data_width=data_width,
                address_width=2),
            rtlink.IInterface(
                data_width=data_width, 
                timestamped=False))
        
        # # #

        trigger_counter = Signal(16)
        trigger_length = Signal.like(trigger_counter, reset=10)
        trigger_mask = Signal(len(primary_triggers_out))
        trigger_in_d = Signal()
        trigger_active = Signal()

        # RTLink support

        self.sync.rio_phy += [
            self.rtlink.i.stb.eq(0),
            If(self.rtlink.o.stb,
                Case(self.rtlink.o.address[:2], {
                    0b01: trigger_mask.eq(self.rtlink.o.data),
                    0b00: self.rtlink.i.stb.eq(1),
                    0b11: trigger_length.eq(self.rtlink.o.data),
                    0b10: self.rtlink.i.stb.eq(1)
                })
            )
        ]

        self.comb += [
            Case(self.rtlink.o.address[1], {
                    0b0: self.rtlink.i.data.eq(trigger_mask),
                    0b1: self.rtlink.i.data.eq(trigger_length),
                })
        ]

        # Trigger logic

        self.sync.rio_phy += [
            If(~trigger_in_d & trigger_in,
                trigger_counter.eq(trigger_length)
            ).Elif(trigger_counter > 0,
                trigger_counter.eq(trigger_counter - 1)),
            trigger_in_d.eq(trigger_in)
        ]

        self.comb += [
            trigger_active.eq(trigger_counter > 0),
            primary_triggers_out.eq(
                Replicate(trigger_active, len(primary_triggers_out)) & trigger_mask
            )
        ]


def rtlink_write(rtlink, address, data):
    yield rtlink.o.stb.eq(1)
    yield rtlink.o.address.eq(address << 1 | 1)
    yield rtlink.o.data.eq(data)
    yield
    yield rtlink.o.stb.eq(0)


def rtlink_read(rtlink, address, wait=1):
    yield rtlink.o.stb.eq(1)
    yield rtlink.o.address.eq(address << 1 | 0)
    for i in range(wait): yield
    assert (yield rtlink.i.stb) == 1
    return (yield rtlink.i.data)


def tb(dut, trigger_in, triggers_out):
    # Test trigger mask setting
    yield from rtlink_write(dut.rtlink, 0, 0x2A)
    yield from rtlink_write(dut.rtlink, 1, 0x4)

    yield trigger_in.eq(1)
    yield
    yield trigger_in.eq(0)
    
    for i in range(30): yield

    yield trigger_in.eq(1)
    yield
    yield trigger_in.eq(0)

    for i in range(5): yield

    yield trigger_in.eq(1)
    yield
    yield trigger_in.eq(0)

    for i in range(30): yield


if __name__ == "__main__":
    from migen.sim import run_simulation
    trigger_in = Signal()
    triggers_out = Signal(6)
    dut = PmtSimTriggerGenerator(trigger_in, triggers_out)
    run_simulation(dut, tb(dut, trigger_in, triggers_out), 
                   vcd_name="pmtsimtrigger.vcd",
                   clocks={'sys': 8, 'rio_phy': 8})
