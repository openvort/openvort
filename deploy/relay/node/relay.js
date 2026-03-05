#!/usr/bin/env node
/**
 * OpenVort Relay — 企微消息中继服务（Node.js 零依赖版）
 *
 * 部署在公网服务器上，接收企微回调消息，供本地/内网的 OpenVort 引擎拉取。
 * 零外部依赖，仅使用 Node.js 内置模块。
 *
 * 使用方法：
 *   1. 修改下方配置（或设置环境变量）
 *   2. node relay.js
 *   3. 在企微后台填写回调 URL: http://your-server:8080/callback/wecom
 *
 * 环境变量：
 *   RELAY_WECOM_CORP_ID       企业ID
 *   RELAY_WECOM_APP_SECRET    应用Secret
 *   RELAY_WECOM_AGENT_ID      应用AgentId
 *   RELAY_WECOM_TOKEN         回调Token
 *   RELAY_WECOM_AES_KEY       回调EncodingAESKey
 *   RELAY_SECRET              Relay API 鉴权密钥（可选）
 *   RELAY_PORT                监听端口（默认 8080）
 *   RELAY_DB_PATH             SQLite 路径（默认 relay.db）— 此版本使用 JSON 文件存储
 */

const http = require("http");
const https = require("https");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const { URL } = require("url");

// ============================================================
// 配置
// ============================================================

const CONFIG = {
  WECOM_CORP_ID: process.env.RELAY_WECOM_CORP_ID || "",
  WECOM_APP_SECRET: process.env.RELAY_WECOM_APP_SECRET || "",
  WECOM_AGENT_ID: process.env.RELAY_WECOM_AGENT_ID || "",
  WECOM_TOKEN: process.env.RELAY_WECOM_TOKEN || "",
  WECOM_AES_KEY: process.env.RELAY_WECOM_AES_KEY || "",
  WECOM_API_BASE: "https://qyapi.weixin.qq.com/cgi-bin",
  RELAY_SECRET: process.env.RELAY_SECRET || "",
  PORT: parseInt(process.env.RELAY_PORT || "8080"),
  DB_PATH: process.env.RELAY_DB_PATH || "relay_data.json",
};

// ============================================================
// 企微消息加解密
// ============================================================

class WeComCrypto {
  constructor(token, encodingAesKey, corpId) {
    this.token = token;
    this.corpId = corpId;
    this.aesKey = Buffer.from(encodingAesKey + "=", "base64");
    this.iv = this.aesKey.subarray(0, 16);
  }

  verifySignature(signature, timestamp, nonce, echostr = "") {
    const items = [this.token, timestamp, nonce, echostr].sort();
    const sha1 = crypto.createHash("sha1").update(items.join("")).digest("hex");
    return sha1 === signature;
  }

  decrypt(encrypted) {
    const decipher = crypto.createDecipheriv("aes-256-cbc", this.aesKey, this.iv);
    decipher.setAutoPadding(false);
    let decrypted = Buffer.concat([decipher.update(encrypted, "base64"), decipher.final()]);
    // 去除 PKCS7 填充
    const padLen = decrypted[decrypted.length - 1];
    decrypted = decrypted.subarray(0, decrypted.length - padLen);
    // 解析：16字节随机串 + 4字节消息长度 + 消息体 + corp_id
    const msgLen = decrypted.readUInt32BE(16);
    const msg = decrypted.subarray(20, 20 + msgLen).toString("utf-8");
    const fromCorpId = decrypted.subarray(20 + msgLen).toString("utf-8");
    if (fromCorpId !== this.corpId) {
      throw new Error(`corp_id 不匹配: ${fromCorpId} != ${this.corpId}`);
    }
    return msg;
  }

  decryptCallback(xmlText, msgSignature, timestamp, nonce) {
    // 提取 Encrypt 节点
    const match = xmlText.match(/<Encrypt><!\[CDATA\[(.*?)\]\]><\/Encrypt>/);
    if (!match) throw new Error("XML 中缺少 Encrypt 节点");
    const encrypted = match[1];
    if (!this.verifySignature(msgSignature, timestamp, nonce, encrypted)) {
      throw new Error("签名验证失败");
    }
    const decryptedXml = this.decrypt(encrypted);
    // 简单 XML 解析
    const result = {};
    const tagRegex = /<(\w+)><!\[CDATA\[([\s\S]*?)\]\]><\/\1>/g;
    const tagRegex2 = /<(\w+)>([\s\S]*?)<\/\1>/g;
    let m;
    while ((m = tagRegex.exec(decryptedXml)) !== null) result[m[1]] = m[2];
    while ((m = tagRegex2.exec(decryptedXml)) !== null) if (!result[m[1]]) result[m[1]] = m[2];
    return result;
  }
}

