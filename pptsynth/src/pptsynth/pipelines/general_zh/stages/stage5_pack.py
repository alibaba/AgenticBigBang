"""Stage 5: Pack — pure Python, no LLM.

Produces generation_task/statistics.yaml and case_status.json.
Records domain/sub_domain/document_type_label from DomainPack.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pptsynth.pdf_utils import page_count

from ._runner import StageOutcome
from ..domain_registry import DomainPack


@dataclass
class _PackResult:
    issues: list[str]
    stats: dict


def _coarse_token_estimate(text: str) -> int:
    return max(1, len(text) // 4)


def _pack(case_dir: Path, domain_pack: DomainPack | None = None) -> _PackResult:
    issues: list[str] = []
    material_pdf = case_dir / "material.pdf"

    # Accept either _doc_card.json or _paper_card.json
    doc_card_path = case_dir / "_doc_card.json"
    if not doc_card_path.exists():
        doc_card_path = case_dir / "_paper_card.json"

    instructions_path = case_dir / "generation_task" / "instructions.md"
    judge_path = case_dir / "generation_task" / "judge_prompt.json"
    audit_path = case_dir / "_audit_report.json"

    for must in (material_pdf, doc_card_path, instructions_path, judge_path):
        if not must.exists():
            issues.append(f"missing required artifact: {must.relative_to(case_dir)}")

    pdf_pages = page_count(material_pdf) if material_pdf.exists() else 0
    instructions_text = instructions_path.read_text(encoding="utf-8") if instructions_path.exists() else ""
    instructions_tokens_est = _coarse_token_estimate(instructions_text)

    completeness_count = correctness_count = 0
    if judge_path.exists():
        try:
            judge = json.loads(judge_path.read_text(encoding="utf-8"))
            completeness_count = len(judge.get("material_dependent_checklist_1") or [])
            correctness_count = len(judge.get("material_dependent_checklist_2") or [])
        except json.JSONDecodeError as e:
            issues.append(f"judge_prompt.json parse error: {e}")

    audit_pass = None
    audit_scores: dict | None = None
    if audit_path.exists():
        try:
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            audit_pass = bool(audit.get("pass"))
            audit_scores = audit.get("scores")
        except json.JSONDecodeError as e:
            issues.append(f"_audit_report.json parse error: {e}")

    verify_refine_info: dict = {"triggered": False}
    vr_report_path = case_dir / "_verify_refine_report.json"
    if vr_report_path.exists():
        try:
            vr_report = json.loads(vr_report_path.read_text(encoding="utf-8"))
            revisions = vr_report.get("revisions") or []
            if isinstance(revisions, list):
                actions = [r.get("action", "") for r in revisions if isinstance(r, dict)]
                verify_refine_info = {
                    "triggered": True,
                    "items_revised": sum(1 for a in actions if a in ("rewrite", "rewritten")),
                    "items_added": sum(1 for a in actions if a in ("split", "add")),
                    "items_removed": sum(1 for a in actions if a in ("remove", "dedup")),
                }
            else:
                verify_refine_info = {
                    "triggered": True,
                    "items_revised": revisions.get("c2_rewritten", 0) + revisions.get("c1_rewritten", 0),
                    "items_added": revisions.get("c2_added_for_traps", 0) + revisions.get("c2_split_into", 0),
                    "items_removed": revisions.get("c2_removed", 0) + revisions.get("c1_removed", 0) + revisions.get("dedup_removed", 0),
                }
        except (json.JSONDecodeError, KeyError):
            verify_refine_info = {"triggered": True, "parse_error": True}

    doc_card_summary: dict = {}
    if doc_card_path.exists():
        try:
            card = json.loads(doc_card_path.read_text(encoding="utf-8"))
            doc_card_summary = {
                "title": card.get("title"),
                "source_event": card.get("source_event") or card.get("conference"),
                "document_type": card.get("document_type"),
                "page_count_range": card.get("page_count_range"),
                "ordered_section_count": len(card.get("ordered_sections") or []),
                "key_numbers_count": len(card.get("key_numbers") or []),
                "key_figures_count": len(card.get("key_figures") or []),
                "key_terms_count": len(card.get("key_terms") or []),
                "trap_count": len(card.get("traps") or []),
            }
        except json.JSONDecodeError as e:
            issues.append(f"_doc_card.json parse error: {e}")

    # Domain info
    primary = domain_pack.primary if domain_pack else "unknown"
    secondary = domain_pack.secondary if domain_pack else "unknown"
    doc_type_label = domain_pack.document_type_label if domain_pack else ""

    stats = {
        "case_path": str(case_dir.relative_to(case_dir.parent.parent.parent))
        if len(case_dir.parents) >= 3
        else case_dir.name,
        "category": "broad_domain",
        "primary_domain": primary,
        "sub_domain": secondary,
        "document_type_label": doc_type_label,
        "language": "zh",
        "input_metrics": {
            "instructions_tokens_estimate": instructions_tokens_est,
            "material_count": 1,
            "pdf_total_pages": pdf_pages,
            "file_details": [
                {"name": "material.pdf", "pages": pdf_pages},
            ],
        },
        "checklist_counts": {
            "specific": {
                "details": {
                    "内容完整性": completeness_count,
                    "内容正确性": correctness_count,
                    "Content Fidelity (per-slide-deck dynamic)": 0,
                },
                "sum": completeness_count + correctness_count,
            },
        },
        "doc_card_summary": doc_card_summary,
        "audit": {
            "passed": audit_pass,
            "scores": audit_scores,
        },
        "verify_refine": verify_refine_info,
        "issues": issues,
    }
    return _PackResult(issues=issues, stats=stats)


def _render_yaml(stats: dict) -> str:
    def _scalar(v: object) -> str:
        if v is None: return "null"
        if isinstance(v, bool): return "true" if v else "false"
        if isinstance(v, (int, float)): return str(v)
        if isinstance(v, str):
            risky = any(ch in v for ch in ":#-?[]{},&*!|>'\"%@`\n")
            if risky or v == "" or v.strip() != v:
                return json.dumps(v, ensure_ascii=False)
            return v
        return json.dumps(v, ensure_ascii=False)

    def _dump(node: object, indent: int = 0) -> list[str]:
        out: list[str] = []
        prefix = "  " * indent
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, (dict, list)) and v:
                    out.append(f"{prefix}{k}:")
                    out.extend(_dump(v, indent + 1))
                elif isinstance(v, (dict, list)):
                    out.append(f"{prefix}{k}: {{}}" if isinstance(v, dict) else f"{prefix}{k}: []")
                else:
                    out.append(f"{prefix}{k}: {_scalar(v)}")
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, dict):
                    out.append(f"{prefix}-")
                    out.extend(_dump(item, indent + 1))
                else:
                    out.append(f"{prefix}- {_scalar(item)}")
        else:
            out.append(f"{prefix}{_scalar(node)}")
        return out

    return "\n".join(_dump(stats)) + "\n"


_SCAFFOLDING_TO_REMOVE = [
    "_doc_card.schema.json",
    "_paper_card.schema.json",
    "_audit_report.schema.json",
    "_verify_refine_report.schema.json",
    "_boilerplate_sections.md",
    "_hint.txt",
]


def _cleanup_case_dir(case_dir: Path) -> list[str]:
    removed: list[str] = []
    for name in _SCAFFOLDING_TO_REMOVE:
        p = case_dir / name
        if p.exists():
            try:
                p.unlink()
                removed.append(name)
            except OSError:
                pass
    # Remove composed system prompt files written by prompt_compose
    for p in case_dir.iterdir():
        if not p.is_file():
            continue
        n = p.name
        if n.startswith("_system_") and n.endswith(".md"):
            try:
                p.unlink()
                removed.append(n)
            except OSError:
                pass
        if n.startswith("_") and (n.endswith(".py") or n.endswith(".sh")):
            try:
                p.unlink()
                removed.append(n)
            except OSError:
                pass
    return removed


async def run(
    *,
    case_slug: str,
    case_dir: Path,
    domain_pack: DomainPack | None = None,
) -> StageOutcome:
    import time

    start = time.monotonic()
    removed = _cleanup_case_dir(case_dir)
    res = _pack(case_dir, domain_pack=domain_pack)
    stats_path = case_dir / "generation_task" / "statistics.yaml"
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(_render_yaml(res.stats), encoding="utf-8")
    status_payload = dict(res.stats)
    if removed:
        status_payload["scaffolding_removed"] = removed
    status_path = case_dir / "case_status.json"
    status_path.write_text(
        json.dumps(status_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return StageOutcome(
        stage="5_pack",
        case_slug=case_slug,
        ok=not res.issues,
        duration_s=time.monotonic() - start,
        cmd=[],
        parsed_payload={"stats": status_payload, "issues": res.issues},
        error=None if not res.issues else "; ".join(res.issues[:5]),
    )
