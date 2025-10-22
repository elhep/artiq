from artiq.gateware import diot
from artiq.gateware.rtio.phy import ttl_serdes_7series, edge_counter, ttl_simple


def peripheral_ohwr_diot_loopback(module, peripheral, **kwargs):
    slot = peripheral["slot"]
    diot.OhwrDiotLoopback.add_std(
        module, slot, ttl_input_cls=ttl_simple.Input, 
        ttl_output_cls=ttl_simple.Output, 
        edge_counter_cls=edge_counter.SimpleEdgeCounter, **kwargs)


def peripheral_urukul_diot(module, peripheral, **kwargs):
    slot = peripheral["slot"]
    if peripheral["synchronization"]:
        sync_gen_cls = ttl_simple.ClockGen
    else:
        sync_gen_cls = None
    diot.UrukulDIOT.add_std(module, slot, ttl_serdes_7series.Output_8X,
        peripheral["dds"], sync_gen_cls, **kwargs)




peripheral_processors = {
    "ohwr_diot_loopback": peripheral_ohwr_diot_loopback,
    "urukul_diot": peripheral_urukul_diot
}


def add_peripherals(module, peripherals, **kwargs):
    for peripheral in peripherals:
        peripheral_processors[peripheral["type"]](module, peripheral, **kwargs)
