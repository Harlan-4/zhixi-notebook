"""试卷服务：试卷识别（AI）+ 纵向进步分析（纯算法，无 Key 也可用）+ 失分题入错题本。"""
from collections import defaultdict

from sqlalchemy.orm import Session

from ..models import Paper, Question
from . import ai_client
from .knowledge import compute_mastery

PAPER_STRUCT_PROMPT = """你是初高中老师。下面几张图片是某次考试的试卷（按页序）。请逐题识别，只输出一个JSON对象：
{
  "title": "考试名称（试卷上可见则填，如"高一上学期期中考试"；没有则空字符串）",
  "questions": [
    {"no": "题号（字符串）", "text": "题干要点摘要（数学式子用LaTeX）",
     "score": 该题满分数字, "knowledge_points": ["教材标准知识点"]}
  ]
}
要求：
1. 逐题完整列出、不重复、不遗漏；多张图片按页序拼接；含多个小问的解答题按整题一条，text 中标注 (1)(2) 小问。
2. 图片不清的题目 text 填"(图片不清，请手动补充)"。
3. 分值不可见时按题型常规分值，并在 text 末尾注明"(分值为推断)"。
4. knowledge_points 尽量准确（高中如"基本不等式"，初中如"因式分解"）。
输出硬性要求：第一字符必须是"{"，禁止 markdown 代码块与任何解释文字。"""

ANSWER_GRADE_PROMPT = """你是初高中老师。下面几张图片是这次考试的学生答题卡（学生作答与批改痕迹：勾/叉、每题得分数字、扣分标记）。
后面附有本次考试的题目清单（题号、满分、摘要）。请对照批改痕迹给每题判分，只输出一个JSON对象：
{
  "scores": [{"no": "题号（与清单一致）", "got_score": 学生得分数字}]
}
判分规则：
1. 勾号计满分，叉号计 0 分；多个小问分别给分的取合计；答题卡上有明确得分数字的直接采用。
2. 题号不清晰时按批改位置与题目清单的顺序对应。
3. 只输出清单里有的题号；看不清或未批改的题不要输出（宁缺勿猜）。
输出硬性要求：第一字符必须是"{"，禁止 markdown 代码块与任何解释文字。"""

WEAK_RATIO = 0.3  # 单知识点失分率超过该值记为薄弱


def _guess_question_type(text: str) -> str:
    """按题干形态粗判题型（录入后可改）。"""
    if "____" in text:
        return "填空题"
    if "（　）" in text or "（ )" in text or "(　)" in text:
        return "选择题"
    return "解答题"


def add_wrong_to_notebook(db: Session, paper: Paper, nos: list | None = None) -> tuple[list[Question], list[int]]:
    """把试卷中失分题（得分<满分）批量创建为错题，返回 (新建错题列表, 因重复跳过的题号)。

    nos 为指定题号列表；None 表示全部失分题。去重依据：来源练习册=试卷标题 且 定位=第N题。
    """
    wanted = {str(n) for n in nos} if nos is not None else None
    created: list[Question] = []
    skipped: list[int] = []
    for item in paper.questions or []:
        no = item.get("no")
        try:
            full = float(item.get("score") or 0)
            got = float(item.get("got_score") or 0)
        except (TypeError, ValueError):
            continue
        if full <= 0 or got >= full:
            continue  # 满分或数据异常的题不算失分
        if wanted is not None and str(no) not in wanted:
            continue
        exists = (
            db.query(Question)
            .filter(Question.source_workbook == paper.title)
            .filter(Question.source_location == f"第{no}题")
            .first()
        )
        if exists:
            skipped.append(no)
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        q = Question(
            subject=paper.subject or "数学",
            grade="",
            question_type=_guess_question_type(text),
            question_text=text,
            my_answer="",
            source_workbook=paper.title,
            source_location=f"第{no}题",
            status="new",
        )
        db.add(q)
        created.append(q)
    db.commit()
    return created, skipped


def recognize_paper(paper_images: list, answer_images: list) -> dict:
    """两步识别整次考试（每步只做一件事，准确率高于混合单次）：

    第一步：试卷图 -> 题目结构（题号/摘要/满分/知识点）；
    第二步：答题卡图 + 题目清单 -> 每题得分（看不清的题不输出，宁缺勿猜）。
    答题卡缺失或判分失败时返回试卷结构、得分留空待手动补填。
    """
    def _parts(items: list, label_prefix: str) -> list:
        return [
            {
                "data": img["data"],
                "mime": img.get("mime", "image/jpeg"),
                "label": f"【{label_prefix} 第{i}张】",
            }
            for i, img in enumerate(items, 1)
        ]

    draft = ai_client.vision_json_multi(PAPER_STRUCT_PROMPT, _parts(paper_images, "试卷"))
    questions = draft.get("questions") or []
    if not isinstance(questions, list):
        questions = []
    for q in questions:
        q["got_score"] = None

    if not answer_images or not questions:
        draft["questions"] = questions
        draft["grade_note"] = "未上传答题卡，得分请对照批改结果手动填写"
        return draft

    listing = "\n".join(
        f'{q.get("no")}.（满分{q.get("score")}分）{(q.get("text") or "")[:40]}'
        for q in questions
    )
    try:
        grade = ai_client.vision_json_multi(
            ANSWER_GRADE_PROMPT + "\n\n【题目清单】\n" + listing,
            _parts(answer_images, "答题卡"),
        )
    except ai_client.AIServiceError:
        draft["questions"] = questions
        draft["grade_note"] = "答题卡判分失败，得分请手动填写（试卷题目已识别）"
        return draft

    score_map: dict[str, float] = {}
    for row in grade.get("scores") or []:
        no = str(row.get("no") or "").strip()
        val = row.get("got_score")
        if no and val is not None:
            try:
                score_map[no] = float(val)
            except (TypeError, ValueError):
                continue
    for q in questions:
        g = score_map.get(str(q.get("no")))
        if g is not None:
            q["got_score"] = g
    graded = sum(1 for q in questions if q.get("got_score") is not None)
    draft["questions"] = questions
    draft["grade_note"] = f"答题卡判分：{graded}/{len(questions)} 题已自动得分，其余请手动补填"
    return draft


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
