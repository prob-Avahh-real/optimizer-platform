"""Bonus — AI Reporter: synthesize all module data into actionable health report."""
from datetime import datetime
from .base import BaseModule


class AIReporter(BaseModule):
    def __init__(self, *module_results):
        super().__init__()
        self.module_results = module_results

    def _scan(self):
        return self.analyze(self.module_results)

    def analyze(self, results):
        score, issues, suggestions, wins = 100, [], [], []
        for mod in results:
            if not isinstance(mod, dict): continue
            name, data = mod.get("module", "unknown"), mod.get("data", {})
            if mod.get("status") == "error":
                score -= 10; issues.append(f"[{name}] 扫描失败: {mod.get('error','?')}")
                continue
            if name == "NetworkCenter":
                for r in data.get("recommendation", {}).get("recommendations", []):
                    score = min(score, data["recommendation"].get("score", 100))
                    issues.append(f"[网络] {r['issue']} — {r['action']}")
            elif name == "StorageCenter":
                w = data.get("waste_estimate", {})
                gb = w.get("total_reclaimable_gb", 0)
                if gb > 50: score -= 20; issues.append(f"[存储] 可释放{gb}GB")
                elif gb > 10: score -= 10; suggestions.append(f"可清理{gb}GB存储")
                elif gb > 1: suggestions.append(f"可回收{gb}GB")
                pct = data.get("disk_usage", {}).get("used_pct", 0)
                if pct > 90: score -= 15; issues.append(f"[磁盘] 使用率{pct}%")
                elif pct > 80: score -= 5; suggestions.append(f"磁盘{pct}%")
            elif name == "DevOpsCenter":
                gb = data.get("total_cache_gb", 0)
                if gb > 30: score -= 10; issues.append(f"[开发环境] 缓存{gb}GB")
                elif gb > 5: suggestions.append(f"开发缓存{gb}GB")
            elif name == "ContainerCenter":
                if data.get("docker_available"):
                    gb = data.get("reclaimable", {}).get("total_reclaimable_gb", 0)
                    if gb > 10: score -= 10; issues.append(f"[Docker] 可回收{gb}GB")
                    elif gb > 1: suggestions.append(f"Docker可回收{gb}GB")
            elif name == "BenchmarkCenter":
                g = data.get("summary", {}).get("grade", "")
                if "E" in g or "D" in g: score -= 15; issues.append(f"[性能] {g}")
                elif "C" in g: suggestions.append(f"性能{g}")

        status = "健康" if score >= 90 else "需要注意" if score >= 70 else "需要处理" if score >= 50 else "紧急"
        if not issues: wins.append("系统运行良好，未发现显著问题")
        return {"health_score": max(0, score), "status": status, "timestamp": datetime.now().isoformat(),
                "issues": issues, "suggestions": suggestions, "wins": wins,
                "summary": self._build(score, issues, suggestions, wins)}

    def _build(self, score, issues, suggestions, wins):
        lines = [f"## 系统健康度: {score}/100\n"]
        if wins:
            lines.append("### ✅ 正常项")
            for w in wins: lines.append(f"- {w}")
            lines.append("")
        if issues:
            lines.append("### 🔴 需处理")
            for i in issues: lines.append(f"- {i}")
            lines.append("")
        if suggestions:
            lines.append("### 💡 建议")
            for s in suggestions[:5]: lines.append(f"- {s}")
            lines.append("")
        if not issues and not suggestions: lines.append("系统状态良好，无需干预。")
        return "\n".join(lines)

    def quick_summary(self):
        d = self.scan().get("data", {})
        return f"Health:{d.get('health_score',100)}/100 | Issues:{len(d.get('issues',[]))} | {d.get('status','?')}"
