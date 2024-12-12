"""RTIO drivers for ALICE FIT verification modules."""

from artiq.language.core import kernel
from artiq.coredevice import spi2 as spi
from artiq.coredevice.ad53xx import SPI_AD53XX_CONFIG, AD53xx

_SPI_CS_DAC = 1


class PmtSimDac(AD53xx):

    def __init__(self, dmgr, spi_device, 
                 div_write=4, div_read=16, core="core"):
        AD53xx.__init__(self, dmgr=dmgr, spi_device=spi_device,
                        chip_select=_SPI_CS_DAC, div_write=div_write,
                        div_read=div_read, core=core)


class PmtSimChannel:

    def __init__(self, dmgr, dac, dac_ch, ttl, core="core"):
        self.dac = dmgr.get(dac)
        self.hit_dac_ch = dac_ch
        self.hit_ttl = [ dmgr.get(x) for x in ttl ]
        self.core = dmgr.get(core)
    
    @kernel
    def wirte_hit_cal(self, hit, value):
        self.dac.write_dac(self.hit_dac_ch[hit], value)
