"""错题服务：AI 识题、错因解析、举一反三、错因追问对话、复习打卡（艾宾浩斯间隔）。"""
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from ..models import Question
from . import ai_client
from .knowledge import normalize_kps, point_map

REVIEW_INTERVALS = [1, 3, 7]  # 天

RECOGNIZE_PROMPT = """你是初高中数学老师。请识别图片中的数学题目，只输出一个JSON对象：
{
  "question_text": "题目完整文字（数学式子用LaTeX，行内公式用$...$包裹）",
  "subject": "数学",
  "grade": "七年级|八年级|九年级|高一|高二|高三 之一（按题目内容推断）",
  "question_type": "选择题|填空题|解答题 之一",
  "options": ["A. ...", "B. ...", "C. ...", "D. ..."]（仅选择题有，其他为空数组）,
  "my_answer_visible": "图片中可见的学生作答/痕迹，没有则为空字符串"
}
输出硬性要求：直接输出上述 JSON 对象本身，第一字符必须是"{"；禁止使用 markdown 代码块（```）、禁止任何解释、注释或多余文字。所有字段必须为双引号字符串或数组，字符串内不得出现未转义的英文双引号。"""

ANALYZE_PROMPT = """你是经验丰富的初高中数学老师。学生做错了一道题，请给出完整解析，只输出一个JSON对象：
{
  "correct_answer": "最终答案",
  "solution_steps": ["步骤1（含关键算式，LaTeX）", "步骤2", "..."],
  "error_type": "概念不清|计算失误|审题错误|方法未掌握|其他 之一",
  "cause_evidence": "confirmed|inferred 之一",
  "error_analysis": "错因分析：指出具体哪一步出错、为什么错、暴露了什么知识漏洞",
  "diagnose_questions": ["用于向学生确认真实错因的追问1", "追问2"],
  "knowledge_points": ["教材标准知识点名称", "..."],
  "tips": ["避免再犯的提醒1", "提醒2"]
}
cause_evidence 规则（借鉴 good-learning-skill：错因必须有证据）：
- 学生作答清晰暴露了具体错误 → "confirmed"，此时 diagnose_questions 为空数组；
- 未提供作答、或作答不足以定位真实原因 → 必须填 "inferred"，error_analysis 开头注明"（推测错因）"，
  并在 diagnose_questions 中给出1~2条面向学生的诊断性追问（如"你当时第二步是怎么算的？"），不要替学生编造错因。
knowledge_points 请使用教材章节的标准知识点名称（高中示例如"基本不等式"、"函数的单调性"，初中示例如"因式分解"、"二次函数的图象与性质"）。"""

VARIANTS_PROMPT = """基于下面的原题与错因分析，按"四步教学法"设计举一反三练习，只输出一个JSON对象：
{
  "steps_problem": {
    "type": "填步题",
    "text": "与原题同构的题目（考查同一易错点，但数字/情境不同）",
    "steps": ["已给出的解题步骤…", "……______……（挖空的关键步骤）", "后续步骤…"],
    "answer": "最终答案",
    "solution": "完整解题过程（供完成后对照）"
  },
  "variants": [
    {"text": "变式题1（数学式子用LaTeX）", "difficulty": "基础", "answer": "最终答案", "solution": "简要解题过程"},
    {"text": "变式题2", "difficulty": "提高", "answer": "最终答案", "solution": "简要解题过程"}
  ]
}
设计要求：
- 填步题：解法框架完整给出，但把 2~3 个关键步骤（如条件检验、公式使用、求等号条件）替换为 ______ 让学生补全；挖空应针对学生的易错环节；
- 变式题：在填步题基础上独立完成，一道基础一道提高，数字与原题、与填步题都不同。"""


def recognize_question(image_bytes: bytes, mime: str = "image/jpeg") -> dict:
    """识题：图片 -> 结构化题目草稿（不入库，由用户确认修改后保存）。"""
    return ai_client.vision_json(RECOGNIZE_PROMPT, image_bytes, mime)


def _textbook_location(db: Session, kps: list[str]) -> str:
    pmap = point_map(db)
    chapters = [pmap[k].chapter for k in kps if k in pmap]
    return "；".join(dict.fromkeys(chapters))


