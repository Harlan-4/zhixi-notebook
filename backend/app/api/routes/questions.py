"""错题相关 API。"""
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Question
from ...serializers import question_to_dict
from ...services import ai_client, gamification, question_service

router = APIRouter(prefix="/api/questions", tags=["questions"])


def _get_question(db: Session, question_id: int) -> Question:
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "错题不存在")
    return q


@router.get("")
def list_questions(
    status: str = "",
    kp: str = "",
    subject: str = "",
    grade: str = "",
    q: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(Question).order_by(Question.created_at.desc())
    if status:
        query = query.filter(Question.status == status)
    if subject:
        query = query.filter(Question.subject == subject)
    if grade:
        query = query.filter(Question.grade == grade)
    items = [question_to_dict(x) for x in query.all()]
    if kp:
        items = [x for x in items if x["analysis"] and kp in (x["analysis"].get("knowledge_points") or [])]
    if q:
        items = [x for x in items if q in x["question_text"] or q in x["source_workbook"]]
    return {"total": len(items), "items": items}


@router.post("")
def create_question(payload: dict, db: Session = Depends(get_db)):
    text = (payload.get("question_text") or "").strip()
    if not text:
        raise HTTPException(400, "题目内容不能为空")
    question = Question(
        subject=payload.get("subject") or "数学",
        grade=payload.get("grade") or "",
        question_type=payload.get("question_type") or "解答题",
        question_text=text,
        my_answer=payload.get("my_answer") or "",
        image_path=payload.get("image_path") or "",
        source_workbook=payload.get("source_workbook") or "",
        source_location=payload.get("source_location") or "",
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question_to_dict(question)


@router.get("/{question_id}")
def get_question(question_id: int, db: Session = Depends(get_db)):
    return question_to_dict(_get_question(db, question_id))


@router.patch("/{question_id}")
def update_question(question_id: int, payload: dict, db: Session = Depends(get_db)):
    question = _get_question(db, question_id)
    fields = [
        "subject", "grade", "question_type", "question_text", "my_answer",
        "source_workbook", "source_location", "status", "error_type",
    ]
    for f in fields:
        if f in payload:
            setattr(question, f, payload[f])
    if "analysis" in payload:
        question.analysis = payload["analysis"]
    db.commit()
    db.refresh(question)
    return question_to_dict(question)


@router.delete("/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db)):
    question = _get_question(db, question_id)
    db.delete(question)
    db.commit()
    return {"ok": True}


@router.post("/upload")
async def upload_image(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """通用图片上传（错题拍照/试卷照片）。"""
    from ...config import UPLOAD_DIR

    ext = (file.filename or "img.jpg").rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp", "bmp"):
        ext = "jpg"
    name = f"{uuid.uuid4().hex}.{ext}"
    data = await file.read()
    if not data:
        raise HTTPException(400, "空文件")
    (UPLOAD_DIR / name).write_bytes(data)
    return {"image_path": name, "image_url": f"/uploads/{name}"}


@router.post("/recognize")
async def recognize_question(
    file: UploadFile = File(...),
    mime: str = Form(default="image/jpeg"),
    db: Session = Depends(get_db),
):
    """AI 识题：图片 -> 题目草稿（不入库）。"""
    data = await file.read()
    if not data:
        raise HTTPException(400, "空文件")
    try:
        draft = question_service.recognize_question(data, mime)
    except ai_client.AINotConfigured as e:
        raise HTTPException(503, str(e))
    except ai_client.AIServiceError as e:
        raise HTTPException(502, str(e))
    return {"draft": draft}


@router.post("/{question_id}/analyze")
def analyze_question(question_id: int, db: Session = Depends(get_db)):
    """AI 解析：正确解法 + 错因 + 知识点 + 教材章节定位。"""
    question = _get_question(db, question_id)
    try:
        question_service.analyze_question(db, question)
    except ai_client.AINotConfigured as e:
        raise HTTPException(503, str(e))
    except ai_client.AIServiceError as e:
        raise HTTPException(502, str(e))
    return question_to_dict(question)


@router.post("/{question_id}/variants")
def generate_variants(question_id: int, db: Session = Depends(get_db)):
    """举一反三：生成变式题。"""
    question = _get_question(db, question_id)
    try:
        question_service.generate_variants(db, question)
    except ai_client.AINotConfigured as e:
        raise HTTPException(503, str(e))
    except ai_client.AIServiceError as e:
        raise HTTPException(502, str(e))
    return question_to_dict(question)


@router.post("/{question_id}/reexplain")
def reexplain_question(question_id: int, payload: dict | None = None, db: Session = Depends(get_db)):
    """换种讲法：学生对原解析"没听懂"时，AI 换策略重讲（借鉴 Study-Mate）。"""
    question = _get_question(db, question_id)
    if not question.analysis:
        raise HTTPException(400, "请先进行 AI 解析，再切换讲法")
    try:
        question_service.reexplain_question(db, question, (payload or {}).get("style") or "")
    except ai_client.AINotConfigured as e:
        raise HTTPException(503, str(e))
    except ai_client.AIServiceError as e:
        raise HTTPException(502, str(e))
    return question_to_dict(question)


@router.post("/{question_id}/check-answer")
def check_answer(question_id: int, payload: dict, db: Session = Depends(get_db)):
    """答案核验：学生提交重做答案，AI 判定对错（按证据核验，借鉴 Study-Mate）。"""
    question = _get_question(db, question_id)
    if not question.analysis or not (question.analysis.get("correct_answer") or "").strip():
        raise HTTPException(400, "请先进行 AI 解析（需要参考答案才能批改）")
    answer = (payload or {}).get("answer", "").strip()
    if not answer:
        raise HTTPException(400, "请先填写你的答案")
    try:
        result = question_service.check_answer(question, answer)
    except ai_client.AINotConfigured as e:
        raise HTTPException(503, str(e))
    except ai_client.AIServiceError as e:
        raise HTTPException(502, str(e))
    return result


@router.post("/{question_id}/qa-chat")
def qa_chat(question_id: int, payload: dict, db: Session = Depends(get_db)):
    """讲解答疑对话：学生就本题解析中没看懂的地方向 AI 提问。"""
    question = _get_question(db, question_id)
    try:
        result = question_service.qa_chat_question(db, question, (payload or {}).get("message", ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except ai_client.AINotConfigured as e:
        raise HTTPException(503, str(e))
    except ai_client.AIServiceError as e:
        raise HTTPException(502, str(e))
    return result


@router.post("/{question_id}/diagnose-chat")
def diagnose_chat(question_id: int, payload: dict, db: Session = Depends(get_db)):
    """错因追问对话：学生回答诊断追问，AI 收集证据，证据足够时确认错因并回写。"""
    question = _get_question(db, question_id)
    try:
        result = question_service.diagnose_chat_question(db, question, (payload or {}).get("message", ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except ai_client.AINotConfigured as e:
        raise HTTPException(503, str(e))
    except ai_client.AIServiceError as e:
        raise HTTPException(502, str(e))
    return result


@router.post("/{question_id}/review")
def review_question(question_id: int, payload: dict, db: Session = Depends(get_db)):
    """复习打卡：result = pass / fail，按艾宾浩斯间隔推进；pass 返回鼓励语，fail 返回共情语。"""
    question = _get_question(db, question_id)
    try:
        just_collected = question_service.review_question(question, payload.get("result", ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    db.commit()
    db.refresh(question)
    streak = gamification.record_review(db)
    db.commit()
    passed = payload.get("result") == "pass"
    return {
        "question": question_to_dict(question),
        "praise": gamification.praise_for(question) if passed else "",
        "streak": streak,
        "just_collected": just_collected,
    }
