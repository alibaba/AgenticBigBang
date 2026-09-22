#!/usr/bin/env python3
"""Fail closed when a PPTSynth release tree or archive contains unsafe content."""
from __future__ import annotations

import argparse
import re
import sys
import tarfile
import zipfile
from pathlib import Path


TEXT_SUFFIXES = {
    ".cfg", ".ini", ".json", ".md", ".py", ".sh", ".toml", ".txt", ".yaml", ".yml",
}
DISALLOWED_SUFFIXES = {".csv", ".docx", ".pdf", ".pptx", ".xlsx", ".jsonl"}
UNWANTED_PARTS = {".ds_store", ".pytest_cache", "__pycache__", "build", "dist"}
UNWANTED_NAME_SUFFIXES = (".egg-info",)

# Keep organization-specific markers split so this source file does not itself
# contain a release-blocking marker. Add newly discovered markers here rather
# than relying on a one-time manual search.
SENSITIVE = re.compile(
    r"sk-[A-Za-z0-9_-]{8,}|(?:api[_-]?key|auth[_-]?token|secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9_./=-]{8,}",
    re.I,
)
CORPORATE = re.compile(
    r"alib" r"aba|alip" r"ay|tao" r"bao|ding" r"talk|ant" r"group|code\.alib" r"aba-inc\.com",
    re.I,
)
LOCAL_MARKERS = re.compile(
    r"(?:/Us" r"ers/|[A-Za-z]:\\Us" r"ers\\|routi" r"fy|evam" r"ux|\\b" r"oss-[A-Za-z0-9_-]+|"
    r"(?:intranet|internal|corp)\.[A-Za-z0-9.-]+|https?://[^\s/]*(?:\.internal|\.corp)[^\s]*)",
    re.I,
)


def _path_issues(name: str, *, allow_package_metadata: bool = False) -> list[str]:
    issues: list[str] = []
    lowered_name = name.casefold()
    parts = lowered_name.split("/")
    if any(part in UNWANTED_PARTS for part in parts):
        issues.append(f"generated/cache path in package: {name}")
    if not allow_package_metadata and any(part.endswith(UNWANTED_NAME_SUFFIXES) for part in parts):
        issues.append(f"generated package metadata in package: {name}")
    if Path(name).suffix.casefold() in DISALLOWED_SUFFIXES:
        issues.append(f"source or generated document in package: {name}")
    return issues


def _text_issues(name: str, raw: bytes) -> list[str]:
    if Path(name).suffix.lower() not in TEXT_SUFFIXES:
        return []
    issues: list[str] = []
    text = raw.decode("utf-8", errors="ignore")
    if SENSITIVE.search(text):
        issues.append(f"possible credential in text: {name}")
    if CORPORATE.search(text):
        issues.append(f"organization marker in text: {name}")
    if LOCAL_MARKERS.search(text):
        issues.append(f"internal path or endpoint in text: {name}")
    return issues


def _check_one(name: str, raw: bytes, *, allow_package_metadata: bool = False) -> list[str]:
    issues = _path_issues(name, allow_package_metadata=allow_package_metadata)
    return issues + _text_issues(name, raw)


def check_tree(root: Path) -> list[str]:
    issues: list[str] = []
    for path in root.rglob("*"):
        if path.is_file():
            issues.extend(_check_one(path.relative_to(root).as_posix(), path.read_bytes()))
    return issues


def check_archive(path: Path) -> list[str]:
    issues: list[str] = []
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if not info.is_dir():
                    issues.extend(_check_one(info.filename, archive.read(info), allow_package_metadata=True))
        return issues
    if tarfile.is_tarfile(path):
        with tarfile.open(path) as archive:
            for info in archive.getmembers():
                if info.isfile():
                    member = archive.extractfile(info)
                    if member is not None:
                        issues.extend(_check_one(info.name, member.read(), allow_package_metadata=True))
        return issues
    return [f"unsupported archive format: {path}"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    issues = check_tree(args.root)
    if args.archive:
        issues.extend(check_archive(args.archive))
    if issues:
        print("RELEASE CHECK FAILED", file=sys.stderr)
        print("\n".join(f"- {issue}" for issue in issues), file=sys.stderr)
        return 1
    print("RELEASE CHECK PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
