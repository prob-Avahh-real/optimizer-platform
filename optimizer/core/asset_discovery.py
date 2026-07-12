"""Module 1 — Asset Discovery: CPU, memory, disk, GPU, Docker, databases, dev tools."""
import platform, os, shutil, socket
from .base import BaseModule, IS_WIN, IS_MAC, IS_LINUX


class AssetDiscovery(BaseModule):
    def _scan(self):
        return {
            "hostname": socket.gethostname(),
            "system": platform.system(), "release": platform.release(), "machine": platform.machine(),
            "cpu": self._cpu_info(), "memory": self._memory_info(), "disk": self._disk_info(),
            "gpu": self._gpu_info(), "network": self._network_info(),
            "docker": self._detect(["docker", "--version"]),
            "kubernetes": self._detect(["kubectl", "version", "--client"]),
            "databases": self._detect_databases(),
            "dev_tools": self._detect_dev_tools(),
        }

    def _cpu_info(self):
        if IS_MAC:
            brand = self.run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"]) or "unknown"
            cores = self.run_cmd(["sysctl", "-n", "hw.ncpu"]) or "?"
            return {"brand": brand.strip(), "cores": int(cores) if cores.isdigit() else cores}
        elif IS_LINUX:
            brand, cores = "unknown", os.cpu_count() or "?"
            try:
                with open("/proc/cpuinfo") as f:
                    for line in f:
                        if "model name" in line: brand = line.split(":")[-1].strip(); break
            except Exception: pass
            return {"brand": brand, "cores": cores}
        else:
            brand = self.run_cmd(["wmic", "cpu", "get", "name"]) or "unknown"
            return {"brand": brand.split("\n")[-1].strip(), "cores": os.cpu_count() or "?"}

    def _memory_info(self):
        if IS_MAC:
            raw = self.run_cmd(["sysctl", "-n", "hw.memsize"])
            gb = round(int(raw) / (1024**3), 1) if raw and raw.isdigit() else "?"
            return {"total_gb": gb}
        elif IS_LINUX:
            try:
                with open("/proc/meminfo") as f:
                    for line in f:
                        if "MemTotal" in line: return {"total_gb": round(int(line.split()[1]) / 1024 / 1024, 1)}
            except Exception: pass
            return {"total_gb": "?"}
        else:
            raw = self.run_cmd(["wmic", "memorychip", "get", "capacity"])
            total = sum(int(x) for x in (raw or "").split() if x.isdigit()) if raw else 0
            return {"total_gb": round(total / (1024**3), 1)}

    def _disk_info(self):
        disks = []
        if IS_MAC:
            out = self.run_cmd(["df", "-h", "/"]) or ""
            for line in out.split("\n")[1:]:
                parts = line.split()
                if len(parts) >= 6: disks.append({"mount": parts[-1], "size": parts[1], "used": parts[2], "avail": parts[3], "pct": parts[4]})
        elif IS_LINUX:
            out = self.run_cmd(["df", "-h", "/"]) or ""
            for line in out.split("\n")[1:]:
                parts = line.split()
                if len(parts) >= 6: disks.append({"mount": parts[-1], "size": parts[1], "avail": parts[3], "pct": parts[4]})
        else:
            out = self.run_cmd(["wmic", "logicaldisk", "get", "size,freespace,name"]) or ""
            for line in out.strip().split("\n")[1:]:
                parts = line.split()
                if len(parts) >= 3:
                    disks.append({"mount": parts[0], "size_gb": round(int(parts[1])/(1024**3), 1), "free_gb": round(int(parts[2])/(1024**3), 1)})
        if not disks:
            u = shutil.disk_usage("/")
            disks.append({"mount": "/", "size_gb": round(u.total/(1024**3),1), "free_gb": round(u.free/(1024**3),1)})
        return disks

    def _gpu_info(self):
        if IS_MAC:
            out = self.run_cmd(["system_profiler", "SPDisplaysDataType"]) or ""
            return [l.split(":")[-1].strip() for l in out.split("\n") if "Chipset Model:" in l] or ["unknown"]
        elif IS_LINUX:
            out = self.run_cmd(["lspci"]) or ""
            return [l.split(":")[-1].strip() for l in out.split("\n") if "VGA" in l or "3D" in l] or ["unknown"]
        else:
            out = self.run_cmd(["wmic", "path", "win32_videocontroller", "get", "name"]) or ""
            return [x.strip() for x in out.split("\n")[1:] if x.strip()] or ["unknown"]

    def _network_info(self):
        ifaces = []
        if IS_MAC or IS_LINUX:
            out = self.run_cmd(["ifconfig"]) or ""
            for line in out.split("\n"):
                if line and not line.startswith("\t") and not line.startswith(" "):
                    iface = line.split(":")[0].split()[0] if ":" in line else line.split()[0]
                    if iface and iface != "lo" and not iface.startswith("utun") and not iface.startswith("llw"):
                        if iface not in ifaces: ifaces.append(iface)
        return {"interfaces": ifaces[:6]}

    def _detect(self, cmd):
        out = self.run_cmd(cmd)
        return bool(out and "[error]" not in out)

    def _detect_databases(self):
        return [n for n, c in [("postgresql", ["psql", "--version"]), ("mysql", ["mysql", "--version"]),
                ("mongodb", ["mongosh", "--version"]), ("redis", ["redis-cli", "--version"]),
                ("sqlite3", ["sqlite3", "--version"])] if self._detect(c)]

    def _detect_dev_tools(self):
        return [n for n, c in [("python", ["python3", "--version"]), ("node", ["node", "--version"]),
                ("npm", ["npm", "--version"]), ("go", ["go", "version"]), ("rust", ["rustc", "--version"]),
                ("java", ["java", "--version"]), ("gcc", ["gcc", "--version"]), ("git", ["git", "--version"]),
                ("brew", ["brew", "--version"])] if self._detect(c)]

    def _optimize(self, targets, dry_run):
        return [{"item": "asset", "action": "无操作", "result": "资产发现仅提供信息", "freed_mb": 0}]
