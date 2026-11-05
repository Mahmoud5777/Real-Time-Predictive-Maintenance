"""Initialisation idempotente des catalogues ; aucune mesure de demonstration."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import FogNode, Machine

ZONES = ("A", "B", "C")


@dataclass(frozen=True)
class CatalogueResult:
    fog_inserted: int
    machines_inserted: int
    fog_total: int
    machines_total: int


async def initialize_catalogue(session: AsyncSession) -> CatalogueResult:
    """Insere seulement les entrees absentes ; l'appelant gere la transaction.

    Les etats observes, noms personnalises et metadonnees existants sont preserves.
    UNSPECIFIED indique un type de machine a renseigner ; installed_at reste inconnu.
    """
    fog_result = await session.execute(
        insert(FogNode)
        .values([{"fog_id": f"FOG_{zone}", "zone": zone} for zone in ZONES])
        .on_conflict_do_nothing(index_elements=["fog_id"])
        .returning(FogNode.fog_id)
    )
    fog_inserted = len(fog_result.scalars().all())

    machines = []
    for number in range(1, 13):
        machine_id = f"M{number:02d}"
        zone = ZONES[(number - 1) // 4]
        machines.append(
            {
                "machine_id": machine_id,
                "name": f"Machine {machine_id}",
                "zone": zone,
                "fog_id": f"FOG_{zone}",
            }
        )

    machine_result = await session.execute(
        insert(Machine)
        .values(machines)
        .on_conflict_do_nothing(index_elements=["machine_id"])
        .returning(Machine.machine_id)
    )
    machines_inserted = len(machine_result.scalars().all())

    fog_total = (await session.execute(select(func.count()).select_from(FogNode))).scalar_one()
    machines_total = (await session.execute(select(func.count()).select_from(Machine))).scalar_one()
    return CatalogueResult(fog_inserted, machines_inserted, fog_total, machines_total)
