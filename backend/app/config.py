"""全局配置：路径、数据库、AI 后端（OpenAI 兼容，均可通过 .env 或网页设置覆盖）。"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
UPLOAD_DIR = BACKEND_DIR / "uploads"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_url: str = f"sqlite:///{(DATA_DIR / 'zhixi.db').as_posix()}"
    ai_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    ai_api_key: str = ""
    ai_model: str = "glm-4.5v"       # 多模态模型：识题
    ai_text_model: str = "glm-4.6"   # 文本模型：解析/变式题
    ai_timeout: float = 180.0


settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_ai_config(db_settings: dict | None = None) -> dict:
    """网页设置（数据库）优先于 .env。返回统一的 AI 调用配置。"""
    db = db_settings or {}
    return {
        "base_url": db.get("ai_base_url") or settings.ai_base_url,
        "api_key": db.get("ai_api_key") or settings.ai_api_key,
        "vision_model": db.get("ai_model") or settings.ai_model,
        "text_model": db.get("ai_text_model") or settings.ai_text_model,
        "timeout": settings.ai_timeout,
    }
