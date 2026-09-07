## Purpose

定义每项目平台系统用户凭据在 OpenVort 中的存储与下发：只覆盖 `HCM_BASE_URL / HCM_USERNAME / HCM_PASSWORD` 三项，通用凭据（Jira / GitLab / CodeBuddy / ocx）不在本能力范围、保持宿主只读文件现状。

## ADDED Requirements

### Requirement: 凭据加密存储、脱敏读出
项目配置 MUST 提供平台地址、系统用户名、密码三个字段；密码 MUST 加密落库；读取接口 MUST 只返回脱敏形式（末 4 位），MUST NOT 返回明文。

#### Scenario: 读取项目配置
- WHEN 管理员读取项目配置
- THEN 密码字段 MUST 显示为 `****` 加末 4 位

#### Scenario: 更新时未改密码
- WHEN 保存的密码字段以 `****` 开头
- THEN MUST 视为未修改，保留原值

### Requirement: 派发前写入仓内 .env，只改三行
每次派发前 MUST 把三项写入项目仓 `03_config/.env`：只替换 `HCM_BASE_URL` / `HCM_USERNAME` / `HCM_PASSWORD` 三行，其余行（含 `HCM_TOKEN`）MUST 原样保留；文件不存在时 MUST 创建并只含这三行；写入 MUST 经 master 以 stdin 传递内容，MUST NOT 经环境变量或命令行参数；结果文件权限 MUST 为 0600。

#### Scenario: token 行保留
- WHEN `.env` 里已有 hcmo 刷新过的 `HCM_TOKEN=…`
- THEN 写入后该行 MUST 逐字不变

#### Scenario: 内容相同不写
- WHEN 三行现有值与 OpenVort 中一致
- THEN MUST 不写文件、不改 mtime

#### Scenario: 内容不同覆盖并留痕
- WHEN 三行中任一与 OpenVort 不一致
- THEN MUST 覆盖并记录一条日志（项目、变更的键名，不含值）

### Requirement: 凭据缺失时不派发
项目三项凭据任一为空时 MUST 拒绝派发并说明缺项；同步与查询不受影响。

#### Scenario: 缺密码
- WHEN 项目未填系统用户密码
- THEN 立即派发与定时派发都 MUST 对该项目返回「凭据缺项：HCM_PASSWORD」
