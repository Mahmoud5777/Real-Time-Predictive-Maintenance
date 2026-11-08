
from scheduler.scheduling_policy import (
    calculate_node_score,
    select_destination,
    select_recovery_destination,
)


def sample_nodes():
    return [
        {
            "fog_id": "fog-a",
            "status": "DEGRADED",
            "availability": "ONLINE",
            "cpu_percent": 90,
            "ram_percent": 85,
            "queued_tasks": 5,
        },
        {
            "fog_id": "fog-b",
            "status": "ONLINE",
            "availability": "ONLINE",
            "cpu_percent": 20,
            "ram_percent": 30,
            "queued_tasks": 1,
        },
        {
            "fog_id": "fog-c",
            "status": "OFFLINE",
            "availability": "OFFLINE",
            "cpu_percent": 10,
            "ram_percent": 20,
            "queued_tasks": 0,
        },
    ]


def test_calculate_node_score():
    node = {
        "cpu_percent": 20,
        "ram_percent": 30,
        "queued_tasks": 2,
    }

    score = calculate_node_score(node)

    assert score == 22.0


def test_medium_task_selects_best_node():
    destination = select_destination(
        "MEDIUM",
        "fog-a",
        sample_nodes(),
    )

    assert destination["fog_id"] == "fog-b"


def test_low_task_selects_best_node():
    destination = select_destination(
        "LOW",
        "fog-a",
        sample_nodes(),
    )

    assert destination["fog_id"] == "fog-b"


def test_high_task_migrates_when_source_degraded():
    destination = select_destination(
        "HIGH",
        "fog-a",
        sample_nodes(),
    )

    assert destination is not None
    assert destination["fog_id"] == "fog-b"


def test_source_online_keeps_task_local():
    nodes = sample_nodes()
    nodes[0]["status"] = "ONLINE"

    destination = select_destination(
        "LOW",
        "fog-a",
        nodes,
    )

    assert destination is None


def test_degraded_destinations_are_never_selected():
    nodes = [
        {
            "fog_id": "fog-a",
            "status": "DEGRADED",
            "availability": "ONLINE",
            "cpu_percent": 90,
            "ram_percent": 90,
            "queued_tasks": 10,
        },
        {
            "fog_id": "fog-b",
            "status": "DEGRADED",
            "availability": "ONLINE",
            "cpu_percent": 20,
            "ram_percent": 30,
            "queued_tasks": 1,
        },
        {
            "fog_id": "fog-c",
            "status": "DEGRADED",
            "availability": "ONLINE",
            "cpu_percent": 30,
            "ram_percent": 40,
            "queued_tasks": 2,
        },
    ]

    destination = select_destination(
        "LOW",
        "fog-a",
        nodes,
    )

    assert destination is None


def test_offline_node_is_never_selected():
    nodes = sample_nodes()
    nodes[1]["availability"] = "OFFLINE"
    nodes[1]["status"] = "OFFLINE"

    destination = select_destination(
        "MEDIUM",
        "fog-a",
        nodes,
    )

    assert destination is None


def test_no_available_destination():
    nodes = [
        {
            "fog_id": "fog-a",
            "status": "DEGRADED",
            "availability": "ONLINE",
            "cpu_percent": 90,
            "ram_percent": 90,
            "queued_tasks": 5,
        },
        {
            "fog_id": "fog-b",
            "status": "DEGRADED",
            "availability": "ONLINE",
            "cpu_percent": 20,
            "ram_percent": 30,
            "queued_tasks": 1,
        },
    ]

    destination = select_destination(
        "MEDIUM",
        "fog-a",
        nodes,
    )

    assert destination is None


def test_recovery_selects_best_online_node():
    nodes = [
        {
            "fog_id": "fog-a",
            "availability": "OFFLINE",
            "status": "OFFLINE",
            "cpu_percent": 10,
            "ram_percent": 10,
            "queued_tasks": 0,
        },
        {
            "fog_id": "fog-b",
            "availability": "ONLINE",
            "status": "ONLINE",
            "cpu_percent": 70,
            "ram_percent": 60,
            "queued_tasks": 4,
        },
        {
            "fog_id": "fog-c",
            "availability": "ONLINE",
            "status": "ONLINE",
            "cpu_percent": 20,
            "ram_percent": 30,
            "queued_tasks": 1,
        },
    ]

    destination = select_recovery_destination("fog-a", nodes)

    assert destination["fog_id"] == "fog-c"


def test_recovery_returns_none_without_available_nodes():
    nodes = [
        {
            "fog_id": "fog-a",
            "availability": "OFFLINE",
            "status": "OFFLINE",
            "cpu_percent": 10,
            "ram_percent": 10,
            "queued_tasks": 0,
        },
        {
            "fog_id": "fog-b",
            "availability": "OFFLINE",
            "status": "OFFLINE",
            "cpu_percent": 20,
            "ram_percent": 30,
            "queued_tasks": 1,
        },
    ]

    destination = select_recovery_destination("fog-a", nodes)

    assert destination is None
