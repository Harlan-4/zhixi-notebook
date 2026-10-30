"""统计概览 + 设置 + 演示数据管理 API。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import AppSetting, Paper, Question, StudyPlan
from ...services import ai_client
from ...services.gamification import get_gamification
from ...services.knowledge import compute_mastery
from ...seed import reset_demo

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/stats/gamification")
def stats_gamification(db: Session = Depends(get_db)):
    """游戏化徽标：连续打卡天数 + 已收服题数。"""
    return get_gamification(db)


@router.get("/stats/overview")
def overview(db: Session = Depends(get_db)):
    questions = db.query(Question).all()
    mastery = compute_mastery(db)
    status_count = {"new": 0, "reviewing": 0, "mastered": 0}
    for q in questions:
        status_count[q.status] = status_count.get(q.status, 0) + 1
    papers = db.query(Paper).order_by(Paper.exam_date).all()
    plans = db.query(StudyPlan).count()
    weak = sorted(((k, v) for k, v in mastery.items() if v < 0.65), key=lambda x: x[1])
    return {
        "question_count": len(questions),
        "status_count": status_count,
        "paper_count": len(papers),
        "plan_count": plans,
        "kp_count": len(mastery),
        "weak_points": [{"name": k, "mastery": v} for k, v in weak[:8]],
        "score_trend": [
            {
                "date": p.exam_date.isoformat(),
                "title": p.title,
                "rate": round(p.my_score / p.total_score, 3) if p.total_score else 0,
            }
            for p in papers
        ],
    }


@router.get("/stats/profile")
def learner_profile(db: Session = Depends(get_db)):
    """学习者画像：错因分布 / 薄弱点 / 进步趋势 / 规则化建议（借鉴 Study-Mate 的共享记忆）。"""
    mastery = compute_mastery(db)
    questions = db.query(Question).all()
    error_dist: dict[str, int] = {}
    for q in questions:
        et = q.error_type or ("已解析" if q.analysis else "未解析")
        error_dist[et] = error_dist.get(et, 0) + 1
    total_q = sum(error_dist.values())
    error_ratio = sorted(
        (
            {"type": k, "count": v, "ratio": round(v / total_q, 3)}
            for k, v in error_dist.items()
        ),
        key=lambda x: x["count"],
        reverse=True,
    )
    weak = sorted(((k, v) for k, v in mastery.items() if v < 0.65), key=lambda x: x[1])
    strong_count = sum(1 for v in mastery.values() if v >= 0.85)
    papers = db.query(Paper).order_by(Paper.exam_date).all()
    trend = [
        {
            "date": p.exam_date.isoformat(),
            "title": p.title,
            "my_score": p.my_score,
            "total_score": p.total_score,
            "rate": round(p.my_score / p.total_score, 3) if p.total_score else 0,
        }
        for p in papers
    ]

    suggestions: list[str] = []
    if not questions:
        suggestions.append("先录入几道错题，这里会生成你的个性化画像。")
    if error_ratio and total_q >= 3 and error_ratio[0]["ratio"] >= 0.4 and error_ratio[0]["type"] != "未解析":
        suggestions.append(
            f"你的错题主要集中在“{error_ratio[0]['type']}”（约 {round(error_ratio[0]['ratio'] * 100)}%），"
            f"建议每次做题前先默念一遍该类坑点，每天固定练 3 道同类题再收工。"
        )
    if weak:
        suggestions.append(
            "当前最需要突破的知识点：" + "、".join(k for k, _ in weak[:3]) + "。可到「学习计划」页一键生成前置驱动补习计划。"
        )
    elif questions:
        suggestions.append("暂无明显薄弱知识点，保持节奏，可挑战更综合的题目。")
    if len(trend) >= 2 and trend[-1]["rate"] > trend[-2]["rate"]:
        suggestions.append(f"最近一次考试得分率比上次提升约 {round((trend[-1]['rate'] - trend[-2]['rate']) * 100)} 个百分点，进步明显，保持！")
    if strong_count:
        suggestions.append(f"已掌握 {strong_count} 个知识点（掌握度≥85%），考前翻一遍保持手感即可。")

    return {
        "question_count": len(questions),
        "error_dist": error_ratio,
        "weak_top": [{"name": k, "mastery": v} for k, v in weak[:5]],
        "strong_count": strong_count,
        "kp_tracked": len(mastery),
        "trend": trend,
        "suggestions": suggestions,
    }


_SETTING_KEYS = ("ai_base_url", "ai_api_key", "ai_model", "ai_text_model")


def _db_settings(db: Session) -> dict:
    return {s.key: s.value for s in db.query(AppSetting).all() if s.key in _SETTING_KEYS}


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    from ...config import settings as env

    db_cfg = _db_settings(db)
    key = db_cfg.get("ai_api_key") or env.ai_api_key
    return {
        "ai_base_url": db_cfg.get("ai_base_url") or env.ai_base_url,
        "ai_model": db_cfg.get("ai_model") or env.ai_model,
        "ai_text_model": db_cfg.get("ai_text_model") or env.ai_text_model,
        "api_key_set": bool(key),
        "api_key_masked": (key[:4] + "****" + key[-4:]) if len(key) > 8 else ("****" if key else ""),
        "source": "db" if db_cfg else "env",
    }


@router.put("/settings")
def put_settings(payload: dict, db: Session = Depends(get_db)):
    for k in _SETTING_KEYS:
        if k in payload and payload[k] is not None and payload[k] != "":
            row = db.get(AppSetting, k)
            if row:
                row.value = str(payload[k])
            else:
                db.add(AppSetting(key=k, value=str(payload[k])))
        elif k in payload and payload[k] == "":
            row = db.get(AppSetting, k)
            if row:
                db.delete(row)
    db.commit()
    return get_settings(db)


@router.post("/settings/test")
def test_settings(db: Session = Depends(get_db)):
    ok, message = ai_client.test_connection()
    return {"ok": ok, "message": message}


@router.post("/demo/reset")
def demo_reset(db: Session = Depends(get_db)):
    reset_demo(db)
    return {"ok": True, "message": "已重置为演示数据"}
