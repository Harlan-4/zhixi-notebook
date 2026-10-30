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
        app.state.test_session_factory = TestingSession  # 供测试用新会话重读临时库（验证真正落库）
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
    assert kps["total"] >= 500, "四科图谱（数学/物理/化学/生物）合计应不少于500点"
    names = {k["name"] for k in kps["items"]}
    assert "因式分解" in names and "二次函数的实际应用" in names
    assert "等差数列" in names and "椭圆的标准方程" in names, "图谱应含高二（数列/圆锥曲线）内容"
    assert "正态分布" in names, "图谱应含高三（选必三）内容"
    # 物理化学生物全学段抽查
    assert "欧姆定律及其应用" in names and "物体的浮沉条件" in names, "物理图谱应覆盖初中（八/九年级）"
    assert "氧化还原反应的概念与本质" in names and "盐类水解的原理与规律" in names, "化学图谱应覆盖必修与选必1"
    assert "光合作用" in names and "基因的显性和隐性" in names, "生物图谱应覆盖初中（七/八年级）"

    qs = client.get("/api/questions").json()
    assert qs["total"] >= 4, "演示错题应已导入"
    assert any(
        q["status"] == "mastered" and q["collected_at"] for q in qs["items"]
    ), "演示数据应包含已收服（collected_at 非空）的掌握题"
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

    # 复习打卡：fail -> 次日复习 + 共情（无 praise），streak 记 1 天
    r = client.post(f"/api/questions/{qid}/review", json={"result": "fail"})
    body = r.json()
    assert body["question"]["status"] == "reviewing"
    assert body["question"]["next_review_at"] is not None
    assert body["praise"] == ""
    assert body["just_collected"] is False
    assert body["streak"] >= 1

    # 连续通过3次 -> 已掌握（收服）：collected_at 非空 + 鼓励语 + just_collected
    for _ in range(3):
        r = client.post(f"/api/questions/{qid}/review", json={"result": "pass"})
    body = r.json()
    assert body["question"]["status"] == "mastered"
    assert body["question"]["next_review_at"] is None
    assert body["question"]["collected_at"], "收服后应记录 collected_at"
    assert body["just_collected"] is True
    assert body["praise"], "通过复习应有鼓励语"

    # 回炉：已收服的题打 fail -> 收回徽章
    r = client.post(f"/api/questions/{qid}/review", json={"result": "fail"})
    body = r.json()
    assert body["question"]["collected_at"] is None

    # 游戏化徽标接口：streak 与收服计数可用
    g = client.get("/api/stats/gamification").json()
    assert g["streak"] >= 1
    assert g["collected_count"] >= 0

    r = client.patch(f"/api/questions/{qid}", json={"source_workbook": "某练习册", "source_location": "P1 T1"})
    assert r.json()["source_location"] == "P1 T1"
    assert client.delete(f"/api/questions/{qid}").json()["ok"] is True


