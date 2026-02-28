"""VortFlow 配置"""

from pydantic_settings import BaseSettings


class VortFlowSettings(BaseSettings):
    """VortFlow 插件配置，环境变量前缀 OPENVORT_VORTFLOW_"""

    model_config = {"env_prefix": "OPENVORT_VORTFLOW_"}

    # 默认适配器: local | zentao
    adapter: str = "local"

    # 同步轮询间隔（秒），0 表示不轮询
    sync_interval: int = 300

    # SLA 检查 cron（每天早上 9 点）
    sla_check_cron: str = "0 9 * * *"

    # 逾期预警天数（提前 N 天预警）
    overdue_warn_days: int = 2
