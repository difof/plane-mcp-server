"""Keep the optional Plane server-side Pages patch explicit and narrowly scoped."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "compat/plane-v1.4.2/public-project-pages.patch"
README = ROOT / "compat/plane-v1.4.2/README.md"


def test_backend_patch_is_isolated_and_is_not_in_the_mcp_python_package():
    text = PATCH.read_text()
    paths = [line.removeprefix("+++ b/") for line in text.splitlines() if line.startswith("+++ b/")]
    assert len(paths) == 11
    assert all(path.startswith("apps/api/plane/") for path in paths)
    assert not any(path.startswith("plane_mcp/") for path in paths)
    assert "apps/api/plane/api/urls/page.py" in paths
    assert "apps/api/plane/tests/contract/api/test_pages.py" in paths
    assert "AGPL-3.0-only" in text
    assert "git apply --check" in README.read_text()
    assert "not the MCP" in README.read_text()
