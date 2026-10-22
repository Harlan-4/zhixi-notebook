"""冒烟测试：不依赖 AI Key，覆盖数据模型、图谱、试卷分析、学习计划排程与设置。"""
import os
import tempfile
from pathlib import Path

os.environ.setdefault("AI_API_KEY", "")  # 确保测试环境无 Key，AI 端点应返回 503

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

import app.services.ai_client as ai_client_module
from app.config import settings
from app.database import get_db
from app.main import app
from app.seed import init_db


@pytest.fixture()
def client():
    with tempfile.TemporaryDirectory() as tmp:
        test_url = f"sqlite:///{(Path(tmp) / 'test.db').as_posix()}"
        orig_url = settings.db_url
        settings.db_url = test_url

        engine = sa.create_engine(test_url, connect_args={"check_same_thread": False})
        from app.database import Base

        Base.metadata.create_all(engine)
        TestingSession = sa.orm.sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

        db = TestingSession()
        init_db(db)
        db.close()

        def override_get_db():
            s = TestingSession()
            try:
                yield s
                s.commit()
            finally:
                s.close()

        app.dependency_overrides[get_db] = override_get_db
        # ai_client 读取配置用的是模块内直接导入的 SessionLocal，一并指向测试库
        orig_session_local = ai_client_module.SessionLocal
        ai_client_module.SessionLocal = TestingSession
        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides.clear()
            ai_client_module.SessionLocal = orig_session_local
            settings.db_url = orig_url
            engine.dispose()  # Windows 下必须先释放 SQLite 文件句柄，临时目录才能删除


def test_health_and_seed(client):
    assert client.get("/api/health").json()["ok"] is True
    kps = client.get("/api/knowledge-points").json()
    assert kps["total"] >= 60, "知识图谱知识点应不少于60个"
    names = {k["name"] for k in kps["items"]}
    assert "因式分解" in names and "二次函数的实际应用" in names

    qs = client.get("/api/questions").json()
    assert qs["total"] >= 4, "演示错题应已导入"
    papers = client.get("/api/papers").json()
    assert papers["total"] == 2, "演示试卷应已导入"


def test_graph_structure(client):
    g = client.get("/api/graph").json()
    assert len(g["nodes"]) >= 60
    assert len(g["edges"]) >= 50
    pid = {n["name"]: n["id"] for n in g["nodes"]}
    # 前置依赖边抽查：因式分解 -> 一元二次方程及其解法
    assert any(
        e["source"] == pid["因式分解"] and e["target"] == pid["一元二次方程及其解法"]
        for e in g["edges"]
    )


def test_question_crud_and_review(client):
    r = client.post(
        "/api/questions",
        json={"question_text": "计算：$2^3+(-2)^2$", "grade": "七年级", "my_answer": "12"},
    )
    assert r.status_code == 200
    qid = r.json()["id"]

    # 无 Key 时 AI 解析应 503
    r = client.post(f"/api/questions/{qid}/analyze")
    assert r.status_code == 503
    assert "API Key" in r.json()["detail"]

    # 复习打卡：fail -> 次日复习
    r = client.post(f"/api/questions/{qid}/review", json={"result": "fail"})
    assert r.json()["status"] == "reviewing"
    assert r.json()["next_review_at"] is not None

    # 连续通过3次 -> 已掌握
    for _ in range(3):
        r = client.post(f"/api/questions/{qid}/review", json={"result": "pass"})
    assert r.json()["status"] == "mastered"
    assert r.json()["next_review_at"] is None

    r = client.patch(f"/api/questions/{qid}", json={"source_workbook": "某练习册", "source_location": "P1 T1"})
    assert r.json()["source_location"] == "P1 T1"
    assert client.delete(f"/api/questions/{qid}").json()["ok"] is True


def test_paper_analyze_and_trend(client):
    """演示数据：期中(82/100)应有薄弱点，且趋势 0.74 -> 0.82。"""
    papers = client.get("/api/papers").json()["items"]
    papers.sort(key=lambda p: p["exam_date"])
    latest = papers[-1]
    r = client.post(f"/api/papers/{latest['id']}/analyze")
    assert r.status_code == 200
    analysis = r.json()["analysis"]
    trend = analysis["trend"]
    assert trend["score_rates"][-2] == 0.74
    assert trend["score_rates"][-1] == 0.82
    weak_names = {w["name"] for w in analysis["weak_points"]}
    assert "函数的应用（一）" in weak_names
    assert analysis["summary"], "应有规则化分析结论"


def test_graph_subject_grade_filter(client):
    """图谱支持科目/年级过滤；边只保留两端都在结果内的。"""
    # 未收录科目 -> 空图
    r = client.get("/api/graph", params={"subject": "物理"})
    assert r.json()["nodes"] == []

    # 年级过滤：高一节点约30个，且不混入其他年级
    g = client.get("/api/graph", params={"grade": "高一"}).json()
    grades = {n["grade"] for n in g["nodes"]}
    assert grades == {"高一"}
    assert 25 <= len(g["nodes"]) <= 40

    # 边剪枝：两端都必须在过滤后的节点集内
    ids = {n["id"] for n in g["nodes"]}
    assert g["edges"], "高一内部应有前置边"
    assert all(e["source"] in ids and e["target"] in ids for e in g["edges"])

    # 知识点列表同样支持过滤
    kp = client.get("/api/knowledge-points", params={"subject": "数学", "grade": "七年级"}).json()
    assert kp["total"] >= 20
    assert all(k["grade"] == "七年级" for k in kp["items"])


