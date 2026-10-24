"""Refresh the public Plane v1/v2 route catalogue from official documentation.

Usage:
    git clone --depth=1 https://github.com/makeplane/developer-docs /tmp/plane-docs
    python scripts/update_api_catalog.py --v1-docs /tmp/plane-docs/docs/api-reference

Requires `requests`, already used by the pinned plane-sdk. Never fetches
credentials or contacts a private Plane instance.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import requests

DOCS = "https://developers.plane.so"
METHOD = r"GET|POST|PATCH|PUT|DELETE"
V1 = re.compile(rf'<span class="method\s+\w+">\s*({METHOD})\s*</span>\s*<span class="path">([^<]+)</span>', re.I)
V2_ROWS = re.compile(
    rf"<tr>\s*<td><code>({METHOD})</code></td>\s*<td><code>(/api/v2/[^<]+)</code></td>\s*<td>(.*?)</td>\s*</tr>",
    re.I | re.S,
)
ENDPOINTS = re.compile(r'<h2 id="endpoints"[^>]*>.*?</h2>(<table.*?</table>)', re.S)


def _sitemap() -> tuple[set[str], str]:
    response = requests.get(DOCS + "/sitemap.xml", timeout=20)
    response.raise_for_status()
    tree = ET.fromstring(response.content)
    urls = {node.text for node in tree.findall(".//{*}loc") if node.text}
    return urls, response.headers.get("Last-Modified", "unknown")


def _v1(directory: Path) -> list[dict[str, str]]:
    if not directory.is_dir():
        raise ValueError(f"no v1 reference directory: {directory}")
    items = []
    for file in directory.rglob("*.md"):
        text = file.read_text(encoding="utf-8")
        hit = V1.search(text)
        if not hit:
            continue
        method, path = hit.groups()
        if not path.startswith("/api/v1/"):
            continue
        relative = file.relative_to(directory).with_suffix("")
        heading = re.search(r"^#\s+(.+)$", text, re.M)
        items.append(
            {
                "method": method.upper(),
                "path": html.unescape(path).strip(),
                "name": heading.group(1).strip() if heading else file.stem,
                "url": f"{DOCS}/api-reference/{relative}",
            }
        )
    return items


def _v2_overview(url: str, known_urls: set[str]) -> list[dict[str, str]]:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    match = ENDPOINTS.search(response.text)
    if not match:
        raise ValueError(f"missing endpoints table: {url}")
    section = url.split("/v2/", 1)[1].split("/", 1)[0]
    rows = []
    for method, path, description in V2_ROWS.findall(match.group(1)):
        name = html.unescape(re.sub(r"<[^>]+>", "", description)).strip()
        words = [part for part in re.findall(r"[a-z0-9]+", name.lower()) if part not in ("a", "an", "the")]
        detail = url.removesuffix("/overview") + "/" + "-".join(words)
        rows.append(
            {
                "method": method.upper(),
                "path": html.unescape(path),
                "name": name,
                "url": detail if detail in known_urls else url,
                "section": section,
            }
        )
    if not rows:
        raise ValueError(f"empty endpoints table: {url}")
    return rows


def _unique(items: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        {(item["method"], item["path"]): item for item in items}.values(), key=lambda i: (i["path"], i["method"])
    )


def build(v1_docs: Path) -> dict:
    urls, updated = _sitemap()
    overviews = sorted(url for url in urls if "/api-reference/v2/" in url and url.endswith("/overview"))
    with ThreadPoolExecutor(max_workers=8) as pool:
        v2_parts = list(pool.map(lambda url: _v2_overview(url, urls), overviews))
    versions = {"v1": _unique(_v1(v1_docs)), "v2": _unique([row for part in v2_parts for row in part])}
    if len(versions["v1"]) < 230 or len(versions["v2"]) < 540:
        raise ValueError(f"Unexpectedly small API inventory: {len(versions['v1'])} v1, {len(versions['v2'])} v2")
    try:
        sha = subprocess.check_output(["git", "-C", str(v1_docs), "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        sha = "unknown"
    return {
        "source": {
            "v1": f"makeplane/developer-docs@{sha}",
            "v2": f"{DOCS}/api-reference/v2 (sitemap {updated})",
            "captured_at": str(date.today()),
        },
        "versions": versions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1-docs", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).resolve().parents[1] / "plane_mcp/api_catalog.json"
    )
    args = parser.parse_args()
    result = build(args.v1_docs)
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("Updated", args.output, {version: len(items) for version, items in result["versions"].items()})


if __name__ == "__main__":
    main()
