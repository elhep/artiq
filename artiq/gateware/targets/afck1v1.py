#!/usr/bin/env python3

import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import MultiReg
from migen.build.generic_platform import *
from migen.genlib.io import DifferentialOutput
from migen.build.generic_platform import *

from misoc.interconnect.csr import *
from misoc.cores import gpio
from misoc.cores.a7_gtp import *
from misoc.targets.afck1v1 import MiniSoC, BaseSoC, soc_afck1v1_argdict, soc_afck1v1_args
from misoc.integration.soc_sdram import soc_sdram_argdict
from misoc.integration.builder import builder_args, builder_argdict

from artiq.gateware.amp import AMPSoC
from artiq.gateware import rtio
from artiq.build_soc import build_artiq_soc, add_identifier
from artiq.gateware.rtio.phy.ttl_simple import Output


iostd_single = {
    "fmc1_LA": [IOStandard("LVCMOS25")],
    "fmc1_HA": [IOStandard("LVCMOS25")],
    "fmc1_HB": [IOStandard("LVCMOS25")],
    "fmc2_LA": [IOStandard("LVCMOS25")],
    "fmc2_HA": [IOStandard("LVCMOS25")],
    "fmc2_HB": [IOStandard("LVCMOS18")]
}

iostd_diff = {
    "fmc1_LA": [IOStandard("LVDS_25"), Misc("DIFF_TERM=TRUE")],
    "fmc1_HA": [IOStandard("LVDS_25"), Misc("DIFF_TERM=TRUE")],
    "fmc1_HB": [IOStandard("LVDS_25"), Misc("DIFF_TERM=TRUE")],
    "fmc2_LA": [IOStandard("LVDS_25"), Misc("DIFF_TERM=TRUE")],
    "fmc2_HA": [IOStandard("LVDS_25"), Misc("DIFF_TERM=TRUE")],
    "fmc2_HB": [IOStandard("LVDS"), Misc("DIFF_TERM=TRUE")],
}


class CRG(Module):
    def __init__(self, platform):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_rtio = ClockDomain()
        self.clock_domains.cd_sys4x = ClockDomain(reset_less=True)
        self.clock_domains.cd_rtiox4 = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x_dqs = ClockDomain(reset_less=True)
        self.clock_domains.cd_clk200 = ClockDomain()
        clk125 = platform.request("fpga_clk")  #TODO: Check with schematics
        platform.add_period_constraint(clk125, 8.)
        self.clk125_buf = Signal()
        self.specials += [
            Instance("IBUFGDS",
                     p_DIFF_TERM="TRUE", p_IBUF_LOW_PWR="TRUE",
                     i_I=clk125.p, i_IB=clk125.n, o_O=self.clk125_buf),
        ]
        self.mmcm_locked = mmcm_locked = Signal()
        mmcm_fb = Signal()
        mmcm_sys = Signal()
        mmcm_sys4x = Signal()
        mmcm_sys4x_dqs = Signal()
        mmcm_clk200 = Signal()
        self.specials += [
            Instance("MMCME2_BASE",
                p_CLKIN1_PERIOD=8.0,
                i_CLKIN1=self.clk125_buf,

                i_CLKFBIN=mmcm_fb,
                o_CLKFBOUT=mmcm_fb,
                o_LOCKED=mmcm_locked,

                # VCO @ 1GHz with MULT=16
                p_CLKFBOUT_MULT_F=8, p_DIVCLK_DIVIDE=1,

                # ~125MHz
                p_CLKOUT0_DIVIDE_F=8.0, p_CLKOUT0_PHASE=0.0, o_CLKOUT0=mmcm_sys,

                # ~500MHz. Must be more than 400MHz as per DDR3 specs.
                p_CLKOUT1_DIVIDE=2, p_CLKOUT1_PHASE=0.0, o_CLKOUT1=mmcm_sys4x,

                # ~200MHz for IDELAYCTRL. Datasheet specified tolerance +/- 10MHz.
                p_CLKOUT2_DIVIDE=5, p_CLKOUT2_PHASE=0.0, o_CLKOUT2=mmcm_clk200,

                p_CLKOUT3_DIVIDE=2, p_CLKOUT3_PHASE=90.0, o_CLKOUT3=mmcm_sys4x_dqs,
            ),
            Instance("BUFG", i_I=mmcm_sys, o_O=self.cd_sys.clk),
            Instance("BUFG", i_I=mmcm_sys, o_O=self.cd_rtio.clk),
            Instance("BUFG", i_I=mmcm_sys4x, o_O=self.cd_rtiox4.clk),
            Instance("BUFG", i_I=mmcm_sys4x, o_O=self.cd_sys4x.clk),
            Instance("BUFG", i_I=mmcm_sys4x_dqs, o_O=self.cd_sys4x_dqs.clk),
            Instance("BUFG", i_I=mmcm_clk200, o_O=self.cd_clk200.clk),
            AsyncResetSynchronizer(self.cd_sys, ~mmcm_locked),
            AsyncResetSynchronizer(self.cd_clk200, ~mmcm_locked),
        ]

        reset_counter = Signal(4, reset=15)
        ic_reset = Signal(reset=1)
        self.sync.clk200 += \
            If(reset_counter != 0,
                reset_counter.eq(reset_counter - 1)
            ).Else(
                ic_reset.eq(0)
            )
        self.specials += Instance("IDELAYCTRL", i_REFCLK=ClockSignal("clk200"), i_RST=ic_reset)

        platform.add_period_constraint(self.cd_sys.clk, 8.)
        platform.add_period_constraint(self.cd_rtio.clk, 8.)
        platform.add_period_constraint(self.cd_rtiox4.clk, 2.)



