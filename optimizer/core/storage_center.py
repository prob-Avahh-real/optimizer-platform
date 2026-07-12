"""Module 3 — Storage Center: large files, duplicates, caches, logs, empty dirs, waste estimate."""
import os, hashlib, shutil
from pathlib import Path
from collections import defaultdict
from .base import BaseModule


class StorageCenter(BaseModule):
    def _scan(self):
        home = Path.home()
        results = {
            "large_files": self._large(home, min_mb=500, top_n=20),
            "duplicate_files": self._dupes(home, max_depth=4),
            "cache_dirs": self._caches(home),
            "log_files": self._logs(home),
            "empty_dirs": self._empties(home),
            "disk_usage": self._disk_usage(),
        }
        results["waste_estimate"] = self._estimate(results)
        return results

    def _large(self, root, min_mb=500, top_n=20):
        large, min_b = [], min_mb * 1024 * 1024
        skip = {"/proc","/sys","/dev","/System/Volumes/Data/private/var"}
        try:
            for entry in root.rglob("*"):
                if entry.is_file() and not any(s in str(entry) for s in skip):
                    try:
                        sz = entry.stat().st_size
                        if sz > min_b: large.append({"path": str(entry), "size_mb": round(sz/(1024*1024),1), "size_human": self._human(sz)})
                    except (OSError,PermissionError): pass
        except (OSError,PermissionError): pass
        large.sort(key=lambda x: x["size_mb"], reverse=True)
        return large[:top_n]

    def _dupes(self, root, max_depth=4):
        size_map = defaultdict(list)
        skip = {"/proc","/sys","/dev","/System/Volumes/Data/private/var"}
        try:
            for entry in root.rglob("*"):
                if entry.is_file() and not any(s in str(entry) for s in skip):
                    if len(entry.relative_to(root).parts) > max_depth: continue
                    try: size_map[entry.stat().st_size].append(entry)
                    except (OSError,PermissionError): pass
        except (OSError,PermissionError): pass

        duplicates, seen = [], set()
        for size, files in size_map.items():
            if len(files) < 2 or size < 1024: continue
            hm = defaultdict(list)
            for f in files[:10]:
                try: hm[self._qhash(f, size)].append(f)
                except (OSError,PermissionError): pass
            for h, group in hm.items():
                if len(group) >= 2 and h not in seen:
                    seen.add(h)
                    waste = sum(f.stat().st_size for f in group[1:])
                    duplicates.append({"count": len(group), "size_mb": round(size/(1024*1024),1),
                                       "paths": [str(f) for f in group[:5]], "waste_mb": round(waste/(1024*1024),1)})
        duplicates.sort(key=lambda x: x["waste_mb"], reverse=True)
        return {"total_groups": len(duplicates), "total_waste_mb": round(sum(d["waste_mb"] for d in duplicates),1),
                "top_duplicates": duplicates[:15]}

    def _qhash(self, fpath, size):
        h = hashlib.md5()
        with open(fpath, "rb") as f:
            h.update(f.read(min(1024*1024, size)))
            if size > 2*1024*1024:
                f.seek(-1024*1024, os.SEEK_END)
                h.update(f.read(1024*1024))
        return h.hexdigest()

    def _caches(self, root):
        patterns = ["**/node_modules","**/__pycache__","**/.cache","**/target","**/.gradle/caches",
                    "**/.m2/repository","**/Library/Caches","**/AppData/Local/Temp","**/vendor/bundle"]
        caches, seen = [], set()
        for pat in patterns:
            try:
                for entry in root.rglob(pat.split("**/")[-1] if "**/" in pat else pat.strip("*")):
                    if entry.is_dir() and str(entry) not in seen:
                        seen.add(str(entry))
                        sz = self._dsize(entry)
                        if sz > 1: caches.append({"path": str(entry), "type": self._ctype(entry), "size_mb": sz})
            except (OSError,PermissionError): pass
        caches.sort(key=lambda x: x["size_mb"], reverse=True)
        return caches[:30]

    def _ctype(self, p):
        n = str(p).lower()
        if "node_modules" in n: return "npm"
        if "__pycache__" in n: return "python"
        if ".cargo" in n or "/target" in n: return "rust"
        if ".gradle" in n: return "gradle"
        if ".m2" in n: return "maven"
        if "vendor/bundle" in n: return "ruby"
        if "library/caches" in n: return "macos"
        if ".cache" in n: return "system"
        return "other"

    def _logs(self, root):
        logs = []
        try:
            for entry in root.rglob("*.log"):
                if entry.is_file():
                    try:
                        sz = entry.stat().st_size
                        if sz > 1024*1024: logs.append({"path": str(entry), "size_mb": round(sz/(1024*1024),1)})
                    except (OSError,PermissionError): pass
        except (OSError,PermissionError): pass
        logs.sort(key=lambda x: x["size_mb"], reverse=True)
        for ld in ["/var/log", str(Path.home()/"Library/Logs"), str(Path.home()/".local/share")]:
            if os.path.isdir(ld):
                sz = self._dsize(Path(ld))
                if sz > 1: logs.append({"path": ld, "size_mb": sz, "is_dir": True})
        return logs[:15]

    def _empties(self, root):
        count, skip = 0, {"/proc","/sys","/dev"}
        try:
            for entry in root.rglob("*"):
                if entry.is_dir() and not any(s in str(entry) for s in skip):
                    try:
                        if not any(entry.iterdir()): count += 1
                    except (OSError,PermissionError): pass
        except (OSError,PermissionError): pass
        return {"count": count}

    def _dsize(self, path):
        total = 0
        try:
            for entry in path.rglob("*"):
                if entry.is_file():
                    try: total += entry.stat().st_size
                    except OSError: pass
        except (OSError,PermissionError): pass
        return round(total/(1024*1024), 1)

    def _disk_usage(self):
        try:
            u = shutil.disk_usage(Path.home())
            return {"total_gb": round(u.total/(1024**3),1), "used_gb": round(u.used/(1024**3),1),
                    "free_gb": round(u.free/(1024**3),1), "used_pct": round(u.used/u.total*100,1)}
        except Exception: return {}

    def _estimate(self, results):
        total = sum(c["size_mb"] for c in results.get("cache_dirs",[]))
        total += sum(l.get("size_mb",0) for l in results.get("log_files",[]))
        dup_w = results.get("duplicate_files",{}).get("total_waste_mb",0)
        total += dup_w
        return {"total_reclaimable_gb": round(total/1024,2), "cache_waste_gb": round(sum(c["size_mb"] for c in results.get("cache_dirs",[]))/1024,2),
                "duplicate_waste_gb": round(dup_w/1024,2), "empty_dirs": results.get("empty_dirs",{}).get("count",0),
                "breakdown": []}

    @staticmethod
    def _human(b):
        for u in ["B","KB","MB","GB","TB"]:
            if b < 1024: return f"{b:.1f}{u}"
            b /= 1024
        return f"{b:.1f}PB"

    # ── Optimize ─────────────────────

    def _optimize(self, targets, dry_run):
        actions, data = [], self._scan()
        root, skip = Path.home(), {"/proc","/sys","/dev"}

        if not targets or "empty_dirs" in targets:
            count = 0
            try:
                for entry in root.rglob("*"):
                    if entry.is_dir() and not any(s in str(entry) for s in skip):
                        try:
                            if not any(entry.iterdir()): count += 1
                            if not dry_run: entry.rmdir()
                        except (OSError,PermissionError): pass
            except (OSError,PermissionError): pass
            actions.append({"item":"空目录","action":f"删除{count}个","result":"ok" if not dry_run else "dry_run","freed_mb":0})

        if not targets or "logs" in targets:
            freed = 0
            for l in data.get("log_files",[]):
                p = Path(l["path"])
                if p.exists() and p.is_file():
                    freed += l.get("size_mb",0)
                    if not dry_run:
                        try: p.unlink()
                        except OSError: pass
            actions.append({"item":"日志","action":f"清理{len(data.get('log_files',[]))}个","result":"ok" if not dry_run else "dry_run","freed_mb":round(freed,1)})

        if not targets or "cache" in targets:
            freed = 0
            for cd in data.get("cache_dirs",[])[:10]:
                p = Path(cd["path"])
                if p.exists() and p.is_dir():
                    freed += cd.get("size_mb",0)
                    if not dry_run:
                        try: shutil.rmtree(p, ignore_errors=True)
                        except OSError: pass
            actions.append({"item":"缓存","action":"清理缓存目录","result":"ok" if not dry_run else "dry_run","freed_mb":round(freed,1)})

        return actions
