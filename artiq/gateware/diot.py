from migen import *
from migen.build.generic_platform import *
from migen.genlib.io import DifferentialInput
from migen.genlib.cdc import MultiReg

from migen.fhdl.module import _ModuleProxy

from artiq.gateware import rtio


def _diot_signal(i):
    n = "d{}".format(i)
    if i in [0, 8]:
        n += "_cc"
    return n


def _diot_pin(slot, i, pol):
    return "diot{}:{}_{}".format(slot, _diot_signal(i), pol)


def default_iostandard(slot):
    return IOStandard("LVDS_25")


class _DIOT:
    @classmethod
    def add_extension(cls, target, slot, *args, is_drtio_over_diot=False, **kwargs):
        name = cls.__name__
        target.platform.add_extension(cls.io(slot, *args, **kwargs))
        if is_drtio_over_diot:
            print("{} (SLOT{}) starting at DRTIO channel 0x{:06x}"
                .format(name, slot, (len(target.gt_drtio.channels) + len(target.eem_drtio_channels) + 1) << 16))
        else:
            print("{} (SLOT{}) starting at RTIO channel 0x{:06x}"
                .format(name, slot, len(target.rtio_channels)))


class OhwrDiotLoopback(_DIOT):
    @staticmethod
    def io(slot, iostandard):
        return [("ohwr_loopback{}".format(slot), i,
            Subsignal("p", Pins(_diot_pin(slot, i, "p"))),
            Subsignal("n", Pins(_diot_pin(slot, i, "n"))),
            iostandard(slot))
            for i in range(16)]

    @classmethod
    def add_std(cls, target, slot, ttl_input_cls, ttl_output_cls, edge_counter_cls,
                iostandard=default_iostandard):
        cls.add_extension(target, slot, iostandard=iostandard)

        phys = []

        # First LVDS pair is routed to clock on the loopback
        pads = target.platform.request("ohwr_loopback{}".format(slot), 0)

        class ClockDiv(Module):
            def __init__(self, pads):
                self.out = Signal()

                # # #

                self.clock_domains.fmeter = ClockDomain(reset_less=True)
                self.specials += DifferentialInput(pads.p, pads.n, self.fmeter.clk)
                
                cnt = Signal(8)
                self.sync.fmeter += [ cnt.eq(cnt + 1) ]
                self.specials += MultiReg(cnt[-1], self.out, "rio_phy")

        clkdiv = ClockDiv(pads)
        setattr(target.submodules, f"clkdiv{slot}", clkdiv)

        counter = edge_counter_cls(clkdiv.out)
        target.submodules += counter
        target.rtio_channels.append(rtio.Channel.from_phy(counter))

        # LVDS15 os not supported on OHWR DIOT Loopback
        for i in range(7):
            pads = target.platform.request("ohwr_loopback{}".format(slot), 1 + 2 * i + 0)
            phy = ttl_output_cls(pads.p, pads.n)
            phys.append(phy)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))

            pads = target.platform.request("ohwr_loopback{}".format(slot), 1 + 2 * i + 1)
            phy = ttl_input_cls(pads.p, pads.n)
            phys.append(phy)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))
