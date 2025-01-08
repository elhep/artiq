use i2c;

pub struct SFP {
    busno: u8,
    port: u8,
    address: u8,    
}

impl SFP {
    #[cfg(all(soc_platform = "kasli", hw_rev = "v2.0"))]
    pub fn new(index: u8) -> Self {
        SFP {
            busno: 0,
            port: 8+index,
            address: 0xa0,
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

    pub fn read_diag<'a>(&self, addr: u8, buf: &'a mut [u8]) -> Result<(), &'static str> {
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

    pub fn dump_data(&self) -> [u8; 256] {
        let mut sfp_data = [0u8; 256];
        self.read(0, &mut sfp_data);
        #[cfg(feature = "log")]
        for i in 0..255 {
            log::info!("SFP diag {}: {}", i, sfp_data[i as usize]);
        }
        sfp_data
    }

    pub fn dump_diag(&self) -> [u8; 256] {
        let mut sfp_data = [0u8; 256];
        self.read_diag(0, &mut sfp_data);
        #[cfg(feature = "log")]
        for i in 0..255 {
            log::info!("SFP diag {}: {}", i, sfp_data[i as usize]);
        }
        sfp_data
    }
}