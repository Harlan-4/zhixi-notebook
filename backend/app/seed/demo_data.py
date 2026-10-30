"""演示数据：高一上学期（人教A版必修第一册）示例错题（含 AI 风格解析与变式题）、
两张试卷（构成进步趋势）、练习册示例目录。

日期均为相对 date.today() 动态生成，保证任意时间导入数据都"新鲜"。
"""
from datetime import date, timedelta

WORKBOOK_NAME = "同步练习册（高一上·示例）"


def build_demo_questions() -> list[dict]:
    today = date.today()
    return [
        {
            "subject": "数学",
            "grade": "高一",
            "question_type": "解答题",
            "question_text": "已知 $x<0$，求函数 $f(x)=x+\\dfrac{4}{x}$ 的最大值。",
            "my_answer": (
                "由基本不等式：$x+\\dfrac{4}{x}\\ge 2\\sqrt{x\\cdot\\dfrac{4}{x}}=4$，"
                "所以 $f(x)$ 的最小值是 4，最大值不存在。"
            ),
            "source_workbook": WORKBOOK_NAME,
            "source_location": "P45 T6",
            "status": "reviewing",
            "error_type": "概念不清",
            "review_count": 1,
            "review_stage": 0,
            "last_result": "fail",
            "next_review_at": today + timedelta(days=1),
            "analysis": {
                "correct_answer": "最大值为 $-4$，此时 $x=-2$",
                "solution_steps": [
                    "先检验条件：基本不等式 $a+b\\ge 2\\sqrt{ab}$ 要求 $a,b>0$（\"一正\"），而本题 $x<0$，不能直接使用。",
                    "取相反数化正：$-x>0$，对 $-f(x)=(-x)+\\dfrac{-4}{x}$ 使用基本不等式：$-f(x)\\ge 2\\sqrt{(-x)\\cdot\\dfrac{-4}{x}}=2\\sqrt{4}=4$。",
                    "即 $f(x)\\le -4$。",
                    "求等号条件：当且仅当 $-x=\\dfrac{-4}{x}$，即 $x^2=4$；又 $x<0$，故 $x=-2$。",
                    "所以当 $x=-2$ 时，$f(x)$ 取得最大值 $-4$。",
                ],
                "error_analysis": (
                    "学生忽略基本不等式的使用条件。$a+b\\ge 2\\sqrt{ab}$ 要求 $a,b$ 均为正数"
                    "（\"一正\"），本题 $x<0$ 直接套用，得到的 $\\sqrt{x\\cdot\\frac{4}{x}}$ 虽然等于 2，"
                    "但不等式 $a+b\\ge 2\\sqrt{ab}$ 对含负数的项不成立，结论方向完全错了。"
                    "负数情形的正确做法是先取相反数化为正数再用基本不等式。"
                ),
                "knowledge_points": ["基本不等式", "等式性质与不等式性质"],
                "cause_evidence": "confirmed",
                "diagnose_questions": [],
                "alt_explanations": [
                    {
                        "strategy": "生活类比",
                        "explanation": "把基本不等式想象成一架\"跷跷板\"：$a+b\\ge 2\\sqrt{ab}$ 这条规则，只有在两端\"都是正数\"时才成立，就像两个小朋友必须坐在同一边，跷跷板规律才玩得转。你的 $x$ 是负数——相当于有个小朋友坐到了反面，规则直接失效，所以算出来的\"最小值4\"是空中楼阁。正确做法是先把两个数\"翻到正数那边\"：取 $-x$ 和 $\\dfrac{-4}{x}$（都为正），套公式得 $-f(x)\\ge 2\\sqrt{(-x)\\cdot\\dfrac{-4}{x}}=4$，最后把不等号方向一翻（负负得反），$f(x)\\le -4$。记住口诀：\"一翻正、二套公式、三翻回\"，负数求最值就再也难不倒你了。",
                    },
                ],
                "tips": [
                    "口诀\"一正、二定、三相等\"：三个条件缺一不可，用之前逐条检查",
                    "遇到负数求最值，先取相反数化为正数，最后再把不等号方向反过来",
                    "求出最值后回代验证等号能否取到，并检查所得值是否符合题目要求（最大/最小）",
                ],
                "textbook_location": "高一上·必修第一册第2章 一元二次函数、方程和不等式",
            },
            "variants": [
                {
                    "type": "填步题",
                    "text": "已知 $x<0$，求函数 $f(x)=x+\\dfrac{9}{x}$ 的最大值。",
                    "steps": [
                        "因 $x<0$，基本不等式要求\"一正\"，先取相反数：$-f(x)=(-x)+\\dfrac{9}{-x}$，此时两项均为______。",
                        "由基本不等式：$-f(x)\\ge 2\\sqrt{(-x)\\cdot\\dfrac{9}{-x}}=$______。",
                        "即 $f(x)\\le$ ______。",
                        "求等号条件：当且仅当 $-x=\\dfrac{9}{-x}$，即 $x^2=9$，又 $x<0$，故 $x=$ ______。",
                        "所以 $f(x)$ 的最大值为______。",
                    ],
                    "answer": "最大值为 $-6$，此时 $x=-3$",
                    "solution": "$-f(x)=(-x)+\\dfrac{9}{-x}\\ge 2\\sqrt{9}=6$，即 $f(x)\\le -6$；等号当 $-x=3$ 即 $x=-3$ 时取得。",
                },
                {
                    "text": "已知 $x>0$，求函数 $f(x)=\\dfrac{x^2+3}{x}$ 的最小值。",
                    "difficulty": "基础",
                    "answer": "$2\\sqrt{3}$（当 $x=\\sqrt{3}$ 时取得）",
                    "solution": "$f(x)=x+\\dfrac{3}{x}$，因 $x>0$，由基本不等式 $f(x)\\ge 2\\sqrt{x\\cdot\\dfrac{3}{x}}=2\\sqrt{3}$，当且仅当 $x=\\dfrac{3}{x}$ 即 $x=\\sqrt{3}$ 时取等号。",
                },
                {
                    "text": "已知 $x>1$，求函数 $f(x)=x+\\dfrac{4}{x-1}$ 的最小值。",
                    "difficulty": "提高",
                    "answer": "最小值为 $5$（当 $x=3$ 时取得）",
                    "solution": "配凑：$f(x)=(x-1)+\\dfrac{4}{x-1}+1$。因 $x>1$，则 $x-1>0$，故 $f(x)\\ge 2\\sqrt{(x-1)\\cdot\\dfrac{4}{x-1}}+1=4+1=5$，当且仅当 $x-1=2$ 即 $x=3$ 时取等号。",
                },
            ],
        },
        {
            "subject": "数学",
            "grade": "高一",
            "question_type": "解答题",
            "question_text": (
                "已知集合 $A=\\{x\\mid x^2-3x+2=0\\}$，$B=\\{x\\mid ax-2=0,\\ x\\in \\mathbb{R}\\}$。"
                "若 $B\\subseteq A$，求实数 $a$ 的取值集合。"
            ),
            "my_answer": (
                "$A=\\{1,2\\}$。由 $B\\subseteq A$，$B$ 只能是 $\\{2\\}$，即 $2a-2=0$？"
                "解得 $a=1$；又检验 $a=2$ 时 $B=\\{1\\}$ 也满足。所以 $a=1$ 或 $a=2$。"
            ),
            "source_workbook": WORKBOOK_NAME,
            "source_location": "P12 T9",
            "status": "reviewing",
            "error_type": "概念不清",
            "review_count": 1,
            "review_stage": 1,
            "last_result": "pass",
            "next_review_at": today + timedelta(days=3),
            "analysis": {
                "correct_answer": "$a$ 的取值集合为 $\\{0,1,2\\}$",
                "solution_steps": [
                    "解方程 $x^2-3x+2=0$ 得 $A=\\{1,2\\}$。",
                    "由 $B\\subseteq A$，对 $B$ 分类讨论。① $B=\\varnothing$：方程 $ax-2=0$ 无解，当且仅当 $a=0$，满足题意；",
                    "② $B\\neq\\varnothing$（$a\\neq 0$）：$B=\\left\\{\\dfrac{2}{a}\\right\\}$，需 $\\dfrac{2}{a}\\in\\{1,2\\}$。",
                    "若 $\\dfrac{2}{a}=1$，则 $a=2$；若 $\\dfrac{2}{a}=2$，则 $a=1$。",
                    "综上，$a$ 的取值集合为 $\\{0,1,2\\}$。",
                ],
                "error_analysis": (
                    "学生漏掉了 $B=\\varnothing$ 的情形。空集是任何集合的子集——当 $a=0$ 时"
                    "$B=\\varnothing$，同样满足 $B\\subseteq A$。凡\"由含参数方程确定的集合是另一个"
                    "集合的子集\"，必须首先讨论集合为空集的情况，这是集合模块最典型的分类讨论陷阱。"
                ),
                "knowledge_points": ["集合间的基本关系", "集合的概念"],
                "cause_evidence": "confirmed",
                "tips": [
                    "见到\"B⊆A 且 B 中含参数\"，第一步就分\"B=∅\"与\"B≠∅\"两类讨论",
                    "记住：空集是任何集合的子集，是任何非空集合的真子集",
                    "a=0 时 ax=2 型方程无解，这是空集情形最常见的来源",
                ],
                "textbook_location": "高一上·必修第一册第1章 集合与常用逻辑用语",
            },
            "variants": [
                {
                    "type": "填步题",
                    "text": "已知 $A=\\{x\\mid x^2-5x+6=0\\}$，$B=\\{x\\mid ax-3=0,\\ x\\in\\mathbb{R}\\}$，若 $B\\subseteq A$，求实数 $a$ 的取值集合。",
                    "steps": [
                        "第一步，解出 $A=$ ______。",
                        "第二步，分类讨论：当 $a=$ ______ 时，$B=\\varnothing$，满足 $B\\subseteq A$；",
                        "第三步，当 $a\\neq 0$ 时，$B=\\left\\{\\dfrac{3}{a}\\right\\}$，需 $\\dfrac{3}{a}\\in A$，解得 $a=$ ______ 或 $a=$ ______；",
                        "综上，$a$ 的取值集合为 ______。",
                    ],
                    "answer": "$\\{0,\\ \\dfrac{3}{2},\\ 1\\}$",
                    "solution": "$A=\\{2,3\\}$。$a=0$ 时 $B=\\varnothing$ 满足；$a\\neq 0$ 时 $\\dfrac{3}{a}=2\\Rightarrow a=\\dfrac{3}{2}$，$\\dfrac{3}{a}=3\\Rightarrow a=1$。综上 $a\\in\\left\\{0,\\dfrac{3}{2},1\\right\\}$。",
                },
                {
                    "text": "已知 $A=\\{x\\mid x^2=4\\}$，$B=\\{x\\mid ax=2,\\ x\\in\\mathbb{R}\\}$，若 $B\\subseteq A$，求实数 $a$ 的取值集合。",
                    "difficulty": "基础",
                    "answer": "$\\{-1,\\ 0,\\ 1\\}$",
                    "solution": "$A=\\{-2,2\\}$。① $a=0$ 时 $B=\\varnothing$，满足；② $a\\neq 0$ 时 $B=\\left\\{\\dfrac{2}{a}\\right\\}$，令 $\\dfrac{2}{a}=2$ 得 $a=1$，令 $\\dfrac{2}{a}=-2$ 得 $a=-1$。综上 $a\\in\\{-1,0,1\\}$。",
                },
                {
                    "text": "已知 $A=\\{x\\mid x^2-4x+3=0\\}$，$B=\\{x\\mid mx-1=0,\\ x\\in\\mathbb{R}\\}$，若 $B\\subseteq A$，求实数 $m$ 的取值集合。",
                    "difficulty": "提高",
                    "answer": "$\\left\\{0,\\ \\dfrac{1}{3},\\ 1\\right\\}$",
                    "solution": "$A=\\{1,3\\}$。① $m=0$ 时 $B=\\varnothing$，满足；② $m\\neq 0$ 时 $B=\\left\\{\\dfrac{1}{m}\\right\\}$，令 $\\dfrac{1}{m}=1$ 得 $m=1$，令 $\\dfrac{1}{m}=3$ 得 $m=\\dfrac{1}{3}$。综上 $m\\in\\left\\{0,\\dfrac{1}{3},1\\right\\}$。",
                },
            ],
        },
        {
            "subject": "数学",
            "grade": "高一",
            "question_type": "解答题",
            "question_text": "计算：$\\left(\\dfrac{1}{4}\\right)^{-\\frac{1}{2}}+\\left(\\dfrac{1}{27}\\right)^{\\frac{2}{3}}$",
            "my_answer": "$\\dfrac{7}{3}$（把 $\\left(\\dfrac{1}{27}\\right)^{\\frac{2}{3}}$ 算成了 $\\dfrac{1}{3}$）",
            "source_workbook": WORKBOOK_NAME,
            "source_location": "P102 T2",
            "status": "mastered",
            "error_type": "概念不清",
            "review_count": 3,
            "review_stage": 3,
            "last_result": "pass",
            "next_review_at": None,
            "collected_at": today,
            "analysis": {
                "correct_answer": "$\\dfrac{19}{9}$",
                "solution_steps": [
                    "负指数幂：$\\left(\\dfrac{1}{4}\\right)^{-\\frac{1}{2}}=4^{\\frac{1}{2}}=\\sqrt{4}=2$。",
                    "分数指数幂：$\\dfrac{2}{3}$ 的分母是根指数、分子是幂指数，$\\left(\\dfrac{1}{27}\\right)^{\\frac{2}{3}}=\\left[\\left(\\dfrac{1}{3}\\right)^{3}\\right]^{\\frac{2}{3}}=\\left(\\dfrac{1}{3}\\right)^{2}=\\dfrac{1}{9}$。",
                    "相加：$2+\\dfrac{1}{9}=\\dfrac{19}{9}$。",
                ],
                "error_analysis": (
                    "分数指数幂 $a^{\\frac{m}{n}}=\\sqrt[n]{a^m}$ 中，分母 $n$ 是根指数、分子 $m$ 是幂指数。"
                    "学生只取了三次根却丢掉了平方，把 $\\left(\\dfrac{1}{27}\\right)^{\\frac{2}{3}}$ 算成"
                    "$\\dfrac{1}{3}$，属于对分数指数幂定义理解不清。"
                ),
                "knowledge_points": ["指数的运算", "指数"],
                "cause_evidence": "confirmed",
                "tips": [
                    "口诀\"分母开方，分子乘方\"：先开 $n$ 次方，再 $m$ 次方",
                    "底数是分数的负指数幂：先取倒数化正，再处理分数指数",
                    "把底数化成幂的形式（如 $27=3^3$）再运算，不易出错",
                ],
                "textbook_location": "高一上·必修第一册第4章 指数函数与对数函数",
            },
            "variants": None,
        },
        {
            "subject": "数学",
            "grade": "高一",
            "question_type": "解答题",
            "question_text": "计算：$\\log_2 8+\\log_3\\dfrac{1}{9}-\\lg 100$",
            "my_answer": "",
            "source_workbook": WORKBOOK_NAME,
            "source_location": "P110 T4",
            "status": "new",
            "error_type": "",
            "review_count": 0,
            "review_stage": 0,
            "last_result": "",
            "next_review_at": None,
            "analysis": None,
            "variants": None,
        },
    ]


