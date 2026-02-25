# OpenVort

开源 AI 研发工作流引擎 — 通过 IM 与 AI 交互，自动化项目管理、代码仓库、团队协作。

## 特性

- **AI 驱动** — 基于 Claude tool use，Agent 自主决策调用哪些工具
- **多 IM 支持** — 企业微信（内置）、钉钉、飞书（插件扩展）
- **插件化架构** — Channel（IM 通道）和 Tool（业务工具）均可插拔
- **开箱即用** — `pip install openvort` + 配置 API Key 即可启动

## 快速开始

```bash
# 安装
pip install openvort

# 初始化配置
openvort init

# 启动
openvort start
```

## 架构

```
用户 → IM（企微/钉钉/飞书）→ Channel 适配器 → Agent Runtime → Tool 插件 → 外部系统
                                                    ↕
                                              LLM（Claude）
```

## 开发

```bash
git clone https://github.com/nicekate/openvort.git
cd openvort
make install
make dev
```

## 协议

Apache-2.0
