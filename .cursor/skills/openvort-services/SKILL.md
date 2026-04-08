---
name: openvort-services
description: OpenVort 前后端服务启动、重启、停止。当用户要求启动/重启/停止 OpenVort 服务、修改后端代码需要重启、或需要检查服务状态时使用此 Skill。
---

# OpenVort 服务管理

项目根目录：工作区根目录（含 `web/`、`src/`）。

Python 虚拟环境位于 `~/.virtualenvs/openvort/`（固定路径，不随项目目录移动）。

| 服务 | 端口 | 技术 |
|------|------|------|
| 后端 (FastAPI) | 8090 | Python + uvicorn |
| 前端 (Vite dev) | 9090 | Vue 3 + Vite，`/api` 代理到 8090 |

**所有 Shell 命令必须设置 `required_permissions: ["all"]`**，否则沙箱会阻止 PID 文件写入和网络接口访问。

## 后端操作

### 启动

```bash
PYTHONUNBUFFERED=1 ~/.virtualenvs/openvort/bin/openvort start 2>&1
```

### 开发模式启动（推荐开发者使用）

```bash
PYTHONUNBUFFERED=1 ~/.virtualenvs/openvort/bin/openvort start --dev 2>&1
```

`--dev` 模式跳过 IM 通道/ASR/TTS/Embedding/NotificationCenter 初始化，启动更快。Banner 显示 `Backend http://localhost:8090` 而非 `site_url`。

### 重启（推荐）

```bash
PYTHONUNBUFFERED=1 ~/.virtualenvs/openvort/bin/openvort restart 2>&1
# 或开发模式
PYTHONUNBUFFERED=1 ~/.virtualenvs/openvort/bin/openvort restart --dev 2>&1
```

### 停止

```bash
~/.virtualenvs/openvort/bin/openvort stop
```

### 执行方式

1. `block_until_ms: 0` 让命令立即进入后台
2. `sleep 12` 等待启动完成（`--dev` 模式可缩短到 `sleep 8`）
3. 读 terminal 文件最后 15 行，确认包含：
   - `OpenVort v*.* started` — 启动成功 banner（dev 模式含 `[DEV]`）
   - `Backend http://...` (dev) 或 `Panel http://...` (正常模式) — 服务地址
4. 若出现 `未安装 uvicorn/fastapi，Web 面板未启动。ImportError: No module named 'xxx'`：
   - 用 `~/.virtualenvs/openvort/bin/pip install <缺失模块>` 安装
   - 再次执行 restart

## 前端操作

### 启动

```bash
cd web && npm run dev 2>&1
```

### 重启

先杀掉占用 9090 端口的进程，再启动：

```bash
lsof -ti:9090 | xargs kill -9 2>/dev/null; sleep 1; cd web && npm run dev 2>&1
```

### 执行方式

1. `block_until_ms: 0` 让命令立即进入后台
2. `sleep 5` 等待启动
3. 读 terminal 文件，确认包含 `VITE v*.* ready` 和 `Local: http://localhost:9090/`
4. 若出现 `Port 9090 is already in use`，用 `lsof -ti:9090 | xargs kill -9` 清理后重试

### 注意

前端有 HMR，修改前端代码**不需要重启**。只有以下情况需要重启前端：
- `vite.config.ts` 修改
- `package.json` 依赖变更
- 进程意外退出

## 全部启动/重启

后端和前端可**并行启动**（两个独立 Shell 调用）：

```
Shell 1: PYTHONUNBUFFERED=1 ~/.virtualenvs/openvort/bin/openvort restart --dev 2>&1
Shell 2: lsof -ti:9090 | xargs kill -9 2>/dev/null; sleep 1; cd web && npm run dev 2>&1
```

两个都用 `block_until_ms: 0`，然后 `sleep 14`，最后分别读两个 terminal 文件确认状态。

> 后端 :8090，前端 :9090（Vite 代理 /api 到 :8090）。开发时通过 :9090 访问，享受前端 HMR。

## 手动重启（备用）

只在 CLI 命令不可用时使用：

```bash
# 查看 PID
cat ~/.openvort/openvort.pid 2>/dev/null

# 优雅停止
PID=$(cat ~/.openvort/openvort.pid 2>/dev/null); if [ -n "$PID" ]; then kill $PID 2>/dev/null; sleep 5; kill -0 $PID 2>/dev/null && kill -9 $PID 2>/dev/null; fi

# 启动
PYTHONUNBUFFERED=1 ~/.virtualenvs/openvort/bin/openvort start 2>&1
```

## 数据库

连接信息在 `.env` 的 `OPENVORT_DATABASE_URL`。

需要直连数据库时，**必须从 `.env` 读取**实际连接信息，不要假设 localhost 或默认密码。
