import os
import time
import fnmatch
import json
import threading
from typing import Optional
from datetime import datetime
from watchdog.events import FileSystemEventHandler

def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def wait_for_file_stable(path, min_stable_seconds=2, timeout_seconds=300):
    start = time.time()
    last_size = -1
    stable_since = None

    while True:
        try:
            size = os.path.getsize(path)
        except OSError:
            time.sleep(0.5)
            if time.time() - start > timeout_seconds:
                return False
            continue

        if size == last_size:
            if stable_since is None:
                stable_since = time.time()
            elif time.time() - stable_since >= min_stable_seconds:
                return True
        else:
            last_size = size
            stable_since = None

        if time.time() - start > timeout_seconds:
            return False

        time.sleep(0.5)

def build_file_created_event(path: str) -> dict:
    try:
        size = os.path.getsize(path)
    except OSError:
        size = None

    return {
        "ts": ts(),
        "event": "file_created",
        "path": path,
        "size": size,
    }

# ===== SNAPSHOT STATE SUPPORT =====

def scan_folder(root: str) -> dict:
    files = {}
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            full_path = os.path.join(dirpath, name)
            try:
                stat = os.stat(full_path)
            except FileNotFoundError:
                continue
            rel_path = os.path.relpath(full_path, root)
            files[rel_path] = {
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
            }
    return {"files": files}

def load_last_snapshot(snapshot_path: str, folder: str) -> Optional[dict]:
    try:
        with open(snapshot_path, "r", encoding="utf-8") as f:
            for line in reversed(f.readlines()):
                entry = json.loads(line)
                folders = entry.get("folders", {})
                if folder in folders:
                    return folders[folder]
    except FileNotFoundError:
        return None
    return None

def diff_snapshots(prev: Optional[dict], curr: dict) -> list[dict]:
    events = []
    prev_files = prev.get("files", {}) if prev else {}
    curr_files = curr.get("files", {})

    prev_set = set(prev_files)
    curr_set = set(curr_files)

    for path in curr_set - prev_set:
        meta = curr_files[path]
        events.append({
            "event": "file_created",
            "path": path,
            "size": meta["size"],
            "mtime": meta["mtime"],
            "source": "snapshot_diff",
        })

    for path in prev_set - curr_set:
        meta = prev_files[path]
        events.append({
            "event": "file_deleted",
            "path": path,
            "last_size": meta["size"],
            "last_mtime": meta["mtime"],
            "source": "snapshot_diff",
        })

    for path in prev_set & curr_set:
        p = prev_files[path]
        c = curr_files[path]
        if p["size"] != c["size"] or p["mtime"] != c["mtime"]:
            events.append({
                "event": "file_modified",
                "path": path,
                "prev_size": p["size"],
                "size": c["size"],
                "prev_mtime": p["mtime"],
                "mtime": c["mtime"],
                "source": "snapshot_diff",
            })

    return events

def append_snapshot(snapshot_path: str, folder: str, snapshot: dict):
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "folders": {
            folder: snapshot
        }
    }
    os.makedirs(os.path.dirname(snapshot_path), exist_ok=True)
    with open(snapshot_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

class JsonlSink:
    """
    Prosty sink JSONL (1 event = 1 linia JSON).
    Bezpieczny przy wielu handlerach.
    """
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()

    def emit(self, event: dict):
        if not self.path:
            return
        line = json.dumps(event, ensure_ascii=False)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

class NewFileHandler(FileSystemEventHandler):
    """
    Handler zdarzeń tworzenia plików.
    Nie zna CLI ani konfiguracji – tylko emitowanie eventów.
    """
    def __init__(self,
                 include_patterns=None,
                 exclude_patterns=None,
                 stabilize=True,
                 stabilize_seconds=2,
                 event_sink=None,
                 printer=print):
        super().__init__()
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []
        self.stabilize = stabilize
        self.stabilize_seconds = stabilize_seconds
        self.event_sink = event_sink
        self.printer = printer

    def _match_patterns(self, path: str) -> bool:
        if self.include_patterns:
            if not any(fnmatch.fnmatch(path, pat) for pat in self.include_patterns):
                return False
        if self.exclude_patterns:
            if any(fnmatch.fnmatch(path, pat) for pat in self.exclude_patterns):
                return False
        return True

    def on_created(self, event):
        if event.is_directory:
            return

        path = str(event.src_path)
        if not self._match_patterns(path):
            return

        self.printer(f"[{ts()}] Wykryto utworzenie pliku: {path}")

        if self.stabilize:
            ok = wait_for_file_stable(path, min_stable_seconds=self.stabilize_seconds)
            self.printer(f" Stabilizacja pliku: {'OK' if ok else 'TIMEOUT'}")
            if not ok:
                return

        event_data = build_file_created_event(path)
        if self.event_sink:
            self.event_sink.emit(event_data)
        # Add any additional logic or handlers here
        pass

# Ensure the file ends with the correct structure
if __name__ == "__main__":
    print("Core module loaded successfully.")