def build_demo_workbook() -> dict:
    return {
        "name": WORKBOOK_NAME,
        "publisher": "示例数据",
        "catalog": [
            {"chapter": "第1章 集合与常用逻辑用语", "page": "P1-P30", "knowledge_points": ["集合的概念", "集合间的基本关系", "集合的基本运算", "充分条件与必要条件", "全称量词与存在量词"]},
            {"chapter": "第2章 一元二次函数、方程和不等式", "page": "P31-P60", "knowledge_points": ["等式性质与不等式性质", "基本不等式", "二次函数与一元二次方程、不等式"]},
            {"chapter": "第3章 函数的概念与性质", "page": "P61-P96", "knowledge_points": ["函数的概念", "函数的表示法", "函数的单调性", "函数的奇偶性", "幂函数", "函数的应用（一）"]},
            {"chapter": "第4章 指数函数与对数函数", "page": "P97-P136", "knowledge_points": ["指数", "指数的运算", "指数函数", "对数", "对数的运算", "对数函数", "不同函数增长的差异", "函数与方程", "函数模型的应用"]},
            {"chapter": "第5章 三角函数", "page": "P137-P172", "knowledge_points": ["任意角与弧度制", "三角函数的概念", "诱导公式", "三角函数的图象与性质", "三角恒等变换", "函数y=Asin(wx+φ)", "三角函数的应用"]},
        ],
    }


