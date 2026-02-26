"""
禅道插件配置

通过环境变量 OPENVORT_ZENTAO_* 配置禅道数据库连接。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ZentaoSettings(BaseSettings):
    """禅道数据库连接配置"""

    model_config = SettingsConfigDict(
        env_prefix="OPENVORT_ZENTAO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = ""
    port: int = 3306
    user: str = ""
    password: str = ""
    database: str = "zentao"
    charset: str = "utf8mb4"
    connect_timeout: int = 10

    def to_pymysql_kwargs(self) -> dict:
        """转换为 pymysql.connect() 参数"""
        from pymysql.cursors import DictCursor
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "charset": self.charset,
            "connect_timeout": self.connect_timeout,
            "cursorclass": DictCursor,
        }
