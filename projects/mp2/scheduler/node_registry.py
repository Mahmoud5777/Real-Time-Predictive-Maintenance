
from threading import Lock
from time import monotonic


class NodeRegistry:
    """
    Central registry for monitoring Fog nodes.
    """

    EXPECTED_NODES = {
        "fog-a": "A",
        "fog-b": "B",
        "fog-c": "C",
    }

    def __init__(self, offline_timeout: int = 15):
        self.offline_timeout = offline_timeout
        self._lock = Lock()
        self._nodes = {}
        self._last_seen = {}
        self._failure_count = {}

        now = monotonic()

        for fog_id, zone in self.EXPECTED_NODES.items():
            self._nodes[fog_id] = {
                "fog_id": fog_id,
                "zone": zone,
                "status": "UNKNOWN",
                "cpu_percent": None,
                "ram_percent": None,
                "queued_tasks": 0,
                "availability": "UNKNOWN",
                "last_heartbeat": None,
                "failure_count": 0,
            }

            self._last_seen[fog_id] = now
            self._failure_count[fog_id] = 0

    def update_node(self, payload: dict) -> None:
        """Update node information after receiving a heartbeat."""

        fog_id = payload.get("fog_id")

        if fog_id not in self.EXPECTED_NODES:
            return

        with self._lock:
            node = self._nodes[fog_id]

            node.update(payload)
            node["availability"] = "ONLINE"
            node["failure_count"] = self._failure_count[fog_id]

            self._last_seen[fog_id] = monotonic()

    def check_offline_nodes(self) -> list[str]:
        """Detect nodes that stopped sending heartbeats."""

        offline_nodes = []
        now = monotonic()

        with self._lock:
            for fog_id, last_seen in self._last_seen.items():

                elapsed = now - last_seen

                if elapsed > self.offline_timeout:
                    node = self._nodes[fog_id]

                    if node["availability"] != "OFFLINE":
                        node["availability"] = "OFFLINE"
                        node["status"] = "OFFLINE"

                        self._failure_count[fog_id] += 1
                        node["failure_count"] = self._failure_count[fog_id]

                        offline_nodes.append(fog_id)

        return offline_nodes

    def get_node(self, fog_id: str):
        """Return information about one Fog node."""

        with self._lock:
            node = self._nodes.get(fog_id)

            return dict(node) if node else None

    def get_all_nodes(self) -> list[dict]:
        """Return information about all Fog nodes."""

        with self._lock:
            return [
                dict(node)
                for node in self._nodes.values()
            ]

    def get_failure_count(self, fog_id: str) -> int:
        """Return the number of detected failures."""

        with self._lock:
            return self._failure_count.get(fog_id, 0)
