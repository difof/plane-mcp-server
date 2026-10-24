"""Keep the checked-in Plane agent skill discoverable and aligned with MCP."""

from __future__ import annotations

import re
from pathlib import Path

from plane_mcp.tools.registry import RESOURCES

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/plane"


def test_skill_has_valid_discoverable_identity():
    content = (SKILL / "SKILL.md").read_text()
    assert content.startswith("---\n")
    frontmatter = content.split("---", 2)[1]
    assert re.search(r"(?m)^name: plane$", frontmatter)
    assert re.search(r"(?m)^description: .{40,}$", frontmatter)
    assert (SKILL / "agents/openai.yaml").is_file()
    assert 'display_name: "Plane MCP"' in (SKILL / "agents/openai.yaml").read_text()


def test_skill_links_all_resolve_inside_this_repository():
    files = sorted(SKILL.rglob("*.md"))
    assert len(files) >= 5
    for file in files:
        text = file.read_text()
        for destination in re.findall(r"\]\(([^)]+)\)", text):
            if "://" in destination or destination.startswith("#"):
                continue
            target = (file.parent / destination.split("#", 1)[0]).resolve()
            assert target.is_file(), f"broken skill reference {destination} from {file}"
            assert target.is_relative_to(ROOT), f"skill reference left repo: {target}"


def test_named_resources_in_skill_exist_on_mcp():
    content = (SKILL / "SKILL.md").read_text()
    for name in ("api", "page", "collection", "workitem", "cycle", "member", "project_estimate"):
        assert f"`{name}`" in content
        assert name in {mod.NAME for mod in RESOURCES}
    assert "776" in content and "545" in content and "231" in content


def test_skill_documents_safer_gateway_and_older_plane_limitations():
    all_text = "\n".join(file.read_text() for file in SKILL.rglob("*.md"))
    for phrase in ("ok === true", "api_version", "estimate_point_expanded", "404", "same credentials"):
        assert phrase.lower() in all_text.lower()
    assert "PLANE_API_KEY=" not in all_text
