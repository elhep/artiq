from artiq.gateware import diot
from artiq.gateware.rtio.phy import ttl_serdes_7series, edge_counter, ttl_simple


def peripheral_ohwr_diot_loopback(module, peripheral, **kwargs):
    slot = peripheral["slot"]
    diot.OhwrDiotLoopback.add_std(
        module, slot, ttl_input_cls=ttl_simple.Input, 
        ttl_output_cls=ttl_simple.Output, 
        edge_counter_cls=edge_counter.SimpleEdgeCounter, **kwargs)


def peripheral_urukul(module, peripheral, **kwargs):
    slot = peripheral["slot"]
    if peripheral["synchronization"]:
        sync_gen_cls = ttl_simple.ClockGen
    else:
        sync_gen_cls = None
    diot.Urukul.add_std(module, slot, ttl_serdes_7series.Output_8X,
        peripheral["dds"], peripheral["proto_rev"], sync_gen_cls, **kwargs)


peripheral_processors = {
    "ohwr_diot_loopback": peripheral_ohwr_diot_loopback,
    "urukul": peripheral_urukul
}


def add_peripherals(module, peripherals, **kwargs):
    for peripheral in peripherals:
        peripheral_processors[peripheral["type"]](module, peripheral, **kwargs)
