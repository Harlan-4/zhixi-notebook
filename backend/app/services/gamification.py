"""游戏化激励：复习打卡的鼓励语与连续打卡天数。

纯规则实现（模板池 + AppSetting 计数），不依赖 AI，离线可用。
"""
import json
import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..models import AppSetting, Question

_GAMIFICATION_KEY = "gamification"

# 通过复习时的鼓励语（{kp} 为知识点名，无知识点时用 PLAIN 池）
PRAISE_WITH_KP = [
    "「{kp}」被你彻底拿下了，这个坑再也拦不住你！",
    "又收服一只错题怪兽，「{kp}」从此写进你的武器库。",
    "漂亮！「{kp}」三连过，遗忘曲线都追不上你。",
    "「{kp}」正式毕业，下次考试遇到它就是送分题。",
    "稳！「{kp}」已经刻进肌肉记忆，保持这个节奏。",
    "「{kp}」点亮成功！你的知识图谱又亮了一块。",
]
PRAISE_PLAIN = [
    "这道题被你彻底拿下了，这个坑再也拦不住你！",
    "又收服一只错题怪兽，它已经进你的武器库了。",
    "漂亮！三次复习全过，遗忘曲线都追不上你。",
    "这题正式毕业，下次考试遇到它就是送分题。",
    "稳！已经刻进肌肉记忆，保持这个节奏。",
    "又一块知识拼图点亮了，你的图谱越来越完整。",
]


def praise_for(q: Question) -> str:
    """按题目的知识点随机挑一条鼓励语。"""
    kps = []
    if isinstance(q.analysis, dict):
        kps = [k for k in (q.analysis.get("knowledge_points") or []) if isinstance(k, str) and k]
    tpl = random.choice(PRAISE_WITH_KP if kps else PRAISE_PLAIN)
    return tpl.format(kp=kps[0]) if kps else tpl


def _load_state(db: Session) -> dict:
    row = db.get(AppSetting, _GAMIFICATION_KEY)
    if not row or not row.value:
        return {"streak": 0, "last_review_date": None}
    try:
        state = json.loads(row.value)
        if not isinstance(state, dict):
            raise ValueError
        state.setdefault("streak", 0)
        state.setdefault("last_review_date", None)
        return state
    except (ValueError, TypeError):
        return {"streak": 0, "last_review_date": None}


def record_review(db: Session) -> int:
    """记一次复习打卡，维护连续天数（昨天打过→+1；今天已打→不变；否则→1）。返回当前 streak。"""
    state = _load_state(db)
    today = date.today()
    last = state.get("last_review_date")
    try:
        last_date = date.fromisoformat(last) if isinstance(last, str) and last else None
    except ValueError:
        last_date = None
    if last_date == today:
        streak = int(state["streak"]) or 1
    elif last_date == today - timedelta(days=1):
        streak = int(state["streak"]) + 1
    else:
        streak = 1
    db.merge(
        AppSetting(
            key=_GAMIFICATION_KEY,
            value=json.dumps({"streak": streak, "last_review_date": today.isoformat()}, ensure_ascii=False),
        )
    )
    return streak


def get_gamification(db: Session) -> dict:
    """顶栏徽标数据：连续打卡天数 + 已收服题数。"""
    state = _load_state(db)
    # 超过一天没打卡，展示时归零（今天还没打不计昨天之前的中断）
    last = state.get("last_review_date")
    try:
        last_date = date.fromisoformat(last) if isinstance(last, str) and last else None
    except ValueError:
        last_date = None
    streak = int(state["streak"]) if last_date and last_date >= date.today() - timedelta(days=1) else 0
    collected = db.query(Question).filter(Question.collected_at.isnot(None)).count()
    return {"streak": streak, "collected_count": collected}