// ============================================================
// JSON 文件存储（零依赖，不用 SQLite）
// ============================================================

const PROCESSING_TIMEOUT_MS = 30000; // 处理中状态超时 30 秒

class RelayStore {
  constructor(dbPath) {
    this.dbPath = dbPath;
    this.data = { nextId: 1, messages: [] };
    this._load();

    // 启动超时清理定时器
    setInterval(() => this._releaseTimeout(), 5000);
  }

  _load() {
    try {
      if (fs.existsSync(this.dbPath)) {
        this.data = JSON.parse(fs.readFileSync(this.dbPath, "utf-8"));
      }
    } catch (e) {
      console.error(`[Relay] 加载数据失败: ${e.message}`);
    }
  }

  _save() {
    fs.writeFileSync(this.dbPath, JSON.stringify(this.data, null, 2));
  }

  // 释放超时的 processing 消息
  _releaseTimeout() {
    const now = Date.now();
    let changed = false;
    for (const msg of this.data.messages) {
      if (msg.status === "processing" && now - msg.processing_since > PROCESSING_TIMEOUT_MS) {
        msg.status = "pending";
        delete msg.processing_since;
        changed = true;
      }
    }
    if (changed) this._save();
  }

  save(msg) {
    const id = this.data.nextId++;
    this.data.messages.push({
      id,
      msg_id: msg.MsgId || "",
      from_user: msg.FromUserName || "",
      msg_type: msg.MsgType || "text",
      content: msg.Content || "",
      raw_data: msg,
      status: "pending", // pending | processing | processed
      created_at: parseFloat(msg.CreateTime) || Date.now() / 1000,
    });
    this._save();
    return id;
  }

  // 原子性获取并标记消息为处理中（防止多客户端重复消费）
  getAndMarkProcessing(sinceId = 0, limit = 50) {
    const now = Date.now();
    const messages = [];

    for (const msg of this.data.messages) {
      if (messages.length >= limit) break;
      if (msg.id <= sinceId) continue;
      if (msg.status === "processed") continue;
      if (msg.status === "pending") {
        // 原子性标记为 processing
        msg.status = "processing";
        msg.processing_since = now;
        messages.push(msg);
      } else if (msg.status === "processing") {
        // 超时的 processing 也视为可用
        if (now - (msg.processing_since || 0) > PROCESSING_TIMEOUT_MS) {
          msg.processing_since = now;
          messages.push(msg);
        }
      }
    }

    if (messages.length > 0) {
      this._save();
    }

    return messages;
  }

  // 确认处理完成
  markProcessed(msgId) {
    const msg = this.data.messages.find((m) => m.id === msgId);
    // 只有 processing 状态才能确认，防止重复 ack
    if (msg && msg.status === "processing") {
      msg.status = "processed";
      delete msg.processing_since;
      this._save();
      return true;
    }
    return false;
  }

  cleanup(maxAgeHours = 72) {
    const cutoff = Date.now() / 1000 - maxAgeHours * 3600;
    const before = this.data.messages.length;
    this.data.messages = this.data.messages.filter(
      (m) => !(m.status === "processed" && m.created_at < cutoff)
    );
    this._save();
    return before - this.data.messages.length;
  }

  // 调试用：获取所有消息（包括已消费的）
  getAllMessages(sinceId = 0, limit = 50, status = "all") {
    return this.data.messages
      .filter((m) => {
        if (m.id <= sinceId) return false;
        if (status !== "all" && m.status !== status) return false;
        return true;
      })
      .slice(-limit) // 返回最新的
      .reverse(); // 按时间倒序
  }

  // 调试用：重置消息状态
  resetMessage(msgId, newStatus = "pending") {
    const msg = this.data.messages.find((m) => m.id === msgId);
    if (msg) {
      msg.status = newStatus;
      if (newStatus === "pending") {
        delete msg.processing_since;
      }
      this._save();
      return true;
    }
    return false;
  }
}

// ============================================================
// 企微 Token 管理
// ============================================================

let tokenCache = { token: "", expires: 0 };

function httpsGet(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        try { resolve(JSON.parse(data)); } catch (e) { reject(e); }
      });
    }).on("error", reject);
  });
}

