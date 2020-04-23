"""RTIO driver for Phaser
"""

from artiq.language.core import kernel, delay
from artiq.language.units import us, ms
from artiq.language.types import TInt32, TNone

from numpy import int32

from artiq.coredevice import spi2 as spi


SPI_CONFIG = (0*spi.SPI_OFFLINE | 0*spi.SPI_END |
              0*spi.SPI_INPUT | 1*spi.SPI_CS_POLARITY |
              0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
              0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)

# SPI clock write and read dividers
SPIT_WR = 4
SPIT_RD = 16

SPI_CS = 1

WE = 1 << 24

EXT_DAC  = 5
EXT_MOD0 = 6
EXT_MOD1 = 7
EXT_ATT0 = 8
EXT_ATT1 = 9

# (ADDRESS, OFFSET, LENGTH)
REG_TERM = (0x0, 0, 2)
REG_HW_REV = (0x0, 2, 4)
REG_PROTO_REV = (0x0, 6, 2)
REG_ASSY_VAR = (0x0, 8, 1)

REG_LED = (0x1, 0, 6)
REG_CLK_SEL = (0x1, 6, 1)
REG_ATT_RSTn = (0x1, 7, 2)

REG_DAC_TX_ENA = (0x2,0,1)
REG_DAC_SLEEP = (0x2,1,1)
REG_DAC_RESETn = (0x2,2,1)
REG_DAC_ALARM = (0x2,3,1)
REG_DAC_PLAY = (0x2,4,1)
REG_DAC_IFRSTn = (0x2,5,1)
REG_DAC_TEST_ENA = (0x2,6,1)

REG_MOD_POWER_SAVE = (0x4, 0, 2)
REG_MOD_LOCK_DET = (0x4, 2, 2)



