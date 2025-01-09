use i2c;
use core::str;

pub struct SFP {
    busno: u8,
    port: u8,
    address: u8,
    sfp_data: [u8; 256],
    sfp_diag: [u8; 256],
}

impl SFP {
    #[cfg(all(soc_platform = "kasli", hw_rev = "v2.0"))]
    pub fn new(index: u8) -> Self {
        SFP {
            busno: 0,
            port: 8+index,
            address: 0xa0,
            sfp_data: [0u8; 256],
            sfp_diag: [0u8; 256],
        }
    }

    fn select(&self) -> Result<(), &'static str> {
        let mask: u16 = 1 << self.port;
        i2c::switch_select(self.busno, 0x70, mask as u8)?;
        i2c::switch_select(self.busno, 0x71, (mask >> 8) as u8)?;
        Ok(())
    }

    fn read<'a>(&self, addr: u8, buf: &'a mut [u8]) -> Result<(), &'static str> {
        self.select()?;

        i2c::start(self.busno)?;
        i2c::write(self.busno, self.address)?;
        i2c::write(self.busno, addr)?;

        i2c::restart(self.busno)?;
        i2c::write(self.busno, self.address | 1)?;
        let buf_len = buf.len();
        for (i, byte) in buf.iter_mut().enumerate() {
            *byte = i2c::read(self.busno, i < buf_len - 1)?;
        }

        i2c::stop(self.busno)?;

        Ok(())
    }

    fn read_diag<'a>(&self, addr: u8, buf: &'a mut [u8]) -> Result<(), &'static str> {
        self.select()?;

        i2c::start(self.busno)?;
        i2c::write(self.busno, self.address+2)?;
        i2c::write(self.busno, addr)?;

        i2c::restart(self.busno)?;
        i2c::write(self.busno, (self.address+1) | 1)?;
        let buf_len = buf.len();
        for (i, byte) in buf.iter_mut().enumerate() {
            *byte = i2c::read(self.busno, i < buf_len - 1)?;
        }

        i2c::stop(self.busno)?;

        Ok(())
    }

    pub fn dump_data(&mut self) -> [u8; 256] {
        let mut sfp_data = [0u8; 256];
        self.read(0, &mut sfp_data);
        self.sfp_data = sfp_data;
        sfp_data
    }

    pub fn dump_diag(&mut self) -> [u8; 256] {
        let mut sfp_data = [0u8; 256];
        self.read_diag(0, &mut sfp_data);
        self.sfp_diag = sfp_data;
        sfp_data
    }

    #[cfg(feature = "log")]
    pub fn print_all(&self) {
        for i in 0..255 {
            log::debug!("SFP data {}: {}", i, self.sfp_data[i as usize]);
        }
        for i in 0..255 {
            log::debug!("SFP diag {}: {}", i, self.sfp_diag[i as usize]);
        }
    }

    #[cfg(feature = "log")]
    pub fn print_some(&self) {
        log::debug!("SFP{} data:", self.port-8);
        log::debug!("Type: {:#x}", self.sfp_data[0]);
        log::debug!("Extended type: {:#x}", self.sfp_data[1]);
        log::debug!("Connector: {:#x}", self.sfp_data[2]);
        log::debug!("Transceiver fields:");
        log::debug!("Bit: 76543210");
        for i in 3..11 {
            log::debug!("{:3}: {:8b}", i, self.sfp_data[i as usize]);
        }
        log::debug!("Bit rate: {}00 MBit/s", self.sfp_data[12]);
        log::debug!("Rate select: {:x}", self.sfp_data[13]);
        log::debug!("Supported link length:");
        log::debug!("9/125 um fiber: {} km, {}00 m", self.sfp_data[14], self.sfp_data[15]);
        log::debug!("50/125 um OM2 fiber: {}0 m", self.sfp_data[16]);
        log::debug!("62.5/125 um OM1 fiber: {}0 m", self.sfp_data[17]);
        log::debug!("Copper cables: {} m", self.sfp_data[18]);
        log::debug!("50/125 um fiber: {}0 m", self.sfp_data[19]);
        log::debug!("Vendor: {}", str::from_utf8(&self.sfp_data[20..36]).unwrap());
        log::debug!("Part number: {}", str::from_utf8(&self.sfp_data[40..56]).unwrap());
        log::debug!("Revision: {}", str::from_utf8(&self.sfp_data[56..60]).unwrap());
        log::debug!("Serial number: {}", str::from_utf8(&self.sfp_data[68..84]).unwrap());
        log::debug!("Date code: {}.{}.20{}, lot: {}", str::from_utf8(&self.sfp_data[84..86]).unwrap(), str::from_utf8(&self.sfp_data[86..88]).unwrap(), str::from_utf8(&self.sfp_data[88..90]).unwrap(), str::from_utf8(&self.sfp_data[90..92]).unwrap());
        log::debug!("Laser wavelength: {} nm", ((self.sfp_data[60] as u32)<<8)+(self.sfp_data[61] as u32));
        log::debug!("Optional signals:");
        log::debug!("Bit: 76543210");
        for i in 64..66 {
            log::debug!("{:3}: {:8b}", i, self.sfp_data[i as usize]);
        }
        log::debug!("Rate select implented: {}", (self.sfp_data[65]>>5)&1);
        log::debug!("TX disable implented: {}", (self.sfp_data[65]>>4)&1);
        log::debug!("TX fault implented: {}", (self.sfp_data[65]>>3)&1);
        log::debug!("Loss of signal implented: {}", (self.sfp_data[65]>>1)&1);
        log::debug!("Link margin: min {}%, max {}% ", self.sfp_data[67], self.sfp_data[66]);
        log::debug!("Diagnostic monitoring signals: {:#b}", self.sfp_data[92]);
        log::debug!("Enhanced options: {:#b}", self.sfp_data[93]);
        log::debug!("SFF-8472 compliance: {:#x}", self.sfp_data[94]);

        log::debug!("Diagnostics:");
        log::debug!("\t\tTemp\tVCC\tTX bias\tTX power\tRX power\tLaser Temp\tTEC");
        
        
    }
}