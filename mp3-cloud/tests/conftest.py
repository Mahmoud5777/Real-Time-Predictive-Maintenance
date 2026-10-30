"""Configuration des tests : aucune dependance sur un PostgreSQL ou un broker reel ici.

Les tests d integration base reale vivent dans `tests/test_integration_*.py` et sont
sautés quand `DATABASE_URL` ne pointe pas sur une base accessible.
"""

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _force_ingest_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixe le token d ingestion pour que les tests ne dependent jamais du `.env` local."""
    monkeypatch.setattr(settings, "ingest_token", "test-token", raising=False)
