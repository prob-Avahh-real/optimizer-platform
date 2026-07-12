"""Module 5 — Container Center: Docker images, containers, volumes, orphans, prune."""
import subprocess, json, re
from .base import BaseModule


class ContainerCenter(BaseModule):
    def _scan(self):
        if not self._docker(): return {"docker_available": False, "message": "Docker未安装或未运行"}
        return {"docker_available": True, "docker_version": self._version(),
                "system_df": {"raw": self.run_cmd(["docker","system","df"], timeout=10) or ""},
                "images": self._images(), "containers": self._containers(),
                "volumes": self._volumes(), "networks": self._networks(),
                "orphans": self._orphans(), "reclaimable": self._reclaimable()}

    def _docker(self):
        try: subprocess.run(["docker","info"], capture_output=True, timeout=5); return True
        except Exception: return False

    def _version(self):
        return (self.run_cmd(["docker","--version"], timeout=5) or "").strip()

    def _dj(self, args):
        try:
            r = subprocess.run(["docker"]+args+["--format","json"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                results = []
                for line in r.stdout.strip().split("\n"):
                    if line.strip():
                        try: results.append(json.loads(line))
                        except json.JSONDecodeError: results.append({"raw": line})
                return results
        except Exception: pass
        return []

    def _images(self):
        imgs = self._dj(["images"])
        dangling, total = 0, 0
        for img in imgs:
            if isinstance(img, dict):
                total += self._parse_mb(img.get("Size","0B"))
                if img.get("Repository") == "<none>" or img.get("Tag") == "<none>": dangling += 1
        return {"count": len(imgs), "dangling": dangling, "total_size_mb": round(total,1),
                "total_size_gb": round(total/1024,2), "images": imgs[:20]}

    def _containers(self):
        all_c = self._dj(["ps","-a"])
        running = sum(1 for c in all_c if isinstance(c,dict) and "Up" in str(c.get("Status","")))
        return {"count": len(all_c), "running": running, "stopped": len(all_c)-running, "containers": all_c[:20]}

    def _volumes(self):
        vols = self._dj(["volume","ls"]); orphans = 0
        for v in vols:
            if isinstance(v,dict):
                chk = self.run_cmd(["docker","ps","-a","--filter",f"volume={v.get('Name','')}","--format","{{.ID}}"], timeout=5)
                if not chk or not chk.strip(): orphans += 1
        return {"count": len(vols), "orphans": orphans, "volumes": vols[:20]}

    def _networks(self):
        nets = self._dj(["network","ls"])
        return {"count": len(nets), "networks": nets[:10]}

    def _orphans(self):
        d_out = self.run_cmd(["docker","images","-f","dangling=true","--format","{{.ID}} {{.Size}}"], timeout=10)
        dangling = []
        if d_out:
            for line in d_out.strip().split("\n"):
                p = line.split(); dangling.append({"id": p[0], "size": " ".join(p[1:])}) if p else None
        e_out = self.run_cmd(["docker","ps","-a","-f","status=exited","--format","{{.ID}} {{.Image}} {{.Names}}"], timeout=10)
        exited = []
        if e_out:
            for line in e_out.strip().split("\n"):
                p = line.split(maxsplit=2)
                if len(p) >= 2: exited.append({"id": p[0], "image": p[1], "name": p[2] if len(p)>2 else "?"})
        return {"dangling_images": len(dangling), "exited_containers": len(exited)}

    def _reclaimable(self):
        imgs = self._images(); vols = self._volumes(); orph = self._orphans()
        total = imgs.get("total_size_mb", 0) + vols.get("orphans", 0) * 50
        return {"total_reclaimable_mb": round(total,1), "total_reclaimable_gb": round(total/1024,2),
                "breakdown": {"images_mb": imgs.get("total_size_mb",0),
                              "orphan_volumes_est_mb": vols.get("orphans",0)*50,
                              "dangling_images": orph.get("dangling_images",0),
                              "exited_containers": orph.get("exited_containers",0)}}

    @staticmethod
    def _parse_mb(s):
        m = re.match(r"(\d+\.?\d*)\s*(GB|MB|kB|TB|B)?", s, re.IGNORECASE)
        if not m: return 0
        v, u = float(m.group(1)), (m.group(2) or "B").upper()
        return v * {"TB": 1048576, "GB": 1024, "MB": 1, "kB": 0.001, "B": 0.000001}.get(u, 0)

    # ── Optimize ─────────────────────

    def _optimize(self, targets, dry_run):
        if not self._docker(): return [{"item":"docker","action":"跳过","result":"Docker不可用","freed_mb":0}]
        actions = []
        prune_tgts = targets if targets else ["containers","images","volumes"]
        for t in prune_tgts:
            t_singular = t[:-1] if t.endswith("s") else t
            if dry_run:
                actions.append({"item":t,"action":f"docker {t_singular} prune -f{' -a' if t=='images' else ''}","result":"dry_run","freed_mb":0})
                continue
            try:
                cmd = ["docker", t_singular, "prune", "-f"]
                if t == "images": cmd.append("-a")
                out = self.run_cmd(cmd, timeout=60) or ""
                freed = 0
                for val, unit in re.findall(r'(\d+\.?\d*)\s*(GB|MB|kB)', out, re.IGNORECASE):
                    v = float(val)
                    freed += v * 1024 if unit.upper() == "GB" else v if unit.upper() == "MB" else v / 1024
                actions.append({"item":t,"action":f"docker {t_singular} prune","result":"ok","freed_mb":round(freed,1)})
            except Exception as e:
                actions.append({"item":t,"action":f"docker {t_singular} prune","result":f"error:{e}","freed_mb":0})
        return actions
