import importlib.util
from pathlib import Path
import zipfile

from pptsynth.router import PROFILE_CHOICES, overridden_route
from pptsynth.pdf_utils import extract_text_sample, page_count


def test_override_profiles_are_stable():
    assert set(PROFILE_CHOICES) == {"academic_en", "academic_zh", "finance_en", "general_zh"}
    route = overridden_route("finance_en")
    assert route.profile == "finance_en"
    assert route.source == "override"


def test_general_taxonomy_loads():
    from pptsynth.pipelines.general_zh.domain_registry import load_for_paper

    root = Path(__file__).parents[1] / "src" / "pptsynth" / "pipelines" / "general_zh" / "domains"
    yaml_files = [p for p in root.rglob("*.yaml") if p.name != "_base.yaml"]
    assert len(yaml_files) >= 139
    pack = load_for_paper("科技互联网", "产品介绍")
    assert pack.primary == "科技互联网"
    assert pack.secondary == "产品介绍"


def test_pdf_helpers_extract_bounded_sample_and_count_pages(tmp_path, monkeypatch):
    source = tmp_path / "material.pdf"
    source.write_bytes(b"synthetic PDF fixture")

    class FakePage:
        def __init__(self, text: str):
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class FakeReader:
        def __init__(self, *_args, **_kwargs):
            self.pages = [FakePage(f"page-{number}") for number in range(1, 11)]

    monkeypatch.setattr("pptsynth.pdf_utils.PdfReader", FakeReader)
    sample = extract_text_sample(source, max_chars=10_000)
    assert "page-1" in sample
    assert "page-6" in sample
    assert "page-7" not in sample
    assert "page-9" in sample
    assert "page-10" in sample
    assert page_count(source) == 10


def test_pdf_page_count_reads_a_real_pdf(tmp_path):
    from pypdf import PdfWriter

    source = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    with source.open("wb") as stream:
        writer.write(stream)
    assert page_count(source) == 2


def _release_check_module():
    path = Path(__file__).parents[1] / "tools" / "release_check.py"
    spec = importlib.util.spec_from_file_location("release_check", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_check_accepts_clean_tree(tmp_path):
    (tmp_path / "README.md").write_text("# Clean snapshot\n", encoding="utf-8")
    assert _release_check_module().check_tree(tmp_path) == []


def test_release_check_rejects_sensitive_and_generated_content(tmp_path):
    (tmp_path / ".DS_Store").write_text("cache", encoding="utf-8")
    (tmp_path / "config.yaml").write_text("api_" "key: secret-token-value\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("host: code.alib" "aba-inc.com\n", encoding="utf-8")
    issues = _release_check_module().check_tree(tmp_path)
    assert any("generated/cache" in issue for issue in issues)
    assert any("credential" in issue for issue in issues)
    assert any("organization marker" in issue for issue in issues)


def test_release_check_accepts_package_archive_metadata(tmp_path):
    archive = tmp_path / "pptsynth.whl"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("pptsynth-0.1.0.dist-info/METADATA", "Name: pptsynth\n")
    assert _release_check_module().check_archive(archive) == []
