"""Refresh one closed hour by default; explicit UTC whole-hour ranges supported."""

import argparse
import asyncio
from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.analytics.aggregate import refresh
from app.analytics.windows import HOUR, closed_hour
from app.config import get_settings


async def run(args):
    config = get_settings()
    engine = create_async_engine(config.database_url, pool_pre_ping=True)
    try:
        end = args.to or closed_hour(datetime.now(UTC))
        start = args.from_ or end - HOUR
        count = await refresh(async_sessionmaker(engine), config, start, end)
        if count is None:
            raise SystemExit("Another KPI refresher is active; retry later")
        print(f"Committed {count} hourly KPI records")
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    except (SQLAlchemyError, OSError, TimeoutError) as exc:
        raise SystemExit(f"Refresh unavailable ({type(exc).__name__}); cache preserved") from None
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="from_", type=datetime.fromisoformat)
    parser.add_argument("--to", type=datetime.fromisoformat)
    asyncio.run(run(parser.parse_args()))
