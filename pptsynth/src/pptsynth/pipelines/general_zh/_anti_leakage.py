"""Shared anti-pre-disclosure patterns for broad_domain synthesis pipeline.

Base patterns cover all domains. Domain-specific patterns are appended via
DomainPack.anti_leakage_patterns (loaded from domain YAML packs) by
stages/stage2_task.py and verify.py.

Adapted from sinoconf_synth_rubrics_v3/_anti_leakage.py with additional
patterns for business/general-domain documents.
"""
from __future__ import annotations

import re

PRE_DISCLOSURE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # --- Core numeric patterns (all domains) ---
    (re.compile(r"(?<![.\d])\d+\.\d+\s*%"), "浮点百分比"),
    (
        re.compile(r"\d+(?:\.\d+)?%?\s*[，,]\s*\S+\s*为\s*\d+(?:\.\d+)?%?"),
        "中文数值比较",
    ),
    (
        re.compile(
            r"(?:提高|降低|增加|减少|增大|减小|升高|下降|提升|下滑|增长|缩减)了?\s*\d+(?:\.\d+)?\s*"
            r"(?:%|个百分点|℃|°C|kPa|MPa|mm|cm|m|kg|g|mg|μg|L|mL|mol|mmol|ppm|dB|亿|万|元)"
        ),
        "量化变化表述",
    ),
    (re.compile(r"[Pp]\s*[<>=]\s*0\.\d+"), "统计显著性值"),
    (re.compile(r"[Rr][²2]\s*[=＝]\s*0\.\d+"), "相关系数值"),
    (
        re.compile(r"[+\-]\s?\d+(?:\.\d+)?\s*(?:%|个百分点|℃|°C|kPa|MPa|mm|kg|g|mg|L|mL|dB|亿|万|元)"),
        "带符号增量",
    ),
    (re.compile(r"\d+(?:\.\d+)?\s*倍"), "倍数表达"),
    (
        re.compile(
            r"\d+\.\d+[%℃°]?\s*[~～\-–—]\s*\d+(?:\.\d+)?[%℃°]?"
            r"|\d+(?:\.\d+)?[%℃°]\s*[~～\-–—]\s*\d+(?:\.\d+)?[%℃°]?"
        ),
        "数值区间",
    ),
    # --- Comparative conclusions ---
    (
        re.compile(
            r"[一-鿿\w]+(?:优于|劣于|高于|低于|大于|小于|强于|弱于|好于|差于|多于|少于)[一-鿿\w]+"
            r"|[一-鿿\w]+比[一-鿿\w]+(?:提高|降低|增加|减少|增大|减小|升高|下降)了"
        ),
        "对比结论表述",
    ),
    (
        re.compile(
            r"(?:从高到低|从低到高|从大到小|从小到大|依次为|排序为|排名为)"
            r"|(?:最优|最佳|最高|最低|最大|最小)(?:的|为|是)\S+"
        ),
        "性能排名",
    ),
    # --- Business/financial metrics ---
    (
        re.compile(
            r"(?<![.\d])\d+(?:\.\d+)?\s*(?:亿元|万元|百万元|千万元|亿美元|万美元)\b"
        ),
        "金融数值",
    ),
    (
        re.compile(r"(?:GMV|营收|销售额|利润|净利润|增速|同比|环比)\s*(?:为|达|达到|超|破)\s*\d+"),
        "商业业绩数值",
    ),
    # --- Multiplier / enumerations ---
    (
        re.compile(
            r"(?:\S+\s*为\s*\d+(?:\.\d+)?[%℃°]?\s*[，,]\s*){2,}\S+\s*为\s*\d+(?:\.\d+)?[%℃°]?"
        ),
        "并列数值列举",
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


def get_domain_patterns(
    domain_anti_leakage: list[dict[str, str]],
) -> list[tuple[re.Pattern, str]]:
    """Compile domain-specific patterns from a DomainPack's anti_leakage_patterns list."""
    extra: list[tuple[re.Pattern, str]] = []
    for entry in domain_anti_leakage or []:
        pattern_str = entry.get("pattern")
        label = entry.get("label", "领域数值")
        if pattern_str:
            try:
                extra.append((re.compile(pattern_str), label))
            except re.error:
                pass
    return extra
