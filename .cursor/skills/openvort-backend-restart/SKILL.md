# OpenVort 后端重启

## 适用场景

当修改了后端 Python 代码（路由、service、model 等）后，需要AI顺手操作重启后端服务使改动生效。

## 操作步骤

1. 在 terminals 目录中找到当前正在运行的后端进程：
   ```bash
   for f in ~/.cursor/projects/Users-yangqiang-Work-Projects-openvort/terminals/*.txt; do
     if ! grep -q "exit_code" "$f" 2>/dev/null; then
       echo "RUNNING: $f"; head -3 "$f"; echo "---"
     fi
   done
   ```
   后端进程的特征：command 包含 `openvort start`，不是 `npm run dev`。

2. Kill 后端进程（用找到的 pid）：
   ```bash
   kill <pid> 2>/dev/null; sleep 2
   ```

3. 重启后端（使用 block_until_ms=8000 让它进入后台）：
   ```bash
   cd /Users/yangqiang/Work/Projects/openvort && .venv/bin/openvort start --web 2>&1
   ```

4. 检查输出中是否有 `Web 管理面板已启动` 和 `OpenVort 已就绪` 字样，确认启动成功。

## 注意事项

- 前端 dev server（`npm run dev`，端口 9090）不需要重启，Vite 有 HMR。
- 后端监听端口 8090，前端通过 Vite proxy 转发 `/api` 请求到后端。
- 每次修改后端代码后都应该执行重启，否则改动不会生效。