class Phaser:
    """Phaser RF generator.

    :param spi_device: SPI bus device
    :param core_device: Core device name (default: "core")
    """
    kernel_invariants = {"bus", "core"}

    def __init__(self, dmgr, spi_device, variant, core_device="core"):
        self.core = dmgr.get(core_device)
        self.bus = dmgr.get(spi_device)
        self.variant = variant
        if variant not in ["baseband", "upconverter"]:
            raise ValueError("Invalid variant")

    @kernel
    def read_reg(self, addr):
        """Read a register"""
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_INPUT | spi.SPI_END, 24,
                               SPIT_RD, SPI_CS)
        self.bus.write((addr << 25))
        return self.bus.read() & int32(0xffff)

    @kernel
    def write_reg(self, addr, data):
        """Write a register"""
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END, 24, SPIT_WR, SPI_CS)
        self.bus.write((addr << 25) | WE | ((data & 0xffff) << 8))

    @kernel
    def write_ext(self, addr, length, data):
        """Perform SPI write to a prefixed address"""
        self.bus.set_config_mu(SPI_CONFIG, 8, SPIT_WR, SPI_CS)
        self.bus.write(addr << 25)
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END, length,
                               SPIT_WR, SPI_CS)
        if length < 32:
            data <<= 32 - length
        self.bus.write(data)

    @kernel
    def read_ext(self, addr, length, data):
        self.bus.set_config_mu(SPI_CONFIG, 8, SPIT_WR, SPI_CS)
        self.bus.write(addr << 25)
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END | spi.SPI_INPUT, length,
                               SPIT_RD, SPI_CS)
        self.bus.write(data << 8)

        return self.bus.read()

    @kernel
    def write_dac(self, addr, data):
        """Write DAC configuration register"""
        self.write_ext(EXT_DAC, 24, ((addr & 0xFF) << 16) | data)
        delay(10*us)

    @kernel
    def read_dac(self, addr):
        """Read from DAC configuration register"""
        r = self.read_ext(EXT_DAC, 24, ((1 << 7) | addr) << 16)
        delay(20*us)
        return r

    @kernel
    def write_mod(self, mod, addr, data):
        """Write modulator configuration register"""
        # self.write_ext(EXT_MOD0+mod, 32, (data << 5) | (1 << 3) | (addr & 0x7))

        self.bus.set_config_mu(SPI_CONFIG, 8, SPIT_WR, SPI_CS)
        self.bus.write(EXT_MOD0+mod << 25)

        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END | spi.SPI_LSB_FIRST, 32,
                               SPIT_WR*16, SPI_CS)
        self.bus.write(data << 5 | (1 << 3) | (addr & 0x7))

    @kernel
    def read_mod(self, mod, addr):
        """Read from modulator configuration register"""
        # self.bus.set_config_mu(SPI_CONFIG, 8, SPIT_WR, SPI_CS)
        # self.bus.write(EXT_MOD0+mod << 25)

        # self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END | spi.SPI_LSB_FIRST, 32,
        #                        SPIT_WR*16, SPI_CS)
        # self.bus.write((1 << 31) | (addr & 0x7) << 28 | 0b01000)
        self.write_mod(mod, 0, 1 << 26 | (addr & 0x7) << 23)

        self.bus.set_config_mu(SPI_CONFIG, 8, SPIT_WR, SPI_CS)
        self.bus.write(EXT_MOD0+mod << 25)

        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_CLK_PHASE, 1, SPIT_WR*16, SPI_CS)
        self.bus.write(0)

        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_CLK_PHASE | spi.SPI_INPUT | spi.SPI_END | spi.SPI_LSB_FIRST, 32,
                        SPIT_WR*16, SPI_CS)
        self.bus.write(0)
        delay_mu(5000)

        # Workaround for register read failure after clock polarity change
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END, 8, SPIT_WR, 0x0)
        self.bus.write(0)

        r = self.bus.read()
        delay(10*us)

        # Disable 
        # self.bus.set_config_mu(SPI_CONFIG, 8, SPIT_WR, SPI_CS)
        # self.bus.write(EXT_MOD0+mod << 25)

        # self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END | spi.SPI_LSB_FIRST, 32,
        #                        SPIT_WR*16, SPI_CS)
        # self.bus.write(0x0 | 0b01000)
        self.write_mod(mod, 0, 0)

        return r
        
    @kernel
    def dac_check_iopattern(self):
        self.write_dac(0x4, 0)
        delay(10*ms)
        r = self.read_dac(0x4)
        delay(10*us)
        return r == 0

    @kernel
    def write_field(self, field, value):
        addr, offset, length = field
        r = self.read_reg(addr)
        delay(1000*us)
        mask = (2**length-1)
        r &= ~(mask << offset)
        r |= (value & mask) << offset
        self.write_reg(addr, r)

    @kernel
    def read_field(self, field) -> TInt32:
        addr, offset, length = field
        r = self.read_reg(addr)
        delay(20*us)
        mask = (2**length-1)
        return (r >> offset) & mask

    @kernel
    def init(self):
        """Initialize Phaser by reading the status register and verifying
        compatible hardware and protocol revisions"""
    
        if self.read_field(REG_HW_REV) > 1:
            raise ValueError("Unsupported board version")

        if self.read_field(REG_PROTO_REV) > 0:
            raise ValueError("Unsupported protocol version")

        if self.read_field(REG_PROTO_REV) > 0:
            raise ValueError("Unsupported protocol version")
        
        if self.read_field(REG_ASSY_VAR) == 0:
            # Check MOD communication
            if (self.read_mod(0, 0) & 0x7F) != 0x68:
                raise ValueError("MOD0 readout failure")
            if (self.read_mod(1, 0) & 0x7F) != 0x68:
                raise ValueError("MOD0 readout failure")

        # Disable ATT reset
        self.write_field(REG_ATT_RSTn, 0x3)

        # DAC initialization
        self.write_field(REG_DAC_RESETn, 0)
        self.write_field(REG_DAC_IFRSTn, 0)
        delay(10*us)
        self.write_field(REG_DAC_RESETn, 1)
        self.write_field(REG_DAC_IFRSTn, 1)
        delay(10*us)
        
        # Enable DAC 4-wire interface
        self.write_dac(0x2, 0x7080)

        # Check DAC communication
        if self.read_dac(0x7F) != 0x5409:
            raise ValueError("DAC version mismatch")
             
        # iotest_ena = 1, 64cnt_ena = 1
        self.write_dac(0x1, 0x040E | (1 << 15) | (1 << 12))
        
        self.write_field(REG_DAC_TEST_ENA, 1)
        self.write_field(REG_DAC_PLAY, 1)
        delay(10*us)
        self.write_dac(0x5, 0)
        delay(100*ms)
        r = self.read_dac(0x5)

        if r & (1 << 7) != 0:
            print("DAC LVDS interface failed")
            raise ValueError("DAC LVDS interface failed")

        # disable iotest
        self.write_dac(0x1, 0x040E | (1 << 12))
        self.write_field(REG_DAC_TEST_ENA, 0)
        self.write_field(REG_DAC_PLAY, 0)

        # self.write_field(REG_DAC_PLAY, 1)
        
        
        # self.set_att_mu(0, 0x0)
        # self.set_att_mu(1, 0x0)

    @kernel
    def set_att_mu(self, channel, att):
        """Set digital step attenuator in machine units.

        :param att: Attenuation setting, 8 bit digital.
        """
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END, 16, SPIT_WR, SPI_CS)
        self.bus.write(((EXT_ATT0 + channel) << 25) | (att << 16))

    @kernel
    def dac_enable_generation(self):
        
        self.write_field(REG_CLK_SEL, 0) # clock from SMA
        self.write_field(REG_DAC_TX_ENA, 0)

        self.write_dac(0x0, 0x0080) # interpolation 1x, fifo enabled
        self.write_dac(0x1, 0x100E) # 64cnt_ena, alarm_*away_ena, alarm_collision_ena
        self.write_dac(0x2, 0x0080) # sif4_ena = 1
        # self.write_dac(0x3, 0xF000) # keep default
        self.write_dac(0x4, 0x0000) # clear
        self.write_dac(0x5, 0x0000) # clear
        # 0x6 read only
        self.write_dac(0x7, ~(0b111 << 11)) # unmask alarm_fifo_collision and alarm_fifo_*away
        # 0x8 - keep default
        self.write_dac(0x9, 4 << 13) # fifo_offset
        # 0x10 - 0x17 - keep default
        self.write_dac(0x18, 1 << 13) # pll disabled
        # 0x19 - keep default
        # 0x1A - keep default, pll in sleep mode
        # 0x1B - fuse sleep - set at the end
        # 0x1C - 0x1F - keep default
        self.write_dac(0x20, 0x2201) # all via ISTR
        # 0x21 - 0x2F - keep default

        self.write_dac(0x2D, 1 << 13 | 4)

        self.write_dac(0x1B, 1 << 11) # fuse_sleep = 1

        self.write_field(REG_DAC_PLAY, 1)
        self.write_field(REG_DAC_TX_ENA, 1)

        self.write_dac(0x5, 0)
        delay(1*ms)
        r = self.read_dac(0x5)

        print("")
        print("DACCLK_GONE ", (r >> 10) & 1)
        print("DATACLK_GONE", (r >> 9) & 1)
        print("FIFO 2 AWAY ", (r >> 11) & 1)
        print("FIFO 1 AWAY ", (r >> 12) & 1)
        print("FIFO COLLIS ", (r >> 13) & 1)
        # self.core.break_realtime()
        # self.write_field(REG_DAC_PLAY, 0)
    
    config_400M = [
        0x60100149 >> 5,
        0x08A0148A >> 5,
        0x0000000B >> 5,
        0x4A00000C >> 5,
        0x0D03A28D >> 5,
        0x9F90100E >> 5,
        0xD041100F >> 5
    ]

    @kernel
    def configure_mod(self, config):
        for a in range(len(config)):
            self.core.break_realtime()
            self.write_mod(0, a+1, config[a])
            self.write_mod(1, a+1, config[a])
            r0 = self.read_mod(0, a+1)
            r1 = self.read_mod(1, a+1)
            print("R0", r0)
            print("R1", r1)

        delay(100*ms)
        print("MOD LD", self.read_field(REG_MOD_LOCK_DET))




 