def analyze_question(db: Session, q: Question) -> Question:
    """AI 解析：正确解法 + 错因（带证据分级） + 知识点 + 教材章节定位。"""
    user = (
        f"【题目】{q.question_text}\n"
        f"【学生作答】{q.my_answer.strip() or '（未提供）'}\n"
        f"【年级】{q.grade or '中学'}"
    )
    data = ai_client.chat_json(
        [{"role": "user", "content": ANALYZE_PROMPT + "\n\n" + user}]
    )
    kps = normalize_kps(db, data.get("knowledge_points"))
    cause_evidence = data.get("cause_evidence")
    if cause_evidence not in ("confirmed", "inferred"):
        # 模型未按约定输出时，按是否有作答兜底判定
        cause_evidence = "confirmed" if q.my_answer.strip() else "inferred"
    q.analysis = {
        "correct_answer": data.get("correct_answer", ""),
        "solution_steps": data.get("solution_steps") or [],
        "error_analysis": data.get("error_analysis", ""),
        "cause_evidence": cause_evidence,
        "diagnose_questions": data.get("diagnose_questions") or [],
        "knowledge_points": kps,
        "tips": data.get("tips") or [],
        "textbook_location": _textbook_location(db, kps),
    }
    q.error_type = data.get("error_type", "其他")
    if q.status == "new":
        q.status = "reviewing"
    db.commit()
    db.refresh(q)
    return q


def generate_variants(db: Session, q: Question) -> Question:
    """举一反三（四步教学法）：同构填步题 -> 基础/提高变式，统一存入 variants 列表。"""
    analysis = q.analysis or {}
    user = (
        f"【原题】{q.question_text}\n"
        f"【学生作答】{q.my_answer or '无'}\n"
        f"【错因】{analysis.get('error_analysis') or q.error_type or '未知'}\n"
        f"【涉及知识点】{', '.join(analysis.get('knowledge_points') or []) or '未知'}"
    )
    data = ai_client.chat_json(
        [{"role": "user", "content": VARIANTS_PROMPT + "\n\n" + user}]
    )
    items = []
    steps_problem = data.get("steps_problem")
    if isinstance(steps_problem, dict) and steps_problem.get("text"):
        steps_problem.setdefault("type", "填步题")
        items.append(steps_problem)
    variants = data.get("variants") or []
    for v in variants:
        if isinstance(v, dict) and v.get("text"):
            v.setdefault("type", "变式")
            items.append(v)
    q.variants = items
    db.commit()
    db.refresh(q)
    return q


def review_question(q: Question, result: str) -> bool:
    """复习打卡：pass 沿 1/3/7 天间隔推进，三次通过转为已掌握（收服）；fail 回炉。

    返回 just_collected：本次打卡是否触发"转为已掌握"的收服时刻。
    """
    if result not in ("pass", "fail"):
        raise ValueError("result 必须是 pass 或 fail")
    q.review_count += 1
    q.last_result = result
    today = date.today()
    just_collected = False
    if result == "pass":
        q.review_stage += 1
        if q.review_stage >= len(REVIEW_INTERVALS):
            q.status = "mastered"
            q.next_review_at = None
            if q.collected_at is None:
                q.collected_at = today
            just_collected = True
        else:
            q.status = "reviewing"
            q.next_review_at = today + timedelta(days=REVIEW_INTERVALS[q.review_stage - 1])
    else:
        q.review_stage = 0
        q.status = "reviewing"
        q.next_review_at = today + timedelta(days=1)
        q.collected_at = None  # 已收服的题回炉则收回徽章
    return just_collected


REEXPLAIN_PROMPT = """你是一名初高中数学老师。学生对之前的讲解说"没听懂"，请换一个策略重新讲解这道题，只输出一个JSON对象：
{
  "strategy": "所用策略名称（如：回到定义/生活类比/拆小步骤/从错误倒推/考试视角）",
  "explanation": "完整重讲内容（可含LaTeX，行内公式用$...$），务必与之前的讲解思路明显不同，300-500字"
}
可选策略（学生已用过的请避开）：
- 回到定义：退回概念定义，从最基础重新搭建
- 生活类比：用生活场景做类比（如天平、分蛋糕、行程）
- 拆小步骤：拆成更小的步骤，每一步只做一个动作并说明为什么
- 从错误倒推：从学生出错的那一步出发，倒推正确思路
- 考试视角：总结这类题的通法和考试时如何下手"""

CHECK_ANSWER_PROMPT = """你是一名初高中数学老师，正在批改学生重做后的答案。只输出一个JSON对象：
{
  "correct": true或false,
  "partial": "完全正确|思路对计算有误|方法错误|部分正确 之一",
  "feedback": "正确则一句话肯定并鼓励；错误则温和指出大概错在哪一步、给一个提示（不要直接给完整解答）"
}
注意：学生答案与参考答案数学等价（形式不同、约分方式不同）也算正确。"""


