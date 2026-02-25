# OpenVort Relay — Node.js 版（零依赖）

轻量独立服务，部署在公网服务器上，接收企微回调消息，供本地/内网的 OpenVort 引擎拉取。

**零外部依赖**，仅使用 Node.js 内置模块（http, https, crypto, fs）。

## 部署

```bash
# 1. 拷贝到服务器（只需一个文件）
scp relay.js root@your-server:~/openvort-relay/

# 2. SSH 登录服务器

# 3. 配置（二选一）

# 方式 A：设置环境变量
export RELAY_WECOM_CORP_ID=your_corp_id
export RELAY_WECOM_APP_SECRET=your_app_secret
export RELAY_WECOM_AGENT_ID=your_agent_id
export RELAY_WECOM_TOKEN=your_callback_token
export RELAY_WECOM_AES_KEY=your_callback_aes_key

# 方式 B：直接改 relay.js 顶部的 CONFIG

# 4. 启动
node relay.js
```

## 后台运行

```bash
# 使用 nohup
nohup node relay.js > relay.log 2>&1 &

# 或使用 pm2（如果有）
pm2 start relay.js --name openvort-relay
```

## 与 Python 版的区别

| | Node.js 版 | Python 版 |
|---|-----------|-----------|
| 外部依赖 | 0 | 4 个 pip 包 |
| 存储 | JSON 文件 | SQLite |
| 适合场景 | 消息量小、快速部署 | 消息量大、需要可靠存储 |
| 文件数 | 1 个 | 3 个 |
