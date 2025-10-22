from migen import *
from migen.build.generic_platform import *
from migen.genlib.io import DifferentialInput
from migen.genlib.cdc import MultiReg

from migen.fhdl.module import _ModuleProxy

from artiq.gateware import rtio
from artiq.gateware.rtio.phy import spi2, dds


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


class UrukulDIOT(_DIOT):
    @staticmethod
    def io(slot, iostandard):
        ios = [
            ("urukul_diot{}_spi_p".format(slot), 0,
                Subsignal("clk", Pins(_diot_pin(slot, 0, "p"))),            # G1
                Subsignal("mosi", Pins(_diot_pin(slot, 1, "p"))),           # M1
                Subsignal("miso", Pins(_diot_pin(slot, 2, "p"))),           # K3
                Subsignal("cs_n", Pins(
                    *(_diot_pin(slot, i + 3, "p") for i in range(3)))),     # [H2, G2, E3 ]
                iostandard(slot),
            ),
            ("urukul_diot{}_spi_n".format(slot), 0,
                Subsignal("clk", Pins(_diot_pin(slot, 0, "n"))),
                Subsignal("mosi", Pins(_diot_pin(slot, 1, "n"))),
                Subsignal("miso", Pins(_diot_pin(slot, 2, "n"))),           # K1
                Subsignal("cs_n", Pins(
                    *(_diot_pin(slot, i + 3, "n") for i in range(3)))),
                iostandard(slot),
            ),
        ]
               
        ttls = [
                    # EEM 0
                    (6, slot, "io_update"),                             # D2
                    (7, slot, "dds_reset_sync_in", Misc("IOB=TRUE")),   # B2?

                    # EEM 1
                    (8, slot, "sync_clk"),                              # H1 ?
                     (9, slot, "sync_in"),                              # L1
                     (10, slot, "io_update_ret"),                        # J1 -> add io_update_ret_n as J2
                     (11, slot, "nu_mosi3"),                             # F2
                     (12, slot, "sw0"),                                  # E2
                     (13, slot, "sw1"),                                  # D1
                     (14, slot, "sw2"),                                  # C2
                     (15, slot, "sw3")]                                  # B1
        
        for i, j, sig, *extra_args in ttls:
            ios.append(
                ("urukul_diot{}_{}".format(slot, sig), 0,
                    Subsignal("p", Pins(_diot_pin(j, i, "p"))),
                    Subsignal("n", Pins(_diot_pin(j, i, "n"))),
                    iostandard(j), *extra_args
                ))
        return ios

    @staticmethod
    def io_qspi(slot, iostandard):
        ios = [
            ("urukul_diot{}_spi_p".format(slot), 0,
                Subsignal("clk", Pins(_diot_pin(slot, 0, "p"))),
                Subsignal("mosi", Pins(_diot_pin(slot, 1, "p"))),
                Subsignal("cs_n", Pins(
                    _diot_pin(slot, 3, "p"), _diot_pin(slot, 4, "p"))),
                iostandard(slot),
            ),
            ("urukul_diot{}_spi_n".format(slot), 0,
                Subsignal("clk", Pins(_diot_pin(slot, 0, "n"))),
                Subsignal("mosi", Pins(_diot_pin(slot, 1, "n"))),
                Subsignal("cs_n", Pins(
                    _diot_pin(slot, 3, "n"), _diot_pin(slot, 4, "n"))),
                iostandard(slot),
            ),
        ]
        ttls = [(6, slot, "io_update"),
                (7, slot, "dds_reset_sync_in"),
                (12, slot, "sw0"),
                (13, slot, "sw1"),
                (14, slot, "sw2"),
                (15, slot, "sw3")]
        for i, j, sig in ttls:
            ios.append(
                ("urukul_diot{}_{}".format(slot, sig), 0,
                    Subsignal("p", Pins(_diot_pin(j, i, "p"))),
                    Subsignal("n", Pins(_diot_pin(j, i, "n"))),
                    iostandard(j)
                ))
        ios += [
            ("urukul_diot{}_qspi_p".format(slot), 0,
                Subsignal("cs", Pins(_diot_pin(slot, 5, "p")), iostandard(slot)),
                Subsignal("clk", Pins(_diot_pin(slot, 2, "p")), iostandard(slot)),
                Subsignal("mosi0", Pins(_diot_pin(slot, 8, "p")), iostandard(slot)),
                Subsignal("mosi1", Pins(_diot_pin(slot, 9, "p")), iostandard(slot)),
                Subsignal("mosi2", Pins(_diot_pin(slot, 10, "p")), iostandard(slot)),
                Subsignal("mosi3", Pins(_diot_pin(slot, 11, "p")), iostandard(slot)),
            ),
            ("urukul_diot{}_qspi_n".format(slot), 0,
                Subsignal("cs", Pins(_diot_pin(slot, 5, "n")), iostandard(slot)),
                Subsignal("clk", Pins(_diot_pin(slot, 2, "n")), iostandard(slot)),
                Subsignal("mosi0", Pins(_diot_pin(slot, 8, "n")), iostandard(slot)),
                Subsignal("mosi1", Pins(_diot_pin(slot, 9, "n")), iostandard(slot)),
                Subsignal("mosi2", Pins(_diot_pin(slot, 10, "n")), iostandard(slot)),
                Subsignal("mosi3", Pins(_diot_pin(slot, 11, "n")), iostandard(slot)),
            ),
        ]
        return ios

    @classmethod
    def add_std(cls, target, slot, ttl_out_cls, dds_type, sync_gen_cls=None, iostandard=default_iostandard):
        cls.add_extension(target, slot, iostandard=iostandard)

        spi_phy = spi2.SPIMaster(target.platform.request("urukul_diot{}_spi_p".format(slot)),
            target.platform.request("urukul_diot{}_spi_n".format(slot)))
        target.submodules += spi_phy
        target.rtio_channels.append(rtio.Channel.from_phy(spi_phy, ififo_depth=4))

        pads = target.platform.request("urukul_diot{}_dds_reset_sync_in".format(slot))
        if sync_gen_cls is not None:  # AD9910 variant and SYNC_IN from slot
            phy = sync_gen_cls(pad=pads.p, pad_n=pads.n, ftw_width=4)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))

        pads = target.platform.request("urukul_diot{}_io_update".format(slot))
        io_upd_phy = ttl_out_cls(pads.p, pads.n)
        target.submodules += io_upd_phy
        target.rtio_channels.append(rtio.Channel.from_phy(io_upd_phy))

        dds_monitor = dds.UrukulMonitor(spi_phy, io_upd_phy, dds_type)
        target.submodules += dds_monitor
        spi_phy.probes.extend(dds_monitor.probes)

        for signal in "sw0 sw1 sw2 sw3".split():
            pads = target.platform.request("urukul_diot{}_{}".format(slot, signal))
            phy = ttl_out_cls(pads.p, pads.n)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))

