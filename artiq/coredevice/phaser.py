"""RTIO driver for Phaser
"""

from artiq.language.core import kernel, delay
from artiq.language.units import us
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

EXT_DAC = 5
EXT_MOD0 = 6
EXT_MOD1 = 7
EXT_ATT0 = 8
EXT_ATT1 = 9



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

    @kernel
    def read_dac(self, addr):
        """Read from DAC configuration register"""
        return self.read_ext(EXT_DAC, 24, ((1 << 7) | addr) << 16)

    @kernel
    def write_mod(self, mod, addr, data):
        """Write modulator configuration register"""
        self.write_ext(EXT_MOD0+mod, 32, (data << 5) | (1 << 3) | (addr & 0x7))

    @kernel
    def read_mod(self, mod, addr):
        """Read from modulator configuration register"""
        self.bus.set_config_mu(SPI_CONFIG, 8, SPIT_WR, SPI_CS)
        self.bus.write(EXT_MOD0+mod << 25)

        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END | spi.SPI_LSB_FIRST, 32,
                               SPIT_WR*16, SPI_CS)
        self.bus.write((1 << 31) | (addr & 0x7) << 28 | 0b01000)

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

        return self.bus.read()
        
    @kernel
    def init(self):
        """Initialize Phaser by reading the status register and verifying
        compatible hardware and protocol revisions"""
        
        reg0 = self.read_reg(0)
        delay(100*us)
        if ((reg0 >> 2) & 0xF) > 1:
            raise ValueError("Unsupported board version")
        if ((reg0 >> 6) & 0x3) > 0:
            raise ValueError("Unsupported protocol version")

        # Disable DAC reset
        self.write_reg(2, 1 << 2)

        # Enable DAC 4-wire interface
        self.write_dac(0x2, 1 << 7)

        # Check DAC communication
        if self.read_dac(0x7F) != 0x5409:
            raise ValueError("DAC version mismatch")
        delay(100*us)

        # Check MOD communication
        # TODO: Add condition for baseband
        if (self.read_mod(0, 0) & 0x7F) != 0x68:
            raise ValueError("MOD0 readout failure")
        if (self.read_mod(1, 0) & 0x7F) != 0x68:
            raise ValueError("MOD0 readout failure")

    @kernel
    def set_att_mu(self, channel, att):
        """Set digital step attenuator in machine units.

        :param att: Attenuation setting, 8 bit digital.
        """
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END, 16, SPIT_WR, SPI_CS)
        self.bus.write(((channel | 8) << 25) | (att << 16))

 
