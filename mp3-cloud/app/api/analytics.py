"""Read the hourly cache without computing KPI during HTTP requests."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.catalogue import MEASUREMENTS, METRICS, PREDICTION_METRICS, UNAVAILABLE
from app.analytics.windows import HOUR, closed_hour, validate_window
from app.api.deps import PageParams
from app.db.session import get_session
from app.models.tables import KpiRecord
from app.schemas.analytics import KpiPage, KpiRead, Scope
from app.schemas.common import UtcDatetime
from app.services.reads import READ_RESPONSES, read_page

router = APIRouter(prefix="/analytics", tags=["analytics"], responses=READ_RESPONSES)


def invalid(message, field="from"):
    raise RequestValidationError(
        [{"type": "value_error", "loc": ("query", field), "msg": message, "input": None}]
    )


class HourRange:
    def __init__(
        self,
        from_: UtcDatetime | None = Query(default=None, alias="from"),
        to: UtcDatetime | None = Query(default=None),
    ):
        end = to or closed_hour(datetime.now(UTC))
        start = from_ or end - HOUR
        try:
            self.start, self.end = validate_window(start, end, datetime.now(UTC))
        except ValueError as exc:
            invalid(str(exc))


class KpiScope:
    def __init__(
        self,
        scope: Scope = "plant",
        scope_value: str | None = Query(default=None, min_length=1, max_length=64),
    ):
        valid = {
            "plant": {"all"},
            "zone": {"A", "B", "C"},
            "fog": {"FOG_A", "FOG_B", "FOG_C"},
            "machine": {f"M{number:02d}" for number in range(1, 13)},
        }
        if scope_value is not None and scope in valid and scope_value not in valid[scope]:
            invalid("scope_value does not belong to scope", "scope_value")
        self.scope = scope
        self.value = "all" if scope == "plant" else scope_value


async def cached(
    session,
    window,
    page,
    scope,
    metrics,
    value=None,
    *,
    risk_order=False,
    note="Hourly observations; missing rows have no numeric value",
):
    query = select(KpiRecord).where(
        KpiRecord.metric.in_([metric for metric in metrics if metric in METRICS]),
        KpiRecord.scope == scope,
        KpiRecord.bucket_start >= window.start,
        KpiRecord.bucket_start < window.end,
    )
    if value is not None:
        query = query.where(KpiRecord.scope_value == value)
    if risk_order:
        query = query.order_by(KpiRecord.value.desc(), KpiRecord.scope_value)
    else:
        query = query.order_by(
            KpiRecord.bucket_start.desc(), KpiRecord.scope_value, KpiRecord.metric
        )
    result = await read_page(session, query, page, KpiRead)
    return KpiPage(
        **result.model_dump(),
        from_=window.start,
        to=window.end,
        unavailable_metrics=UNAVAILABLE,
        empty_reason="No cached observations match; refresh may be pending or input absent"
        if result.meta.total == 0
        else None,
        note=note,
    )


@router.get("/kpis", response_model=KpiPage)
async def kpis(
    metric: str | None = Query(default=None, min_length=1, max_length=48),
    scope: KpiScope = Depends(),
    window: HourRange = Depends(),
    page: PageParams = Depends(),
    session: AsyncSession = Depends(get_session),
):
    if metric is not None and metric not in METRICS and metric not in UNAVAILABLE:
        invalid("Unknown metric; see KPI_FORMULAS.md", "metric")
    return await cached(
        session, window, page, scope.scope, [metric] if metric else METRICS, scope.value
    )


@router.get("/measurements", response_model=KpiPage)
async def measurements(
    scope: KpiScope = Depends(),
    window: HourRange = Depends(),
    page: PageParams = Depends(),
    session: AsyncSession = Depends(get_session),
):
    if scope.scope == "model":
        invalid("Measurements do not have a model scope", "scope")
    return await cached(
        session,
        window,
        page,
        scope.scope,
        [f"mean_{name}" for name in MEASUREMENTS] + ["measurement_count"],
        scope.value,
    )


@router.get("/model-comparison", response_model=KpiPage)
async def model_comparison(
    model_version: str | None = Query(default=None, min_length=1, max_length=64),
    window: HourRange = Depends(),
    page: PageParams = Depends(),
    session: AsyncSession = Depends(get_session),
):
    return await cached(
        session,
        window,
        page,
        "model",
        PREDICTION_METRICS,
        model_version,
        note="Prediction distributions by model/hour; this does not measure accuracy",
    )


@router.get("/risk-ranking", response_model=KpiPage)
async def risk_ranking(
    window: HourRange = Depends(),
    page: PageParams = Depends(),
    session: AsyncSession = Depends(get_session),
):
    if window.end - window.start != HOUR:
        invalid("Risk ranking compares exactly one completed hour")
    return await cached(
        session,
        window,
        page,
        "machine",
        ["mean_risk_score"],
        risk_order=True,
        note="Machines ranked by mean reported risk; sample sizes may differ",
    )
