"""Bonus — Auto-Heal: rule engine for automatic optimization with safety checks."""
import json, time
from pathlib import Path
from .base import BaseModule, BACKUP_ROOT


class AutoHeal(BaseModule):
    RULES = [
        {"id":"free_space_low", "condition":"storage.disk_usage.used_pct > 90", "action":"clean_cache", "description":"磁盘>90%", "auto_execute": False},
        {"id":"docker_large", "condition":"container.reclaimable.total_reclaimable_gb > 20", "action":"docker_prune", "description":"Docker缓存>20GB", "auto_execute": False},
        {"id":"dns_slow", "condition":"network.dns_speed.fastest.avg_ms > 50", "action":"recommend_dns", "description":"DNS>50ms", "auto_execute": False},
        {"id":"dev_cache_large", "condition":"devops.total_cache_gb > 30", "action":"clean_dev_cache", "description":"开发缓存>30GB", "auto_execute": False},
    ]

    def __init__(self, module_data=None):
        super().__init__()
        self.module_data = module_data or {}
        BACKUP_ROOT.mkdir(exist_ok=True)

    def _scan(self):
        return self.evaluate_rules(self.module_data)

    def evaluate_rules(self, data):
        triggered = []
        for rule in self.RULES:
            if self._eval(rule["condition"], data):
                triggered.append({"rule_id": rule["id"], "action": rule["action"], "description": rule["description"], "auto_execute": rule.get("auto_execute", False)})
        return {"triggered_rules": triggered, "total": len(triggered)}

    def _eval(self, cond, data):
        try:
            parts = cond.split(" ")
            if len(parts) < 3: return False
            path, op, threshold = parts[0], parts[1], float(parts[2])
            val = data
            for key in path.split("."):
                if isinstance(val, dict):
                    val = val.get(key, val.get("data", {}).get(key))
                elif isinstance(val, list) and key.isdigit():
                    val = val[int(key)]
                else: return False
                if val is None: return False
            if not isinstance(val, (int, float)): return False
            if op == ">": return val > threshold
            if op == "<": return val < threshold
            if op == ">=": return val >= threshold
            if op == "<=": return val <= threshold
            return False
        except Exception: return False
