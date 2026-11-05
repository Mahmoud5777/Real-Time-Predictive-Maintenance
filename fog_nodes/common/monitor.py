
import psutil

from shared.models import FogStatus, FogState


class ResourceMonitor:
    """Monitor CPU and RAM usage of a Fog Node."""

    def __init__(self, config):
        self.config = config

    def get_status(self, queued_tasks: int = 0) -> FogStatus:

        # Get CPU usage
        cpu = psutil.cpu_percent(interval=0.5)

        # Get RAM usage
        ram = psutil.virtual_memory().percent

        # Determine Fog state
        if (
            cpu >= self.config.cpu_threshold
            or ram >= self.config.ram_threshold
        ):
            state = FogState.DEGRADED
        else:
            state = FogState.ONLINE

        # Build status object
        return FogStatus(
            fog_id=self.config.fog_id,
            status=state,
            cpu_percent=cpu,
            ram_percent=ram,
            queued_tasks=queued_tasks
        )
