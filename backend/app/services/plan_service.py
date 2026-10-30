"""学习计划排程算法（团队自主实现，本作品核心创新点之一）。

与常见"间隔重复"计划不同，本算法利用知识图谱的**前置依赖关系**：
1. 汇总证据：未掌握错题的知识点 + 近期试卷薄弱知识点（失分率>=0.3）；
2. 掌握度估计后筛出薄弱点，并沿前置边把"薄弱的祖先"一并纳入（先补地基再盖楼）；
3. 在子图上做拓扑排序（前置知识优先），同层级按掌握度升序（最弱的先学）；
4. 每个知识点生成三类任务：概念巩固(教材章节) -> 错题重做 -> 举一反三变式，
   并关联练习册章节定位（若有目录数据）；
5. 顺序填充到每天（每天至多3个任务，约40分钟），薄弱点附加末段复测任务（间隔重复）。
"""
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..models import Paper, Question, StudyPlan
from .knowledge import WEAK_THRESHOLD, ancestors_closure, compute_mastery, point_map

TASKS_PER_DAY = 3
PAPER_WEAK_RATIO = 0.3


def _collect_candidates(db: Session) -> dict[str, list[str]]:
    """返回 候选知识点 -> 证据描述列表。"""
    evidence: dict[str, list[str]] = defaultdict(list)
    for q in db.query(Question).filter(Question.status != "mastered").all():
        kps = (q.analysis or {}).get("knowledge_points") or []
        for kp in kps:
            evidence[kp].append(f"错题 #{q.id}")
    for paper in db.query(Paper).order_by(Paper.exam_date.desc()).all():
        for item in paper.questions or []:
            total = float(item.get("score") or 0)
            got = float(item.get("got_score") or 0)
            if total <= 0 or got / total >= 1 - PAPER_WEAK_RATIO:
                continue
            for kp in item.get("knowledge_points") or []:
                evidence[kp].append(f"试卷《{paper.title}》失分")
    return evidence


def _topological_with_levels(pmap: dict, sub: set[str]) -> tuple[list[str], dict[str, int]]:
    """子图上的拓扑排序，并计算每个知识点的层级（最长前置链深度）。

    返回 (拓扑序, 层级表)。前置节点层级必然小于后继，可据此做"前置优先、
    同层级按掌握度"的稳定排序。
    """
    indegree = {k: 0 for k in sub}
    children: dict[str, list[str]] = defaultdict(list)
    for name in sub:
        node = pmap.get(name)
        if not node:
            continue  # 不在图谱中的名字（防御：理论上已被上游过滤）
        for pre in node.prereqs or []:
            if pre in sub:
                indegree[name] += 1
                children[pre].append(name)
    queue = sorted([k for k, d in indegree.items() if d == 0])
    ordered = []
    while queue:
        cur = queue.pop(0)
        ordered.append(cur)
        for ch in children[cur]:
            indegree[ch] -= 1
            if indegree[ch] == 0:
                queue.append(ch)
        queue.sort()
    # 图中若有未收录前置导致的环/断链，兜底把剩余的追加在末尾
    ordered += [k for k in sub if k not in set(ordered)]
    # 层级 = 前置链最长深度（根为 0）
    levels: dict[str, int] = {}
    for name in ordered:
        pres = [p for p in (pmap.get(name).prereqs or []) if p in sub]
        levels[name] = max((levels[p] for p in pres), default=-1) + 1
    return ordered, levels


def _locate_workbook(db: Session, kp: str) -> str:
    from ..models import Workbook

    for w in db.query(Workbook).all():
        for entry in w.catalog or []:
            if kp in (entry.get("knowledge_points") or []):
                page = f"（{entry['page']}）" if entry.get("page") else ""
                return f"《{w.name}》{entry['chapter']}{page}"
    return ""


