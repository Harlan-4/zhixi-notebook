"""知识图谱 API：图谱数据（ECharts）、知识点详情、掌握度着色、数据校验、AI 讲解。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import KnowledgePoint, Question
from ...serializers import question_to_dict
from ...services import ai_client
from ...services.knowledge import compute_mastery, graph_issues, point_map

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/knowledge-points")
def knowledge_points(subject: str = "", grade: str = "", db: Session = Depends(get_db)):
    mastery = compute_mastery(db)
    query = db.query(KnowledgePoint)
    if subject:
        query = query.filter(KnowledgePoint.subject == subject)
    if grade:
        query = query.filter(KnowledgePoint.grade == grade)
    points = query.all()
    items = [
        {
            "name": p.name,
            "subject": p.subject,
            "grade": p.grade,
            "ktype": p.ktype,
            "chapter": p.chapter,
            "prereqs": p.prereqs,
            "description": p.description,
            "mastery": mastery.get(p.name),
        }
        for p in points
    ]
    items.sort(key=lambda x: (x["grade"], x["chapter"]))
    return {"total": len(items), "items": items}


@router.get("/knowledge-points/{name}")
def knowledge_point_detail(name: str, db: Session = Depends(get_db)):
    pmap = point_map(db)
    if name not in pmap:
        raise HTTPException(404, "知识点不存在")
    p = pmap[name]
    mastery = compute_mastery(db)
    related = [
        question_to_dict(q)
        for q in db.query(Question).order_by(Question.created_at.desc()).all()
        if q.analysis and name in (q.analysis.get("knowledge_points") or [])
    ]
    return {
        "name": p.name,
        "subject": p.subject,
        "grade": p.grade,
        "ktype": p.ktype,
        "chapter": p.chapter,
        "prereqs": p.prereqs,
        "description": p.description,
        "mastery": mastery.get(p.name),
        "related_questions": related,
    }


@router.get("/graph")
def graph(subject: str = "", grade: str = "", db: Session = Depends(get_db)):
    """ECharts 力导向图数据；节点按掌握度着色（前端处理）。

    支持按科目/年级过滤；前置边只保留两端都在过滤结果内的（跨年级边剪枝）。
    """
    mastery = compute_mastery(db)
    query = db.query(KnowledgePoint)
    if subject:
        query = query.filter(KnowledgePoint.subject == subject)
    if grade:
        query = query.filter(KnowledgePoint.grade == grade)
    points = query.all()
    nodes = [
        {
            "id": str(p.id),
            "name": p.name,
            "subject": p.subject,
            "grade": p.grade,
            "ktype": p.ktype,
            "chapter": p.chapter,
            "mastery": mastery.get(p.name),
            "symbolSize": 14 + 22 * max(0.0, 1 - (mastery.get(p.name) or 1.0)),
        }
        for p in points
    ]
    id_by_name = {p.name: str(p.id) for p in points}
    edges = []
    for p in points:
        for pre in p.prereqs or []:
            if pre in id_by_name:
                edges.append({"source": id_by_name[pre], "target": id_by_name[p.name]})
    return {"nodes": nodes, "edges": edges, "mastery": mastery}


@router.get("/graph/validate")
def validate_graph(db: Session = Depends(get_db)):
    """知识图谱数据完整性校验：名称唯一、章节非空、前置引用存在、无环（借鉴 Study-Mate）。"""
    issues = graph_issues(db)
    return {"ok": not issues, "issues": issues, "checked": db.query(KnowledgePoint).count()}


@router.get("/knowledge-points/{name}/lesson")
def knowledge_point_lesson(name: str, db: Session = Depends(get_db)):
    """AI 讲解知识点：生成迷你微课卡（导语/核心/易错点/自测题/答案）。"""
    pmap = point_map(db)
    if name not in pmap:
        raise HTTPException(404, "知识点不存在")
    p = pmap[name]
    prereq_txt = "、".join(p.prereqs or []) or "无（起点知识点）"
    user = (
        f"知识点：{name}\n教材位置：{p.chapter}\n年级：{p.grade}\n课型：{p.ktype}\n前置知识：{prereq_txt}"
    )
    prompt = (
        "你是一名初高中数学老师。请为下面的知识点生成一张迷你微课卡，只输出一个JSON对象：\n"
        '{\n'
        '  "hook": "导语：这个知识点解决什么问题、用在哪里（1-2句）",\n'
        '  "core": "核心内容：定义/公式/定理讲清楚，带1道例题及分步解答（LaTeX行内公式用$...$）",\n'
        '  "pitfalls": "易错点提醒（1-2条）",\n'
        '  "check": "1道自测题（不含答案）",\n'
        '  "answer": "自测题答案与简要解答"\n'
        '}\n'
        "面向该年级学生，语言亲切，core 部分不超过400字。"
    )
    data = ai_client.chat_json([{"role": "user", "content": prompt + "\n\n" + user}])
    return {"name": name, "lesson": data}
