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
    pub fn new(index: u8) -> Result<Self, &'static str> {
        let mut sfp = SFP {
            busno: 0,
            port: 8+index,
            address: 0xa0,
            sfp_data: [0u8; 256],
            sfp_diag: [0u8; 256],
        };
        if !sfp.check_ack()? {
            return Err("SFP module not found.");
        };
        // Initialize with module data
        sfp.dump_data();
        // If diagnostic data is implemented on SFP and doesn't require an address change
        if ((sfp.sfp_data[92]>>2) & 1) == 0 && (((sfp.sfp_data[92]>>6) & 1) == 1 || sfp.sfp_data[94] != 0) {
            sfp.dump_diag();
        }
        Ok(sfp)
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
        i2c::write(self.busno, (self.address+2) | 1)?;
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

    pub fn read_diagnostic_data(&mut self) -> [u8; 22] {
        let mut sfp_data = [0u8; 22];
        if ((self.sfp_data[92]>>2) & 1) == 0 && (((self.sfp_data[92]>>6) & 1) == 1 || self.sfp_data[94] != 0) {
            self.read_diag(96, &mut sfp_data);
            self.sfp_diag[96..118].clone_from_slice(&sfp_data);
        }
        sfp_data
    }

    #[cfg(feature = "log")]
    pub fn print_alarms(&self) {
        let alarm = ["Temperature high", "Temperature low", "Vcc high", "Vcc low", "TX Bias high", "TX Bias low", "TX Power high", "TX Power low", "RX Power high", "RX Power low"];
        // if ((self.sfp_data[93] >> 7) & 1) == 1 {
            for i in 0..10 {
                let register = i/8;
                let bit = 7 - i % 8;
                if (self.sfp_diag[112 + register] >> bit) & 1 == 1 {
                    log::error!("SFP{}: {} alarm.", self.port-8, alarm[i]);
                } else if (self.sfp_diag[116 + register] >> bit) & 1 == 1 {
                    log::warn!("SFP{}: {} warning.", self.port-8, alarm[i]);
                }
            }
        // }
    }

    pub fn check_ack(&self) -> Result<bool, &'static str> {
        // Check for ack from the SFP module
        self.select()?;
        i2c::start(self.busno)?;
        let ack = i2c::write(self.busno, self.address)?;
        i2c::stop(self.busno)?;
        Ok(ack)
    }

    #[cfg(feature = "log")]
    pub fn print_all(&self) {
        for i in 0..255 {
            log::trace!("SFP{} data {}: {}", self.port-8, i, self.sfp_data[i as usize]);
        }
        for i in 0..255 {
            log::trace!("SFP{} diag {}: {}", self.port-8, i, self.sfp_diag[i as usize]);
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
        log::debug!("Diagnostic monitoring signals: {:#08b}", self.sfp_data[92]);
        if ((self.sfp_data[92]>>4) & 1) == 1 {
            log::warn!("SFP{}: External calibration conversion is not implemented, shown values won't be correct!", self.port-8)
        }
        if ((self.sfp_data[92]>>2) & 1) == 1 {
            log::warn!("SFP{}: Address change for diagnostic monitoring is not implemented!", self.port-8)
        }
        log::debug!("Enhanced options: {:#08b}", self.sfp_data[93]);
        log::debug!("SFF-8472 compliance: {:#x}", self.sfp_data[94]);

        if ((self.sfp_data[92]>>2) & 1) == 0 && (((self.sfp_data[92]>>6) & 1) == 1 || self.sfp_data[94] != 0) {
            log::debug!("Diagnostics:");
            log::debug!("\t\tTemp [°C]\tVcc [V]\tTX bias [mA]\tTX power [mW]\tRX power [mW]");
            log::debug!("+ Alarm: \t{:.2}\t\t{:.2}\t{:.2}\t\t{:.4}\t\t{:.4}", 
                        temperature_convert(&self.sfp_diag[0..2]), 
                        voltage_convert(&self.sfp_diag[8..10]),
                        current_convert(&self.sfp_diag[16..18]),
                        power_convert(&self.sfp_diag[24..26]),
                        power_convert(&self.sfp_diag[32..34]),
                    );
            log::debug!("+ Warning: \t{:.2}\t\t{:.2}\t{:.2}\t\t{:.4}\t\t{:.4}", 
                        temperature_convert(&self.sfp_diag[4..6]), 
                        voltage_convert(&self.sfp_diag[12..14]),
                        current_convert(&self.sfp_diag[20..22]),
                        power_convert(&self.sfp_diag[28..30]),
                        power_convert(&self.sfp_diag[36..38]),
                    );
            log::debug!("Value: \t{:.2}\t\t{:.2}\t{:.2}\t\t{:.4}\t\t{:.4}", 
                        temperature_convert(&self.sfp_diag[96..98]),
                        voltage_convert(&self.sfp_diag[98..100]),
                        current_convert(&self.sfp_diag[100..102]),
                        power_convert(&self.sfp_diag[102..104]),
                        power_convert(&self.sfp_diag[104..106]),
                    );
            log::debug!("- Warning: \t{:.2}\t\t{:.2}\t{:.2}\t\t{:.4}\t\t{:.4}", 
                        temperature_convert(&self.sfp_diag[6..8]), 
                        voltage_convert(&self.sfp_diag[14..16]),
                        current_convert(&self.sfp_diag[22..24]),
                        power_convert(&self.sfp_diag[30..32]),
                        power_convert(&self.sfp_diag[38..40]),
                    );
            log::debug!("- Alarm: \t{:.2}\t\t{:.2}\t{:.2}\t\t{:.4}\t\t{:.4}", 
                        temperature_convert(&self.sfp_diag[2..4]), 
                        voltage_convert(&self.sfp_diag[10..12]),
                        current_convert(&self.sfp_diag[18..20]),
                        power_convert(&self.sfp_diag[26..28]),
                        power_convert(&self.sfp_diag[34..36]),
                    );

            log::debug!("Status/Control Bits: {:#08b}", self.sfp_diag[110]);
            log::debug!("TX disable: {}", (self.sfp_diag[110] >> 7) & 1);
            log::debug!("Soft TX disable: {}", (self.sfp_diag[110] >> 6) & 1);
            log::debug!("Rate Select 1: {}", (self.sfp_diag[110] >> 5) & 1);
            log::debug!("Rate Select 0: {}", (self.sfp_diag[110] >> 4) & 1);
            log::debug!("Soft Rate Select 0: {}", (self.sfp_diag[110] >> 3) & 1);
            log::debug!("TX Fault: {}", (self.sfp_diag[110] >> 2) & 1);
            log::debug!("RX_LOS: {}", (self.sfp_diag[110] >> 1) & 1);
            log::debug!("Data not ready: {}", self.sfp_diag[110] & 1);

            let alarm = ["Temperature high", "Temperature low", "Vcc high", "Vcc low", "TX Bias high", "TX Bias low", "TX Power high", "TX Power low", "RX Power high", "RX Power low"];
            for i in 0..10 {
                let register = i/8;
                let bit = 7 - i % 8;
                log::debug!("{} alarm value: {}", alarm[i], (self.sfp_diag[112 + register] >> bit) & 1);
                log::debug!("{} warning value: {}", alarm[i], (self.sfp_diag[116 + register] >> bit) & 1);
            }
        } else {
        log::debug!("Diagnostic monitoring is not implemented on the module.");
        }
    }
}

fn temperature_convert(value: &[u8]) -> f32 {
    ((value[0] as i8) as f32) + (value[1] as f32) / 256.
}

fn voltage_convert(value: &[u8]) -> f32 {
    ((value[0] as f32) * 256. + (value[1] as f32)) / 10000.
}

fn current_convert(value: &[u8]) -> f32 {
    ((value[0] as f32) * 256. + (value[1] as f32)) / 500.
}

fn power_convert(value: &[u8]) -> f32 {
    ((value[0] as f32) * 256. + (value[1] as f32)) / 10000.
}