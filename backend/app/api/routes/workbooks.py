"""练习册目录库 API：错题↔练习册定位（本作品差异化功能）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Workbook
from ...serializers import workbook_to_dict

router = APIRouter(prefix="/api/workbooks", tags=["workbooks"])


@router.get("")
def list_workbooks(db: Session = Depends(get_db)):
    items = [workbook_to_dict(w) for w in db.query(Workbook).order_by(Workbook.id).all()]
    return {"total": len(items), "items": items}


@router.post("")
def create_workbook(payload: dict, db: Session = Depends(get_db)):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "练习册名称不能为空")
    exists = db.query(Workbook).filter(Workbook.name == name).first()
    if exists:
        raise HTTPException(400, "同名练习册已存在")
    w = Workbook(
        name=name,
        publisher=payload.get("publisher") or "",
        catalog=payload.get("catalog") or [],
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return workbook_to_dict(w)


@router.delete("/{workbook_id}")
def delete_workbook(workbook_id: int, db: Session = Depends(get_db)):
    w = db.get(Workbook, workbook_id)
    if not w:
        raise HTTPException(404, "练习册不存在")
    db.delete(w)
    db.commit()
    return {"ok": True}


@router.get("/locate")
def locate(kp: str, db: Session = Depends(get_db)):
    """按知识点反查练习册章节：错题/薄弱点 -> 去练习册哪几页做哪些题。"""
    hits = []
    for w in db.query(Workbook).all():
        for entry in w.catalog or []:
            kps = entry.get("knowledge_points") or []
            if kp in kps or any(kp in k or k in kp for k in kps):
                hits.append(
                    {
                        "workbook": w.name,
                        "chapter": entry.get("chapter", ""),
                        "page": entry.get("page", ""),
                        "matched_kp": kp if kp in kps else next(k for k in kps if kp in k or k in kp),
                    }
                )
    return {"total": len(hits), "items": hits}
