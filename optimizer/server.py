"""OptimizerPlatform FastAPI Server v1.1 — scan + optimize + rollback"""
import sys, os, json, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from optimizer.core.asset_discovery import AssetDiscovery
from optimizer.core.network_center import NetworkCenter
from optimizer.core.storage_center import StorageCenter
from optimizer.core.devops_center import DevOpsCenter
from optimizer.core.container_center import ContainerCenter
from optimizer.core.benchmark import BenchmarkCenter
from optimizer.core.ai_reporter import AIReporter
from optimizer.core.auto_heal import AutoHeal

try:
    from fastapi import FastAPI, Query, BackgroundTasks, Body
    from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
except ImportError:
    print("需要安装: pip install fastapi uvicorn")
    sys.exit(1)

app = FastAPI(title="OptimizerPlatform", description="轻量版系统运维平台 — 5大模块", version="1.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

asset = AssetDiscovery()
network = NetworkCenter()
storage = StorageCenter()
devops = DevOpsCenter()
container = ContainerCenter()
benchmark = BenchmarkCenter()
healer = AutoHeal()

MOD_MAP = {"asset": asset, "network": network, "storage": storage, "devops": devops, "container": container, "benchmark": benchmark}

_scan_cache = {}
_CACHE_TTL = 60

def _full_scan():
    results = {}
    for k, m in MOD_MAP.items(): results[k] = m.scan()
    results["ai_report"] = AIReporter(*results.values()).scan()
    ad = {k: v.get("data", {}) for k, v in results.items()}
    results["auto_heal"] = {"module": "AutoHeal", "data": healer.evaluate_rules(ad)}
    global _scan_cache
    _scan_cache = {"data": results, "ts": time.time()}
    return results

def _cached(force=False):
    if not force and _scan_cache and (time.time() - _scan_cache["ts"]) < _CACHE_TTL:
        return _scan_cache["data"]
    return _full_scan()

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.1.0", "timestamp": time.time()}

@app.get("/api/scan")
async def scan_all(force: bool = Query(False)):
    return JSONResponse(content=_cached(force=force))

@app.get("/api/scan/{module}")
async def scan_module(module: str, force: bool = Query(False)):
    if module == "ai_report":
        data = _cached(force=force)
        return JSONResponse(content=AIReporter(*[MOD_MAP[m].scan() for m in MOD_MAP]).scan())
    if module == "auto_heal":
        data = _cached(force=force)
        ad = {k: v.get("data", {}) for k, v in data.items() if k not in ("ai_report", "auto_heal")}
        return JSONResponse(content={"module": "AutoHeal", "data": healer.evaluate_rules(ad)})
    if module in MOD_MAP:
        return JSONResponse(content=MOD_MAP[module].scan())
    return JSONResponse({"error": f"未知模块: {module}"}, status_code=404)

@app.post("/api/optimize/{module}")
async def optimize_module(module: str, dry_run: bool = Query(False), targets: str = Query("")):
    if module == "all":
        results = {}
        for n, m in MOD_MAP.items():
            t = targets.split(",") if targets else []
            results[n] = m.optimize(targets=t, dry_run=dry_run)
        results["status"] = "dry_run" if dry_run else "ok"
        return JSONResponse(content=results)
    if module not in MOD_MAP:
        return JSONResponse({"error": f"未知模块: {module}"}, status_code=404)
    t = targets.split(",") if targets else []
    return JSONResponse(content=MOD_MAP[module].optimize(targets=t, dry_run=dry_run))

@app.post("/api/rollback/{module}")
async def rollback_module(module: str, backup_id: str = Query("")):
    if module not in MOD_MAP:
        return JSONResponse({"error": f"未知模块: {module}"}, status_code=404)
    return JSONResponse(content=MOD_MAP[module].rollback(backup_id or None))

@app.get("/api/backups/{module}")
async def list_backups(module: str):
    return JSONResponse(content={"module": module, "backups": asset.list_backups(module if module != "all" else None)})

@app.get("/api/dashboard")
async def dashboard():
    p = Path(__file__).parent.parent / "dashboard.html"
    return FileResponse(str(p)) if p.exists() else HTMLResponse("<h1>Dashboard not found</h1>")

@app.get("/api/report")
async def report():
    results = _cached(force=True)
    ai = AIReporter(*[v for k, v in results.items() if k not in ("ai_report", "auto_heal")]).scan()
    return {"markdown": ai.get("data", {}).get("summary", "?"), "timestamp": time.time()}

def main():
    import argparse, socket, webbrowser, subprocess

    def port_free(p):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", p)); s.close()
            return True
        except OSError:
            return False

    p = argparse.ArgumentParser(description="OptimizerPlatform Server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args()

    # Kill existing process on this port
    import platform
    import os, signal
    if not port_free(args.port):
        print(f"  🧹 端口 {args.port} 被占用，正在清理…")
        try:
            out = subprocess.check_output(
                f"lsof -ti :{args.port} || fuser {args.port}/tcp 2>/dev/null",
                shell=True, text=True, timeout=5
            ).strip()
            for pid in out.split("\n"):
                if pid:
                    try: os.kill(int(pid), signal.SIGKILL)
                    except Exception: pass
        except Exception: pass
        import time; time.sleep(1)

    # If still occupied, find next free port
    while not port_free(args.port):
        print(f"  端口 {args.port} 仍被占用，尝试 {args.port + 1}…")
        args.port += 1

    print(f"\n  🖥  OptimizerPlatform v1.1.0")
    print(f"  📡 http://{args.host}:{args.port}")
    print(f"  📊 Dashboard: http://{args.host}:{args.port}/api/dashboard")
    print(f"  📋 API Docs: http://{args.host}:{args.port}/docs\n")

    if not args.no_browser:
        webbrowser.open(f"http://{args.host}:{args.port}/api/dashboard")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")

if __name__ == "__main__":
    main()
