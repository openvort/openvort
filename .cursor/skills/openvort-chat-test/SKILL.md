---
name: openvort-chat-test
description: 通过 API 模拟用户与 OpenVort AI 聊天，用于端到端测试。当需要测试 AI 对话、工具调用、SSE 流式输出、git_code_task 等功能时使用。
---

# OpenVort Chat 对话测试

通过 curl 直接调用后端 API，模拟用户发消息并监听 SSE 流式回复。

## 前置条件

- 后端已启动（端口 8090）
- 测试账号：`杨强` / `openvort`

## 测试流程

### 1. 登录获取 Token

```bash
TOKEN=$(curl -s -X POST "http://localhost:8090/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"杨强","password":"openvort"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
echo "Token: ${TOKEN:0:20}..."
```

### 2. 创建会话（可选，复用已有 session_id 也行）

```bash
SESSION=$(curl -s -X POST "http://localhost:8090/api/chat/sessions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"测试会话"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
echo "Session: $SESSION"
```

### 3. 发送消息

```bash
MSG_ID=$(curl -s -X POST "http://localhost:8090/api/chat/send" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"content\":\"你好\",\"images\":[],\"session_id\":\"$SESSION\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['message_id'])")
echo "Message ID: $MSG_ID"
```

### 4. 监听 SSE 流式回复

```bash
curl -N -s --max-time 300 \
  -H "Accept: text/event-stream" \
  "http://localhost:8090/api/chat/stream/${MSG_ID}?token=${TOKEN}"
```

## API 速查

| 操作 | 方法 | 路径 | 认证 |
|------|------|------|------|
| 登录 | POST | `/api/auth/login` | 无（body: `{user_id, password}`） |
| 创建会话 | POST | `/api/chat/sessions` | Bearer Token（body: `{title}`） |
| 发送消息 | POST | `/api/chat/send` | Bearer Token（body: `{content, images, session_id}`） |
| SSE 流 | GET | `/api/chat/stream/{message_id}?token=xxx` | Query param token |
| 聊天历史 | GET | `/api/chat/history?session_id=xxx` | Bearer Token |

## SSE 事件类型

| event | 含义 | data 格式 |
|-------|------|-----------|
| `thinking` | AI 开始思考 | `"start"` |
| `text` | AI 文本输出（累积全文） | 纯文本字符串 |
| `tool_use` | 开始调用工具 | `{"name": "xxx"}` |
| `tool_output` | 工具实时输出（CLI 逐行） | `{"name": "xxx", "output": "..."}` |
| `tool_progress` | 工具执行进度 | `{"name": "xxx", "elapsed": 10}` |
| `tool_result` | 工具执行完成 | `{"name": "xxx", "result": "..."}` |
| `usage` | Token 用量 | `{"input_tokens":..., "output_tokens":...}` |
| `done` | 回复结束 | `"ok"` |
| `server_error` | 服务端错误 | 错误描述字符串 |

## 一键测试脚本

将步骤 1-4 合并为一条命令（适合在 Shell tool 中直接执行）：

```bash
cd /Users/yangqiang/Work/Projects/openvort && \
TOKEN=$(curl -s -X POST "http://localhost:8090/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"杨强","password":"openvort"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])") && \
SESSION=$(curl -s -X POST "http://localhost:8090/api/chat/sessions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"测试"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])") && \
MSG_ID=$(curl -s -X POST "http://localhost:8090/api/chat/send" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"content\":\"<MESSAGE>\",\"images\":[],\"session_id\":\"$SESSION\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['message_id'])") && \
echo "Session=$SESSION MsgID=$MSG_ID" && \
curl -N -s --max-time 300 \
  -H "Accept: text/event-stream" \
  "http://localhost:8090/api/chat/stream/${MSG_ID}?token=${TOKEN}"
```

将 `<MESSAGE>` 替换为实际消息内容。

## 注意事项

- SSE stream 端点的认证是通过 **query param** `?token=xxx` 传的，不是 Header
- `text` 事件的 data 是**累积全文**（每次都是完整文本），不是增量 delta
- 消息发送后必须**立即**请求 stream，`message_id` 存在内存中，超时会丢失
- 长时间工具执行（如 `git_code_task`）需设置 `--max-time 300` 或更长
- 如果 SSE 返回前端 HTML 而非事件流，说明请求被 Vite proxy 拦截了——确认直接访问 8090 端口