def reexplain_question(db: Session, q: Question, style: str = "") -> Question:
    """换种讲法：按不同策略重讲，追加到 analysis.alt_explanations（最多保留6条）。"""
    analysis = q.analysis or {}
    used = [a.get("strategy") for a in (analysis.get("alt_explanations") or []) if a.get("strategy")]
    user = (
        f"【题目】{q.question_text}\n"
        f"【学生作答】{q.my_answer or '无'}\n"
        f"【之前讲解的错因分析】{(analysis.get('error_analysis') or '')[:200]}\n"
        f"【已用过的策略】{'、'.join(used) if used else '无'}"
    )
    if style:
        user += f"\n【请本次采用策略】{style}"
    data = ai_client.chat_json([{"role": "user", "content": REEXPLAIN_PROMPT + "\n\n" + user}])
    entry = {
        "strategy": data.get("strategy") or (style or "换种讲法"),
        "explanation": data.get("explanation", ""),
    }
    alts = analysis.setdefault("alt_explanations", [])
    alts.append(entry)
    if len(alts) > 6:
        del alts[: len(alts) - 6]
    q.analysis = analysis
    flag_modified(q, "analysis")  # 就地修改 JSON 后必须显式标记，否则不落库
    db.commit()
    db.refresh(q)
    return q


def check_answer(q: Question, answer: str) -> dict:
    """答案核验：AI 批改学生重做答案（数学等价也算对）。"""
    user = (
        f"【题目】{q.question_text}\n"
        f"【参考答案】{q.analysis.get('correct_answer')}\n"
        f"【学生答案】{answer}"
    )
    return ai_client.chat_json([{"role": "user", "content": CHECK_ANSWER_PROMPT + "\n\n" + user}])


DIAGNOSE_CHAT_PROMPT = """你是经验丰富的初高中数学老师，正在通过一对一追问确认学生做错这道题的真实错因。
当前AI解析给出的是推测错因，你的任务是通过对话收集证据。只输出一个JSON对象：
{
  "reply": "回应学生的话（口语化、简短、以鼓励为主）；证据足够时改为简短的确认与点拨",
  "concluded": true或false,
  "error_type": "概念不清|计算失误|审题错误|方法未掌握|其他 之一（仅concluded为true时必填）",
  "cause_summary": "一两句确认后的错因结论（仅concluded为true时必填）"
}
规则：
- 每轮 reply 末尾最多追问 1 个问题，问完就等学生回答，不要连珠炮；
- 学生回答暴露了具体错误环节（说得出错在哪一步、为什么错）即可 concluded，不要无休止追问；
- 学生回答模糊时换个角度再问一次；三轮后仍模糊，就按现有信息 concluded，并在 cause_summary 注明依据有限；
- cause_summary 要写清"具体错在哪一步、为什么"，不要只写大类名词。"""

DIAGNOSE_CHAT_LIMIT = 30    # analysis.diagnose_chat 最多保留的条数
DIAGNOSE_CHAT_CONTEXT = 10  # 每次请求带给 AI 的最近对话条数
ERROR_TYPES = ("概念不清", "计算失误", "审题错误", "方法未掌握", "其他")



QA_CHAT_PROMPT = """你是耐心的初高中学科老师。学生刚看完这道错题的 AI 解析，还有没看懂的地方，正在向你提问。
回答要求：
1. 只回答与本题目、本题解法或相关知识点有关的疑问；一次只讲清楚一个点，语气口语化、鼓励为主。
2. 学生已看过解题步骤，回答时可直接引用步骤编号（如"第 2 步"），不要整题重讲。
3. 公式和算式一律用 $...$ 的 LaTeX 书写；一次回答控制在 150 字以内，宁可留一个追问点让学生继续问。
4. 学生的问题太笼统时，先给一句话直觉解释，再反问确认他卡在哪一步。
5. 若问题与本题目完全无关，简短回应并把话题拉回这道题；若学生表示已看懂，给一句肯定并建议下一步（重做变式/复习相邻知识点）。
6. 只输出回答正文，不要输出 JSON、前缀或任何多余解释。"""
QA_CHAT_LIMIT = 30    # analysis.qa_chat 最多保留的条数
QA_CHAT_CONTEXT = 10  # 每次请求带给 AI 的最近对话条数


