"""AI 客户端：OpenAI 兼容协议，多后端可配置（智谱/Qwen/DeepSeek/本地 Ollama 等）。

网页「设置」页的配置存于 AppSetting 表，优先于 .env；未配置 Key 时所有 AI 端点
返回 503，应用其余功能（浏览/试卷统计/学习计划）不依赖 AI，可正常演示。
"""
import base64
import json
import re

from openai import OpenAI

from ..config import get_ai_config
from ..database import SessionLocal
from ..models import AppSetting


class AINotConfigured(Exception):
    """未配置 API Key。"""


class AIServiceError(Exception):
    """调用失败或输出不符合约定格式。"""


def load_db_settings() -> dict:
    db = SessionLocal()
    try:
        return {s.key: s.value for s in db.query(AppSetting).all()}
    finally:
        db.close()


def get_config() -> dict:
    return get_ai_config(load_db_settings())


def image_data_url(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64," + base64.b64encode(image_bytes).decode()


def extract_json(text: str):
    """从模型输出中稳健地提取 JSON 对象（容忍 markdown 代码块与多余说明文字）。"""
    if not text:
        return None
    candidates = []
    m = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if m:
        candidates.append(m.group(1))
    candidates.append(text)
    for c in candidates:
        try:
            return json.loads(c.strip())
        except (json.JSONDecodeError, ValueError):
            pass
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except (json.JSONDecodeError, ValueError):
                        return None
    return None


def chat_json(messages: list, model: str | None = None, temperature: float = 0.3) -> dict:
    cfg = get_config()
    if not cfg["api_key"]:
        raise AINotConfigured(
            "尚未配置 AI 服务：请在网页「设置」页填写 API Key（OpenAI 兼容接口），或编辑 backend/.env"
        )
    client = OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"], timeout=cfg["timeout"])
    use_model = model or cfg["text_model"]
    msgs = list(messages)
    last_text = ""
    for _ in range(2):  # 首次输出非 JSON 时给一次纠正机会
        try:
            resp = client.chat.completions.create(model=use_model, messages=msgs, temperature=temperature)
        except Exception as e:  # noqa: BLE001 — 网络/鉴权等上游错误统一转成可读信息
            raise AIServiceError(f"AI 调用失败：{type(e).__name__}: {e}") from e
        last_text = resp.choices[0].message.content or ""
        data = extract_json(last_text)
        if data is not None:
            return data
        msgs = msgs + [
            {"role": "assistant", "content": last_text},
            {"role": "user", "content": "以上输出不是合法的JSON。请重新输出：只输出一个JSON对象，不要任何解释文字，不要markdown代码块。"},
        ]
    raise AIServiceError("AI 未返回有效的 JSON，请重试或更换模型")


def vision_json(prompt: str, image_bytes: bytes, mime: str = "image/jpeg") -> dict:
    cfg = get_config()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data_url(image_bytes, mime)}},
            ],
        }
    ]
    return chat_json(messages, model=cfg["vision_model"])


def test_connection() -> tuple[bool, str]:
    try:
        cfg = get_config()
        if not cfg["api_key"]:
            return False, "未配置 API Key"
        data = chat_json(
            [{"role": "user", "content": '回复一个JSON对象：{"ok": true, "model": "你的模型名"}'}],
            temperature=0.0,
        )
        return True, f"连接成功，模型返回：{json.dumps(data, ensure_ascii=False)[:120]}"
    except AINotConfigured as e:
        return False, str(e)
    except Exception as e:  # noqa: BLE001 — 把任何上游错误转成可读信息
        return False, f"连接失败：{e}"
