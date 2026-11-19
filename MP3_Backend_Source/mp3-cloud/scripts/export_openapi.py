"""Synchronise les lectures livrees et conserve les operations futures marquees planned.

    python -m scripts.export_openapi
    python -m scripts.export_openapi --check

Le contrat reste en OpenAPI 3.0.3 pour les consommateurs existants. FastAPI expose
3.1 : les schemas nullable et const sont convertis sans changer le contenu JSON.
"""

import argparse
import copy
import re
from pathlib import Path

import yaml
from openapi_spec_validator import validate

from app.config import get_settings
from app.main import app

CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"
METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def openapi30(value):
    if isinstance(value, list):
        return [openapi30(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: openapi30(item) for key, item in value.items()}
    alternatives = result.get("anyOf", [])
    if {"type": "null"} in alternatives:
        non_null = [item for item in alternatives if item != {"type": "null"}]
        if len(non_null) != 1:
            raise ValueError("Unsupported nullable union in OpenAPI 3.0 export")
        result.pop("anyOf")
        inner = non_null[0]
        if "$ref" in inner:
            inner = {"allOf": [inner]}
        result = {**inner, **result, "nullable": True}
    if "const" in result:
        result["enum"] = [result.pop("const")]
    if result.get("nullable") and "enum" in result and None not in result["enum"]:
        result["enum"].append(None)
    for bound, inclusive in (("exclusiveMinimum", "minimum"), ("exclusiveMaximum", "maximum")):
        if bound in result and not isinstance(result[bound], bool):
            result[inclusive] = result[bound]
            result[bound] = True
    return result


def referenced_schemas(value) -> set[str]:
    if isinstance(value, dict):
        refs = set()
        reference = value.get("$ref", "")
        if reference.startswith("#/components/schemas/"):
            refs.add(reference.rsplit("/", 1)[1])
        for item in value.values():
            refs.update(referenced_schemas(item))
        return refs
    if isinstance(value, list):
        return set().union(*(referenced_schemas(item) for item in value))
    return set()


def build_contract(existing: dict) -> dict:
    contract = copy.deepcopy(existing)
    live = app.openapi()
    prefix = get_settings().api_prefix
    contract["info"]["description"] = (
        "Contrat MP3 : les lectures marquees implemented correspondent a l'API FastAPI. "
        "Les operations marquees planned sont une feuille de route, pas des routes disponibles. "
        "Lectures publiques pour la demonstration locale ; ingestion protegee par bearer token."
    )
    contract["servers"] = [{"url": f"http://localhost:8000{prefix}"}]
    for path, operations in contract["paths"].items():
        for method, operation in operations.items():
            if method in METHODS:
                operation["x-implementation-status"] = (
                    "implemented" if path == "/ingest/batch" and method == "post" else "planned"
                )
    schemas = contract["components"]["schemas"]
    required = set()
    for path, operations in live["paths"].items():
        if not path.startswith(prefix + "/") or "get" not in operations:
            continue
        relative = path.removeprefix(prefix)
        template = re.sub(r"\{[^}]+\}", "{}", relative)
        for old_path in list(contract["paths"]):
            if old_path != relative and re.sub(r"\{[^}]+\}", "{}", old_path) == template:
                del contract["paths"][old_path]
        operation = openapi30(operations["get"])
        operation["x-implementation-status"] = "implemented"
        contract["paths"].setdefault(relative, {})["get"] = operation
        required.update(referenced_schemas(operation))
    pending = list(required)
    while pending:
        name = pending.pop()
        schema = openapi30(live["components"]["schemas"][name])
        schemas[name] = schema
        for dependency in referenced_schemas(schema) - required:
            required.add(dependency)
            pending.append(dependency)
    validate(contract)
    return contract


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verifier sans modifier le fichier")
    args = parser.parse_args()
    current = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    expected = build_contract(current)
    if args.check:
        if current != expected:
            raise SystemExit("Contrat des lectures obsolete : python -m scripts.export_openapi")
        print("Contrat OpenAPI 3.0.3 valide et lectures synchronisees.")
        return
    CONTRACT.write_text(
        yaml.safe_dump(expected, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )
    print(f"Contrat synchronise : {CONTRACT}")


if __name__ == "__main__":
    main()
