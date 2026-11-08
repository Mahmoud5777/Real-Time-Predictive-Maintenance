
def calculate_node_score(node: dict) -> float:
    """
    Calculate the load score of a Fog node.
    Lower score means more available resources.
    """

    cpu = node.get("cpu_percent")
    ram = node.get("ram_percent")
    queued_tasks = node.get("queued_tasks", 0)

    cpu = 100 if cpu is None else cpu
    ram = 100 if ram is None else ram

    return (
        cpu * 0.4
        + ram * 0.4
        + min(queued_tasks * 5, 100) * 0.2
    )


def select_destination(
    task_priority: str,
    source_fog_id: str,
    nodes: list[dict],
) -> dict | None:
    """
    Select the best destination Fog node for a task.

    HIGH priority tasks are always kept locally.

    MEDIUM and LOW priority tasks can be migrated
    only when the source Fog node is DEGRADED.

    The destination must be ONLINE and not DEGRADED.
    """

    priority = getattr(task_priority, "value", task_priority)
    priority = str(priority).upper()

    # HIGH priority tasks always stay local.
    if priority == "HIGH":
        return None

    if priority not in ("MEDIUM", "LOW"):
        return None

    # Find the source Fog node.
    source_node = next(
        (
            node for node in nodes
            if node.get("fog_id") == source_fog_id
        ),
        None,
    )

    if source_node is None:
        return None

    # Do not migrate if the source is not overloaded.
    if source_node.get("status") != "DEGRADED":
        return None

    # Find available and non-degraded destinations.
    candidates = [
        node for node in nodes
        if node.get("fog_id") != source_fog_id
        and node.get("availability") == "ONLINE"
        and node.get("status") == "ONLINE"
    ]

    if not candidates:
        return None

    # Select the least loaded destination.
    return min(candidates, key=calculate_node_score)


def select_recovery_destination(
    failed_fog_id: str,
    nodes: list[dict],
) -> dict | None:
    """
    Select the best available Fog node to recover tasks
    from a failed Fog node.

    Recovery accepts all priorities, including HIGH.
    """

    candidates = [
        node for node in nodes
        if (
            node.get("fog_id") != failed_fog_id
            and node.get("availability") == "ONLINE"
            and node.get("status") == "ONLINE"
        )
    ]

    if not candidates:
        return None

    return min(candidates, key=calculate_node_score)
