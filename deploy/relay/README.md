# OpenVort Relay — 企微消息中继服务

部署在公网服务器上，接收企微回调消息，供本地/内网的 OpenVort 引擎拉取和代理发送。

## 两种版本

| 版本 | 目录 | 依赖 | 存储 | 适合场景 |
|------|------|------|------|---------|
| **Node.js** | `node/` | 零依赖 | JSON 文件 | 快速部署、消息量小 |
| **Python** | `python/` | 4 个 pip 包 | SQLite | 消息量大、需要可靠存储 |

## 快速开始

### Node.js 版（推荐，最简单）

```bash
# 拷贝一个文件到服务器
scp node/relay.js root@your-server:~/openvort-relay/

# SSH 登录后直接跑
export RELAY_WECOM_CORP_ID=xxx
export RELAY_WECOM_APP_SECRET=xxx
export RELAY_WECOM_TOKEN=xxx
export RELAY_WECOM_AES_KEY=xxx
node relay.js
```

### Python 版

```bash
# 拷贝目录到服务器
scp -r python/ root@your-server:~/openvort-relay/

# SSH 登录后安装依赖并跑
cd ~/openvort-relay
pip install -r requirements.txt
python relay.py
```

## 本地 OpenVort 连接

```bash
# .env 中配置
OPENVORT_RELAY_URL=http://your-server:8080

# 启动
openvort start --relay-url http://your-server:8080
```

## API 接口

两个版本提供完全相同的 API：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/callback/wecom` | GET | 企微 URL 验证 |
| `/callback/wecom` | POST | 接收企微回调消息 |
| `/relay/messages?since_id=0&limit=50` | GET | 拉取新消息 |
| `/relay/messages/{id}/ack` | POST | 标记消息已处理 |
| `/relay/send` | POST | 代理发送消息到企微 |
| `/relay/health` | GET | 健康检查 |
| `/relay/cleanup` | POST | 清理过期消息 |
