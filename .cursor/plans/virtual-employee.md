---
name: 虚拟员工功能实现计划
description: 实现虚拟员工 + 考勤模块
todos:
  - id: data_model
    content: 数据模型：Member 扩展 + 考勤表 + 汇报表
  - id: attendance_module
    content: 实现考勤模块 attendance/
  - id: virtual_employee_module
    content: 实现虚拟员工模块 virtual_employee/
  - id: skill_templates
    content: 创建预置角色模板 Skills
  - id: frontend_attendance
    content: 前端考勤管理页面
  - id: frontend_virtual_employee
    content: 前端虚拟员工管理页面
---

# 虚拟员工功能实现计划

## 架构设计

采用两个模块分离设计：

```
src/openvort/
├── contacts/              # 通讯录（已有）
│   └── models.py         # Member 表扩展：is_virtual, virtual_role, virtual_system_prompt
├── attendance/           # 考勤模块（新建）- 真实+虚拟员工共用
│   ├── models.py         # Attendance 打卡记录, Report 工作汇报
│   ├── service.py
│   ├── plugin.py         # AI Tools：打卡、提交汇报
│   └── router.py        # API
└── virtual_employee/    # 虚拟员工扩展（新建）
    ├── models.py         # 虚拟员工扩展配置
    ├── service.py
    ├── plugin.py         # AI Tools：虚拟员工特有
    ├── templates/        # 角色模板 Skills
    │   ├── developer.md
    │   ├── designer.md
    │   ├── pm.md
    │   └── qa.md
    └── router.py         # API
```

## 数据模型设计

### 1. Member 表扩展

在 `contacts/models.py` 的 Member 表增加字段：

```python
is_virtual: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否虚拟员工
virtual_role: Mapped[str] = mapped_column(String(32), default="")  # 角色模板标识
virtual_system_prompt: Mapped[str] = mapped_column(Text, default="")  # AI 角色设定
skills: Mapped[str] = mapped_column(Text, default="[]")  # 技能 ID 列表 JSON
work_schedule: Mapped[str] = mapped_column(Text, default="{}")  # 工时配置 JSON
auto_report: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否自动汇报
report_frequency: Mapped[str] = mapped_column(String(16), default="daily")  # 汇报频率
```

### 2. 考勤表 attendance/

新建 `src/openvort/attendance/models.py`：

```python
class Attendance(Base):
    """打卡记录 - 真实+虚拟员工共用"""
    __tablename__ = "attendances"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    check_in: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    check_in_location: Mapped[str] = mapped_column(String(256), default="")  # 打卡位置
    check_out: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    check_out_location: Mapped[str] = mapped_column(String(256), default="")
    work_duration: Mapped[int] = mapped_column(Integer, default=0)  # 工作时长（分钟）
    overtime: Mapped[int] = mapped_column(Integer, default=0)  # 加班时长（分钟）
    status: Mapped[str] = mapped_column(String(16), default="normal")  # normal/late/earlyleave/absent
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class WorkReport(Base):
    """工作汇报 - 真实+虚拟员工共用"""
    __tablename__ = "work_reports"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    content: Mapped[str] = mapped_column(Text, default="")  # 汇报内容
    tasks: Mapped[str] = mapped_column(Text, default="[]")  # 任务列表 JSON
    attachments: Mapped[str] = mapped_column(Text, default="[]")  # 附件 JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

### 3. 虚拟员工扩展表 virtual_employee/

新建 `src/openvort/virtual_employee/models.py`：

```python
class VirtualEmployeeConfig(Base):
    """虚拟员工扩展配置"""
    __tablename__ = "virtual_employee_configs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), unique=True)
    template_id: Mapped[str] = mapped_column(String(32), default="")  # 模板 ID
    personality: Mapped[str] = mapped_column(Text, default="{}")  # 个性化配置
    manager_id: Mapped[str] = mapped_column(String(32), default="")  # 所属主管（真实员工）
    status: Mapped[str] = mapped_column(String(16), default="active")  # active/inactive/vacation
    hire_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

## 模块功能

### 1. 考勤模块 attendance/

**AI Tools（plugin.py）：**
- `attendance_checkin` - 上班打卡
- `attendance_checkout` - 下班打卡
- `attendance_query` - 查询考勤记录
- `attendance_submit_report` - 提交工作汇报
- `attendance_query_reports` - 查询汇报历史

**API（router.py）：**
- `POST /api/attendance/checkin` - 打卡
- `POST /api/attendance/report` - 提交汇报
- `GET /api/attendance/records` - 考勤记录列表
- `GET /api/attendance/reports` - 汇报列表
- `GET /api/attendance/stats` - 考勤统计

### 2. 虚拟员工模块 virtual_employee/

**预置角色模板：**

| 模板 ID | 名称 | 描述 |
|---------|------|------|
| developer | 开发工程师 | 擅长代码开发、代码审查 |
| designer | 设计师 | UI/UX 设计 |
| pm | 产品经理 | 需求分析、产品规划 |
| qa | 测试工程师 | 测试用例、缺陷管理 |
| assistant | 通用助手 | 日常办公辅助 |

**AI Tools（plugin.py）：**
- `virtual_employee_create` - 创建虚拟员工
- `virtual_employee_update` - 更新虚拟员工
- `virtual_employee_assign_task` - 指派任务
- `virtual_employee_report_progress` - 汇报进度
- `virtual_employee_daily_summary` - 生成日报

**API（router.py）：**
- `POST /api/virtual-employees` - 创建虚拟员工
- `GET /api/virtual-employees` - 列表
- `GET /api/virtual-employees/{id}` - 详情
- `PUT /api/virtual-employees/{id}` - 更新
- `DELETE /api/virtual-employees/{id}` - 删除
- `GET /api/virtual-employees/templates` - 获取角色模板
- `POST /api/virtual-employees/{id}/tasks` - 指派任务

### 3. Agent 集成

对话时识别虚拟员工身份：
1. 用户发送消息给虚拟员工
2. 系统通过 member_id 加载虚拟员工配置
3. 拼接 system_prompt + skills 注入到 Agent
4. Agent 以第一人称响应

## 前端页面

### 1. 考勤入口

在现有导航或侧边栏增加"考勤"入口：
- 打卡功能
- 考勤记录
- 提交汇报

### 2. 虚拟员工管理

新建 `web/src/views/virtual-employee/`：
- `Index.vue` - 虚拟员工列表
- `Detail.vue` - 详情/编辑

### 3. 通讯录集成

修改 `web/src/views/contacts/Index.vue`：
- 新增成员时增加"虚拟员工"类型选择
- 选择后引导选择角色模板和技能
- 成员列表显示"虚拟"标签

## 实施顺序

1. **数据模型** - Member 扩展 + 考勤表 + 汇报表 + 虚拟员工配置表
2. **考勤模块** - service + plugin + router
3. **虚拟员工模块** - service + plugin + router
4. **角色模板** - 创建 5 个预置模板
5. **前端考勤页面**
6. **前端虚拟员工页面**
7. **通讯录集成**
