# Plane v1.4.2 public project Pages API patch (server-side)

**This is a patch for the Plane application backend, not the MCP package.**
Plane Community v1.4.2 displays pages using its session-authenticated internal
`/api/.../pages/` routes but does **not** register matching project Pages
under the API-key-authenticated `/api/v1` API. No MCP-only fix can change
what URLs the target server actually serves.

`public-project-pages.patch` is the upstream, **AGPL-3.0-only** source patch
from [makeplane/plane#9528](https://github.com/makeplane/plane/pull/9528).
It is kept separately from this fork's MIT-licensed MCP Python package.
Source: `RemoYukoff/plane`, branch `feat/public-api-project-pages`, reviewed
against official Plane tag `v1.4.2` on 2026-10-24. The patch applies cleanly
(`git apply --check`), and includes upstream API contract tests (not executed as part
of the MCP's offline test suite). Upstream PR remains **unmerged**.

It adds **project-scoped** Pages API-key endpoints at:

| Method | Route |
| --- | --- |
| GET, POST | `/api/v1/workspaces/{slug}/projects/{project_id}/pages/` |
| GET, PATCH, DELETE | `/api/v1/workspaces/{slug}/projects/{project_id}/pages/{page_id}/` |
| POST, DELETE | `/api/v1/workspaces/{slug}/projects/{project_id}/pages/{page_id}/archive/` |

It checks active project membership, keeps other users' private pages hidden,
validates/sanitizes HTML, and guards ownership-sensitive writes. **It does
not add workspace wiki Pages or collections.** Those still require upstream
server endpoints and must never be simulated through cookie impersonation.

## Verify against exact source before integrating

```bash
git clone --filter=blob:none --branch v1.4.2 --depth 1 https://github.com/makeplane/plane.git plane-src
cd plane-src
git apply --check ../plane-mcp-server/compat/plane-v1.4.2/public-project-pages.patch
git apply ../plane-mcp-server/compat/plane-v1.4.2/public-project-pages.patch
python3 -m compileall -q apps/api/plane/api/{views,urls,serializers} apps/api/plane/utils/openapi
```

Before a production rollout, run Plane's backend contract suite on an
**isolated PostgreSQL database**, including `test_pages.py` from this patch;
inspect the exact deployed backend image/source and ensure the patch still
matches. Deploy the patched backend as an **immutable image** or explicit,
reviewed file overlays, not by mutating live Django files in place.
Preserve existing credentials and data; use a staged restart/health check
with a rollback path. This repository intentionally does not perform a
production patch as a side effect of installing the MCP.

After updating the Plane server, probe the new endpoint with its existing
API key and verify the project only returns public and own private pages;
then use `page(action="list",project_id="...",api_version="v1")` in the
MCP. A regular 404 on `/api/v1/.../pages/` before patching is expected.

Avoid mounting a new `plane/api/urls/__init__.py` without verifying upstream
version: that file registers the entire public API router and a careless
replacement could remove unrelated routes.
