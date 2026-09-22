"""Domain pack loader for the broad_domain_synth pipeline.

Loads and merges:
  domains/<primary>/_base.yaml  — primary-level shared context
  domains/<primary>/<secondary>.yaml  — secondary-level overrides

Returns a DomainPack dataclass used by prompt_compose.py to inject
domain context into each stage's system prompt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # pyyaml >= 6

_DOMAINS_DIR = Path(__file__).resolve().parent / "domains"

# Canonical Chinese → directory name mapping (handles spaces/slashes)
_PRIMARY_DIR_MAP: dict[str, str] = {
    "科技互联网": "科技互联网",
    "科技/互联网": "科技互联网",
    "医疗健康": "医疗健康",
    "法律合规": "法律合规",
    "政务党建": "政务党建",
    "政务/党建": "政务党建",
    "房地产建筑": "房地产建筑",
    "房地产/建筑": "房地产建筑",
    "汽车制造": "汽车制造",
    "汽车/制造": "汽车制造",
    "文旅餐饮": "文旅餐饮",
    "文旅/餐饮": "文旅餐饮",
    "人力行政": "人力行政",
    "人力/行政": "人力行政",
    "电商零售": "电商零售",
    "电商/零售": "电商零售",
    "环保能源": "环保能源",
    "环保/能源": "环保能源",
    "通信电子": "通信电子",
    "通信/电子": "通信电子",
    "文学人文历史": "文学人文历史",
    "文学/人文/历史": "文学人文历史",
    "体育运动": "体育运动",
    "体育/运动": "体育运动",
    "农业食品": "农业食品",
    "农业/食品": "农业食品",
    "个人生活": "个人生活",
    "个人/生活": "个人生活",
    "个人/生活场景": "个人生活",
    # --- unified_domain_synth: 新增职能型一级领域（来自 2号业务职能 + 3号任务场景）---
    "财务金融": "财务金融",
    "财务/金融": "财务金融",
    "销售市场": "销售市场",
    "销售/市场": "销售市场",
    "运营供应链": "运营供应链",
    "运营/供应链": "运营供应链",
    "战略咨询": "战略咨询",
    "战略/咨询": "战略咨询",
    "项目管理": "项目管理",
    "客户服务": "客户服务",
    "媒体新闻": "媒体新闻",
    "媒体/新闻": "媒体新闻",
    "教育培训": "教育培训",
    "教育/培训": "教育培训",
}


@dataclass
class DomainPack:
    primary: str
    secondary: str
    document_type_label: str = ""
    reading_hints: str = ""
    domain_terminology: list[str] = field(default_factory=list)
    anti_leakage_patterns: list[dict[str, str]] = field(default_factory=list)
    title_slide_fields: list[str] = field(default_factory=list)
    document_categories: list[str] = field(default_factory=list)

    def context_text(self) -> str:
        """Render the domain context section that gets appended to base prompts."""
        lines: list[str] = [
            "---",
            "",
            "## 领域上下文（Domain Context — 由管线自动注入）",
            "",
            f"**一级领域：** {self.primary}",
            f"**文档类型：** {self.secondary} — {self.document_type_label or self.secondary}",
            "",
        ]
        if self.reading_hints:
            lines += ["**本文档类型的阅读要点：**", ""]
            for ln in self.reading_hints.strip().splitlines():
                lines.append(f"> {ln}" if ln.strip() else ">")
            lines.append("")
        if self.domain_terminology:
            lines += ["**领域术语参考：**", ""]
            lines.append("、".join(self.domain_terminology[:20]))
            lines.append("")
        if self.title_slide_fields:
            lines += ["**标题页字段（Stage 2 应包含）：**", ""]
            for f_ in self.title_slide_fields:
                lines.append(f"- `{f_}`")
            lines.append("")
        if self.anti_leakage_patterns:
            lines += ["**领域特定反泄露警示（Section 1 禁止预泄露以下类型的具体数值/结论）：**", ""]
            for pat in self.anti_leakage_patterns:
                label = pat.get("label", "")
                lines.append(f"- {label}")
            lines.append("")
        return "\n".join(lines)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _primary_dir(primary: str) -> str:
    return _PRIMARY_DIR_MAP.get(primary, primary)


def load(primary: str, secondary: str) -> DomainPack:
    """Load and merge base + secondary YAML packs into a DomainPack."""
    pdir = _primary_dir(primary)
    base_path = _DOMAINS_DIR / pdir / "_base.yaml"
    sec_path = _DOMAINS_DIR / pdir / f"{secondary}.yaml"

    base = _load_yaml(base_path)
    sec = _load_yaml(sec_path)

    # Merge: secondary fields override base where present
    terminology: list[str] = list(base.get("domain_terminology") or [])
    if sec.get("extra_terminology"):
        terminology.extend(sec["extra_terminology"])

    anti_leakage: list[dict[str, str]] = list(base.get("anti_leakage_patterns") or [])
    if sec.get("extra_anti_leakage_patterns"):
        anti_leakage.extend(sec["extra_anti_leakage_patterns"])

    title_fields: list[str] = (
        sec.get("title_slide_fields")
        or base.get("title_slide_fields")
        or ["文档标题:", "作者:", "单位:", "场合:"]
    )

    reading_hints = sec.get("reading_hints") or base.get("reading_hints_base") or ""

    return DomainPack(
        primary=primary,
        secondary=secondary,
        document_type_label=sec.get("document_type_label") or secondary,
        reading_hints=reading_hints,
        domain_terminology=terminology,
        anti_leakage_patterns=anti_leakage,
        title_slide_fields=title_fields,
        document_categories=base.get("document_categories") or [],
    )


def load_for_paper(primary: str, secondary: str) -> DomainPack:
    """Convenience wrapper used by synth_batch.py."""
    return load(primary, secondary)
