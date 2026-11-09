"""Producteurs MQTT cadences et lecteur HTTP sur l'hote, hors des processus backend."""

import asyncio
import hashlib
import json
import math
import platform
import threading
import time
from collections import Counter
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import paho.mqtt.client as mqtt
from prometheus_client.parser import text_string_to_metric_families

from scripts.lab import ROOT, STATE_FILE, probe
from scripts.lab_common import distribution, histogram_quantile, prediction, sensor

READ_PATHS = (
    "/api/v1/machines?limit=12",
    "/api/v1/measurements?machine_id=M01&limit=50",
    "/api/v1/predictions?fog_id=FOG_B&limit=50",
    "/api/v1/alerts?status=OPEN",
    "/api/v1/fog/nodes",
    "/api/v1/tasks/events?time_field=received_at",
)


def parse_metrics(body):
    return {(sample.name, tuple(sorted(sample.labels.items()))): sample.value
            for family in text_string_to_metric_families(body) for sample in family.samples}


def total(samples, name, **labels):
    return sum(value for (metric, actual), value in samples.items()
               if metric == name and all(dict(actual).get(k) == v for k, v in labels.items()))


async def metrics(client, state):
    result = {}
    for service, offset in (("ingest", 1), ("analytics", 2), ("supervision", 3), ("retention", 4)):
        response = await client.get(f"http://127.0.0.1:{state['api_port'] + offset}/metrics")
        response.raise_for_status()
        result[service] = parse_metrics(response.text)
    return result


def confirmed_for_run(before, current, published):
    confirmed = total(current, "fog_cloud_mqtt_accepted_total") - total(
        before, "fog_cloud_mqtt_accepted_total"
    )
    if confirmed < 0:
        raise ValueError("Compteur MQTT reinitialise pendant le test ; mesure invalide")
    if confirmed > published:
        raise ValueError("Trafic MQTT exterieur au run : confirmes depasse publies. "
                         "Les metriques partagees ne peuvent pas valider cet essai")
    return confirmed


async def wait_for_quiet_ingest(client, state):
    """Laisser finir un ancien run interrompu avant la baseline des metriques."""
    deadline = time.perf_counter() + 30
    previous, quiet_since = None, time.perf_counter()
    while True:
        snapshot = (await metrics(client, state))["ingest"]
        counts = tuple(total(snapshot, name) for name in (
            "fog_cloud_mqtt_received_total", "fog_cloud_mqtt_accepted_total",
            "fog_cloud_mqtt_duplicates_total", "fog_cloud_mqtt_rejected_total",
            "fog_cloud_mqtt_acknowledgements_total",
        ))
        now = time.perf_counter()
        if counts != previous or total(snapshot, "fog_cloud_mqtt_queue_depth") != 0:
            previous, quiet_since = counts, now
        elif now - quiet_since >= 2:
            return
        if now >= deadline:
            raise ValueError("MQTT reste actif avant le test ; arreter les autres producteurs")
        await asyncio.sleep(.25)


def connect_publisher(state, zone):
    connected = threading.Event()
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"lab-{zone}-{uuid4().hex[:16]}")

    def on_connect(_client, _userdata, _flags, reason, _properties):
        if not reason.is_failure:
            connected.set()

    client.on_connect = on_connect
    client.connect("127.0.0.1", state["mqtt_port"], keepalive=30)
    client.loop_start()
    if not connected.wait(5):
        client.disconnect()
        client.loop_stop()
        raise ValueError("MQTT laboratory connection timed out")
    return client


