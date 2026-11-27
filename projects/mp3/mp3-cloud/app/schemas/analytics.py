"""Long-form hourly results with units, sample support and freshness."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import computed_field

from app.analytics.catalogue import METRICS
from app.config import get_settings
from app.schemas.common import UtcDatetime
from app.schemas.reads import Page, ReadModel

Scope = Literal["plant", "zone", "machine", "fog", "model"]


class KpiRead(ReadModel):
    metric: str
    scope: Scope
    scope_value: str
    bucket_start: UtcDatetime
    bucket_end: UtcDatetime
    value: float
    sample_size: int
    computed_at: UtcDatetime

    @computed_field
    @property
    def unit(self) -> str:
        return METRICS[self.metric].unit

    @computed_field
    @property
    def time_basis(self) -> str:
        return METRICS[self.metric].time_basis

    @computed_field
    @property
    def quality(self) -> Literal["LOW_SAMPLE", "OBSERVED"]:
        return "LOW_SAMPLE" if self.sample_size < 30 else "OBSERVED"

    @computed_field
    @property
    def stale(self) -> bool:
        return (datetime.now(UTC) - self.computed_at).total_seconds() > (
            3 * get_settings().kpi_refresh_seconds
        )


class KpiPage(Page[KpiRead]):
    from_: UtcDatetime
    to: UtcDatetime
    unavailable_metrics: dict[str, str]
    empty_reason: str | None
    note: str
