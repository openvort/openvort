---
name: openvort-official-docs
description: 更新 OpenVort 官网文档。文档存储在 PostgreSQL 数据库中，通过 psql 直接操作。涉及官网文档新增、编辑、查看时使用。
---

# OpenVort 官网文档维护

## 架构概要

官网项目路径：`/Users/yangqiang/Work/Projects/openvort/openvort-official`

文档存储在 **PostgreSQL 数据库**中，不是 markdown 文件。`content/docs/` 目录为遗留文件，不是文档数据源。

前端使用 TipTap 编辑器，内容以 Markdown 格式存储在 `doc_pages.content` 字段中（包含 HTML 实体如 `&gt;`、`<img>` 标签等）。

## 数据库连接

从 `.env` 文件读取连接信息（**每次操作前必须先读取，不要硬编码**）：

```bash
cat /Users/yangqiang/Work/Projects/openvort/openvort-official/.env
```

连接示例：

```bash
PGPASSWORD='<password>' psql -h <host> -U <user> -d <dbname>
```

## 数据库表结构

```
doc_categories (文档分类)
├── id          uuid PK
├── slug        varchar(128) UNIQUE  -- 如 "guide"
├── title       varchar(128)
├── sort_order  integer
└── timestamps

doc_sections (侧边栏分组，归属某分类)
├── id           uuid PK
├── category_id  uuid FK -> doc_categories.id
├── title        varchar(128)
├── sort_order   integer
└── timestamps

doc_pages (文档页面)
├── id          uuid PK
├── section_id  uuid FK -> doc_sections.id
├── slug        varchar(256) UNIQUE  -- 格式: "category-slug/page-slug"，如 "guide/channels-feishu"
├── title       varchar(256)
├── description text
├── content     text          -- Markdown 正文
├── sort_order  integer
├── author_id   uuid FK -> users.id
├── status      varchar(16)   -- "published" / "draft"
└── timestamps
```

## 常用操作

### 查看文档内容

```bash
# 通过 API 查看（推荐，可验证前端展示效果）
curl -s http://192.168.5.201:3001/api/docs/pages/<slug> | python3 -c "import sys,json; d=json.load(sys.stdin); print('id:', d['id']); print('title:', d['title']); print(d['content'])"

# 通过 psql 查看
PGPASSWORD='<pwd>' psql -h <host> -U <user> -d <db> -t -A -c "SELECT content FROM doc_pages WHERE slug = '<slug>';"
```

### 更新文档内容

1. 先获取当前内容，保存到临时文件备份
2. 编写新内容到 `/tmp/doc_new.txt`
3. 用 Python 脚本执行 SQL 更新（自动处理单引号转义）：

```python
python3 -c "
import subprocess, os

with open('/tmp/doc_new.txt', 'r') as f:
    content = f.read().rstrip('\n')

escaped = content.replace(\"'\", \"''\")
sql = f\"UPDATE doc_pages SET content = '{escaped}', updated_at = NOW() WHERE slug = '<slug>' RETURNING id, length(content) as content_len;\"

result = subprocess.run(
    ['psql', '-h', '<host>', '-U', '<user>', '-d', '<db>', '-c', sql],
    env={**os.environ, 'PGPASSWORD': '<pwd>'},
    capture_output=True, text=True
)
print(result.stdout)
if result.stderr:
    print('STDERR:', result.stderr)
"
```

4. 更新后通过 API 验证内容

### 新增文档页面

```sql
-- 先查询目标 section 的 ID
SELECT s.id, s.title, c.slug as category_slug
FROM doc_sections s
JOIN doc_categories c ON s.category_id = c.id
WHERE c.slug = '<category-slug>';

-- 插入新页面（slug 格式必须为 "category-slug/page-slug"）
INSERT INTO doc_pages (section_id, slug, title, description, content, sort_order, status)
VALUES ('<section-id>', '<category-slug>/<page-slug>', '<标题>', '<描述>', '<content>', <order>, 'published')
RETURNING id, slug;
```

### 查看文档导航结构

```sql
SELECT c.slug as category, s.title as section, p.slug, p.title, p.sort_order
FROM doc_pages p
JOIN doc_sections s ON p.section_id = s.id
JOIN doc_categories c ON s.category_id = c.id
ORDER BY c.sort_order, s.sort_order, p.sort_order;
```

## 注意事项

- 内容格式：Markdown，但表格和部分元素可能以 TipTap 编辑器的格式存储（表格为纯文本拼接、箭头为 `&gt;`、图片可能用 `<img>` 标签）
- slug 规则：全局唯一，格式为 `category-slug/page-slug`（如 `guide/channels-feishu`）
- 更新后无需重启服务，刷新页面即可看到新内容
- 官网地址：`http://192.168.5.201:3001`（开发环境）
- 每次操作前从 `.env` 读取数据库凭证，不要硬编码密码