def _paper(title: str, days_ago: int, paper_type: str, items: list[tuple]) -> dict:
    questions = [
        {"no": str(i + 1), "text": t, "score": s, "got_score": g, "knowledge_points": kps}
        for i, (t, s, g, kps) in enumerate(items)
    ]
    return {
        "title": title,
        "exam_date": (date.today() - timedelta(days=days_ago)).isoformat(),
        "paper_type": paper_type,
        "subject": "数学",
        "total_score": sum(s for _, s, _, _ in items),
        "my_score": sum(g for _, _, g, _ in items),
        "questions": questions,
    }


def build_demo_papers() -> list[dict]:
    """两次考试构成"进步趋势"：74分 -> 82分，充要条件、二次不等式等知识点明显改善。"""
    yuekao = _paper(
        "高一上学期第一次月考", 40, "月考",
        [
            ("已知 $A=\\{1,2,3\\}$，$B=\\{2,3,4\\}$，求 $A\\cap B$（选择题）", 3, 3, ["集合的基本运算"]),
            ("\"$x>1$\"是\"$x^2>1$\"的什么条件（选择题）", 3, 0, ["充分条件与必要条件"]),
            ("命题\"所有素数都是奇数\"的否定（选择题）", 3, 3, ["全称量词与存在量词"]),
            ("集合 $\\{1,2,3\\}$ 的真子集个数（填空）", 4, 4, ["集合间的基本关系"]),
            ("比较 $2a$ 与 $a$ 的大小（按 $a$ 的符号讨论，填空）", 4, 4, ["等式性质与不等式性质"]),
            ("已知 $x>0$，则 $x+\\dfrac{9}{x}$ 的最小值为____（填空）", 4, 4, ["基本不等式"]),
            ("解不等式：$x^2-5x+6>0$", 8, 6, ["二次函数与一元二次方程、不等式"]),
            ("已知 $x>\\dfrac{1}{2}$，求 $f(x)=2x+\\dfrac{1}{2x-1}$ 的最小值", 8, 5, ["基本不等式"]),
            ("用定义证明：$f(x)=x+\\dfrac{1}{x}$ 在 $(0,1)$ 上单调递减", 10, 6, ["函数的单调性"]),
            ("某商品进价每件40元，售价50元时每月卖500件；每涨价1元少卖10件，求月利润最大时的售价", 12, 4, ["函数的应用（一）", "二次函数与一元二次方程、不等式"]),
            ("分段函数：$f(x)=\\begin{cases}x+1, & x\\le 0\\\\ x^2, & x>0\\end{cases}$，求 $f(f(-2))$ 与值域", 12, 10, ["函数的表示法"]),
            ("判断 $f(x)=x^3+x$ 的奇偶性并说明理由", 10, 7, ["函数的奇偶性"]),
            ("已知幂函数 $f(x)=x^a$ 图象过点 $(2,8)$，求解析式", 9, 9, ["幂函数"]),
            ("求函数 $f(x)=\\sqrt{x+1}+\\dfrac{1}{2-x}$ 的定义域", 10, 9, ["函数的概念"]),
        ],
    )
    qizhong = _paper(
        "高一上学期期中考试", 10, "期中",
        [
            ("已知 $A=\\{x\\mid 1\\le x<3\\}$，$B=\\{2,3,4\\}$，求 $A\\cap B$（选择题）", 3, 3, ["集合的基本运算"]),
            ("\"$x>2$\"是\"$x>1$\"的什么条件（选择题）", 3, 3, ["充分条件与必要条件"]),
            ("计算：$\\left(\\dfrac{1}{8}\\right)^{-\\frac{2}{3}}$（选择题）", 3, 3, ["指数的运算"]),
            ("集合 $\\{a,b,c,d\\}$ 的子集个数（填空）", 4, 3, ["集合间的基本关系"]),
            ("计算：$\\log_3 27-\\log_2 \\dfrac{1}{4}$（填空）", 4, 3, ["对数的运算"]),
            ("已知 $x>1$，则 $x+\\dfrac{1}{x-1}$ 的最小值为____（填空）", 4, 4, ["基本不等式"]),
            ("解不等式：$2x^2-7x+3\\le 0$", 8, 8, ["二次函数与一元二次方程、不等式"]),
            ("计算：$\\lg 25+\\lg 4+\\log_5 \\sqrt[3]{25}$", 8, 6, ["对数的运算"]),
            ("已知指数函数 $f(x)=a^x$ 过点 $(1,3)$，讨论其单调性并比较 $f(0.3)$ 与 $f(0.5)$", 10, 8, ["指数函数"]),
            ("某商店销售水果，进价10元/千克，售价16元/千克时每天卖60千克；每降价1元多卖20千克，求日利润最大时的售价", 12, 8, ["函数的应用（一）", "二次函数与一元二次方程、不等式"]),
            ("出租车计费：3千米内8元，超出部分每千米2.4元，写出车费关于里程的分段函数并求10千米车费", 12, 10, ["函数的表示法"]),
            ("已知 $f(x)$ 是奇函数且在 $[0,+\\infty)$ 上单调递增，比较 $f(-2)$ 与 $f(-3)$ 的大小", 10, 8, ["函数的奇偶性", "函数的单调性"]),
            ("已知幂函数 $f(x)=x^{a}$ 的图象经过点 $(4,2)$，求 $f(9)$", 9, 8, ["幂函数"]),
            ("求函数 $f(x)=x^2-2x+3$ 在 $[0,3]$ 上的最大值与最小值", 10, 7, ["函数的概念", "函数的单调性"]),
        ],
    )
    return [yuekao, qizhong]
