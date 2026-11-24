# optimizer-platform

本机资产发现、网络测速、存储回收与 DevOps 缓存巡检一体化平台（FastAPI + Web Dashboard，已归档于 `archive/from-home/optimizer-platform`）。

## 核心模块

- `optimizer/core/asset_discovery.py`：主机硬件、系统环境、开发工具链与 Docker 状态探测
- `optimizer/core/network_center.py`：网络延迟、DNS 响应对比与网络健康评分
- `optimizer/core/storage_center.py` / `devops_center.py` / `container_center.py`：大文件、重复文件、构建缓存与容器体积分析
- `optimizer/core/benchmark.py` & `ai_reporter.py`：系统基准测试与综合优化建议生成
- `dashboard.html` & `run.sh`：一键端口自检启动 Web 看板或 CLI 全量扫描

## 目标平台（Target 判定）

- **移动端**：可选（桌面/主机巡检工具）
- **智能硬件**：可选（可搁置）

## 快速运行与验证

```bash
# 启动 Web 看板（默认自动探测 8765 起可用端口）
./run.sh dashboard

# 命令行巡检模式
./run.sh cli

# 运行归档冒烟测试
npm test
```
