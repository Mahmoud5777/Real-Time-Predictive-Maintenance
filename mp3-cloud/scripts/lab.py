"""CLI du laboratoire Docker isole : start, run, status, logs, sql et stop."""

import argparse
import asyncio
import json
import os
import subprocess
from contextlib import nullcontext
from pathlib import Path
from uuid import uuid4

from scripts.lab_common import validate_state
from scripts.lab_lock import exclusive_lab_action

ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT / "data" / "lab" / "state.json"
COMPOSE = ROOT / "docker-compose.lab.yml"
SERVICES = ("api", "db", "mosquitto", "ingest", "analytics", "supervision", "retention")


def load_state():
    if not STATE_FILE.exists():
        raise ValueError("Laboratoire absent. Lancer : python -m scripts.lab start")
    return validate_state(json.loads(STATE_FILE.read_text(encoding="utf-8")))


def compose(state, *args, capture=True, timeout=60):
    validate_state(state)
    environment = os.environ.copy()
    environment["MP3_LAB_API_PORT"] = str(state["api_port"])
    environment["MP3_LAB_MQTT_PORT"] = str(state["mqtt_port"])
    for offset, service in enumerate(("INGEST", "ANALYTICS", "SUPERVISION", "RETENTION"), 1):
        environment[f"MP3_LAB_{service}_PORT"] = str(state["api_port"] + offset)
    # --env-file nul empeche la lecture du .env de travail par Compose.
    command = ["docker", "compose", "--env-file", os.devnull, "-f", str(COMPOSE),
               "-p", state["project"], *args]
    return subprocess.run(
        command, cwd=ROOT, env=environment, check=True, capture_output=capture,
        text=True, timeout=timeout,
    )


def verify_containers(state):
    """Exiger les sept services du projet exact avant une publication ou une suppression."""
    ids = compose(state, "ps", "--all", "--quiet").stdout.split()
    if not ids:
        raise ValueError("Conteneurs du laboratoire absents ; relancer start ou nettoyer stop")
    inspected = subprocess.run(
        ["docker", "inspect", *ids], check=True, capture_output=True, text=True, timeout=30
    )
    services = set()
    for container in json.loads(inspected.stdout):
        labels = container["Config"].get("Labels") or {}
        verify_owner(labels, state)
        service = labels.get("com.docker.compose.service")
        ports = {"api": (8000, state["api_port"]),
                 "mosquitto": (1883, state["mqtt_port"])}
        for offset, worker in enumerate(("ingest", "analytics", "supervision", "retention"), 1):
            ports[worker] = (8000 + offset, state["api_port"] + offset)
        if service in ports:
            internal, external = ports[service]
            bindings = container["NetworkSettings"]["Ports"].get(f"{internal}/tcp") or []
            if bindings != [{"HostIp": "127.0.0.1", "HostPort": str(external)}]:
                raise ValueError("Laboratory ports do not match state.json; refusing host traffic")
        services.add(service)
    if services != set(SERVICES):
        raise ValueError("Laboratoire incomplet. Examiner les logs avant de le reutiliser")


def verify_owner(labels, state):
    if labels.get("com.docker.compose.project") != state["project"]:
        raise ValueError("Refusing a container outside this laboratory")
    owner = labels.get("com.docker.compose.project.working_dir", "")
    if os.path.normcase(os.path.normpath(owner)) != os.path.normcase(str(ROOT)):
        raise ValueError("Refusing a laboratory owned by another workspace")


def probe(state, action="inspect", run_id=None):
    command = ["exec", "-T", "api", "python", "-m", "scripts.lab_probe", action]
    if run_id:
        command.extend(["--run-id", run_id])
    result = compose(state, *command)
    return json.loads(result.stdout)


