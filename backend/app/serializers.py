"""ORM 对象 -> API 字典 的统一序列化。"""


def question_to_dict(q) -> dict:
    return {
        "id": q.id,
        "subject": q.subject,
        "grade": q.grade,
        "question_type": q.question_type,
        "question_text": q.question_text,
        "my_answer": q.my_answer,
        "image_url": f"/uploads/{q.image_path}" if q.image_path else "",
        "source_workbook": q.source_workbook,
        "source_location": q.source_location,
        "status": q.status,
        "error_type": q.error_type,
        "analysis": q.analysis,
        "variants": q.variants,
        "review_count": q.review_count,
        "review_stage": q.review_stage,
        "last_result": q.last_result,
        "next_review_at": q.next_review_at.isoformat() if q.next_review_at else None,
        "collected_at": q.collected_at.isoformat() if q.collected_at else None,
        "created_at": q.created_at.isoformat() if q.created_at else None,
    }


def paper_to_dict(p, with_analysis: bool = True) -> dict:
    data = {
        "id": p.id,
        "title": p.title,
        "exam_date": p.exam_date.isoformat() if p.exam_date else None,
        "paper_type": p.paper_type,
        "subject": p.subject,
        "total_score": p.total_score,
        "my_score": p.my_score,
        "questions": p.questions or [],
    }
    if with_analysis:
        data["analysis"] = p.analysis
    return data


def workbook_to_dict(w) -> dict:
    return {
        "id": w.id,
        "name": w.name,
        "publisher": w.publisher,
        "catalog": w.catalog or [],
    }


def plan_to_dict(plan) -> dict:
    return {
        "id": plan.id,
        "title": plan.title,
        "start_date": plan.start_date.isoformat() if plan.start_date else None,
        "days": plan.days,
        "plan_data": plan.plan_data or [],
        "status": plan.status,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }
