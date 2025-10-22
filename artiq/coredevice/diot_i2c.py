from numpy import int32

from artiq.experiment import *
from artiq.coredevice.i2c import i2c_write_many, i2c_read_many, i2c_poll

SHARED_I2C_PORT = 3


slot_mapping = {
    "SLOT1": 0,
    "SLOT2": 2,
    "SLOT3": 3,
    "SLOT4": 1,
    "SLOT5": 4,
    "SLOT6": 7,
    "SLOT7": 6,
    "SLOT8": 5
}

class PCA9539:
    NORMAL_OP = 0x60    # no reset, direction external, enabled - done in firmware during init
    output_port0 = 0x02
    output_port1 = 0x03

    def __init__(self, dmgr, busno=0, address=0xec, core_device="core"):
        self.core = dmgr.get(core_device)
        self.busno = busno
        self.address = address

    @kernel
    def set(self, outputs):
        i2c_write_many(self.busno, self.address, self.output_port0, [outputs])



class ServmodSwitch:
    def __init__(self, dmgr, busno=0, core_device="core", 
                 sw_device="i2c_switch0", servmod_device="servmod_expander"):
        self.core = dmgr.get(core_device)
        self.sw = dmgr.get(sw_device)
        self.io_expander = dmgr.get(servmod_device)
        self.busno = busno        
        # self.slot = slot_mapping[slot]
        self.port = SHARED_I2C_PORT

    @kernel
    def set(self, slot):
        self.sw.set(self.port)
        self.io_expander.set(outputs=1<<slot)

    @kernel
    def unset(self):
        self.io_expander.set(outputs=0x00)
        self.sw.unset()


class KasliDIOTEEPROM:
    def __init__(self, dmgr, slot, address=0xa0, busno=1,
            core_device="core", sw_device="servmod_switch"):
        self.core = dmgr.get(core_device)
        self.sw = dmgr.get(sw_device)
        self.busno = busno
        self.slot = slot_mapping[slot]
        self.address = address  # i2c 8 bit

    @kernel
    def select(self):
        self.sw.set(self.slot)

    @kernel
    def deselect(self):
        self.sw.unset()

    @kernel
    def write_i32(self, addr, value):
        self.select()
        try:
            data = [0]*4
            for i in range(4):
                data[i] = (value >> 24) & 0xff
                value <<= 8
            i2c_write_many(self.busno, self.address, addr, data)
            i2c_poll(self.busno, self.address)
        finally:
            self.deselect()

    @kernel
    def read_i32(self, addr):
        self.select()
        try:
            data = [0]*4
            i2c_read_many(self.busno, self.address, addr, data)
            value = int32(0)
            for i in range(4):
                value <<= 8
                value |= data[i]
        finally:
            self.deselect()
        return value
