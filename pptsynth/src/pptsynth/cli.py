"""One entry point for routed PPTSynth task and rubric synthesis."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .router import PROFILE_CHOICES, Route, overridden_route, route_pdf


def _slug(pdf_path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "_", pdf_path.stem).strip("_").lower()[:48] or "document"
    digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()[:8]
    return f"{stem}_{digest}"


def _case_dir(out_root: Path, route: Route, slug: str) -> Path:
    if route.profile == "academic_en":
        return out_root / "academic_en" / slug
    if route.profile == "academic_zh":
        return out_root / "academic_zh" / slug
    if route.profile == "finance_en":
        return out_root / "finance_en" / slug
    return out_root / "general_zh" / route.primary / route.secondary / slug


def _write_route(case_dir: Path, route: Route, pdf_path: Path) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    data = asdict(route) | {"input_filename": pdf_path.name}
    (case_dir / "_routing.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def _synthesize_one(pdf_path: Path, out_root: Path, route: Route, args: argparse.Namespace) -> dict[str, Any]:
    slug = _slug(pdf_path)
    case_dir = _case_dir(out_root, route, slug)
    _write_route(case_dir, route, pdf_path)
    common = dict(
        pdf_path=pdf_path, case_slug=slug, out_root=out_root,
        model=args.model, max_budget_usd=args.max_budget_usd,
        skip_done=args.skip_done, retries_per_stage=args.retries_per_stage,
        max_thinking_tokens=args.max_thinking_tokens,
    )
    if route.profile == "academic_en":
        from .pipelines.academic_en.synth_one import synth_one
        result = await synth_one(**common)
    elif route.profile == "academic_zh":
        from .pipelines.academic_zh.synth_one import synth_one
        result = await synth_one(**common)
    elif route.profile == "general_zh":
        from .pipelines.general_zh.domain_registry import load_for_paper
        from .pipelines.general_zh.synth_one import synth_one
        result = await synth_one(
            **common, primary=route.primary, secondary=route.secondary,
            domain_pack=load_for_paper(route.primary, route.secondary),
        )
    else:
        from .pipelines.finance_en.family_registry import load_for_doc
        from .pipelines.finance_en.synth_one import synth_one
        assets_dir = Path(__file__).parent / "pipelines" / "finance_en" / "assets"
        shared_dir = out_root / "finance_en"
        shared_dir.mkdir(parents=True, exist_ok=True)
        for asset_name in ("common_judge_prompt.json", "judge_weights.yaml"):
            asset = assets_dir / asset_name
            if asset.exists():
                shutil.copy2(asset, shared_dir / asset_name)
        meta = {
            "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
            "family": route.finance_family,
            "sub_genre": route.finance_sub_genre,
            "issuer": route.issuer,
            "reporting_period": route.reporting_period,
            "sector": route.sector,
            "pages": 0,
        }
        profile = load_for_doc(route.finance_family, route.finance_sub_genre, route.issuer, route.reporting_period)
        result = await synth_one(**common, family_profile=profile, doc_meta=meta, effort=args.effort)
    return {
        "input": str(pdf_path), "route": asdict(route), "case_slug": slug,
        "case_dir": str(result.case_dir), "success": result.success,
        "duration_s": round(result.duration_s, 2), "audit_pass": result.audit_pass,
        "verify_refined": result.verify_refined, "error": result.error,
    }


def _discover(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() == ".pdf" else []
    return sorted(p for p in path.rglob("*.pdf") if p.is_file())


def main() -> int:
    ap = argparse.ArgumentParser(description="Create grounded slide-generation tasks and rubrics from PDFs.")
    ap.add_argument("--input", type=Path, required=True, help="a PDF or a directory of PDFs")
    ap.add_argument("--out-root", type=Path, required=True, help="output directory")
    ap.add_argument("--route", choices=PROFILE_CHOICES, help="bypass automatic routing for every input")
    ap.add_argument("--model", default=None, help="optional Claude model override")
    ap.add_argument("--concurrency", type=int, default=1)
    ap.add_argument("--max-budget-usd", type=float, default=None)
    ap.add_argument("--max-thinking-tokens", type=int, default=None)
    ap.add_argument("--effort", choices=("low", "medium", "high"), default="low")
    ap.add_argument("--retries-per-stage", type=int, default=1)
    ap.add_argument("--skip-done", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="list inputs and routing without synthesis")
    args = ap.parse_args()
    if not args.input.exists():
        ap.error(f"input not found: {args.input}")
    if args.concurrency < 1:
        ap.error("--concurrency must be at least 1")
    pdfs = _discover(args.input)
    if not pdfs:
        print("no PDFs found", file=sys.stderr)
        return 2
    routes: list[tuple[Path, Route]] = []
    for pdf in pdfs:
        try:
            route = overridden_route(args.route) if args.route else route_pdf(pdf, model=args.model)
        except Exception as exc:  # selected policy: preserve automation with an explicit fallback record
            route = Route(profile="general_zh", language="other", confidence=0.0, source="fallback", rationale=f"Router error: {exc}")
        routes.append((pdf, route))
        print(f"[route ] {pdf.name} -> {route.profile} ({route.confidence:.2f}, {route.source})")
    if args.dry_run:
        return 0
    args.out_root.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(args.concurrency)

    async def guarded(pdf: Path, route: Route) -> dict[str, Any]:
        async with sem:
            print(f"[start ] {pdf.name} -> {route.profile}", flush=True)
            result = await _synthesize_one(pdf, args.out_root, route, args)
            print(f"[{'OK' if result['success'] else 'FAIL'}] {result['case_slug']} {result['duration_s']:.0f}s", flush=True)
            return result

    async def run_all() -> list[dict[str, Any]]:
        return await asyncio.gather(*(guarded(pdf, route) for pdf, route in routes))

    results = asyncio.run(run_all())
    (args.out_root / "_run_log.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if all(r["success"] for r in results) else 1