def test_paper_wrong_to_notebook(client):
    """失分题一键入错题本：可指定题号、只收失分题、重复导入去重。"""
    paper = client.get("/api/papers/1").json()
    failing = [
        q["no"]
        for q in paper["questions"]
        if float(q.get("got_score") or 0) < float(q.get("score") or 0)
    ]
    assert failing, "演示月考应有失分题"

    # 指定单题导入
    one = failing[0]
    r = client.post("/api/papers/1/add-wrong-to-notebook", json={"nos": [one]})
    body = r.json()
    assert body["created_count"] == 1
    created = body["created"][0]
    assert created["source_workbook"] == paper["title"]
    assert created["source_location"] == f"第{one}题"
    assert created["status"] == "new"
    assert created["question_text"] == next(q["text"] for q in paper["questions"] if q["no"] == one)

    # 全量导入：其余失分题入库，已导入的题去重跳过
    r = client.post("/api/papers/1/add-wrong-to-notebook", json={})
    body = r.json()
    assert body["created_count"] == len(failing) - 1
    assert body["skipped_nos"] == [one]

    # 再次全量导入：全部去重
    r = client.post("/api/papers/1/add-wrong-to-notebook", json={})
    body = r.json()
    assert body["created_count"] == 0
    assert sorted(body["skipped_nos"], key=str) == sorted(failing, key=str)


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
    # 未收录科目 -> 空图（物理/化学/生物已收录，用地理验证空态）
    r = client.get("/api/graph", params={"subject": "地理"})
    assert r.json()["nodes"] == []

    # 物理化学生物：科目过滤只出本科目节点，年级覆盖学段抽查
    p = client.get("/api/graph", params={"subject": "物理"}).json()
    assert {n["subject"] for n in p["nodes"]} == {"物理"}
    assert 180 <= len(p["nodes"]) <= 230, "物理应覆盖八年级~高三全学段"
    c = client.get("/api/graph", params={"subject": "化学", "grade": "九年级"}).json()
    assert {n["grade"] for n in c["nodes"]} == {"九年级"}
    assert len(c["nodes"]) >= 25, "化学九年级应覆盖上下册"
    b = client.get("/api/graph", params={"subject": "生物", "grade": "七年级"}).json()
    assert {n["grade"] for n in b["nodes"]} == {"七年级"}
    assert len(b["nodes"]) >= 25, "生物七年级应覆盖上下册（2024/2025版）"
    assert p["edges"] and c["edges"] and b["edges"], "各科目内部应有前置边"

    # 年级过滤：数学高一（必修一30 + 必修二16）约46个，且不混入其他年级
    g = client.get("/api/graph", params={"subject": "数学", "grade": "高一"}).json()
    grades = {n["grade"] for n in g["nodes"]}
    assert grades == {"高一"}
    assert 40 <= len(g["nodes"]) <= 55
    names1 = {n["name"] for n in g["nodes"]}
    assert "余弦定理与正弦定理" in names1 and "事件的相互独立性" in names1, "必修二应含解三角形/独立性"

    # 仅按年级过滤：四科的高一节点都在（数学46+物理27+化学24+生物27）
    g_all = client.get("/api/graph", params={"grade": "高一"}).json()
    assert {n["grade"] for n in g_all["nodes"]} == {"高一"}
    assert 170 <= len(g_all["nodes"]) <= 210

    # 数学高二（选必一20：含圆锥曲线方程/性质拆分 + 选必二13）与高三（选必三14）
    g2 = client.get("/api/graph", params={"subject": "数学", "grade": "高二"}).json()
    assert {n["grade"] for n in g2["nodes"]} == {"高二"}
    assert 28 <= len(g2["nodes"]) <= 40
    names2 = {n["name"] for n in g2["nodes"]}
    assert "椭圆的标准方程" in names2 and "椭圆的几何性质" in names2, "圆锥曲线应按方程/性质拆分"
    assert "等差数列的前n项和" in names2 and "空间角的向量求法" in names2
    assert g2["edges"], "高二内部应有前置边"
    g3 = client.get("/api/graph", params={"subject": "数学", "grade": "高三"}).json()
    assert {n["grade"] for n in g3["nodes"]} == {"高三"}
    assert 10 <= len(g3["nodes"]) <= 18
    names3 = {n["name"] for n in g3["nodes"]}
    assert "条件概率与全概率公式" in names3 and "二项分布与超几何分布" in names3
    assert "二项式系数的性质与赋值法" in names3
    assert g3["edges"], "高三内部应有前置边"

    # 仅按年级过滤：四科节点合并（高二 = 数学33+物理36+化学22+生物25；高三 = 14+10+12+12）
    g2_all = client.get("/api/graph", params={"grade": "高二"}).json()
    assert {n["grade"] for n in g2_all["nodes"]} == {"高二"}
    assert 145 <= len(g2_all["nodes"]) <= 180
    g3_all = client.get("/api/graph", params={"grade": "高三"}).json()
    assert {n["grade"] for n in g3_all["nodes"]} == {"高三"}
    assert 65 <= len(g3_all["nodes"]) <= 85

    # 跨年级前置边：高二节点可引用高一先修（如 空间向量及其运算 -> 平面向量的线性运算）
    full = client.get("/api/graph").json()
    pid = {n["name"]: n["id"] for n in full["nodes"]}
    assert any(
        e["source"] == pid["平面向量的线性运算"] and e["target"] == pid["空间向量及其运算"]
        for e in full["edges"]
    )

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


def test_diagnose_chat_guards(client):
    """错因追问对话：未解析 -> 400；空消息 -> 400；已解析无 Key -> 503。"""
    r = client.post("/api/questions/4/diagnose-chat", json={"message": "我当时没考虑空集"})
    assert r.status_code == 400
    r = client.post("/api/questions/1/diagnose-chat", json={"message": "  "})
    assert r.status_code == 400
    r = client.post("/api/questions/1/diagnose-chat", json={"message": "我当时没考虑空集"})
    assert r.status_code == 503


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


