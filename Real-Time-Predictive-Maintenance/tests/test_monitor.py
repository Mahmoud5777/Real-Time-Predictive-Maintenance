from fog_nodes.common.monitor import ResourceMonitor
from fog_nodes.fog_a.config import config


def test_resource_monitor():

    monitor = ResourceMonitor(config)

    status = monitor.get_status()

    assert status.fog_id == "fog-a"
    assert status.cpu_percent >= 0
    assert status.ram_percent >= 0
    assert status.queued_tasks == 0