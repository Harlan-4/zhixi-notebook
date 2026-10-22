"""试卷服务：试卷识别（AI）+ 纵向进步分析（纯算法，无 Key 也可用）。"""
from collections import defaultdict

from sqlalchemy.orm import Session

from ..models import Paper
from . import ai_client
from .knowledge import compute_mastery

RECOGNIZE_PROMPT = """你是初高中数学老师。请识别这张试卷图片中的所有题目，只输出一个JSON对象：
{
  "title": "试卷标题（图片中可见的考试名称，没有则空字符串）",
  "questions": [
    {"no": "题号（字符串）", "text": "题干要点摘要（数学式子用LaTeX）",
     "score": 分值数字, "knowledge_points": ["教材标准知识点"]}
  ]
}
要求：把图片里能看到的题目全部列出；图片不清的题目 text 填"(图片不清，请手动补充)"；
knowledge_points 尽量准确（高中如"基本不等式"，初中如"因式分解"）。"""

WEAK_RATIO = 0.3  # 单知识点失分率超过该值记为薄弱


def recognize_paper(image_bytes: bytes, mime: str = "image/jpeg") -> dict:
    return ai_client.vision_json(RECOGNIZE_PROMPT, image_bytes, mime)


def _weak_points(questions: list) -> list[dict]:
    agg: dict[str, dict] = defaultdict(lambda: {"lost": 0.0, "total": 0.0})
    for item in questions:
        total = float(item.get("score") or 0)
        got = float(item.get("got_score") or 0)
        lost = max(0.0, total - got)
        for kp in item.get("knowledge_points") or []:
            agg[kp]["lost"] += lost
            agg[kp]["total"] += total
    weak = []
    for kp, v in agg.items():
        if v["total"] <= 0:
            continue
        ratio = round(v["lost"] / v["total"], 3)
        weak.append(
            {
                "name": kp,
                "total_score": round(v["total"], 1),
                "lost_score": round(v["lost"], 1),
                "lost_ratio": ratio,
            }
        )
    weak.sort(key=lambda x: x["lost_score"], reverse=True)
    return weak


def analyze_paper(db: Session, paper: Paper) -> dict:
    """纵向进步分析：本次薄弱点 + 与历次考试的对比趋势 + 规则化结论。不依赖 AI。"""
    mastery = compute_mastery(db)
    weak = _weak_points(paper.questions or [])
    for w in weak:
        w["mastery"] = mastery.get(w["name"])

    # 历次考试得分率趋势
    papers = (
        db.query(Paper)
        .filter(Paper.subject == paper.subject)
        .order_by(Paper.exam_date)
        .all()
    )
    trend = {
        "dates": [p.exam_date.isoformat() for p in papers],
        "titles": [p.title for p in papers],
        "score_rates": [
            round(p.my_score / p.total_score, 3) if p.total_score else 0 for p in papers
        ],
    }

    # 薄弱知识点的纵向对比（每次考试的失分率）
    per_kp_history: dict[str, dict] = defaultdict(dict)
    for p in papers:
        for w in _weak_points(p.questions or []):
            per_kp_history[w["name"]][p.exam_date.isoformat()] = w["lost_ratio"]
    focus = [w["name"] for w in weak[:6]]
    kp_trends = [
        {"name": kp, "history": per_kp_history.get(kp, {})} for kp in focus
    ]

    # 与上一次考试的对比结论
    summary_lines = []
    idx = papers.index(paper)
    if idx > 0:
        prev = papers[idx - 1]
        rate, prev_rate = trend["score_rates"][idx], trend["score_rates"][idx - 1]
        diff = round((rate - prev_rate) * 100)
        if diff > 0:
            summary_lines.append(f"相比「{prev.title}」，得分率提升约 {diff} 个百分点，整体在进步。")
        elif diff < 0:
            summary_lines.append(f"相比「{prev.title}」，得分率下降约 {abs(diff)} 个百分点，需要关注状态波动。")
        else:
            summary_lines.append(f"与「{prev.title}」得分率持平。")
        # 知识点层面的进退步
        prev_weak = {w["name"]: w["lost_ratio"] for w in _weak_points(prev.questions or [])}
        improved, worse = [], []
        for w in weak:
            prev_r = prev_weak.get(w["name"])
            if prev_r is None:
                continue
            if prev_r - w["lost_ratio"] >= 0.15:
                improved.append(w["name"])
            elif w["lost_ratio"] - prev_r >= 0.15:
                worse.append(w["name"])
        if improved:
            summary_lines.append(f"明显进步的知识点：{'、'.join(improved)}。")
        if worse:
            summary_lines.append(f"出现退步的知识点：{'、'.join(worse)}，建议优先巩固。")
    else:
        summary_lines.append("这是第一份试卷，先建立基线，之后可对比进步趋势。")

    top_weak = [w for w in weak if w["lost_ratio"] >= WEAK_RATIO][:3]
    if top_weak:
        names = "、".join(w["name"] for w in top_weak)
        summary_lines.append(f"当前最需要突破的薄弱点：{names}。")
        summary_lines.append("建议：进入「学习计划」页，一键生成基于知识图谱前置关系的补习计划。")
    else:
        summary_lines.append("本次考试无明显薄弱知识点，保持节奏，可挑战更综合的题目。")

    analysis = {
        "weak_points": weak,
        "trend": trend,
        "kp_trends": kp_trends,
        "summary": summary_lines,
    }
    paper.analysis = analysis
    db.commit()
    return analysis
