import os
import sys
import time
import json
import argparse
from typing import Any, Dict, List
from pathlib import Path

import pandas as pd
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from app.core.core import ts, NewFileHandler, JsonlSink, scan_folder, load_last_snapshot, diff_snapshots, append_snapshot

# -------- Pomocnicze --------

def is_unc_path(path: str) -> bool:
    return path.startswith("\\") or path.startswith("//")


def to_list(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [p.strip() for p in str(value).split(";") if p.strip()]


def truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes", "y", "tak")


def load_sheet_config(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Nie znaleziono arkusza: {p}")

    if p.suffix.lower() == ".csv":
        df = pd.read_csv(p)
    elif p.suffix.lower() in (".xlsx", ".xlsm", ".xltx", ".xltm"):
        df = pd.read_excel(p, engine="openpyxl")
    else:
        raise ValueError("Obsługiwane: CSV, XLSX")

    if "path" not in df.columns:
        raise ValueError("Brak kolumny 'path'")

    entries: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        path = str(row.get("path", "")).strip()
        if not path:
            print(f"[{ts()}] ⚠ Wiersz {idx+2}: pusty path – pomijam")
            continue

        entries.append({
            "path": path,
            "include": to_list(row.get("include")),
            "exclude": to_list(row.get("exclude")),
            "recursive": truthy(row.get("recursive")),
            "observer": str(row.get("observer", "")).strip().lower() or None,
            "stabilize": truthy(row.get("stabilize")),
            "stabilize_seconds": int(row.get("stabilize_seconds", 2)),
            "log_path": str(row.get("log_csv", "")).strip() or None,
            "state_path": str(row.get("state_path", "")).strip() or None,
        })

    return entries


# -------- CLI --------

def parse_args():
    p = argparse.ArgumentParser(description="Monitor folderów – config z Excela, log JSONL")
    p.add_argument("--sheet-config", help="CSV/XLSX z konfiguracją folderów")
    p.add_argument("--observer", choices=["auto", "polling", "auto-smart"], default="auto-smart")
    return p.parse_args()


def effective_observer_for_path(global_choice: str, per_folder_choice: str, path: str) -> str:
    choice = (per_folder_choice or global_choice or "auto-smart").lower()
    if choice == "polling":
        return "polling"
    if choice == "auto":
        return "auto"
    return "polling" if is_unc_path(path) else "auto"


# -------- Main --------

def main():
    args = parse_args()

    if not args.sheet_config:
        print(f"[{ts()}] ❗ Musisz podać --sheet-config")
        sys.exit(2)

    try:
        folders = load_sheet_config(args.sheet_config)
    except Exception as e:
        print(f"[{ts()}] ❗ Błąd wczytywania Excela: {e}")
        sys.exit(1)

    if not folders:
        print(f"[{ts()}] ❗ Brak poprawnych wpisów w konfiguracji")
        sys.exit(2)

    # --- Startup snapshot diff ---
    for e in folders:
        if e.get("state_path") and os.path.exists(e["path"]):
            prev = load_last_snapshot(e["state_path"], e["path"])
            curr = scan_folder(e["path"])
            diff = diff_snapshots(prev, curr)
            if diff:
                sink = JsonlSink(e.get("log_path")) if e.get("log_path") else None
                for ev in diff:
                    if sink:
                        sink.emit({**ev, "ts": ts()})
                append_snapshot(e["state_path"], e["path"], curr)

    group_auto = [e for e in folders if effective_observer_for_path(args.observer, e.get("observer"), e["path"]) == "auto"]
    group_poll = [e for e in folders if effective_observer_for_path(args.observer, e.get("observer"), e["path"]) == "polling"]

    obs_auto = Observer() if group_auto else None
    obs_poll = PollingObserver() if group_poll else None

    try:
        def schedule(group, observer, label):
            for e in group:
                if not os.path.exists(e["path"]):
                    print(f"[{ts()}] ⚠ ({label}) Brak ścieżki: {e['path']}")
                    continue

                sink = JsonlSink(e.get("log_path")) if e.get("log_path") else None

                handler = NewFileHandler(
                    include_patterns=e.get("include"),
                    exclude_patterns=e.get("exclude"),
                    stabilize=e.get("stabilize"),
                    stabilize_seconds=e.get("stabilize_seconds"),
                    event_sink=sink,
                    printer=print,
                )

                observer.schedule(handler, e["path"], recursive=e.get("recursive", False))

        if obs_auto:
            schedule(group_auto, obs_auto, "auto")
            obs_auto.start()
        if obs_poll:
            schedule(group_poll, obs_poll, "polling")
            obs_poll.start()

        print(f"[{ts()}] ▶ Start monitoringu ({len(folders)} folderów)")
        for e in folders:
            eff = effective_observer_for_path(args.observer, e.get("observer"), e["path"])
            print(f"  • {e['path']} | rec={e['recursive']} | obs={eff} | log={e.get('log_path') or '-'}")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print(f"[{ts()}] ⏹ Zatrzymano")
    finally:
        for obs in (obs_auto, obs_poll):
            if obs:
                obs.stop()
                obs.join(5)


if __name__ == "__main__":
    main()