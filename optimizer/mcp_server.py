"""OptimizerPlatform MCP Server — exposes all 5 modules as MCP tools for Claude/Cursor."""
import sys, os, json
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


TOOLS = {
    "optimizer_scan_assets": {
        "description": "扫描所有硬件资产：CPU、内存、磁盘、GPU、网络接口、Docker、数据库、开发工具链",
        "handler": lambda: AssetDiscovery().scan(),
    },
    "optimizer_scan_network": {
        "description": "网络质量检测：延迟、DNS测速、丢包率、TCP连接数、开放端口、公网IP",
        "handler": lambda: NetworkCenter().scan(),
    },
    "optimizer_scan_storage": {
        "description": "存储空间扫描：大文件、重复文件、缓存目录、日志、空目录、可回收空间估算",
        "handler": lambda: StorageCenter().scan(),
    },
    "optimizer_scan_devops": {
        "description": "开发环境检测：Node/Python/Rust/Go/Java等工具缓存大小和清理建议",
        "handler": lambda: DevOpsCenter().scan(),
    },
    "optimizer_scan_docker": {
        "description": "Docker容器管理：镜像、容器、Volume、网络、悬空资源、可回收空间",
        "handler": lambda: ContainerCenter().scan(),
    },
    "optimizer_benchmark": {
        "description": "性能基准测试：CPU、磁盘读写、网络吞吐量评分",
        "handler": lambda: BenchmarkCenter().scan(),
    },
    "optimizer_health_report": {
        "description": "AI综合分析报告：汇总所有模块数据，生成健康评分和优化建议",
        "handler": _make_health_report,
    },
    "optimizer_quick_check": {
        "description": "快速健康检查：一行输出系统状态摘要",
        "handler": _make_quick_check,
    },
    "optimizer_auto_heal": {
        "description": "自动修复规则评估：列出所有触发的优化规则和建议操作",
        "handler": _make_auto_heal,
    },
}


def _make_health_report() -> dict:
    modules = {
        "asset": AssetDiscovery(),
        "network": NetworkCenter(),
        "storage": StorageCenter(),
        "devops": DevOpsCenter(),
        "container": ContainerCenter(),
        "benchmark": BenchmarkCenter(),
    }
    results = []
    for key, mod in modules.items():
        results.append(mod.scan())

    reporter = AIReporter(*results)
    report = reporter.scan()
    return {"module": "AIReport", "data": report.get("data", report)}


def _make_quick_check() -> dict:
    """Fast check — network + storage waste only."""
    network = NetworkCenter()
    storage = StorageCenter()

    n_result = network.scan()
    s_result = storage.scan()

    reporter = AIReporter(n_result, s_result)
    report = reporter.scan()

    return {
        "module": "QuickCheck",
        "data": {
            "health_score": report.get("data", {}).get("health_score", "?"),
            "status": report.get("data", {}).get("status", "?"),
            "issues": report.get("data", {}).get("issues", []),
            "summary": reporter.quick_summary(),
        }
    }


def _make_auto_heal() -> dict:
    """Evaluate auto-heal rules."""
    modules = {
        "asset": AssetDiscovery(),
        "network": NetworkCenter(),
        "storage": StorageCenter(),
        "devops": DevOpsCenter(),
        "container": ContainerCenter(),
        "benchmark": BenchmarkCenter(),
    }
    all_data = {}
    for key, mod in modules.items():
        result = mod.scan()
        all_data[key] = result.get("data", {})

    healer = AutoHeal(all_data)
    return healer.scan()


# --- MCP JSON-RPC handler ---
def handle_jsonrpc(method: str, params: dict | None = None) -> dict:
    """Handle a JSON-RPC method call."""
    if method == "tools/list":
        tool_list = []
        for name, info in TOOLS.items():
            tool_list.append({
                "name": name,
                "description": info["description"],
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            })
        return {"tools": tool_list}

    elif method == "tools/call":
        tool_name = params.get("name", "") if params else ""
        if tool_name in TOOLS:
            try:
                result = TOOLS[tool_name]["handler"]()
                return {
                    "content": [
                        {"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}
                    ]
                }
            except Exception as e:
                return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
        return {"content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}], "isError": True}

    return {"error": f"Unknown method: {method}"}


def main():
    """Run MCP server via stdin/stdout JSON-RPC."""
    print("MCP Server: OptimizerPlatform", file=sys.stderr)
    print("Tools available:", list(TOOLS.keys()), file=sys.stderr)

    import sys, select
    buffer = ""
    while True:
        # Non-blocking read from stdin
        if select.select([sys.stdin], [], [], 0.1)[0]:
            char = sys.stdin.read(1)
            if not char:
                break
            buffer += char
        else:
            if buffer.strip():
                try:
                    request = json.loads(buffer.strip())
                    method = request.get("method", "")
                    params = request.get("params", {})
                    req_id = request.get("id")

                    result = handle_jsonrpc(method, params)

                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": result,
                    }
                    print(json.dumps(response, ensure_ascii=False), flush=True)
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    err_resp = {
                        "jsonrpc": "2.0",
                        "id": request.get("id") if 'request' in dir() else None,
                        "error": {"code": -32603, "message": str(e)},
                    }
                    print(json.dumps(err_resp), flush=True)
                buffer = ""


if __name__ == "__main__":
    main()
