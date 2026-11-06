
import time

from scheduler.node_registry import NodeRegistry


def test_initial_nodes_are_unknown():
    registry = NodeRegistry()

    nodes = registry.get_all_nodes()

    assert len(nodes) == 3

    for node in nodes:
        assert node["availability"] == "UNKNOWN"


def test_update_node_heartbeat():
    registry = NodeRegistry()

    registry.update_node({
        "fog_id": "fog-a",
        "status": "ONLINE",
        "cpu_percent": 20.0,
        "ram_percent": 50.0,
        "queued_tasks": 2,
        "zone": "A",
    })

    node = registry.get_node("fog-a")

    assert node["availability"] == "ONLINE"
    assert node["status"] == "ONLINE"
    assert node["cpu_percent"] == 20.0
    assert node["queued_tasks"] == 2


def test_unknown_node_is_ignored():
    registry = NodeRegistry()

    registry.update_node({
        "fog_id": "fog-x",
        "status": "ONLINE",
    })

    assert registry.get_node("fog-x") is None


def test_node_becomes_offline():
    registry = NodeRegistry(offline_timeout=1)

    registry.update_node({
        "fog_id": "fog-a",
        "status": "ONLINE",
        "zone": "A",
    })

    time.sleep(1.2)

    offline_nodes = registry.check_offline_nodes()

    assert "fog-a" in offline_nodes

    node = registry.get_node("fog-a")

    assert node["availability"] == "OFFLINE"
    assert node["status"] == "OFFLINE"


def test_online_node_is_not_marked_offline():
    registry = NodeRegistry(offline_timeout=10)

    registry.update_node({
        "fog_id": "fog-a",
        "status": "ONLINE",
        "zone": "A",
    })

    offline_nodes = registry.check_offline_nodes()

    assert "fog-a" not in offline_nodes
    assert registry.get_node("fog-a")["availability"] == "ONLINE"
