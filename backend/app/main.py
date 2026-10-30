"""智析错题本 API 入口。首次启动自动建库并导入知识图谱与演示数据。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from .api.routes import graph, misc, papers, plans, questions, workbooks
from .config import UPLOAD_DIR, settings
from .database import Base, SessionLocal, engine
from .seed import init_db
from .services.ai_client import AINotConfigured, AIServiceError


def ensure_schema() -> None:
    """轻量迁移：为老版本数据库补齐新增列（SQLite ALTER TABLE ADD COLUMN）。

    注意 SQLite 的 ADD COLUMN DEFAULT 不回填已有行，需补 UPDATE。
    """
    inspector = inspect(engine)
    if "knowledge_points" not in inspector.get_table_names():
        return
    kcols = {c["name"] for c in inspector.get_columns("knowledge_points")}
    qcols = (
        {c["name"] for c in inspector.get_columns("questions")}
        if "questions" in inspector.get_table_names()
        else set()
    )
    with engine.begin() as conn:
        if "subject" not in kcols:
            conn.execute(
                text("ALTER TABLE knowledge_points ADD COLUMN subject VARCHAR(16) DEFAULT '数学'")
            )
        if "ktype" not in kcols:
            conn.execute(
                text("ALTER TABLE knowledge_points ADD COLUMN ktype VARCHAR(16) DEFAULT '概念'")
            )
        conn.execute(
            text("UPDATE knowledge_points SET subject='数学' WHERE subject IS NULL OR subject=''")
        )
        # 课型启发式回填（顺序重要：综合应用优先于计算技能判定）
        conn.execute(
            text(
                "UPDATE knowledge_points SET ktype='综合应用' "
                "WHERE (ktype IS NULL OR ktype='' OR ktype='概念') AND "
                "(name LIKE '%应用%' OR name LIKE '%实际%' OR name LIKE '%综合%' OR name LIKE '%问题%')"
            )
        )
        conn.execute(
            text(
                "UPDATE knowledge_points SET ktype='计算技能' "
                "WHERE (ktype IS NULL OR ktype='' OR ktype='概念') AND "
                "(name LIKE '%运算%' OR name LIKE '%计算%' OR name LIKE '%方程%' OR name LIKE '%化简%' "
                "OR name LIKE '%分解%' OR name LIKE '%求值%' OR name LIKE '%混合%' OR name LIKE '%面积%')"
            )
        )
        # 游戏化：已掌握的题回填收服时间
        if qcols and "collected_at" not in qcols:
            conn.execute(text("ALTER TABLE questions ADD COLUMN collected_at DATE"))
            conn.execute(
                text(
                    "UPDATE questions SET collected_at=CURRENT_DATE "
                    "WHERE status='mastered' AND collected_at IS NULL"
                )
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    ensure_schema()
    db = SessionLocal()
    try:
        init_db(db)
    finally:
        db.close()
    yield


app = FastAPI(title="智析错题本 API", version="1.5.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(questions.router)
app.include_router(papers.router)
app.include_router(graph.router)
app.include_router(workbooks.router)
app.include_router(plans.router)
app.include_router(misc.router)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.exception_handler(AINotConfigured)
async def ai_not_configured_handler(request: Request, exc: AINotConfigured):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(AIServiceError)
async def ai_service_error_handler(request: Request, exc: AIServiceError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/api/health")
def health():
    return {"ok": True, "app": "智析错题本 API"}


def run():
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    run()