def test_question_subject_filter(client):
    """错题按科目筛选：新增物理错题后，subject 参数只返回对应科目的错题。"""
    r = client.post(
        "/api/questions",
        json={"subject": "物理", "question_text": "画出小车在斜面上的受力示意图", "my_answer": "漏画了摩擦力"},
    )
    assert r.status_code == 200
    physics_id = r.json()["id"]

    physics = client.get("/api/questions", params={"subject": "物理"}).json()
    assert physics["total"] == 1
    assert physics["items"][0]["id"] == physics_id
    assert physics["items"][0]["subject"] == "物理"

    math_list = client.get("/api/questions", params={"subject": "数学"}).json()
    assert math_list["total"] >= 4, "演示错题默认为数学"
    assert all(q["subject"] == "数学" for q in math_list["items"])
    assert all(q["id"] != physics_id for q in math_list["items"])

    # 年级过滤：只返回该年级的错题
    r = client.post(
        "/api/questions",
        json={"subject": "物理", "grade": "高一", "question_text": "画出小车在斜面上的受力示意图", "my_answer": "漏画了摩擦力"},
    )
    assert r.status_code == 200
    g1 = client.get("/api/questions", params={"grade": "高一"}).json()
    assert all(q["grade"] == "高一" for q in g1["items"])
    g9 = client.get("/api/questions", params={"grade": "九年级"}).json()
    assert all(q["id"] not in (physics_id, r.json()["id"]) for q in g9["items"])


def test_qa_chat_guards(client):
    """讲解答疑对话：未解析 -> 400；空消息 -> 400；已解析无 Key -> 503。"""
    # 未解析的错题（演示 #4 无解析）
    qs = client.get("/api/questions").json()["items"]
    unanalyzed = next(q for q in qs if not q["analysis"])
    r = client.post(f"/api/questions/{unanalyzed['id']}/qa-chat", json={"message": "为什么这一步这样算？"})
    assert r.status_code == 400

    # 已解析的错题：空消息 -> 400；正常问题在无 Key 时 -> 503
    analyzed = next(q for q in qs if q["analysis"])
    r = client.post(f"/api/questions/{analyzed['id']}/qa-chat", json={"message": "  "})
    assert r.status_code == 400
    r = client.post(f"/api/questions/{analyzed['id']}/qa-chat", json={"message": "第2步为什么要先开三次方？"})
    assert r.status_code == 503, "测试环境未配置 Key 应友好降级"


def test_chat_history_persists(client, monkeypatch):
    """错因对话/答疑对话的历史必须真正落库（回归：JSON 就地修改未标记变更导致静默丢失）。"""
    from app.models import Question
    from app.services import question_service

    # 已解析的演示题
    qs = client.get("/api/questions").json()["items"]
    target = next(q for q in qs if q["analysis"])

    def fake_chat_json(messages, **kwargs):
        return {"reply": "明白了，谢谢说明", "concluded": True, "error_type": "概念不清", "cause_summary": "测试确认的错因"}

    def fake_chat_text(messages, **kwargs):
        return "这一步的意思是先配方再判定符号。"

    monkeypatch.setattr(question_service.ai_client, "chat_json", fake_chat_json)
    monkeypatch.setattr(question_service.ai_client, "chat_text", fake_chat_text)

    r1 = client.post(f"/api/questions/{target['id']}/diagnose-chat", json={"message": "我当时把符号看反了"})
    assert r1.status_code == 200
    r2 = client.post(f"/api/questions/{target['id']}/qa-chat", json={"message": "第2步为什么要这样变形？"})
    assert r2.status_code == 200

    # 用全新会话重读数据库，确认历史真正持久化（同会话读会看到内存对象，测不出该 bug）
    db = client.app.state.test_session_factory()
    try:
        row = db.query(Question).filter_by(id=target["id"]).first()
        dc = (row.analysis or {}).get("diagnose_chat") or []
        qc = (row.analysis or {}).get("qa_chat") or []
        assert len(dc) >= 2, "错因对话历史未落库"
        assert dc[-1]["role"] == "ai" and "明白" in dc[-1]["text"]
        assert row.error_type == "概念不清", "对话确认后的错因分类未落库"
        assert len(qc) >= 2, "答疑对话历史未落库"
    finally:
        db.close()


