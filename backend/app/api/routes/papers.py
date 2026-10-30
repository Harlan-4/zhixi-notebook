"""试卷相关 API。"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Paper
from ...serializers import paper_to_dict, question_to_dict
from ...services import ai_client, paper_service

router = APIRouter(prefix="/api/papers", tags=["papers"])


def _get_paper(db: Session, paper_id: int) -> Paper:
    p = db.get(Paper, paper_id)
    if not p:
        raise HTTPException(404, "试卷不存在")
    return p


@router.get("")
def list_papers(db: Session = Depends(get_db)):
    papers = db.query(Paper).order_by(Paper.exam_date.desc()).all()
    return {"total": len(papers), "items": [paper_to_dict(p, with_analysis=False) for p in papers]}


@router.post("")
def create_paper(payload: dict, db: Session = Depends(get_db)):
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "试卷标题不能为空")
    questions = payload.get("questions") or []
    total = payload.get("total_score")
    if not total:
        total = sum(float(q.get("score") or 0) for q in questions) or 100
    exam_date = payload.get("exam_date") or date.today().isoformat()
    if isinstance(exam_date, str):
        exam_date = date.fromisoformat(exam_date)
    paper = Paper(
        title=title,
        exam_date=exam_date,
        paper_type=payload.get("paper_type") or "月考",
        subject=payload.get("subject") or "数学",
        total_score=float(total),
        my_score=float(payload.get("my_score") or 0),
        questions=questions,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return paper_to_dict(paper)


@router.get("/{paper_id}")
def get_paper(paper_id: int, db: Session = Depends(get_db)):
    return paper_to_dict(_get_paper(db, paper_id))


@router.patch("/{paper_id}")
def update_paper(paper_id: int, payload: dict, db: Session = Depends(get_db)):
    paper = _get_paper(db, paper_id)
    for f in ("title", "exam_date", "paper_type", "subject", "total_score", "my_score", "questions"):
        if f in payload:
            setattr(paper, f, payload[f])
    db.commit()
    db.refresh(paper)
    return paper_to_dict(paper)


@router.delete("/{paper_id}")
def delete_paper(paper_id: int, db: Session = Depends(get_db)):
    paper = _get_paper(db, paper_id)
    db.delete(paper)
    db.commit()
    return {"ok": True}


@router.post("/recognize")
async def recognize_paper(
    files: list[UploadFile] = File(...),
    kinds: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """AI 识别整次考试：支持试卷+答题卡多图 -> 题目与得分草稿（不入库）。

    kinds 为与 files 顺序对齐的逗号分隔类型（paper=试卷 / answer=答题卡），缺省按 paper 处理。
    """
    kind_list = [k.strip() for k in kinds.split(",") if k.strip()] if kinds else []
    paper_images: list[dict] = []
    answer_images: list[dict] = []
    for i, f in enumerate(files[:8]):  # 上限 8 张，控制单次识别成本
        data = await f.read()
        if not data:
            raise HTTPException(400, "存在空文件")
        img = {"data": data, "mime": f.content_type or "image/jpeg"}
        (answer_images if (kind_list[i] if i < len(kind_list) else "paper") == "answer" else paper_images).append(img)
    if not paper_images:
        raise HTTPException(400, "请至少上传一张试卷照片")
    try:
        draft = paper_service.recognize_paper(paper_images, answer_images)
    except ai_client.AINotConfigured as e:
        raise HTTPException(503, str(e))
    except ai_client.AIServiceError as e:
        raise HTTPException(502, str(e))
    return {"draft": draft}


@router.post("/{paper_id}/analyze")
def analyze_paper(paper_id: int, db: Session = Depends(get_db)):
    """纵向进步分析（纯算法，不依赖 AI）。"""
    paper = _get_paper(db, paper_id)
    analysis = paper_service.analyze_paper(db, paper)
    return paper_to_dict(paper) | {"analysis": analysis}


@router.post("/{paper_id}/add-wrong-to-notebook")
def add_wrong_to_notebook(paper_id: int, payload: dict | None = None, db: Session = Depends(get_db)):
    """把本卷失分题批量加入错题本（payload.nos 可指定题号，缺省为全部失分题）。"""
    paper = _get_paper(db, paper_id)
    nos = (payload or {}).get("nos")
    created, skipped = paper_service.add_wrong_to_notebook(db, paper, nos)
    return {
        "created": [question_to_dict(q) for q in created],
        "skipped_nos": skipped,
        "created_count": len(created),
    }
