"""Unified-domain PPTSynth task synthesis pipeline.

Single shared engine covering the merged domain distribution of requesters 1/2/3
(industry verticals + business functions + task scenarios; Chinese/English
academic papers excluded — those use pipelines A/B). Currently 23 primary
domains / 139 secondary domains.

Merges AB2 rubric quality (Stage4 11-axis audit + Stage4b Verify-Refine) with
sinoconf's domain-migration mechanics (modular anti-leakage, domain packs,
post-audit static recheck, domain-aware Stage5). The engine is
distribution-agnostic: a document's domain is derived from its input path/filename
and injected at runtime via DomainPack — prompts/stages carry no domain list.
"""
