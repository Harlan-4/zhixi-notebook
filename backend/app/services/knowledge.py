"""知识图谱辅助：知识点匹配、前置闭包、掌握度估计、图谱完整性校验（纯算法，不依赖 AI）。"""
from collections import defaultdict

from sqlalchemy.orm import Session

from ..models import KnowledgePoint, Paper, Question

_STATUS_SCORE = {"new": 0.25, "reviewing": 0.5, "mastered": 0.9}
WEAK_THRESHOLD = 0.65  # 低于该值视为"薄弱"

_KTYPE_APPLICATION = ("应用", "实际", "综合", "问题")
_KTYPE_COMPUTATION = ("运算", "计算", "方程", "化简", "分解", "求值", "混合", "面积")


def heuristic_ktype(name: str) -> str:
    """按知识点名称推断课型：综合应用 > 计算技能 > 概念（默认）。"""
    if any(k in name for k in _KTYPE_APPLICATION):
        return "综合应用"
    if any(k in name for k in _KTYPE_COMPUTATION):
        return "计算技能"
    return "概念"


def graph_issues(db: Session) -> list[str]:
    """知识图谱数据完整性校验（借鉴 Study-Mate 的课程结构校验思路）。

    检查：名称唯一、章节非空、前置引用存在、无自引用、前置图无环。
    返回问题列表（空列表 = 通过）。
    """
    points = db.query(KnowledgePoint).all()
    pmap = {p.name: p for p in points}
    issues: list[str] = []
    if len(pmap) != len(points):
        issues.append("存在重复的知识点名称")
    for p in points:
        if not (p.chapter or "").strip():
            issues.append(f"[{p.name}] 缺少教材章节")
        for pre in p.prereqs or []:
            if pre == p.name:
                issues.append(f"[{p.name}] 前置引用了自己")
            elif pre not in pmap:
                issues.append(f"[{p.name}] 的前置知识点 [{pre}] 不存在于图谱")
    # 前置图无环检测（三色 DFS：沿 prereqs 边向上走）
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {name: WHITE for name in pmap}

    def dfs(node: str, path: list[str]) -> None:
        color[node] = GRAY
        for pre in pmap[node].prereqs or []:
            if pre not in pmap:
                continue
            if color.get(pre) == GRAY:
                issues.append(f"前置关系成环：{' -> '.join(path + [node, pre])}")
            elif color.get(pre) == WHITE:
                dfs(pre, path + [node])
        color[node] = BLACK

    for name in pmap:
        if color[name] == WHITE:
            dfs(name, [name])
    return issues


def point_map(db: Session) -> dict[str, KnowledgePoint]:
    return {p.name: p for p in db.query(KnowledgePoint).all()}


def normalize_kps(db: Session, names: list) -> list[str]:
    """把 AI 输出的知识点名对齐到图谱标准名（精确 -> 包含匹配），未收录的保留原文。"""
    pmap = point_map(db)
    result = []
    for raw in names or []:
        name = str(raw).strip()
        if not name:
            continue
        if name in pmap:
            result.append(name)
            continue
        hit = next((k for k in pmap if k in name or name in k), None)
        result.append(hit or name)
    return list(dict.fromkeys(result))  # 去重保序


def ancestors_closure(pmap: dict[str, KnowledgePoint], names: set[str]) -> set[str]:
    """知识点的前置依赖传递闭包。"""
    seen, stack = set(), list(names)
    while stack:
        cur = stack.pop()
        kp = pmap.get(cur)
        if not kp:
            continue
        for pre in kp.prereqs or []:
            if pre not in seen:
                seen.add(pre)
                stack.append(pre)
    return seen


def compute_mastery(db: Session) -> dict[str, float]:
    """知识点掌握度估计（0~1），取错题信号与试卷信号的较保守值。

    - 错题信号：new=0.25 / reviewing=0.5 / mastered=0.9，取该知识点所有错题均值
    - 试卷信号：0.9 - 0.6×失分率，按考试日期推进覆盖（越近的考试越能代表当前水平）
    - 无证据的知识点不返回（"未知"不等于"薄弱"）
    """
    q_scores: dict[str, list[float]] = defaultdict(list)
    for q in db.query(Question).all():
        kps = (q.analysis or {}).get("knowledge_points") or []
        s = _STATUS_SCORE.get(q.status, 0.25)
        for kp in kps:
            q_scores[kp].append(s)

    p_score: dict[str, float] = {}
    papers = db.query(Paper).order_by(Paper.exam_date).all()
    for paper in papers:  # 日期升序，最近一次考试覆盖旧值
        for item in paper.questions or []:
            total = float(item.get("score") or 0)
            got = float(item.get("got_score") or 0)
            if total <= 0:
                continue
            ratio = max(0.0, min(1.0, (total - got) / total))
            for kp in item.get("knowledge_points") or []:
                p_score[kp] = 0.9 - 0.6 * ratio

    mastery: dict[str, float] = {}
    for kp in set(q_scores) | set(p_score):
        vals = []
        if kp in q_scores:
            vals.append(sum(q_scores[kp]) / len(q_scores[kp]))
        if kp in p_score:
            vals.append(p_score[kp])
        mastery[kp] = round(min(vals), 3)
    return mastery
