# OpenVort 后端重启

## 适用场景

当修改了后端 Python 代码（路由、service、model 等）后，需要AI顺手操作重启后端服务使改动生效。

## 一键重启（推荐）

使用 CLI 内置的 restart 命令，它会自动停止旧进程、清理残留连接、再启动：

```bash
cd /Users/yangqiang/Work/Projects/openvort && PYTHONUNBUFFERED=1 .venv/bin/openvort restart --web 2>&1
```

- 设置 `block_until_ms: 0` 让它立即进入后台
- 然后 sleep 10s 再读 terminal 文件检查输出

## 检查启动成功

读 terminal 文件的最后 30 行，确认包含以下关键字样：
- `数据库已初始化` — 数据库建表正常
- `Web 管理面板已启动` — Web 面板就绪
- `OpenVort 已就绪` — 服务完全启动

## 仅停止

```bash
cd /Users/yangqiang/Work/Projects/openvort && .venv/bin/openvort stop
```

## 手动重启（备用方案）

只在 CLI 命令不可用时使用：

1. 找到后端进程 PID：
   ```bash
   cat ~/.openvort/openvort.pid 2>/dev/null
   ```

2. 优雅终止（先 SIGTERM，等 5 秒，再 SIGKILL）：
   ```bash
   PID=$(cat ~/.openvort/openvort.pid 2>/dev/null); if [ -n "$PID" ]; then kill $PID 2>/dev/null; sleep 5; kill -0 $PID 2>/dev/null && kill -9 $PID 2>/dev/null; fi
   ```

3. 启动：
   ```bash
   cd /Users/yangqiang/Work/Projects/openvort && PYTHONUNBUFFERED=1 .venv/bin/openvort start --web 2>&1
   ```

## 数据库操作

需要直连数据库排查数据时，**必须从 `.env` 读取 `OPENVORT_DATABASE_URL`** 提取实际连接信息（host/port/user/password），不要假设是 localhost 或使用默认密码。

```bash
# 正确做法：从 .env 提取数据库连接信息
grep OPENVORT_DATABASE_URL /Users/yangqiang/Work/Projects/openvort/.env
# 然后用提取到的实际 host/port/password 连接
```

## 注意事项

- 前端 dev server（`npm run dev`，端口 9090）如果端口已启动，不需要重启，Vite 有 HMR。
- 后端监听端口 8090，前端通过 Vite proxy 转发 `/api` 请求到后端。
- 每次修改后端代码后都应该执行重启，否则改动不会生效。
- **永远不要用 `kill -9`**，使用 `openvort stop` 或 SIGTERM。
- **数据库是远程共享的**，不是本地 Docker，连接信息见 `.env`。
