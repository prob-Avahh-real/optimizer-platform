"""Bonus — Benchmark Center: CPU, disk I/O, network scoring."""
import time, os, random
from pathlib import Path
from .base import BaseModule


class BenchmarkCenter(BaseModule):
    def _scan(self):
        cpu = self._cpu_bench()
        disk = self._disk_bench()
        net = self._net_bench()
        return {"cpu": cpu, "disk": disk, "network": net, "summary": self._summary(cpu, disk, net)}

    def _cpu_bench(self):
        start = time.time()
        n = 50000
        sieve = [True] * (n + 1)
        sieve[0] = sieve[1] = False
        for i in range(2, int(n**0.5) + 1):
            if sieve[i]:
                for j in range(i*i, n+1, i): sieve[j] = False
        primes = sum(1 for x in sieve if x)
        elapsed = time.time() - start
        score = round(min(primes / max(elapsed, 0.001) / 100, 1000))
        return {"score": score, "primes_found": primes, "elapsed_s": round(elapsed, 3), "method": "sieve_50000"}

    def _disk_bench(self):
        tmp = Path.home() / ".optimizer_bench_test"
        size_mb = 50
        data = bytes([random.randint(0, 255) for _ in range(1024 * 1024)])
        try:
            start = time.time()
            with open(tmp, "wb") as f:
                for _ in range(size_mb): f.write(data)
            write_mbps = round(size_mb / max(time.time() - start, 0.001), 1)
            start = time.time()
            with open(tmp, "rb") as f:
                while f.read(1024 * 1024): pass
            read_mbps = round(size_mb / max(time.time() - start, 0.001), 1)
        except Exception as e:
            return {"error": str(e), "score": 0, "read_mbps": 0, "write_mbps": 0}
        finally:
            try: os.remove(tmp)
            except OSError: pass
        score = round((read_mbps + write_mbps) / 20)
        return {"score": min(score, 1000), "read_mbps": read_mbps, "write_mbps": write_mbps, "test_size_mb": size_mb}

    def _net_bench(self):
        import socket
        times = []
        for host in ["google.com", "github.com", "cloudflare.com", "baidu.com"]:
            try:
                t0 = time.time(); socket.gethostbyname(host)
                times.append((time.time() - t0) * 1000)
            except Exception: times.append(500)
        avg = round(sum(times) / len(times), 1) if times else 500
        score = round(max(0, 1000 - avg * 10))
        return {"score": score, "dns_avg_ms": avg, "dns_samples": times}

    def _summary(self, cpu, disk, net):
        combined = round((cpu["score"] + disk["score"] + net["score"]) / 3)
        return {"cpu_score": cpu["score"], "disk_score": disk["score"], "network_score": net["score"],
                "combined_score": combined, "grade": self._grade(combined)}

    @staticmethod
    def _grade(s):
        if s >= 800: return "A — 优秀"
        if s >= 600: return "B — 良好"
        if s >= 400: return "C — 一般"
        if s >= 200: return "D — 较差"
        return "E — 需优化"
