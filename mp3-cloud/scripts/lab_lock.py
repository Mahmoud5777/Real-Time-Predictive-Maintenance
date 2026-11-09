"""Verrou interprocessus du laboratoire, libere par l'OS meme apres un crash."""

import json
import os
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


@contextmanager
def exclusive_lab_action(action: str, path: Path):
    """Garder le fichier : le supprimer pourrait creer deux verrous independants."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            # Windows peut aussi refuser une lecture du byte verrouille.
            handle.seek(1)
            try:
                owner = json.loads(handle.read().decode("utf-8"))
                detail = f"{owner['action']} (PID {owner['pid']})"
            except (OSError, ValueError, KeyError):
                detail = "une autre commande"
            raise ValueError(
                f"Laboratoire occupe par {detail}. Attendre sa fin ou faire Ctrl+C "
                "dans son terminal. status, logs et sql restent disponibles."
            ) from exc
        try:
            handle.seek(1)
            handle.truncate()
            handle.write(json.dumps({"action": action, "pid": os.getpid(),
                                     "started_at": datetime.now(UTC).isoformat()}).encode("utf-8"))
            handle.flush()
            yield
        finally:
            handle.seek(1)
            handle.truncate()
            handle.flush()
            handle.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
