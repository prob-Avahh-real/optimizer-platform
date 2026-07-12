"""Base class for all optimizer modules — scan / backup / optimize / rollback."""
import platform, subprocess, os, json, time
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Any

IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"
BACKUP_ROOT = Path.home() / ".optimizer_backups"


class BaseModule(ABC):
    def __init__(self):
        self.name = self.__class__.__name__
        self.os = platform.system()
        self.report: dict = {"module": self.name, "os": self.os, "data": {}}
        self._backup_id = None
        BACKUP_ROOT.mkdir(exist_ok=True)

    def run_cmd(self, cmd, timeout=15, shell=False):
        try:
            r = subprocess.run(cmd if isinstance(cmd, list) else cmd,
                               capture_output=True, text=True, timeout=timeout,
                               shell=shell or IS_WIN)
            return (r.stdout or r.stderr or "").strip()
        except Exception as e:
            return f"[error] {e}"

    def scan(self):
        try:
            self.report["data"] = self._scan()
            self.report["status"] = "ok"
        except Exception as e:
            self.report["status"] = "error"
            self.report["error"] = str(e)
        return self.report

    @abstractmethod
    def _scan(self):
        ...

    # ── Backup / Rollback ────────────

    def backup(self, label=""):
        ts = int(time.time())
        self._backup_id = f"{self.name}_{label}_{ts}"
        d = BACKUP_ROOT / self._backup_id
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "info.json", "w") as f:
            json.dump({"module": self.name, "label": label, "timestamp": ts, "time": time.ctime(ts)}, f)
        snapshot = self.scan()
        with open(d / "snapshot.json", "w") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2, default=str)
        return self._backup_id

    def rollback(self, backup_id=None):
        bid = backup_id or self._backup_id
        if not bid: return {"status": "error", "message": "无备份ID"}
        bak = BACKUP_ROOT / bid
        if not bak.exists(): return {"status": "error", "message": f"备份{bid}不存在"}
        info = bak / "info.json"
        if info.exists():
            with open(info) as f: j = json.load(f)
            j["rolled_back"] = True
            j["rolled_back_at"] = time.time()
            with open(info, "w") as f: json.dump(j, f)
        try:
            result = self._rollback(bid)
        except Exception as e:
            result = {"status": "error", "error": str(e)}
        result["backup_id"] = bid
        return result

    def _rollback(self, backup_id):
        return {"status": "rolled_back", "note": "无特定回滚逻辑"}

    def list_backups(self, module=None):
        backups = []
        if BACKUP_ROOT.exists():
            for d in sorted(BACKUP_ROOT.iterdir(), reverse=True):
                if d.is_dir() and (not module or d.name.startswith(module)):
                    f = d / "info.json"
                    if f.exists():
                        with open(f) as fh: info = json.load(fh)
                        info["backup_id"] = d.name
                        backups.append(info)
        return backups[:50]

    # ── Optimize ─────────────────────

    def optimize(self, targets=None, dry_run=False):
        targets = targets or []
        self.backup(label="optimize")
        result = {"status": "ok", "actions": [], "total_freed_mb": 0, "backup_id": self._backup_id, "dry_run": dry_run}
        try:
            actions = self._optimize(targets, dry_run=dry_run)
            result["actions"] = actions
            result["total_freed_mb"] = round(sum(a.get("freed_mb", 0) for a in actions), 1)
            if dry_run: result["status"] = "dry_run"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            self.rollback()
        return result

    def _optimize(self, targets, dry_run):
        return [{"item": "N/A", "action": "未实现", "result": "子类未实现_optimize()", "freed_mb": 0}]

    def get_report(self):
        return self.report