def generate_plan(db: Session, days: int = 7, title: str = "") -> StudyPlan:
    days = max(3, min(21, days))
    pmap = point_map(db)
    mastery = compute_mastery(db)
    evidence = _collect_candidates(db)

    if not evidence:
        plan = StudyPlan(
            title=title or "学习计划",
            start_date=date.today(),
            days=days,
            plan_data=[
                {
                    "date": (date.today() + timedelta(days=i)).isoformat(),
                    "tasks": [],
                }
                for i in range(days)
            ],
        )
        plan.title = plan.title + "（暂无薄弱知识点，保持当前节奏）"
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan

    # 1. 薄弱点 = 有证据且掌握度低（只保留图谱内的标准名；
    #    AI 解析可能自由输出图谱外的知识点名，它们无法按前置依赖排程，跳过）
    weak = {
        kp
        for kp in evidence
        if kp in pmap and mastery.get(kp, WEAK_THRESHOLD - 0.01) < WEAK_THRESHOLD
    }
    # 2. 前置闭包：薄弱点的"薄弱祖先"也纳入（无证据的祖先不视为薄弱，只参与排序）
    anc = ancestors_closure(pmap, weak)
    sub = weak | {a for a in anc if a in mastery and mastery[a] < WEAK_THRESHOLD}

    # 3. 拓扑排序（前置优先），同层级按掌握度升序（最弱优先）。
    # 注意不能在 sort 的 key 里调用 ordered.index()：CPython sort 期间列表被临时置空。
    ordered, levels = _topological_with_levels(pmap, sub)
    ordered.sort(key=lambda k: (levels[k], mastery.get(k, 0.0)))

    # 4. 生成任务
    tasks: list[dict] = []
    non_mastered = db.query(Question).filter(Question.status != "mastered").all()
    for kp in ordered:
        qids = []
        for q in non_mastered:
            if kp in ((q.analysis or {}).get("knowledge_points") or []):
                qids.append(q.id)
        chapter = pmap[kp].chapter if kp in pmap else ""
        ktype = pmap[kp].ktype if kp in pmap else "概念"
        m = mastery.get(kp, 0.0)
        task_list = []
        if chapter:
            # 按课型差异化概念巩固的方式（借鉴 Study-Mate 的课型设计）
            ktype_detail = {
                "概念": f"复习教材「{chapter}」，梳理定义、公式与典型例题",
                "计算技能": f"复习教材「{chapter}」，整理标准解题步骤与易错运算，再做2-3道练手",
                "综合应用": f"复习教材「{chapter}」并精做1道综合题，梳理思路与方法套路",
            }
            task_list.append(
                {
                    "knowledge_point": kp,
                    "action": "概念巩固",
                    "detail": ktype_detail.get(ktype, ktype_detail["概念"]),
                    "question_ids": [],
                    "workbook_ref": "",
                    "done": False,
                    "reason": f"掌握度 {int(m * 100)}% · {ktype}",
                }
            )
        if qids:
            task_list.append(
                {
                    "knowledge_point": kp,
                    "action": "错题重做",
                    "detail": f"不看答案重做 {len(qids)} 道相关错题，做完对照 AI 解析",
                    "question_ids": qids,
                    "workbook_ref": "",
                    "done": False,
                    "reason": f"涉及 {len(qids)} 道未掌握错题",
                }
            )
        wb = _locate_workbook(db, kp)
        task_list.append(
            {
                "knowledge_point": kp,
                "action": "举一反三",
                "detail": (
                    f"在错题本中对相关错题点「举一反三」生成变式题并完成"
                    + (f"；同步练习：{wb}" if wb else "")
                ),
                "question_ids": qids,
                "workbook_ref": wb,
                "done": False,
                "reason": "同知识点变式训练",
            }
        )
        tasks.extend(task_list)

    # 5. 间隔重复：最薄弱的 2 个知识点在计划末尾追加复测
    weakest = sorted(sub, key=lambda k: mastery.get(k, 0.0))[:2]
    for kp in weakest:
        qids = [
            q.id
            for q in non_mastered
            if kp in ((q.analysis or {}).get("knowledge_points") or [])
        ]
        tasks.append(
            {
                "knowledge_point": kp,
                "action": "复测",
                "detail": "计划收官复测：重做该知识点错题，确认真正掌握",
                "question_ids": qids,
                "workbook_ref": "",
                "done": False,
                "reason": "间隔重复（艾宾浩斯）",
            }
        )

    # 6. 分配到天：顺序填充，每天至多 TASKS_PER_DAY 个任务
    plan_data = []
    ti = 0
    for d in range(days):
        day_tasks = tasks[ti : ti + TASKS_PER_DAY]
        ti += TASKS_PER_DAY
        plan_data.append(
            {
                "date": (date.today() + timedelta(days=d)).isoformat(),
                "tasks": day_tasks,
            }
        )
    overflow = tasks[ti:]
    if overflow:
        plan_data[-1]["tasks"].extend(
            [{**t, "detail": "[顺延] " + t["detail"]} for t in overflow]
        )

    plan = StudyPlan(
        title=title or f"{days}天薄弱点补习计划",
        start_date=date.today(),
        days=days,
        plan_data=plan_data,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan
