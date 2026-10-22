"""学习计划 API：基于知识图谱前置关系的排程（本作品核心创新点）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, attributes

from ...database import get_db
from ...models import Question, StudyPlan
from ...serializers import plan_to_dict
from ...services import plan_service
from ...services.question_service import review_question

router = APIRouter(prefix="/api/plans", tags=["plans"])

_STATUS_CN = {"new": "未解析", "reviewing": "复习中", "mastered": "已掌握"}


def _get_plan(db: Session, plan_id: int) -> StudyPlan:
    p = db.get(StudyPlan, plan_id)
    if not p:
        raise HTTPException(404, "学习计划不存在")
    return p


@router.get("")
def list_plans(db: Session = Depends(get_db)):
    plans = db.query(StudyPlan).order_by(StudyPlan.created_at.desc()).all()
    return {"total": len(plans), "items": [plan_to_dict(p) for p in plans]}


@router.post("")
def create_plan(payload: dict, db: Session = Depends(get_db)):
    days = int(payload.get("days") or 7)
    plan = plan_service.generate_plan(db, days=days, title=payload.get("title") or "")
    return plan_to_dict(plan)


@router.get("/{plan_id}")
def get_plan(plan_id: int, db: Session = Depends(get_db)):
    return plan_to_dict(_get_plan(db, plan_id))


@router.get("/{plan_id}/review")
def plan_review(plan_id: int, db: Session = Depends(get_db)):
    """周复盘：计划涉及的知识点 -> 错因分布 / 掌握状态 / 任务完成度，思维导图数据。

    结构（ECharts tree 直接可用）：计划 -> 知识点 -> 三类叶子。
    """
    plan = _get_plan(db, plan_id)
    tasks = [t for day in (plan.plan_data or []) for t in (day.get("tasks") or [])]
    total = len(tasks)
    done = sum(1 for t in tasks if t.get("done"))

    kps = list(dict.fromkeys(t.get("knowledge_point") for t in tasks if t.get("knowledge_point")))
    all_questions = db.query(Question).all()
    children = []
    for kp in kps:
        kp_tasks = [t for t in tasks if t.get("knowledge_point") == kp]
        kp_done = sum(1 for t in kp_tasks if t.get("done"))

        causes: dict[str, int] = {}
        statuses: dict[str, int] = {}
        for q in all_questions:
            if kp in ((q.analysis or {}).get("knowledge_points") or []):
                c = q.error_type or "未解析"
                causes[c] = causes.get(c, 0) + 1
                statuses[q.status] = statuses.get(q.status, 0) + 1

        cause_txt = "、".join(f"{k}×{v}" for k, v in causes.items()) or "暂无关联错题"
        status_txt = "、".join(f"{_STATUS_CN.get(s, s)}×{v}" for s, v in statuses.items()) or "暂无记录"
        children.append(
            {
                "name": kp,
                "children": [
                    {"name": f"错因：{cause_txt}"},
                    {"name": f"现状：{status_txt}"},
                    {"name": f"任务完成 {kp_done}/{len(kp_tasks)}"},
                ],
            }
        )

    tree = {"name": plan.title or "学习周复盘", "children": children}
    return {"tree": tree, "task_total": total, "task_done": done, "kp_count": len(kps)}


@router.delete("/{plan_id}")
def delete_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = _get_plan(db, plan_id)
    db.delete(plan)
    db.commit()
    return {"ok": True}


@router.post("/{plan_id}/toggle")
def toggle_task(plan_id: int, payload: dict, db: Session = Depends(get_db)):
    """勾选/取消任务；勾选"错题重做/复测"时同步把相关错题记为一次复习通过。"""
    plan = _get_plan(db, plan_id)
    day_i = int(payload.get("day_index", -1))
    task_i = int(payload.get("task_index", -1))
    try:
        task = plan.plan_data[day_i]["tasks"][task_i]
    except (IndexError, KeyError, TypeError):
        raise HTTPException(400, "任务索引无效")
    task["done"] = not task.get("done", False)
    if task["done"] and task.get("question_ids"):
        for qid in task["question_ids"]:
            q = db.get(Question, qid)
            if q and q.status != "mastered":
                review_question(q, "pass")
    attributes.flag_modified(plan, "plan_data")
    db.commit()
    return plan_to_dict(plan)
