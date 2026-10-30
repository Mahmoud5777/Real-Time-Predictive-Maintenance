"""Verifie que les fixtures partagees du contrat sont bien acceptees/rejetees.

Usage : python scripts/check_contract.py   (depuis mp3-cloud/)
Ce script est l artefact d integration de la semaine 1 : il prouve a l equipe que le
contrat est executable, pas seulement documente.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError

from app.services.ingest import parse_message

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
FIXTURES = REPO_ROOT / "contracts" / "fixtures"


def load(path: Path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("kind", path.stem.split("_")[0]), raw.get("payload", raw)


def main() -> int:
    failures = []
    for folder, expect_valid in (("valid", True), ("invalid", False)):
        for path in sorted((FIXTURES / folder).glob("*.json")):
            kind, payload = load(path)
            try:
                parse_message(kind, payload)
                ok = expect_valid
                detail = "accepted"
            except (ValidationError, ValueError) as exc:
                ok = not expect_valid
                detail = f"rejected ({exc.__class__.__name__})"
            status = "PASS" if ok else "FAIL"
            print(f"[{status}] {folder}/{path.name}: {detail}")
            if not ok:
                failures.append(path)
    print(f"\n{len(failures)} fixture(s) non conforme(s) au contrat")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