def test_graph_validate_and_ktype(client):
    """图谱数据完整性校验应通过；节点带课型且取值合法。"""
    r = client.get("/api/graph/validate").json()
    assert r["ok"] is True, f"图谱校验失败: {r['issues']}"
    assert r["issues"] == []
    assert r["checked"] >= 100

    g = client.get("/api/graph").json()
    legal = {"概念", "计算技能", "综合应用"}
    assert all(n["ktype"] in legal for n in g["nodes"])
    ktypes = {n["ktype"] for n in g["nodes"]}
    assert ktypes == legal, "启发式课型应覆盖三类"


def test_reexplain_and_check_answer_guards(client):
    """换种讲法/答案核验都需要先有 AI 解析（无解析 -> 400，无需真实 AI）。"""
    # 演示错题 #4 是未解析状态
    r = client.post("/api/questions/4/reexplain", json={"style": "生活类比"})
    assert r.status_code == 400
    r = client.post("/api/questions/4/check-answer", json={"answer": "-1"})
    assert r.status_code == 400

    # 已解析的错题 #1：无 Key 时应得到 503（路由正确转发 AI 未配置）；配置 Key 后为 200/502
    r = client.post("/api/questions/1/reexplain", json={"style": "生活类比"})
    assert r.status_code in (200, 502, 503)
    r = client.post("/api/questions/1/check-answer", json={"answer": "20元"})
    assert r.status_code in (200, 502, 503)


def test_learner_profile(client):
    """学习者画像：错因分布/薄弱点/趋势/建议。"""
    data = client.get("/api/stats/profile").json()
    assert data["question_count"] >= 4
    assert data["error_dist"], "应有错因分布"
    types = {e["type"] for e in data["error_dist"]}
    assert "概念不清" in types, "演示错题应包含概念不清错因"
    assert data["weak_top"], "演示数据应有薄弱点"
    assert len(data["trend"]) == 2
    assert data["suggestions"], "应有规则化建议"


def test_plan_generation_prereq_first(client):
    """演示数据即可驱动计划；前置知识点应排在后继知识点之前。"""
    r = client.post("/api/plans", json={"days": 7})
    assert r.status_code == 200
    plan = r.json()
    tasks = [t for day in plan["plan_data"] for t in day["tasks"]]
    assert tasks, "演示数据下应生成任务"

    kp_order = []
    for t in tasks:
        if t["knowledge_point"] not in kp_order:
            kp_order.append(t["knowledge_point"])

    weak = {w["name"] for w in client.get("/api/stats/overview").json()["weak_points"]}
    assert weak & set(kp_order), "薄弱知识点应被纳入计划"

    # 排程核心断言：薄弱知识点的已收录前置应排在它前面（如 等式性质与不等式性质 -> 基本不等式）
    kps = {k["name"]: k for k in client.get("/api/knowledge-points").json()["items"]}
    for b in kp_order:
        if b not in weak:
            continue
        for a in kps.get(b, {}).get("prereqs", []):
            if a in kp_order:
                assert kp_order.index(a) < kp_order.index(b), f"前置知识点[{a}]应先于[{b}]"


def test_plan_review_tree(client):
    """周复盘接口：返回计划->知识点->错因/现状/完成度 的树，含任务完成统计。"""
    r = client.post("/api/plans", json={"days": 7})
    plan_id = r.json()["id"]
    r = client.get(f"/api/plans/{plan_id}/review")
    assert r.status_code == 200
    data = r.json()
    assert data["task_total"] > 0
    assert data["task_done"] == 0
    assert data["kp_count"] > 0
    tree = data["tree"]
    assert tree["children"], "复盘树应有知识点分支"
    first = tree["children"][0]
    assert {"错因", "现状", "任务完成"} & {leaf["name"][:2] for leaf in first["children"]}


def test_workbook_locate(client):
    r = client.get("/api/workbooks/locate", params={"kp": "二次函数与一元二次方程、不等式"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert items, "示例练习册应能定位到章节"
    assert "一元二次" in items[0]["chapter"]


def test_settings_roundtrip(client):
    assert client.get("/api/settings").json()["api_key_set"] in (True, False)

    r = client.put("/api/settings", json={"ai_api_key": "sk-test-1234567890", "ai_model": "glm-4.5v"})
    assert r.json()["api_key_set"] is True
    assert "****" in r.json()["api_key_masked"]
    assert "sk-test" not in r.json()["api_key_masked"], "明文 Key 不得返回前端"

    # 配置 Key 后不再是 503（无真实服务时应为 502，说明走到了真实调用路径）
    r = client.post("/api/questions/1/analyze")
    assert r.status_code in (200, 502)


def test_overview_stats(client):
    data = client.get("/api/stats/overview").json()
    assert data["question_count"] >= 4
    assert data["paper_count"] == 2
    assert len(data["score_trend"]) == 2
    assert data["score_trend"][-1]["rate"] == 0.82
    assert data["weak_points"], "演示数据应产生薄弱知识点"