async def run_load(state, seconds, hz, read_hz):
    run_id = f"lab{uuid4().hex}"
    started_at = datetime.now(UTC)
    report = {
        "run_id": run_id, "started_at": started_at.isoformat(), "status": "incomplete",
        "load": {"seconds": seconds, "per_machine_hz": hz, "read_hz": read_hz,
                 "machines": 12, "zones": ["A", "B", "C"], "mqtt_qos": 1},
        "environment": {"host_python": platform.python_version(),
                        "host_os": platform.platform(), "api_port": state["api_port"],
                        "project": state["project"],
                        "topology": "host generator; API/ingest/analytics/supervision/retention "
                                    "in five separate Docker processes; dedicated PostgreSQL/MQTT"},
        "method": {"http": "client perf_counter until JSON decoded, per route",
                   "mqtt": "worker monotonic receipt until confirmed persistence decision; "
                           "p95 reported as Prometheus bucket interval, not exact latency",
                   "limits": "synthetic values; no ML or real Fog VM; same physical host; "
                             "not a comparison at the same load as step 9"},
    }
    digest = hashlib.sha256()
    for path in sorted([*ROOT.glob("app/**/*.py"), *ROOT.glob("scripts/lab*.py")]):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    report["environment"]["source_sha256"] = digest.hexdigest()
    sent = Counter()
    infos, publishers = [], []
    first_sensor = []
    errors = []
    send_lags, samples = [], {path: [] for path in READ_PATHS}
    skipped = Counter()
    max_queue = 0
    stop = asyncio.Event()
    tasks = []
    report_path = STATE_FILE.parent / f"{started_at:%Y%m%dT%H%M%S%fZ}-{hz:g}hz.json"
    try:
        preparation = await asyncio.to_thread(probe, state, "prepare", run_id)
        report["preparation"] = preparation
        base_url = f"http://127.0.0.1:{state['api_port']}"
        async with httpx.AsyncClient(base_url=base_url, timeout=15) as client:
            for path in READ_PATHS:
                warmup = await client.get(path)
                warmup.raise_for_status()
            await wait_for_quiet_ingest(client, state)
            before = await metrics(client, state)
            for service, name in (("ingest", "fog_cloud_mqtt_ready"),
                                  ("analytics", "fog_cloud_kpi_ready"),
                                  ("supervision", "fog_cloud_supervision_ready"),
                                  ("retention", "fog_cloud_retention_ready")):
                if total(before[service], name) != 1:
                    raise ValueError(f"Laboratory worker {service} is not ready")
            for zone in "ABC":
                publishers.append(await asyncio.to_thread(connect_publisher, state, zone))

            def publish(index, kind, body):
                if kind == "sensor":
                    topic = f"fog/{body['zone']}/sensor/{body['machine_id']}"
                elif kind == "task_event":
                    topic = "tasks/events"
                else:
                    suffix = {"prediction": "predictions", "fog_status": "status",
                              "alert": "alerts"}[kind]
                    topic = f"fog/{body['fog_id']}/{suffix}"
                info = publishers[index].publish(topic, json.dumps(body), qos=1,
                                                 retain=kind == "fog_status")
                if info.rc != mqtt.MQTT_ERR_SUCCESS:
                    raise ValueError("MQTT publish failed")
                infos.append(info)
                sent[kind] += 1
                if kind == "sensor" and not first_sensor:
                    first_sensor.append(body)

            def heartbeat(index, sequence):
                zone = "ABC"[index]
                publish(index, "fog_status", {
                    "message_id": f"{run_id}-live-h-{zone}-{sequence}", "fog_id": f"FOG_{zone}",
                    "zone": zone, "status": "ONLINE", "cpu_percent": 30 + index * 10,
                    "ram_percent": 45, "queued_tasks": 0, "active_tasks": 1,
                    "last_heartbeat": datetime.now(UTC).isoformat(),
                })

            for index, zone in enumerate("ABC"):
                now = datetime.now(UTC)
                fog, machine = f"FOG_{zone}", f"M{index * 4 + 1:02d}"
                publish(index, "alert", {
                    "message_id": f"{run_id}-live-a-{zone}", "alert_id": f"{run_id}-{zone}",
                    "machine_id": machine, "fog_id": fog, "timestamp": now.isoformat(),
                    "type": "ANOMALY_DETECTED", "severity": "WARNING",
                    "message": "Alerte synthetique du laboratoire",
                })
                task_id = str(uuid4())
                destination = f"FOG_{'ABC'[(index + 1) % 3]}"
                for status in ("CREATED", "MIGRATED", "COMPLETED"):
                    publish(index, "task_event", {
                        "message_id": f"{run_id}-live-t-{zone}-{status}", "task_id": task_id,
                        "task_type": "AGGREGATION", "priority": "MEDIUM", "critical": False,
                        "source_fog": destination if status == "COMPLETED" else fog,
                        "destination_fog": destination if status == "MIGRATED" else None,
                        "status": status, "created_at": now.isoformat(),
                        "completed_at": datetime.now(UTC).isoformat()
                        if status == "COMPLETED" else None,
                        "reason": "Scenario synthetique de partage",
                    })

            clock = time.perf_counter()

            async def produce(index):
                zone = "ABC"[index]
                for tick in range(math.ceil(seconds * hz)):
                    due = clock + tick / hz
                    await asyncio.sleep(max(0, due - time.perf_counter()))
                    lag = time.perf_counter() - due
                    if lag >= 1 / hz:
                        skipped[zone] += 1
                        continue  # Aucun rattrapage par rafale qui fausserait la cadence.
                    send_lags.append(lag)
                    now = datetime.now(UTC)
                    for number in range(index * 4 + 1, index * 4 + 5):
                        machine = f"M{number:02d}"
                        publish(index, "sensor", sensor(
                            f"{run_id}-live-s-{number}-{tick}", machine, zone, now, tick=tick
                        ))

            async def forecasts():
                for tick in range(math.ceil(seconds / 10)):
                    await asyncio.sleep(max(0, clock + tick * 10 - time.perf_counter()))
                    now = datetime.now(UTC)
                    for index, zone in enumerate("ABC"):
                        for number in range(index * 4 + 1, index * 4 + 5):
                            publish(index, "prediction", prediction(
                                f"{run_id}-live-p-{number}-{tick}", f"M{number:02d}",
                                f"FOG_{zone}", now,
                            ))

            async def hearts():
                for tick in range(math.ceil(seconds / 5)):
                    await asyncio.sleep(max(0, clock + tick * 5 - time.perf_counter()))
                    for index in range(3):
                        heartbeat(index, tick)

            async def read(path):
                at = time.perf_counter()
                response = await client.get(path)
                response.json()
                if response.status_code != 200:
                    errors.append({"path": path, "status": response.status_code})
                else:
                    samples[path].append(time.perf_counter() - at)

            async def dashboard():
                for tick in range(math.ceil(seconds * read_hz)):
                    await asyncio.sleep(max(0, clock + tick / read_hz - time.perf_counter()))
                    if time.perf_counter() - (clock + tick / read_hz) >= 1 / read_hz:
                        skipped["dashboard"] += 1
                        continue
                    await asyncio.gather(*(read(path) for path in READ_PATHS))

            async def progress():
                nonlocal max_queue
                while not stop.is_set():
                    snapshot = await metrics(client, state)
                    queue = total(snapshot["ingest"], "fog_cloud_mqtt_queue_depth")
                    max_queue = max(max_queue, queue)
                    elapsed = time.perf_counter() - clock
                    accepted = confirmed_for_run(before["ingest"], snapshot["ingest"],
                                                 sum(sent.values()))
                    print(f"{elapsed:5.1f}s | publies={sum(sent.values()):5d} "
                          f"confirmes={int(accepted):5d} | file MQTT={int(queue)}", flush=True)
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=5)
                    except TimeoutError:
                        pass

            print(f"Test {seconds}s : {hz:g} Hz/machine = {12 * hz:g} mesures/s, "
                  f"dashboard {read_hz:g} Hz. API {base_url}", flush=True)
            progress_task = asyncio.create_task(progress())
            tasks = [asyncio.create_task(operation) for operation in (
                produce(0), produce(1), produce(2), hearts(), forecasts(), dashboard()
            )]
            try:
                workload = asyncio.gather(*tasks)
                done, _pending = await asyncio.wait(
                    [workload, progress_task], return_when=asyncio.FIRST_COMPLETED
                )
                if progress_task in done:
                    progress_task.result()
                    raise ValueError("Suivi du test arrete avant la fin du generateur")
                await workload
                await asyncio.sleep(max(0, clock + seconds - time.perf_counter()))
                deadline = time.perf_counter() + 30
                while True:
                    after = await metrics(client, state)
                    confirmed = confirmed_for_run(before["ingest"], after["ingest"],
                                                  sum(sent.values()))
                    if confirmed == sum(sent.values()) and all(
                        info.is_published() for info in infos
                    ):
                        break
                    if time.perf_counter() >= deadline:
                        raise ValueError("Cloud drain timeout; inspect laboratory ingest logs")
                    await asyncio.sleep(.2)
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                # Consommer aussi l'exception du gather si le suivi a echoue le premier.
                await asyncio.gather(workload, return_exceptions=True)
                stop.set()
                await progress_task
            duration = time.perf_counter() - clock
            database = await asyncio.to_thread(probe, state, "inspect", run_id)
            report["database"] = database
            for kind, expected in sent.items():
                if database["live_counts"][kind] != expected:
                    raise ValueError(f"SQL verification failed for {kind}")
            if errors:
                raise ValueError("Dashboard HTTP requests failed")
            rejected = total(after["ingest"], "fog_cloud_mqtt_rejected_total") - total(
                before["ingest"], "fog_cloud_mqtt_rejected_total"
            )
            if rejected:
                raise ValueError("MQTT messages were rejected")
            # Verifier un rejeu HTTP du meme message, sans ajouter une observation.
            replay = await client.post("/api/v1/ingest/batch", json={"messages": [
                {"kind": "sensor", "payload": first_sensor[0]}
            ] * 2}, headers={"Authorization": "Bearer mp3-lab-token"})
            if replay.status_code != 207 or replay.json()["duplicates"] != 2:
                raise ValueError("Laboratory replay verification failed")
            count_name = "fog_cloud_mqtt_processing_seconds_count"
            count = total(after["ingest"], count_name) - total(before["ingest"], count_name)
            if count != confirmed:
                raise ValueError("Histogramme MQTT contamine par des messages hors run")
            buckets = {
                float(dict(labels)["le"]): value - before["ingest"].get((name, labels), 0)
                for (name, labels), value in after["ingest"].items()
                if name == "fog_cloud_mqtt_processing_seconds_bucket"
            }
            total_time = total(after["ingest"], "fog_cloud_mqtt_processing_seconds_sum") - total(
                before["ingest"], "fog_cloud_mqtt_processing_seconds_sum"
            )
            report.update({
                "status": "passed", "published": dict(sent), "confirmed": int(confirmed),
                "elapsed_including_drain_s": duration,
                "achieved_sensor_hz": sent["sensor"] / (12 * seconds),
                "workload_valid": sent["sensor"] == 12 * math.ceil(seconds * hz)
                                  and not any(skipped.values()),
                "generator_lag": distribution(send_lags), "skipped_ticks": dict(skipped),
                "http_errors": errors, "mqtt_rejected": int(rejected),
                "read_routes": {path: distribution(values) for path, values in samples.items()},
                "all_read_routes": distribution([v for values in samples.values() for v in values]),
                "mqtt_mean_receipt_to_commit_ms": 1000 * total_time / count,
                "mqtt_p95_bucket": histogram_quantile(buckets, count),
                "queue_max_sampled": max_queue, "queue_sampling_seconds": 5,
                "replay_duplicates": 2,
                "worker_cycles": {
                    service: {outcome: int(total(after[service], f"{prefix}_refresh_total",
                                                outcome=outcome) - total(
                        before[service], f"{prefix}_refresh_total", outcome=outcome
                    )) for outcome in ("success", "busy", "error")}
                    for service, prefix in (("analytics", "fog_cloud_kpi"),
                                            ("supervision", "fog_cloud_supervision"),
                                            ("retention", "fog_cloud_retention"))
                },
            })
    except asyncio.CancelledError:
        report["failure"] = {"type": "Interrupted", "message": "Test interrompu avant son bilan"}
        raise
    except Exception as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        raise ValueError(f"Test interrompu ({type(exc).__name__}) : {exc}") from exc
    finally:
        report["finished_at"] = datetime.now(UTC).isoformat()
        report["published"] = dict(sent)
        report.setdefault("read_routes", {
            path: distribution(values) for path, values in samples.items()
        })
        report.setdefault("all_read_routes", distribution([
            value for values in samples.values() for value in values
        ]))
        report.setdefault("skipped_ticks", dict(skipped))
        report.setdefault("generator_lag", distribution(send_lags))
        for publisher in publishers:
            publisher.disconnect()
            await asyncio.to_thread(publisher.loop_stop)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Rapport : {report_path}", flush=True)
    p95 = report["all_read_routes"]["p95_ms"]
    p95_label = f"{p95:.1f} ms" if p95 is not None else "indisponible (<100 lectures)"
    print(f"PASS coherence : {report['confirmed']} messages confirmes ; "
          f"p95 HTTP combine {p95_label} ; "
          f"MQTT moyen {report['mqtt_mean_receipt_to_commit_ms']:.1f} ms", flush=True)
    if not report["workload_valid"]:
        print("Cadence incomplete : consulter skipped_ticks. Ce run ne valide pas la charge cible.")
    print(f"Retention : {report['database']['old_remaining']}/36 anciennes observations restantes. "
          "Swagger reste accessible ; stop supprime seulement le laboratoire.", flush=True)
