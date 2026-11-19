"""Preview one bounded expired-hour batch; --apply finalizes aggregates and removes its raw rows."""

import argparse
import asyncio
import json
from dataclasses import asdict

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.retention.service import run_retention


async def run(args):
    config = get_settings()
    engine = create_async_engine(config.database_url, pool_pre_ping=True)
    try:
        result = await run_retention(async_sessionmaker(engine), config, dry_run=not args.apply)
        if result is None:
            raise SystemExit("App ingestion or another retention cycle is active; retry later")
        print(json.dumps(asdict(result), default=str))
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    except (SQLAlchemyError, OSError, TimeoutError) as exc:
        raise SystemExit(
            f"Retention unavailable ({type(exc).__name__}); no cleanup committed"
        ) from None
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(run(parser.parse_args()))
