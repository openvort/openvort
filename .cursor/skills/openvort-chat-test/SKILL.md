---
name: openvort-chat-test
description: 通过 API 模拟用户与 OpenVort AI 聊天，或通过 Relay 调试接口查看从 IM（企微）发来的真实消息。用于端到端测试、IM 消息调试、工具调用验证等场景。
---

# OpenVort Chat 对话测试 & IM 消息调试

两种调试方式：
1. **Web API 测试** — 通过 curl 直接调用后端 API，模拟用户发消息并监听 SSE 流式回复
2. **Relay 消息调试** — 查看从企微等 IM 通过 Relay 中继的真实消息，排查消息收发问题

## 前置条件

- 后端已启动（端口 8090）
- 测试账号：`杨强` / `openvort`
- Relay 地址：从 `.env` 的 `OPENVORT_RELAY_URL` 获取（当前：`http://wechat.tigshop.com:8080`）

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

---

## Relay IM 消息调试

当需要排查「用户从企微发了消息但 OpenVort 没收到 / 处理异常」等问题时，直接查询 Relay 中继服务器上的原始消息。

### Relay 地址

从项目 `.env` 文件的 `OPENVORT_RELAY_URL` 获取，当前为 `http://wechat.tigshop.com:8080`。
当前未配置 `RELAY_SECRET`，无需鉴权 Header。若后续启用了鉴权，需加 `-H "Authorization: Bearer $SECRET"`。

### 查看 IM 消息

查看所有消息（包括已消费的），支持按状态过滤：

```bash
# 查看最近消息（默认 50 条，所有状态）
curl -s "http://wechat.tigshop.com:8080/relay/messages/all" | python3 -m json.tool

# 按状态过滤：pending（待消费）/ processing（消费中）/ processed（已消费）/ all
curl -s "http://wechat.tigshop.com:8080/relay/messages/all?status=pending" | python3 -m json.tool

# 指定起始 ID 和数量
curl -s "http://wechat.tigshop.com:8080/relay/messages/all?since_id=100&limit=10" | python3 -m json.tool

# 只看最近 5 条待处理消息
curl -s "http://wechat.tigshop.com:8080/relay/messages/all?status=pending&limit=5" | python3 -m json.tool
```

返回格式：
```json
{
  "messages": [
    {
      "id": 123,
      "status": "processed",
      "data": {
        "ToUserName": "企业ID",
        "FromUserName": "用户ID",
        "MsgType": "text",
        "Content": "消息内容",
        "CreateTime": "1709712345"
      },
      "created_at": "2025-03-06T10:00:00.000Z"
    }
  ],
  "total": 456
}
```

### 重置消息状态（重放消息）

将已消费的消息重置为 pending，让 OpenVort 重新拉取处理：

```bash
curl -s -X POST "http://wechat.tigshop.com:8080/relay/messages/reset" \
  -H "Content-Type: application/json" \
  -d '{"msg_id": 123, "status": "pending"}' | python3 -m json.tool
```

### 健康检查

```bash
curl -s "http://wechat.tigshop.com:8080/relay/health" | python3 -m json.tool
```

返回：`{status, crypto, corp_id, db, wecom_api}`

### 清理旧消息

```bash
curl -s -X POST "http://wechat.tigshop.com:8080/relay/cleanup" | python3 -m json.tool
```

### Relay API 速查

| 操作 | 方法 | 路径 | 参数 |
|------|------|------|------|
| 查看所有消息 | GET | `/relay/messages/all` | `?since_id=0&limit=50&status=all` |
| 消费消息 | GET | `/relay/messages` | `?since_id=0&limit=50`（会标记 processing） |
| 确认消费 | POST | `/relay/messages/{id}/ack` | 无 body |
| 重置消息 | POST | `/relay/messages/reset` | body: `{msg_id, status}` |
| 发送消息 | POST | `/relay/send` | body: `{touser, content, msg_type}` |
| 健康检查 | GET | `/relay/health` | 无 |
| 清理 | POST | `/relay/cleanup` | 无 |

### 典型调试场景

**场景 1：用户说发了消息但没收到回复**
```bash
# 1. 检查 Relay 是否收到消息
curl -s "http://wechat.tigshop.com:8080/relay/messages/all?status=all&limit=10" | python3 -m json.tool
# 2. 看消息状态：pending=未被拉取, processing=拉取中, processed=已处理
# 3. 如果是 pending，说明 OpenVort 引擎没在拉取——检查后端是否启动了 relay 模式
# 4. 如果是 processed 但用户没收到回复，问题在 AI 处理或消息发送环节
```

**场景 2：重放一条消息让 AI 重新处理**
```bash
# 1. 找到目标消息 ID
curl -s "http://wechat.tigshop.com:8080/relay/messages/all?limit=5" | python3 -c "
import sys, json
msgs = json.load(sys.stdin)['messages']
for m in msgs:
    print(f'#{m[\"id\"]} [{m[\"status\"]}] {m[\"data\"].get(\"FromUserName\",\"?\")} -> {m[\"data\"].get(\"Content\",\"\")[:50]}')
"
# 2. 重置为 pending
curl -s -X POST "http://wechat.tigshop.com:8080/relay/messages/reset" \
  -H "Content-Type: application/json" \
  -d '{"msg_id": <ID>, "status": "pending"}'
```

**场景 3：检查 Relay 服务是否正常**
```bash
curl -s "http://wechat.tigshop.com:8080/relay/health" | python3 -m json.tool
# 关注 wecom_api: true（企微 API 连通）, crypto: true（加解密已配置）
```
