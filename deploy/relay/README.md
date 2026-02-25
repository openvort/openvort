# OpenVort Relay — 企微消息中继服务

轻量独立服务，部署在公网服务器上，接收企微回调消息，供本地/内网的 OpenVort 引擎拉取。

## 部署

```bash
# 1. 拷贝到服务器
scp -r deploy/relay/ root@your-server:~/openvort-relay/

# 2. SSH 登录服务器，安装依赖
ssh root@your-server
cd ~/openvort-relay
pip install -r requirements.txt

# 3. 配置（二选一）

# 方式 A：直接改 relay.py 顶部的配置
vim relay.py

# 方式 B：设置环境变量
export RELAY_WECOM_CORP_ID=your_corp_id
export RELAY_WECOM_APP_SECRET=your_app_secret
export RELAY_WECOM_AGENT_ID=your_agent_id
export RELAY_WECOM_TOKEN=your_callback_token
export RELAY_WECOM_AES_KEY=your_callback_aes_key

# 4. 启动
python relay.py
```

## 企微后台配置

1. 登录企业微信管理后台
2. 进入 应用管理 → 你的应用 → 接收消息
3. 设置 API 接收：
   - URL: `http://your-server:8080/callback/wecom`
   - Token: 你设置的 RELAY_WECOM_TOKEN
   - EncodingAESKey: 你设置的 RELAY_WECOM_AES_KEY

## 本地 OpenVort 连接

在本地 OpenVort 的 `.env` 中配置：

```
OPENVORT_RELAY_URL=http://your-server:8080
OPENVORT_RELAY_SECRET=your_relay_secret
```

然后启动：

```bash
openvort start --relay-url http://your-server:8080
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/callback/wecom` | GET | 企微 URL 验证 |
| `/callback/wecom` | POST | 接收企微回调消息 |
| `/relay/messages?since_id=0&limit=50` | GET | 拉取新消息 |
| `/relay/messages/{id}/ack` | POST | 标记消息已处理 |
| `/relay/send` | POST | 代理发送消息到企微 |
| `/relay/health` | GET | 健康检查 |
| `/relay/cleanup` | POST | 清理过期消息 |

## 后台运行

```bash
# 使用 nohup
nohup python relay.py > relay.log 2>&1 &

# 或使用 screen
screen -S relay
python relay.py
# Ctrl+A D 退出 screen
```

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `RELAY_WECOM_CORP_ID` | 是 | 企业ID |
| `RELAY_WECOM_APP_SECRET` | 是 | 应用Secret |
| `RELAY_WECOM_AGENT_ID` | 否 | 应用AgentId |
| `RELAY_WECOM_TOKEN` | 是* | 回调Token |
| `RELAY_WECOM_AES_KEY` | 是* | 回调EncodingAESKey |
| `RELAY_SECRET` | 否 | API 鉴权密钥 |
| `RELAY_PORT` | 否 | 监听端口（默认 8080） |
| `RELAY_DB_PATH` | 否 | SQLite 路径（默认 relay.db） |

*接收回调必填，仅代理发送可不填