def qa_chat_question(db: Session, q: Question, message: str) -> dict:
    """讲解答疑对话：学生就本题解析中没看懂的地方向 AI 提问，AI 用口语讲清。

    对话历史存 q.analysis.qa_chat（无独立表）；先调 AI 后写库，失败不落半截状态。
    """
    analysis = q.analysis or {}
    if not analysis:
        raise ValueError("请先进行 AI 解析，再向 AI 提问")
    message = (message or "").strip()
    if not message:
        raise ValueError("问题内容不能为空")

    history = list(analysis.get("qa_chat") or [])
    recent = history[-QA_CHAT_CONTEXT:]
    convo = "\n".join(
        f"{'学生' if h.get('role') == 'student' else '老师'}：{h.get('text', '')}" for h in recent
    )
    steps = "\n".join(str(x) for x in (analysis.get("solution_steps") or []))[:800]
    user = (
        f"【题目】{q.question_text}\n"
        f"【学生作答】{q.my_answer.strip() or '（未提供）'}\n"
        f"【正确答案】{(analysis.get('correct_answer') or '')[:200]}\n"
        f"【解题步骤】\n{steps or '（无）'}\n"
        f"【错因分析】{(analysis.get('error_analysis') or '')[:200]}\n"
        f"【最近的对话】\n{convo or '（尚无对话）'}\n"
        f"【学生本轮提问】{message}"
    )
    reply = ai_client.chat_text([{"role": "user", "content": QA_CHAT_PROMPT + "\n\n" + user}])
    if not reply:
        reply = "这个问题很关键！换个说法：你可以先告诉我，你是从第几步开始觉得不跟上的？"
    ts = datetime.now().strftime("%m-%d %H:%M")
    history += [
        {"role": "student", "text": message, "ts": ts},
        {"role": "ai", "text": reply, "ts": ts},
    ]
    if len(history) > QA_CHAT_LIMIT:
        del history[: len(history) - QA_CHAT_LIMIT]
    analysis["qa_chat"] = history
    q.analysis = analysis
    flag_modified(q, "analysis")  # 就地修改 JSON 后必须显式标记，否则不落库
    db.commit()
    db.refresh(q)
    return {"reply": reply, "chat": analysis["qa_chat"]}


def diagnose_chat_question(db: Session, q: Question, message: str) -> dict:
    """错因追问对话：学生回答诊断追问，AI 收集证据，证据足够时回写确认错因。

    对话历史存 q.analysis.diagnose_chat（无独立表）；先调 AI 后写库，失败不落半截状态。
    """
    analysis = q.analysis or {}
    if not analysis:
        raise ValueError("请先进行 AI 解析，再进行错因对话")
    message = (message or "").strip()
    if not message:
        raise ValueError("回复内容不能为空")

    history = list(analysis.get("diagnose_chat") or [])
    recent = history[-DIAGNOSE_CHAT_CONTEXT:]
    convo = "\n".join(
        f"{'学生' if h.get('role') == 'student' else '老师'}：{h.get('text', '')}" for h in recent
    )
    user = (
        f"【题目】{q.question_text}\n"
        f"【学生作答】{q.my_answer.strip() or '（未提供）'}\n"
        f"【当前推测错因】{(analysis.get('error_analysis') or '')[:300]}\n"
        f"【待确认的诊断问题】{'；'.join(analysis.get('diagnose_questions') or []) or '无'}\n"
        f"【当前错因分类】{q.error_type or '未知'}\n"
        f"【最近的对话】\n{convo or '（尚无对话）'}\n"
        f"【学生本轮回答】{message}"
    )
    data = ai_client.chat_json([{"role": "user", "content": DIAGNOSE_CHAT_PROMPT + "\n\n" + user}])

    reply = str(data.get("reply") or "").strip() or "好的，能再具体说说当时是怎么想的吗？"
    concluded = bool(data.get("concluded"))
    ts = datetime.now().strftime("%m-%d %H:%M")
    history += [
        {"role": "student", "text": message, "ts": ts},
        {"role": "ai", "text": reply, "ts": ts},
    ]
    if len(history) > DIAGNOSE_CHAT_LIMIT:
        del history[: len(history) - DIAGNOSE_CHAT_LIMIT]

    result = {"reply": reply, "concluded": concluded}
    if concluded:
        error_type = str(data.get("error_type") or "").strip()
        if error_type in ERROR_TYPES:
            q.error_type = error_type
            result["error_type"] = error_type
        cause_summary = str(data.get("cause_summary") or "").strip()
        if cause_summary:
            base = analysis.get("error_analysis") or ""
            analysis["error_analysis"] = (base + ("\n\n" if base else "") + "【对话确认】" + cause_summary)[:800]
            result["cause_summary"] = cause_summary
        analysis["cause_evidence"] = "confirmed"
    analysis["diagnose_chat"] = history
    q.analysis = analysis
    flag_modified(q, "analysis")  # 就地修改 JSON 后必须显式标记，否则不落库
    db.commit()
    db.refresh(q)
    result["chat"] = analysis["diagnose_chat"]
    return result
