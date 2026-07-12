"""Module 2 — Network Center: ping, DNS benchmark, packet loss, ports, TCP stats."""
import socket, time, json
from pathlib import Path
from .base import BaseModule, IS_WIN, IS_MAC, IS_LINUX, BACKUP_ROOT


class NetworkCenter(BaseModule):
    DNS_PROVIDERS = {"Cloudflare": "1.1.1.1", "Google": "8.8.8.8", "Quad9": "9.9.9.9",
                     "OpenDNS": "208.67.222.222", "AliDNS": "223.5.5.5", "DNSPod": "119.29.29.29"}

    def _scan(self):
        return {"ping": self._ping("1.1.1.1"), "dns_speed": self._dns_bench(),
                "packet_loss": self._packet_loss("1.1.1.1"),
                "open_ports": self._ports(), "tcp_stats": self._tcp_stats(),
                "public_ip": self._public_ip(), "recommendation": self._recommend()}

    def _ping(self, target, count=4):
        cmd = ["ping", "-n" if IS_WIN else "-c", str(count), target]
        out = self.run_cmd(cmd, timeout=15) or ""
        lats = []
        for line in out.split("\n"):
            if "time=" in line:
                try: lats.append(float(line.split("time=")[-1].split()[0].replace("ms","")))
                except (ValueError,IndexError): pass
            elif "time<" in line:
                try: lats.append(float(line.split("time<")[-1].split()[0].replace("ms","")))
                except (ValueError,IndexError): pass
        return {"target": target, "avg_ms": round(sum(lats)/len(lats), 1) if lats else None, "samples": lats, "count": count}

    def _dns_bench(self, quick=True):
        providers = dict(list(self.DNS_PROVIDERS.items())[:3]) if quick else self.DNS_PROVIDERS
        results = {}
        for name, ip in providers.items():
            lat = self._ping(ip, count=1)
            results[name] = {"ip": ip, "avg_ms": lat.get("avg_ms"), "samples": lat.get("samples")}
        fastest = min([(k, v["avg_ms"]) for k, v in results.items() if v["avg_ms"] is not None],
                      key=lambda x: x[1], default=(None, None))
        return {"providers": results, "fastest": {"provider": fastest[0], "avg_ms": fastest[1]}}

    def _packet_loss(self, target, count=10):
        cmd = ["ping", "-n" if IS_WIN else "-c", str(count), target]
        out = self.run_cmd(cmd, timeout=20) or ""
        loss = None
        for line in out.split("\n"):
            if "%" in line:
                for part in line.split():
                    if "%" in part:
                        try: loss = float(part.replace("%","")); break
                        except ValueError: pass
        return {"target": target, "count": count, "loss_pct": loss}

    def _ports(self):
        common = {22:"SSH",80:"HTTP",443:"HTTPS",3306:"MySQL",5432:"PostgreSQL",6379:"Redis",8080:"HTTP-Alt",8443:"HTTPS-Alt",9090:"Prometheus",3000:"Grafana",5000:"Flask",8000:"Django"}
        open_ports = []
        for port, svc in common.items():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                if s.connect_ex(("127.0.0.1", port)) == 0: open_ports.append({"port": port, "service": svc})
                s.close()
            except Exception: pass
        return {"count": len(open_ports), "ports": open_ports}

    def _tcp_stats(self):
        out = self.run_cmd(["netstat", "-an"], timeout=10) or ""
        if IS_WIN: out = self.run_cmd(["netstat", "-an"]) or ""
        states = {}
        for line in out.split("\n"):
            for s in ["ESTABLISHED","TIME_WAIT","CLOSE_WAIT","LISTEN","SYN_SENT"]:
                if s in line: states[s] = states.get(s, 0) + 1
        return states

    def _public_ip(self):
        try:
            import urllib.request
            return json.loads(urllib.request.urlopen("https://api.ipify.org?format=json", timeout=5).read()).get("ip","unknown")
        except Exception: return "unknown"

    def _recommend(self):
        recs, score = [], 100
        ping = self._ping("1.1.1.1", count=3)
        if ping["avg_ms"] is None: score -= 20; recs.append({"issue":"无网络连接","action":"检查网络"})
        elif ping["avg_ms"] > 100: score -= 15; recs.append({"issue":f"延迟{ping['avg_ms']}ms","action":"检查网络质量"})
        elif ping["avg_ms"] > 50: score -= 5

        dns = self._dns_bench(quick=True)
        f = dns.get("fastest",{})
        if f.get("avg_ms") and f["avg_ms"] > 50:
            score -= 10; recs.append({"issue":f"DNS慢({f['avg_ms']}ms)", "action":f"建议切换{f.get('provider','?')}"})

        pl = self._packet_loss("1.1.1.1", count=10)
        if pl.get("loss_pct") and pl["loss_pct"] > 2:
            score -= 20; recs.append({"issue":f"丢包{pl['loss_pct']}%","action":"检查WiFi/网线"})

        tcp = self._tcp_stats()
        if tcp.get("TIME_WAIT", 0) > 200:
            score -= 5; recs.append({"issue":f"TIME_WAIT过多({tcp['TIME_WAIT']})","action":"检查短连接应用"})

        return {"score": max(0, score), "recommendations": recs}

    # ── Optimize ─────────────────────

    def _optimize(self, targets, dry_run):
        actions = []
        if "dns" in targets or not targets:
            dns = self._dns_bench(quick=True)
            f = dns.get("fastest", {})
            provider, ip = f.get("provider", ""), self.DNS_PROVIDERS.get(f.get("provider", ""), "")
            if dry_run:
                actions.append({"item":"DNS", "action":f"切换到{provider}({ip})", "result":"dry_run", "freed_mb":0})
            elif IS_MAC:
                svcs = self.run_cmd(["networksetup","-listallnetworkservices"], timeout=5)
                if svcs:
                    for svc in svcs.split("\n")[1:]:
                        svc = svc.strip()
                        if svc and not svc.startswith("*"):
                            self.run_cmd(["networksetup","-setdnsservers", svc, ip], timeout=5)
                actions.append({"item":"DNS", "action":f"→{provider}({ip})", "result":"ok", "freed_mb":0})
            elif IS_LINUX:
                try:
                    resolved = Path("/etc/resolv.conf")
                    if resolved.exists():
                        import shutil
                        shutil.copy2(resolved, BACKUP_ROOT / self._backup_id / "resolv.conf.bak")
                        with open(resolved, "w") as fh:
                            fh.write(f"# OptimizerPlatform\nnameserver {ip}\n")
                        actions.append({"item":"DNS", "action":f"→{provider}({ip})", "result":"ok(已备份)","freed_mb":0})
                    else:
                        actions.append({"item":"DNS","action":"跳过","result":"无/etc/resolv.conf","freed_mb":0})
                except Exception as e:
                    actions.append({"item":"DNS", "action":f"→{provider}", "result":f"error:{e}", "freed_mb":0})
            else:
                actions.append({"item":"DNS", "action":f"→{provider}({ip})", "result":"需手动(Windows)", "freed_mb":0})
        return actions

    def _rollback(self, backup_id):
        bak = BACKUP_ROOT / backup_id / "resolv.conf.bak"
        if bak.exists():
            import shutil; shutil.copy2(bak, "/etc/resolv.conf")
            return {"status":"restored", "item":"DNS", "result":"已恢复/etc/resolv.conf"}
        return {"status":"skipped", "note":"无可回滚文件"}