def test_paper_recognize_multi_image(client, monkeypatch):
    """试卷+答题卡两步识别：试卷结构 -> 答题卡判分按题号合并；判分失败时得分留空。"""
    from app.services import paper_service

    calls = []

    def fake_vision_multi(prompt, images):
        calls.append({"prompt_head": prompt[:12], "labels": [i["label"] for i in images]})
        if prompt.startswith("你是初高中老师。下面几张图片是某次考试的试卷"):
            return {
                "title": "高一上学期期中考试",
                "questions": [
                    {"no": "1", "text": "集合运算题", "score": 5, "knowledge_points": ["集合的基本运算"]},
                    {"no": "2", "text": "基本不等式求最值", "score": 5, "knowledge_points": ["基本不等式"]},
                    {"no": "3", "text": "(图片不清，请手动补充)", "score": 5, "knowledge_points": []},
                ],
            }
        if prompt.startswith("你是初高中老师。下面几张图片是这次考试的学生答题卡"):
            assert "题目清单" in prompt and "基本不等式" in prompt, "判分提示词应带题目清单"
            return {"scores": [{"no": "1", "got_score": 5}, {"no": "2", "got_score": 0}]}
        raise AssertionError("未知 prompt: " + prompt[:30])

    monkeypatch.setattr(paper_service.ai_client, "vision_json_multi", fake_vision_multi)

    r = client.post(
        "/api/papers/recognize",
        files=[
            ("files", ("p1.jpg", b"img-paper-1", "image/jpeg")),
            ("files", ("p2.jpg", b"img-paper-2", "image/jpeg")),
            ("files", ("a1.jpg", b"img-answer-1", "image/jpeg")),
        ],
        data={"kinds": "paper,paper,answer"},
    )
    assert r.status_code == 200
    draft = r.json()["draft"]
    assert draft["title"] == "高一上学期期中考试"
    assert calls[0]["labels"] == ["【试卷 第1张】", "【试卷 第2张】"], "第一步只发试卷图"
    assert calls[1]["labels"] == ["【答题卡 第1张】"], "第二步只发答题卡图"
    got = {q["no"]: q["got_score"] for q in draft["questions"]}
    assert got == {"1": 5, "2": 0, "3": None}, "判分按题号合并，未批改的题为 null"
    assert "2/3" in draft["grade_note"]

    # 无答题卡：只走第一步，得分留空
    calls.clear()
    r2 = client.post(
        "/api/papers/recognize",
        files=[("files", ("only.jpg", b"img-only", "image/jpeg"))],
    )
    assert r2.status_code == 200
    draft2 = r2.json()["draft"]
    assert calls[0]["labels"] == ["【试卷 第1张】"] and len(calls) == 1, "无答题卡不应触发判分步"
    assert all(q["got_score"] is None for q in draft2["questions"])

    # 判分步失败（AI 异常）：试卷结构仍返回，得分留空，不整体报错
    calls.clear()

    def broken_grade(prompt, images):
        if prompt.startswith("你是初高中老师。下面几张图片是这次考试的学生答题卡"):
            raise paper_service.ai_client.AIServiceError("模拟判分失败")
        return fake_vision_multi(prompt, images)

    monkeypatch.setattr(paper_service.ai_client, "vision_json_multi", broken_grade)
    r3 = client.post(
        "/api/papers/recognize",
        files=[
            ("files", ("p.jpg", b"img-p", "image/jpeg")),
            ("files", ("a.jpg", b"img-a", "image/jpeg")),
        ],
        data={"kinds": "paper,answer"},
    )
    assert r3.status_code == 200
    draft3 = r3.json()["draft"]
    assert draft3["questions"] and all(q["got_score"] is None for q in draft3["questions"])
    assert "判分失败" in draft3["grade_note"]




def test_plan_generation_skips_unknown_kp(client):
    """回归：错题解析含图谱外的自由知识点名时，生成计划不再 500，且任务不引用图谱外名字。"""
    import json

    import sys
    sys.path.insert(0, ".")
    from app.models import Question

    # 直接造一道已解析、但知识点含图谱外自由名的错题
    db = client.app.state.test_session_factory()
    try:
        db.add(Question(
            subject="数学", grade="高一", question_type="解答题",
            question_text="用配方法求 f(x)=x²+2x+3 的最小值。",
            my_answer="最小值是 3（配方符号出错）", status="new",
            analysis={
                "correct_answer": "最小值 2",
                "knowledge_points": ["配方法求最值（图谱外自由名）", "二次函数的最值（图谱外自由名）"],
                "error_analysis": "配方时符号出错", "cause_evidence": "inferred",
                "diagnose_questions": [], "solution_steps": ["配方", "判最小值"],
            },
        ))
        db.commit()
    finally:
        db.close()

    r = client.post("/api/plans", json={"days": 7})
    assert r.status_code == 200, f"生成计划应成功而非 500：{r.text[:200]}"
    plan = r.json()
    names = [
        t.get("knowledge_point")
        for day in plan.get("plan_data", [])
        for t in day.get("tasks", [])
    ]
    assert names, "演示错题（图谱内知识点）应产生计划任务"
    assert all(n and "图谱外" not in n for n in names), "计划任务不得引用图谱外的自由名字"
