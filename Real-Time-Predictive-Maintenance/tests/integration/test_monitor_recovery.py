import pytest

from scheduler import main as scheduler_main


@pytest.mark.asyncio
async def test_monitor_stops_recovery_attempts_when_fog_returns_online(
    monkeypatch,
):
    recovery_calls = []

    class FakeNodeRegistry:
        def __init__(self):
            self.snapshots = [
                [{"fog_id": "fog-b", "availability": "OFFLINE"}],
                [{"fog_id": "fog-b", "availability": "ONLINE"}],
            ]
            self.index = 0

        def check_offline_nodes(self):
            return []

        def get_all_nodes(self):
            snapshot = self.snapshots[self.index]
            self.index += 1
            return snapshot

    async def fake_recover(fog_id):
        recovery_calls.append(fog_id)

    sleep_calls = 0

    class StopMonitoring(Exception):
        pass

    async def fake_sleep(seconds):
        nonlocal sleep_calls
        sleep_calls += 1

        if sleep_calls == 2:
            raise StopMonitoring

    monkeypatch.setattr(
        scheduler_main,
        "node_registry",
        FakeNodeRegistry(),
    )

    monkeypatch.setattr(
        scheduler_main,
        "last_recovery_attempt",
        {},
    )

    monkeypatch.setattr(
        scheduler_main,
        "monotonic",
        lambda: 100.0,
    )

    monkeypatch.setattr(
        scheduler_main,
        "recover_tasks_from_failed_node",
        fake_recover,
    )

    monkeypatch.setattr(
        scheduler_main.asyncio,
        "sleep",
        fake_sleep,
    )

    with pytest.raises(StopMonitoring):
        await scheduler_main.monitor_nodes()

    # Recovery is attempted while Fog B is offline.
    assert recovery_calls == ["fog-b"]

    # Returning online clears its recovery retry tracking.
    assert "fog-b" not in scheduler_main.last_recovery_attempt