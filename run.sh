#!/bin/bash
# OptimizerPlatform — 一键启动（自动杀旧进程 + 自动换端口）
set -e
cd "$(dirname "$0")"

# Kill any old server on this port
PORT="${PORT:-8765}"
OLD=$(lsof -ti ":$PORT" 2>/dev/null || true)
if [ -n "$OLD" ]; then
  echo "🧹 旧进程占用端口 $PORT，正在清理…"
  kill -9 $OLD 2>/dev/null || true
  sleep 1
fi

# Install deps if needed
if ! python3 -c "import fastapi" 2>/dev/null; then
  echo "📦 安装依赖…"
  pip3 install fastapi uvicorn 2>/dev/null || pip3 install fastapi uvicorn --break-system-packages
fi

echo "🖥  OptimizerPlatform v1.1.0"
echo ""

MODE="${1:-dashboard}"
case "$MODE" in
  dashboard|web)
    while true; do
      if ! lsof -ti ":$PORT" >/dev/null 2>&1; then
        break
      fi
      echo "端口 $PORT 被占用，尝试 $((PORT+1))…"
      PORT=$((PORT+1))
    done
    echo "📡 启动 Web Dashboard → http://127.0.0.1:$PORT/api/dashboard"
    python3 optimizer/server.py --host 127.0.0.1 --port "$PORT"
    ;;
  cli)
    echo "🔧 命令行模式"
    python3 -c "
from optimizer.core.asset_discovery import AssetDiscovery
from optimizer.core.network_center import NetworkCenter
from optimizer.core.storage_center import StorageCenter
from optimizer.core.devops_center import DevOpsCenter
from optimizer.core.container_center import ContainerCenter
from optimizer.core.benchmark import BenchmarkCenter
from optimizer.core.ai_reporter import AIReporter
import json, time

B='='*60
print(B)
print('  OptimizerPlatform — 全面系统扫描')
print(B)

modules={
    '资产发现':AssetDiscovery(),'网络中心':NetworkCenter(),'存储中心':StorageCenter(),
    'DevOps':DevOpsCenter(),'容器中心':ContainerCenter(),'性能基准':BenchmarkCenter()
}
results=[]
for name,mod in modules.items():
    t0=time.time()
    r=mod.scan()
    results.append(r)
    d=r.get('data',{})
    elapsed=time.time()-t0
    print(f'\n📦 {name} ({elapsed:.1f}s) [{r[\"status\"]}]')
    if name=='资产发现':
        print(f'   {d.get(\"hostname\",\"?\")} / {d[\"system\"]} / CPU:{d[\"cpu\"][\"brand\"]} / 内存:{d[\"memory\"][\"total_gb\"]}GB')
        print(f'   工具:{d.get(\"dev_tools\",[])} | Docker:{d[\"docker\"]}')
    elif name=='网络中心':
        rec=d.get('recommendation',{})
        print(f'   评分:{rec.get(\"score\",\"?\")}/100 | Ping:{d[\"ping\"][\"avg_ms\"]}ms')
        fast=d.get('dns_speed',{}).get('fastest',{})
        print(f'   最快DNS:{fast.get(\"provider\",\"?\")}({fast.get(\"avg_ms\",\"?\")}ms) | IP:{d.get(\"public_ip\",\"?\")}')
    elif name=='存储中心':
        w=d.get('waste_estimate',{})
        print(f'   磁盘:{d[\"disk_usage\"].get(\"used_pct\",\"?\")}% | 可回收:{w.get(\"total_reclaimable_gb\",0)}GB')
        print(f'   大文件:{len(d.get(\"large_files\",[]))}个 | 重复:{d[\"duplicate_files\"].get(\"total_groups\",0)}组')
    elif name=='DevOps':
        print(f'   缓存:{d.get(\"total_cache_gb\",0)}GB ({len(d.get(\"detected_tools\",{}))}种)')
    elif name=='容器中心':
        if d.get('docker_available'):
            recl=d.get('reclaimable',{})
            print(f'   Docker ✅ | 可回收:{recl.get(\"total_reclaimable_gb\",0)}GB')
        else: print('   Docker ❌')
    elif name=='性能基准':
        s=d.get('summary',{})
        print(f'   综合:{s.get(\"combined_score\",\"?\")} ({s.get(\"grade\",\"?\")})')

reporter=AIReporter(*results)
report=reporter.scan()
rd=report.get('data',{})
print(f'\n{B}')
print(f'🤖 AI: {rd.get(\"health_score\",\"?\")}/100 — {rd.get(\"status\",\"?\")}')
for i in rd.get('issues',[]): print(f'  🔴 {i}')
for s in rd.get('suggestions',[]): print(f'  💡 {s}')
if not rd.get('issues') and not rd.get('suggestions'): print('  ✅ 系统良好')
print(B)
"
    ;;
  mcp)
    echo "🔌 MCP Server 模式"
    python3 optimizer/mcp_server.py
    ;;
  *)
    echo "用法: ./run.sh [dashboard|cli|mcp]"
    ;;
esac