def start(api_port=8100, mqtt_port=1884):
    if STATE_FILE.exists():
        state = load_state()
        print("Laboratoire existant ; conservation de ses donnees.", flush=True)
    else:
        state = validate_state({"project": f"mp3lab_{uuid4().hex[:12]}",
                                "database": "fog_lab", "api_port": api_port,
                                "mqtt_port": mqtt_port})
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Creation exclusive : deux start concurrents ne doivent pas ecraser l'identite.
        with STATE_FILE.open("x", encoding="utf-8") as file:
            json.dump(state, file)
    print(f"Demarrage du laboratoire {state['project']}...", flush=True)
    compose(state, "build", "api", capture=False, timeout=300)
    compose(state, "up", "-d", "--wait", "--wait-timeout", "120", capture=False, timeout=180)
    verify_containers(state)
    print(f"Swagger laboratoire : http://127.0.0.1:{state['api_port']}/docs", flush=True)
    print("Test : python -m scripts.lab run --seconds 60 --hz 1", flush=True)


def stop(state):
    # Le fichier Compose fixe les seuls deux volumes nommes, sans volumes externes.
    # Le namespace valide interdit de passer mp3-cloud ou un projet arbitraire.
    validate_state(state)
    ids = compose(state, "ps", "--all", "--quiet").stdout.split()
    if ids:
        inspected = subprocess.run(
            ["docker", "inspect", *ids], check=True, capture_output=True, text=True, timeout=30
        )
        for container in json.loads(inspected.stdout):
            labels = container["Config"].get("Labels") or {}
            verify_owner(labels, state)
    compose(state, "down", "--volumes", capture=False, timeout=90)
    STATE_FILE.unlink()
    print("Laboratoire et ses volumes supprimes. Rapports conserves dans data/lab/.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    create = actions.add_parser("start", help="Construire et lancer le laboratoire")
    create.add_argument("--api-port", type=int, default=8100)
    create.add_argument("--mqtt-port", type=int, default=1884)
    run = actions.add_parser("run", help="Mesurer une charge cadensee")
    run.add_argument("--seconds", type=int, default=60)
    run.add_argument("--hz", type=float, default=1, help="Mesures/seconde pour chaque machine")
    run.add_argument("--read-hz", type=float, default=1, help="Rafraichissements dashboard/seconde")
    logs = actions.add_parser("logs", help="Consulter les logs d'un service du laboratoire")
    logs.add_argument("service", choices=SERVICES, default="ingest", nargs="?")
    logs.add_argument("--tail", type=int, default=30)
    actions.add_parser("status", help="Voir les conteneurs et compteurs SQL")
    actions.add_parser("sql", help="Ouvrir psql dans fog_lab uniquement")
    actions.add_parser("stop", help="Supprimer uniquement le laboratoire et ses volumes")
    args = parser.parse_args()
    try:
        action_lock = (
            exclusive_lab_action(args.action, STATE_FILE.parent / "control.lock")
            if args.action in {"start", "run", "stop"} else nullcontext()
        )
        with action_lock:
            if args.action == "start":
                start(args.api_port, args.mqtt_port)
                return
            state = load_state()
            if args.action == "stop":
                stop(state)
                return
            verify_containers(state)
            if args.action == "run":
                if not (10 <= args.seconds <= 600 and .1 <= args.hz <= 20
                        and .1 <= args.read_hz <= 5 and args.seconds * args.hz * 12 <= 100000):
                    parser.error(
                        "seconds 10..600, hz 0.1..20, read-hz 0.1..5, au plus 100000 mesures"
                    )
                from scripts.lab_load import run_load
                asyncio.run(run_load(state, args.seconds, args.hz, args.read_hz))
            elif args.action == "status":
                compose(state, "ps", capture=False)
                snapshot = probe(state)
                snapshot.pop("query_plans", None)
                print(json.dumps(snapshot, indent=2))
                print(f"Swagger : http://127.0.0.1:{state['api_port']}/docs")
            elif args.action == "logs":
                if not 1 <= args.tail <= 1000:
                    parser.error("tail doit etre compris entre 1 et 1000")
                compose(state, "logs", "--tail", str(args.tail), args.service, capture=False)
            elif args.action == "sql":
                compose(state, "exec", "db", "psql", "-U", "lab", "-d", "fog_lab",
                        capture=False, timeout=None)
    except KeyboardInterrupt:
        print("Test interrompu ; le laboratoire reste disponible. Utiliser status ou stop.")
        raise SystemExit(130) from None
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"Laboratoire : {exc}")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
