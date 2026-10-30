"""T10/B3 - Peuple la base avec des donnees de demonstration.

Utilite reelle : rendre MP3 testable et demontrable sans dependre du calendrier de MP1/MP2.

    python scripts/seed.py --scenario degradation --zone A --duration 120
"""

import argparse
import asyncio
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

MACHINES = {f"M{i:02d}": ("A", "B", "C")[(i - 1) // 4] for i in range(1, 13)}
TYPES = ["ELECTRIC_MOTOR", "PUMP", "COMPRESSOR", "FAN", "CONVEYOR", "CNC"]

SCENARIOS = {
    "normal": {},
    "degradation": {"vibration": (4.0, 14.0), "temperature": (68.0, 95.0)},
    "imbalance": {"vibration": (8.0, 20.0)},
    "overheating": {"temperature": (70.0, 110.0)},
}


def build_readings(scenario: str, machine_id: str, at: datetime, progress: float) -> dict:
    profile = SCENARIOS.get(scenario, {})
    rng = random.Random(f"{machine_id}-{at.isoformat()}")

    def ramp(base: float, span: float, key: str, scale: int = 1) -> float:
        if key in profile:
            lo, hi = profile[key]
            return round(lo + (hi - lo) * progress + rng.uniform(-0.4, 0.4) * scale, 2)
        return round(base + rng.uniform(-span, span), 2)

    return {
        "message_id": f"SEED{at.strftime('%Y%m%d%H%M%S')}{machine_id}",
        "machine_id": machine_id,
        "zone": MACHINES[machine_id],
        "timestamp": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "temperature": ramp(68.0, 2.0, "temperature"),
        "vibration": ramp(4.2, 0.6, "vibration"),
        "speed": ramp(1480.0, 25.0, "speed"),
        "current": ramp(12.3, 0.8, "current"),
        "pressure": ramp(6.1, 0.3, "pressure"),
        "power": ramp(8.3, 0.5, "power"),
        "frequency": ramp(50.0, 0.2, "frequency"),
        "state": "FAULT" if progress > 0.85 and scenario != "normal" else "RUNNING",
    }


def generate(scenario: str, zone: str, duration_seconds: int) -> list[dict]:
    start = datetime.now(UTC).replace(microsecond=0)
    targets = [m for m, z in MACHINES.items() if zone == "ALL" or z == zone]
    batch = []
    for step in range(duration_seconds):
        at = start + timedelta(seconds=step)
        progress = step / max(duration_seconds - 1, 1)
        for machine_id in targets:
            batch.append(
                {"kind": "sensor", "payload": build_readings(scenario, machine_id, at, progress)}
            )
    return batch


async def push(messages: list[dict], api_url: str, token: str) -> None:
    import httpx

    async with httpx.AsyncClient(base_url=api_url, timeout=30) as client:
        for chunk_start in range(0, len(messages), 500):
            chunk = messages[chunk_start : chunk_start + 500]
            response = await client.post(
                "/api/v1/ingest/batch",
                json={"messages": chunk},
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            print(f"pushed {chunk_start + len(chunk)}/{len(messages)}: {response.json()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="normal", choices=sorted(SCENARIOS))
    parser.add_argument("--zone", default="ALL", choices=["A", "B", "C", "ALL"])
    parser.add_argument("--duration", type=int, default=60, help="secondes simulees")
    parser.add_argument("--dump", action="store_true", help="ecrire le JSON local, sans API")
    parser.add_argument("--api-url", default="http://localhost:8000/api/v1")
    args = parser.parse_args()

    messages = generate(args.scenario, args.zone, args.duration)
    print(f"{len(messages)} messages generes (scenario={args.scenario}, zone={args.zone})")

    if args.dump:
        out = Path("data") / f"seed_{args.scenario}_{args.zone}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"messages": messages}, indent=2), encoding="utf-8")
        print(f"ecrit dans {out}")
        return

    token = ""
    try:
        from app.config import get_settings

        token = get_settings().ingest_token
    except Exception:  # pragma: no cover - fallback CLI
        pass
    asyncio.run(push(messages, args.api_url, token))


if __name__ == "__main__":
    main()



