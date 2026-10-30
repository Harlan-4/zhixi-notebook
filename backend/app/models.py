"""数据模型：知识点图谱、错题、试卷、练习册、学习计划、应用设置。"""
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class KnowledgePoint(Base):
    """知识点（人教版初中数学，含前置依赖，构成知识图谱）。"""

    __tablename__ = "knowledge_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(16), default="数学", index=True)  # 数学/物理/化学/生物...
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    grade: Mapped[str] = mapped_column(String(16))            # 七年级/八年级/九年级
    ktype: Mapped[str] = mapped_column(String(16), default="概念")  # 课型：概念/计算技能/综合应用
    chapter: Mapped[str] = mapped_column(String(128))          # 教材章节定位，如 "八上·第14章 整式的乘法与因式分解"
    prereqs: Mapped[list] = mapped_column(JSON, default=list)  # 前置知识点名称列表
    description: Mapped[str] = mapped_column(Text, default="")


class Question(Base):
    """错题。"""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(16), default="数学")
    grade: Mapped[str] = mapped_column(String(16), default="")
    question_type: Mapped[str] = mapped_column(String(16), default="解答题")
    question_text: Mapped[str] = mapped_column(Text)            # 支持 LaTeX（$...$）
    my_answer: Mapped[str] = mapped_column(Text, default="")    # 学生的错误作答
    image_path: Mapped[str] = mapped_column(String(256), default="")
    source_workbook: Mapped[str] = mapped_column(String(128), default="")  # 来源练习册
    source_location: Mapped[str] = mapped_column(String(64), default="")   # 如 "P45 T7"

    status: Mapped[str] = mapped_column(String(16), default="new", index=True)  # new/reviewing/mastered
    error_type: Mapped[str] = mapped_column(String(16), default="")  # 概念不清/计算失误/审题错误/方法未掌握/其他

    # AI 解析结果：correct_answer/solution_steps/error_analysis/knowledge_points/tips/textbook_location
    analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # AI 举一反三：[{text, answer, solution, difficulty}]
    variants: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # 复习追踪（艾宾浩斯间隔）
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    review_stage: Mapped[int] = mapped_column(Integer, default=0)   # 通过几次复习间隔
    last_result: Mapped[str] = mapped_column(String(8), default="")  # pass/fail
    next_review_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    collected_at: Mapped[date | None] = mapped_column(Date, nullable=True)  # 收服时间：三次复习通过转掌握的那天

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class Paper(Base):
    """一次考试试卷（含逐题得分与知识点），支撑纵向进步分析。"""

    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    exam_date: Mapped[date] = mapped_column(Date)
    paper_type: Mapped[str] = mapped_column(String(16), default="月考")  # 月考/期中/期末/模拟
    subject: Mapped[str] = mapped_column(String(16), default="数学")
    total_score: Mapped[float] = mapped_column(Float, default=100)
    my_score: Mapped[float] = mapped_column(Float, default=0)
    # 逐题：[{no, text, score, got_score, knowledge_points: []}]
    questions: Mapped[list] = mapped_column(JSON, default=list)
    # 分析结果：weak_points/trend/summary
    analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Workbook(Base):
    """练习册/教辅目录库：错题定位与反向推荐的数据基础。"""

    __tablename__ = "workbooks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    publisher: Mapped[str] = mapped_column(String(64), default="")
    # 目录：[{chapter, page, knowledge_points: []}]
    catalog: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class StudyPlan(Base):
    """学习计划（由排程算法基于知识图谱前置关系生成）。"""

    __tablename__ = "study_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128), default="")
    start_date: Mapped[date] = mapped_column(Date)
    days: Mapped[int] = mapped_column(Integer, default=7)
    # [{date, tasks: [{knowledge_point, action, detail, question_ids, workbook_ref, done, reason}]}]
    plan_data: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active/completed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AppSetting(Base):
    """键值设置（AI 后端配置等，网页可改，优先于 .env）。"""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
