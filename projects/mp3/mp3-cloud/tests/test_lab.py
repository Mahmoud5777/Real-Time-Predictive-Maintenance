"""Protection de la base de travail et quantiles conservateurs du laboratoire."""

import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import lab, lab_probe
from scripts.lab_common import histogram_quantile
from scripts.lab_load import confirmed_for_run
from scripts.lab_lock import exclusive_lab_action

LOCK_CHILD = """
import sys
from pathlib import Path
from scripts.lab_lock import exclusive_lab_action
try:
    with exclusive_lab_action('run', Path(sys.argv[1])):
        print('LOCKED', flush=True)
        sys.stdin.readline()
except ValueError as exc:
    print(str(exc), flush=True)
    sys.exit(1)
"""


@pytest.mark.parametrize("project", ["mp3-cloud", "other_project", "mp3lab_../work"])
def test_cleanup_command_refuses_non_lab_namespace_before_docker(monkeypatch, project):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Docker must not be called for an invalid laboratory identity")

    monkeypatch.setattr(lab.subprocess, "run", forbidden)
    with pytest.raises(ValueError):
        lab.compose({"project": project, "database": "fog_lab", "api_port": 8100,
                     "mqtt_port": 1884}, "down", "--volumes")


def test_cleanup_command_refuses_working_database_even_with_valid_project(monkeypatch):
    monkeypatch.setattr(
        lab.subprocess, "run", lambda *_args, **_kwargs: pytest.fail("Docker called")
    )
    with pytest.raises(ValueError):
        lab.compose({"project": "mp3lab_0123456789ab", "database": "fog_cloud",
                     "api_port": 8100, "mqtt_port": 1884}, "down", "--volumes")


async def test_probe_rejects_fog_cloud_before_connecting(monkeypatch):
    monkeypatch.setattr("sys.argv", ["lab_probe", "inspect"])
    monkeypatch.setattr(lab_probe, "get_settings", lambda: SimpleNamespace(
        database_url="postgresql+asyncpg://unused:unused@127.0.0.1:1/fog_cloud"
    ))
    with pytest.raises(ValueError, match="other than fog_lab"):
        await lab_probe.main()


def test_host_traffic_refused_when_saved_port_differs_from_running_container(monkeypatch):
    state = {"project": "mp3lab_0123456789ab", "database": "fog_lab",
             "api_port": 8000, "mqtt_port": 1884}
    container = {"Config": {"Labels": {
        "com.docker.compose.project": state["project"],
        "com.docker.compose.project.working_dir": str(lab.ROOT),
        "com.docker.compose.service": "api",
    }}, "NetworkSettings": {"Ports": {"8000/tcp": [
        {"HostIp": "127.0.0.1", "HostPort": "8100"}
    ]}}}
    monkeypatch.setattr(lab, "compose", lambda *_args: SimpleNamespace(stdout="lab-container"))
    monkeypatch.setattr(lab.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(
        stdout=json.dumps([container])
    ))
    with pytest.raises(ValueError, match="ports do not match"):
        lab.verify_containers(state)


def test_histogram_p95_reports_bucket_interval_without_interpolation():
    result = histogram_quantile({.01: 90, .025: 98, .05: 100}, 100)
    assert result == {"samples": 100, "lower_ms": 10, "upper_ms": 25, "overflow": False}


def test_histogram_small_sample_has_no_numeric_p95():
    result = histogram_quantile({.01: 99}, 99)
    assert result["upper_ms"] is None and result["samples"] == 99


def test_histogram_overflow_is_unknown_upper_bound():
    result = histogram_quantile({.01: 50, float("inf"): 100}, 100)
    assert result["overflow"] is True and result["upper_ms"] is None


def test_second_process_cannot_enter_an_active_lab_action(tmp_path):
    lock_path = tmp_path / "control.lock"
    with exclusive_lab_action("run", lock_path):
        second = subprocess.run(
            [sys.executable, "-c", LOCK_CHILD, str(lock_path)], cwd=lab.ROOT,
            input="\n", capture_output=True, text=True, timeout=10,
        )
    assert second.returncode == 1
    assert "Laboratoire occupe" in second.stdout
    with exclusive_lab_action("stop", lock_path):
        pass


def test_lab_lock_releases_after_an_exception(tmp_path):
    lock_path = tmp_path / "control.lock"
    with pytest.raises(RuntimeError):
        with exclusive_lab_action("run", lock_path):
            raise RuntimeError("interrupted generator")
    with exclusive_lab_action("run", lock_path):
        pass


def test_run_cli_rejects_busy_lab_before_loading_state(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(lab, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(sys, "argv", ["lab", "run", "--seconds", "10"])
    assert not lab.STATE_FILE.exists()
    with exclusive_lab_action("run", tmp_path / "control.lock"):
        with pytest.raises(SystemExit) as exc:
            lab.main()
    assert exc.value.code == 1
    assert "Laboratoire occupe" in capsys.readouterr().out


def test_os_releases_lab_lock_after_process_is_killed(tmp_path):
    lock_path = tmp_path / "control.lock"
    owner = subprocess.Popen(
        [sys.executable, "-c", LOCK_CHILD, str(lock_path)], cwd=lab.ROOT,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        assert owner.stdout.readline().strip() == "LOCKED"
        with pytest.raises(ValueError, match="Laboratoire occupe"):
            with exclusive_lab_action("run", lock_path):
                pytest.fail("A second run entered")
    finally:
        owner.kill()
        owner.communicate(timeout=10)
    with exclusive_lab_action("run", lock_path):
        pass


@pytest.mark.parametrize("before,current,published", [(10, 9, 4), (10, 15, 4)])
def test_mqtt_counter_reset_or_external_messages_invalidates_run(before, current, published):
    key = ("fog_cloud_mqtt_accepted_total", ())
    with pytest.raises(ValueError):
        confirmed_for_run({key: before}, {key: current}, published)


def test_mqtt_confirmations_can_lag_behind_publications():
    key = ("fog_cloud_mqtt_accepted_total", ())
    assert confirmed_for_run({key: 10}, {key: 13}, 4) == 3