def fix_serdes_timing_path(platform):
    # ignore timing of path from OSERDESE2 through the pad to ISERDESE2
    platform.add_platform_command(
        "set_false_path -quiet "
        "-through [get_pins -filter {{REF_PIN_NAME == OQ || REF_PIN_NAME == TQ}} "
            "-of [get_cells -filter {{REF_NAME == OSERDESE2}}]] "
        "-to [get_pins -filter {{REF_PIN_NAME == D}} "
            "-of [get_cells -filter {{REF_NAME == ISERDESE2}}]]"
    )


class TestMod(Module, AutoCSR):

    def __init__(self):
        self.ledg = CSRStorage(size=1)
        self.ledb = CSRStorage(size=1)
        self.dummy = CSRStorage(size=55)


class StandaloneBase(MiniSoC, AMPSoC):
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x20000000,
        "rtio_dma":      0x30000000,
        "mailbox":       0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, **kwargs):
        MiniSoC.__init__(self,
                         cpu_type="or1k",
                         sdram_controller_type="minicon",
                         l2_size=128*1024,
                         integrated_sram_size=8192,
                         ethmac_nrxslots=4,
                         ethmac_ntxslots=4,
                         cpu_reset_address=0x000000, # 0x800000
                         crg=CRG,
                         **kwargs)
        AMPSoC.__init__(self)
        add_identifier(self)

        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["no_flash_boot"] = 1

        self.rtio_channels = []
        self.rtio_channel_labels = []
        self.add_design()
        self.print_rtio_channels()

        self.config["RTIO_FREQUENCY"] = "125.0"

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(self.rtio_channels)
        self.rtio_channels.append(rtio.LogChannel())

        self.add_rtio(self.rtio_channels)

    def add_rtio_channels(self, channels, names):
        if not isinstance(channels, list):
            channels = [channels]
        if not isinstance(names, list):
            names = [names]
        self.rtio_channels += channels
        self.rtio_channel_labels += names

    def add_design(self):
        pass

    def print_rtio_channels(self):
        if len(self.rtio_channels) != len(self.rtio_channel_labels):
            raise RuntimeError("Missing RTIO channel label(s)")
        with open("rtio_channels.txt", "w+") as f:
            print("RTIO channels:")
            for ch, label in enumerate(self.rtio_channel_labels):
                print(" - {:3d} : {}".format(ch, label))
                f.write("{:3d} : {}".format(ch, label))       

    def add_rtio(self, rtio_channels):
        fix_serdes_timing_path(self.platform)
        self.submodules.rtio_tsc = rtio.TSC("async", glbl_fine_ts_width=3)
        self.submodules.rtio_core = rtio.Core(self.rtio_tsc, rtio_channels)
        self.csr_devices.append("rtio_core")
        self.submodules.rtio = rtio.KernelInitiator(self.rtio_tsc)
        self.submodules.rtio_dma = ClockDomainsRenamer("sys_kernel")(
            rtio.DMA(self.get_native_sdram_if()))
        self.register_kernel_cpu_csrdevice("rtio")
        self.register_kernel_cpu_csrdevice("rtio_dma")
        self.submodules.cri_con = rtio.CRIInterconnectShared(
            [self.rtio.cri, self.rtio_dma.cri],
            [self.rtio_core.cri])
        self.register_kernel_cpu_csrdevice("cri_con")

        # Only add MonInj core if there is anything to monitor
        if any([len(c.probes) for c in rtio_channels]):
            self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
            self.csr_devices.append("rtio_moninj")

        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk)

        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_tsc, self.rtio_core.cri,
                                                      self.get_native_sdram_if())
        self.csr_devices.append("rtio_analyzer")


class _RTIOClockMultiplier(Module):
    def __init__(self, rtio_clk_freq):
        self.clock_domains.cd_rtiox4 = ClockDomain(reset_less=True)

        # See "Global Clock Network Deskew Using Two BUFGs" in ug472.
        clkfbout = Signal()
        clkfbin = Signal()
        rtiox4_clk = Signal()
        self.specials += [
            Instance("MMCME2_BASE",
                p_CLKIN1_PERIOD=1e9/rtio_clk_freq,
                i_CLKIN1=ClockSignal("rtio"),
                i_RST=ResetSignal("rtio"),

                p_CLKFBOUT_MULT_F=8.0, p_DIVCLK_DIVIDE=1,

                o_CLKFBOUT=clkfbout, i_CLKFBIN=clkfbin,

                p_CLKOUT0_DIVIDE_F=2.0, o_CLKOUT0=rtiox4_clk,
            ),
            Instance("BUFG", i_I=clkfbout, o_O=clkfbin),
            Instance("BUFG", i_I=rtiox4_clk, o_O=self.cd_rtiox4.clk)
        ]


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder for AFCK 1v1 systems")
    builder_args(parser)
    soc_afck1v1_args(parser)
    parser.set_defaults(output_dir="artiq_afck1v1")
    args = parser.parse_args()

    soc = StandaloneBase(**soc_afck1v1_argdict(args))
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
