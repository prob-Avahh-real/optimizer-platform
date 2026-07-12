"""Module 4 — DevOps Center: dev tool cache detection & cleanup."""
import subprocess
from pathlib import Path
from .base import BaseModule

class DevOpsCenter(BaseModule):
    TOOLS = {
        "npm":    {"clean_cmd": "npm cache clean --force", "dirs": ["~/.npm", "**/node_modules"]},
        "pip":    {"clean_cmd": "pip cache purge", "dirs": ["~/Library/Caches/pip", "~/.cache/pip"]},
        "cargo":  {"clean_cmd": "cargo cache --autoclean", "dirs": ["~/.cargo/registry/cache", "**/target"]},
        "go":     {"clean_cmd": "go clean -cache -modcache", "dirs": ["~/go/pkg/mod", "~/.cache/go-build"]},
        "gradle": {"clean_cmd": "gradle cleanBuildCache", "dirs": ["~/.gradle/caches"]},
        "maven":  {"clean_cmd": None, "dirs": ["~/.m2/repository"]},
        "brew":   {"clean_cmd": "brew cleanup", "dirs": ["~/Library/Caches/Homebrew"]},
        "docker": {"clean_cmd": "docker system prune -a -f", "dirs": ["~/Library/Containers/com.docker.docker"]},
        "xcode":  {"clean_cmd": "xcrun simctl delete unavailable", "dirs": ["~/Library/Developer/Xcode/DerivedData", "~/Library/Developer/CoreSimulator"]},
        "android":{"clean_cmd": None, "dirs": ["~/.android/cache", "~/Library/Android/sdk/.temp"]},
        "pnpm":   {"clean_cmd": None, "dirs": ["~/Library/Caches/pnpm", "~/.pnpm-store"]},
        "yarn":   {"clean_cmd": "yarn cache clean", "dirs": ["~/Library/Caches/Yarn"]},
        "uv":     {"clean_cmd": "uv cache clean", "dirs": ["~/.cache/uv"]},
    }

    def _scan(self):
        home = Path.home()
        results, total = {"detected_tools": {}, "total_cache_mb": 0, "recommendations": []}, 0
        for tool, cfg in self.TOOLS.items():
            cached = self._measure(tool, cfg, home)
            results["detected_tools"][tool] = cached
            total += cached
        results["total_cache_mb"] = round(total, 1)
        results["total_cache_gb"] = round(total / 1024, 2)
        over = sorted([(t, s) for t, s in results["detected_tools"].items() if s > 500], key=lambda x: x[1], reverse=True)
        for tool, size in over[:5]:
            cmd = self.TOOLS.get(tool, {}).get("clean_cmd")
            results["recommendations"].append({"tool": tool, "cache_mb": round(size,1),
                "cache_gb": round(size/1024,2), "clean_command": cmd or f"手动清理{tool}缓存"})
        return results

    def _measure(self, tool, cfg, home):
        total = 0
        for pat in cfg.get("dirs", []):
            pat = pat.replace("~", str(home))
            if "**" in pat:
                try:
                    base = Path(pat.split("**")[0]).expanduser().resolve()
                    suffix = pat.split("**")[-1].lstrip("/")
                    if base.exists():
                        for d in base.rglob(suffix):
                            if d.is_dir(): total += self._dsize(d)
                except Exception: pass
            else:
                p = Path(pat).expanduser().resolve()
                if p.exists() and p.is_dir(): total += self._dsize(p)
        return round(total, 1)

    def _dsize(self, path):
        total = 0
        try:
            for e in path.rglob("*"):
                if e.is_file():
                    try: total += e.stat().st_size
                    except OSError: pass
        except PermissionError: pass
        return total / (1024 * 1024)

    # ── Optimize ─────────────────────

    def _optimize(self, targets, dry_run):
        actions, data = [], self._scan()
        tools_data = data.get("detected_tools", {})
        tool_list = targets if targets else list(tools_data.keys())
        for tool in tool_list:
            size_mb = tools_data.get(tool, 0)
            if size_mb < 1 and targets:
                actions.append({"item": tool, "action": "跳过", "result": f"缓存<1MB ({size_mb:.1f}MB)", "freed_mb": 0})
                continue
            cmd = self.TOOLS.get(tool, {}).get("clean_cmd")
            if not cmd:
                freed = 0
                if not dry_run:
                    for pat in self.TOOLS.get(tool, {}).get("dirs", []):
                        p = Path(pat.replace("~", str(Path.home()))).expanduser().resolve()
                        if p.exists() and p.is_dir():
                            try:
                                sz = self._dsize(p)
                                import shutil
                                shutil.rmtree(p, ignore_errors=True)
                                freed += sz
                            except OSError: pass
                actions.append({"item": tool, "action": "删除缓存目录", "result": "ok" if not dry_run else "dry_run", "freed_mb": round(freed, 1)})
            else:
                if not dry_run:
                    try:
                        subprocess.run(cmd, shell=True, capture_output=True, timeout=120)
                    except Exception as e:
                        actions.append({"item": tool, "action": cmd, "result": f"error:{e}", "freed_mb": 0})
                        continue
                actions.append({"item": tool, "action": cmd, "result": "ok" if not dry_run else "dry_run", "freed_mb": round(size_mb, 1)})
        return actions