function httpsPost(url, body) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const postData = JSON.stringify(body);
    const options = {
      hostname: parsed.hostname,
      port: 443,
      path: parsed.pathname + parsed.search,
      method: "POST",
      headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(postData) },
    };
    const req = https.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        try { resolve(JSON.parse(data)); } catch (e) { reject(e); }
      });
    });
    req.on("error", reject);
    req.write(postData);
    req.end();
  });
}

async function getWecomToken() {
  if (tokenCache.token && Date.now() / 1000 < tokenCache.expires - 60) {
    return tokenCache.token;
  }
  const url = `${CONFIG.WECOM_API_BASE}/gettoken?corpid=${CONFIG.WECOM_CORP_ID}&corpsecret=${CONFIG.WECOM_APP_SECRET}`;
  const data = await httpsGet(url);
  if (data.errcode) throw new Error(`获取 token 失败: ${JSON.stringify(data)}`);
  tokenCache.token = data.access_token;
  tokenCache.expires = Date.now() / 1000 + (data.expires_in || 7200);
  return tokenCache.token;
}

// ============================================================
// HTTP 服务
// ============================================================

const store = new RelayStore(CONFIG.DB_PATH);
const wecomCrypto =
  CONFIG.WECOM_TOKEN && CONFIG.WECOM_AES_KEY
    ? new WeComCrypto(CONFIG.WECOM_TOKEN, CONFIG.WECOM_AES_KEY, CONFIG.WECOM_CORP_ID)
    : null;

function checkAuth(req) {
  if (!CONFIG.RELAY_SECRET) return true;
  return (req.headers.authorization || "") === `Bearer ${CONFIG.RELAY_SECRET}`;
}

function parseQuery(url) {
  const params = {};
  const idx = url.indexOf("?");
  if (idx === -1) return params;
  url.substring(idx + 1).split("&").forEach((pair) => {
    const [k, v] = pair.split("=");
    params[decodeURIComponent(k)] = decodeURIComponent(v || "");
  });
  return params;
}

function readBody(req) {
  return new Promise((resolve) => {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", () => resolve(body));
  });
}

function json(res, data, status = 200) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(data));
}

function text(res, content, status = 200) {
  res.writeHead(status, { "Content-Type": "text/plain" });
  res.end(content);
}

