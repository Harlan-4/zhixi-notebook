"""数据库初始化：知识图谱导入 + 演示数据（首次启动自动执行）。"""
import json
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import KnowledgePoint, Paper, Question, StudyPlan, Workbook
from ..services import paper_service
from ..services.knowledge import heuristic_ktype
from .demo_data import build_demo_papers, build_demo_questions, build_demo_workbook

GRAPH_FILE = Path(__file__).parent / "knowledge_graph.json"


def seed_graph(db: Session) -> int:
    """导入人教版初中数学知识点图谱（团队自主整理）。"""
    if db.query(KnowledgePoint).count() > 0:
        return 0
    data = json.loads(GRAPH_FILE.read_text(encoding="utf-8"))
    for p in data["points"]:
        db.add(
            KnowledgePoint(
                subject=p.get("subject", data.get("subject", "数学")),
                name=p["name"],
                grade=p["grade"],
                ktype=heuristic_ktype(p["name"]),
                chapter=p["chapter"],
                prereqs=p.get("prereqs", []),
                description=p.get("description", ""),
            )
        )
    db.commit()
    return len(data["points"])


def seed_demo(db: Session) -> None:
    """导入演示错题/试卷/练习册（已有数据时跳过）。"""
    if db.query(Question).count() > 0 or db.query(Paper).count() > 0:
        return
    for q in build_demo_questions():
        db.add(Question(**q))
    w = build_demo_workbook()
    db.add(Workbook(**w))
    for p in build_demo_papers():
        exam_date = p["exam_date"]
        if isinstance(exam_date, str):
            exam_date = date.fromisoformat(exam_date)
        db.add(
            Paper(
                title=p["title"],
                exam_date=exam_date,
                paper_type=p["paper_type"],
                subject=p["subject"],
                total_score=p["total_score"],
                my_score=p["my_score"],
                questions=p["questions"],
            )
        )
    db.commit()
    # 用与线上完全相同的分析管线生成两张试卷的纵向分析（趋势：74 -> 82）
    for paper in db.query(Paper).order_by(Paper.exam_date).all():
        paper_service.analyze_paper(db, paper)


def init_db(db: Session) -> None:
    seed_graph(db)
    seed_demo(db)


def reset_demo(db: Session) -> None:
    """清空业务数据并重新导入演示数据与知识图谱（网页设置页的"重置演示数据"）。"""
    for model in (StudyPlan, Question, Paper, Workbook, KnowledgePoint):
        db.query(model).delete()
    db.commit()
    seed_graph(db)
    seed_demo(db)
