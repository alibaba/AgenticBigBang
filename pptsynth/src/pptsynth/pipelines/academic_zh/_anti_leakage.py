"""Shared anti-pre-disclosure patterns for sinoconf synthesis pipeline.

Single source of truth for regex patterns that detect pre-disclosed
quantitative values in instructions.md Section 1. Used by:
- stages/stage2_task.py (inline static checks after generation)
- verify.py (batch post-hoc validation)

v3: Extracted from stage2_task.py into shared module per implementation plan.
    Enhanced with agriculture/forestry domain units.
"""
from __future__ import annotations

import re

PRE_DISCLOSURE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # --- Core numeric patterns (all domains) ---
    # Floating-point percentage (language-agnostic; no \b — CJK chars break word boundary)
    (re.compile(r"(?<![.\d])\d+\.\d+\s*%"), "浮点百分比"),
    # Chinese numerical comparison: X为90.3%，Y为87.9%
    (
        re.compile(r"\d+(?:\.\d+)?%?\s*[，,]\s*\S+\s*为\s*\d+(?:\.\d+)?%?"),
        "中文数值比较",
    ),
    # Quantified change: 提高了3.8%、降低了12.5℃
    (
        re.compile(
            r"(?:提高|降低|增加|减少|增大|减小|升高|下降|提升|降低)了?\s*\d+(?:\.\d+)?\s*(?:%|个百分点|℃|°C|kPa|MPa|mm|cm|m|kg|g|mg|μg|L|mL|mol|mmol|ppm|dB|hm²|t/hm²|kg/hm²|m³/hm²|g/kg|mg/kg)"
        ),
        "量化变化表述",
    ),
    # P-value / significance level
    (re.compile(r"[Pp]\s*[<>=]\s*0\.\d+"), "统计显著性值"),
    # Specific parameter assignment: 压缩比为15:1、转速为1500 r/min
    (
        re.compile(
            r"(?:压缩比|转速|温度|浓度|含量|剂量|密度|比例|流量|压力|功率|扭矩|速度|质量|体积|面积|长度|宽度|高度|深度|厚度|直径|半径|角度|频率|电压|电流|电阻|产量|郁闭度|覆盖度|含水率|孔隙度|pH值?|有机质|全氮|全磷|全钾|碱解氮|速效磷|速效钾|阳离子交换量)\s*(?:为|=|：|:)\s*\d+(?:\.\d+)?\s*\S{0,10}"
        ),
        "具体参数赋值",
    ),
    # R-squared and correlation coefficients
    (re.compile(r"[Rr][²2]\s*[=＝]\s*0\.\d+"), "相关系数值"),
    # Asymptotic complexity (occasionally in engineering papers)
    (re.compile(r"\bO\([^)]+\)"), "渐近复杂度表达式"),
    # Signed delta with units: +3.8个百分点、-12.5%
    (
        re.compile(r"[+\-]\s?\d+(?:\.\d+)?\s*(?:%|个百分点|℃|°C|kPa|MPa|mm|kg|g|mg|L|mL|dB|hm²|t/hm²)"),
        "带符号增量",
    ),
    # Multiplier expressions: 为对照组的2.3倍、增加了1.5倍
    (
        re.compile(r"\d+(?:\.\d+)?\s*倍"),
        "倍数表达",
    ),
    # Range expressions: 含量在12.5%~18.3%之间 (require decimal or unit on at least one side)
    (
        re.compile(r"\d+\.\d+[%℃°]?\s*[~～\-–—]\s*\d+(?:\.\d+)?[%℃°]?|\d+(?:\.\d+)?[%℃°]\s*[~～\-–—]\s*\d+(?:\.\d+)?[%℃°]?"),
        "数值区间",
    ),
    # --- Engineering domain patterns (v2+) ---
    # Comparative conclusions: A方案的热效率优于B方案, X比Y降低了
    (
        re.compile(
            r"[一-鿿\w]+(?:优于|劣于|高于|低于|大于|小于|强于|弱于|好于|差于|多于|少于)[一-鿿\w]+"
            r"|[一-鿿\w]+比[一-鿿\w]+(?:提高|降低|增加|减少|增大|减小|升高|下降)了"
        ),
        "对比结论表述",
    ),
    # Ranking / ordering: 性能从高到低依次为A>B>C, 最优为X
    (
        re.compile(
            r"(?:从高到低|从低到高|从大到小|从小到大|依次为|排序为|排名为)"
            r"|(?:最优|最佳|最高|最低|最大|最小)(?:的|为|是)\S+"
        ),
        "性能排名",
    ),
    # Precise engineering parameters without prefix: 400K, 0.5MPa, 1500r/min
    (
        re.compile(
            r"(?<![.\d])\d+(?:\.\d+)?\s*(?:K|MPa|kPa|bar|atm|r/min|rpm|Hz|kHz|MW|kW|W|kN|N·m|Nm|mol/L|mg/L|μm|nm|hm²|t/hm²|kg/hm²|m³/hm²|g/kg|mg/kg|μg/g|cmol/kg)\b"
            r"|[+-]?\d+(?:\.\d+)?°?\s*(?:CA|ATDC|BTDC|ABDC|BBDC)"
        ),
        "工程参数精确值",
    ),
    # Formula parameter assignment: 当λ=1.2时, 设n=1500
    (
        re.compile(
            r"(?:当|设|令|取|若)\s*[A-Za-zα-ωΑ-Ωλμεδσρφψθ]\s*[=＝]\s*\d+(?:\.\d+)?"
        ),
        "公式参数赋值",
    ),
    # Parallel enumeration of 3+ values: A为X%, B为Y%, C为Z%
    (
        re.compile(
            r"(?:\S+\s*为\s*\d+(?:\.\d+)?[%℃°]?\s*[，,]\s*){2,}\S+\s*为\s*\d+(?:\.\d+)?[%℃°]?"
        ),
        "并列数值列举",
    ),
    # Optimum point / peak declaration with specific condition values
    (
        re.compile(
            r"(?:在|当)\s*\S{2,20}(?:为|=|＝)\s*\d+(?:\.\d+)?\S{0,8}(?:时|条件下)\s*(?:达到|取得|出现|获得)\s*(?:最大值|最小值|最优|最佳|峰值|最高|最低)"
        ),
        "最优点声明",
    ),
]

FORBIDDEN_META_TERMS: list[str] = [
    "PPTSynth",
    "pptsynth",
    "PPTSYNTH",
    "self-check",
    "Self-check",
    "self check",
    "as required to satisfy",
    "自查",
    "自检",
    "为满足评分要求",
    "为满足评分标准",
    "根据评分细则",
    "按照评分标准",
]