const server = http.createServer(async (req, res) => {
  const urlPath = req.url.split("?")[0];
  const query = parseQuery(req.url);

  try {
    // ---- 企微回调 ----

    if (urlPath === "/callback/wecom" && req.method === "GET") {
      if (!wecomCrypto) return text(res, "crypto not configured", 500);
      const { msg_signature, timestamp, nonce, echostr } = query;
      if (wecomCrypto.verifySignature(msg_signature, timestamp, nonce, echostr)) {
        const decrypted = wecomCrypto.decrypt(echostr);
        console.log("[Relay] URL 验证成功");
        return text(res, decrypted);
      }
      return text(res, "verification failed", 403);
    }

    if (urlPath === "/callback/wecom" && req.method === "POST") {
      if (!wecomCrypto) return text(res, "crypto not configured", 500);
      const body = await readBody(req);
      const { msg_signature, timestamp, nonce } = query;
      const msgDict = wecomCrypto.decryptCallback(body, msg_signature, timestamp, nonce);
      const msgId = store.save(msgDict);
      console.log(`[Relay] 收到消息 #${msgId}: ${msgDict.FromUserName || ""} -> ${msgDict.MsgType || ""} | ${(msgDict.Content || "").substring(0, 50)}`);
      return text(res, "success");
    }

    // ---- Relay API ----

    // 原子性获取消息并标记为处理中（防止多客户端重复消费）
    if (urlPath === "/relay/messages" && req.method === "GET") {
      if (!checkAuth(req)) return json(res, { error: "unauthorized" }, 401);
      const sinceId = parseInt(query.since_id || "0");
      const limit = parseInt(query.limit || "50");
      const messages = store.getAndMarkProcessing(sinceId, limit);
      return json(res, { messages });
    }

    // 确认消息处理完成
    if (urlPath.match(/^\/relay\/messages\/\d+\/ack$/) && req.method === "POST") {
      if (!checkAuth(req)) return json(res, { error: "unauthorized" }, 401);
      const msgId = parseInt(urlPath.split("/")[3]);
      const ok = store.markProcessed(msgId);
      return json(res, { ok });
    }

    if (urlPath === "/relay/send" && req.method === "POST") {
      if (!checkAuth(req)) return json(res, { error: "unauthorized" }, 401);
      const body = JSON.parse(await readBody(req));
      const { touser, content, msg_type = "text", media_id } = body;
      if (!touser) return json(res, { error: "touser required" }, 400);
      if (!content && msg_type !== "voice") return json(res, { error: "content required" }, 400);

      const token = await getWecomToken();
      const payload = { touser, agentid: CONFIG.WECOM_AGENT_ID, msgtype: msg_type };

      if (msg_type === "voice") {
        // 语音消息：需要 media_id
        if (!media_id) return json(res, { error: "media_id required for voice" }, 400);
        payload.voice = { media_id };
      } else if (msg_type === "markdown") {
        payload.markdown = { content };
      } else {
        payload.text = { content };
      }

      const data = await httpsPost(
        `${CONFIG.WECOM_API_BASE}/message/send?access_token=${token}`,
        payload
      );
      if (data.errcode) {
        console.log(`[Relay] 发送失败: ${JSON.stringify(data)}`);
        return json(res, { error: data.errmsg || "unknown" }, 502);
      }
      console.log(`[Relay] 已发送消息 -> ${touser} (${msg_type})`);
      return json(res, { ok: true });
    }

    if (urlPath === "/relay/health" && req.method === "GET") {
      const info = {
        status: "ok",
        crypto: !!wecomCrypto,
        corp_id: CONFIG.WECOM_CORP_ID ? CONFIG.WECOM_CORP_ID.substring(0, 6) + "***" : "",
        db: CONFIG.DB_PATH,
      };
      try {
        const token = await getWecomToken();
        info.wecom_api = !!token;
      } catch {
        info.wecom_api = false;
      }
      return json(res, info);
    }

    if (urlPath === "/relay/cleanup" && req.method === "POST") {
      if (!checkAuth(req)) return json(res, { error: "unauthorized" }, 401);
      const deleted = store.cleanup();
      return json(res, { deleted });
    }

    // 调试接口：获取所有消息（包括已消费的）
    if (urlPath === "/relay/messages/all" && req.method === "GET") {
      if (!checkAuth(req)) return json(res, { error: "unauthorized" }, 401);
      const sinceId = parseInt(query.since_id || "0");
      const limit = parseInt(query.limit || "50");
      const status = query.status || "all"; // pending, processing, processed, all
      const messages = store.getAllMessages(sinceId, limit, status);
      return json(res, { messages, total: store.data.messages.length });
    }

    // 调试接口：重置消息状态
    if (urlPath === "/relay/messages/reset" && req.method === "POST") {
      if (!checkAuth(req)) return json(res, { error: "unauthorized" }, 401);
      const { msg_id, status } = JSON.parse(await readBody(req) || "{}");
      const ok = store.resetMessage(msg_id, status);
      return json(res, { ok });
    }

    // 404
    json(res, { error: "not found" }, 404);
  } catch (e) {
    console.error(`[Relay] 错误: ${e.message}`);
    json(res, { error: e.message }, 500);
  }
});

// ============================================================
// 启动
// ============================================================

if (!CONFIG.WECOM_CORP_ID || !CONFIG.WECOM_APP_SECRET) {
  console.error("❌ 请配置 RELAY_WECOM_CORP_ID 和 RELAY_WECOM_APP_SECRET");
  console.error("   可以修改 relay.js 顶部的配置，或设置环境变量");
  process.exit(1);
}

console.log(`
╔══════════════════════════════════════════╗
║     OpenVort Relay Server v0.1 (Node)    ║
╠══════════════════════════════════════════╣
║  端口: ${String(CONFIG.PORT).padEnd(33)}║
║  存储: ${CONFIG.DB_PATH.padEnd(33)}║
║  加解密: ${(wecomCrypto ? "已配置" : "未配置（无法接收回调）").padEnd(25)}║
║  鉴权: ${(CONFIG.RELAY_SECRET ? "已启用" : "未启用").padEnd(27)}║
║  依赖: 零（纯 Node.js 内置模块）        ║
╠══════════════════════════════════════════╣
║  回调地址:                               ║
║  http://your-domain:${CONFIG.PORT}/callback/wecom  ║
║                                          ║
║  API 地址:                               ║
║  http://your-domain:${CONFIG.PORT}/relay/          ║
╚══════════════════════════════════════════╝
`);

server.listen(CONFIG.PORT, "0.0.0.0", () => {
  console.log(`[Relay] 已启动，监听 0.0.0.0:${CONFIG.PORT}`);
});
