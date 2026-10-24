# Plane REST API coverage

**As of 2026-10-24:** 231 distinct documented v1 method/path pairs, 545 v2 pairs (776 total), from [Plane's developer documentation](https://developers.plane.so/api-reference/v2/introduction). The snapshot is bundled in `plane_mcp/api_catalog.json`. It is a route catalogue, **not a guarantee that every route exists on every self-hosted Plane version or plan**.

## Using the surface

- Existing named tools remain the preferred typed interface for ordinary Plane operations.
- `api(action="list", version="v2", query="pages", limit=30)` searches the documentation snapshot. Pagination uses `offset` and `next_offset`.
- `api(action="describe", path="/api/v2/workspaces/{slug}/pages/")` resolves a route template to its HTTP methods and official documentation links.
- `api(action="request", method="GET", path="/api/v2/workspaces/tech/pages/", params='{"per_page":20,"fields":"id,name,description_html"}')` calls the configured Plane server. Replace `tech` with the connected workspace from `workspace(action="retrieve")`.
- For Pages, `page(action="list", api_version="v2")` and `page(action="retrieve", page_id="...", api_version="v2")` provide direct first-class v2 access. The default `api_version="v1"` preserves older integrations. Other page actions, including CRUD, archive, collection placement and work-item page links, also accept `api_version="v2"`.

The gateway supports **GET, POST, PUT, PATCH and DELETE** for any `/api/v1/` or `/api/v2/` route supported by the server, including new bulk/upsert operations, pages, automations, webhooks and recurring work items. JSON request bodies and query strings are passed as JSON text. Multipart file uploads use `file_base64`, `filename`, optional `file_field`, and `form` (JSON text). Binary downloads are base64 encoded. Responses preserve HTTP status and server data, including v1/v2 pagination fields; non-2xx is never silently reported as success. Requests and responses are limited to 8 MiB.

## Boundaries

- Calls stay on the authenticated **configured Plane origin**, with matching workspace slug. The tool does not accept arbitrary URLs, custom authentication headers, redirect following or path traversal. Other non-workspace API paths (for example `/api/v2/users/me/`) remain usable with the same credentials.
- `api.request` exposes writes and bulk deletes; treat them as destructive and obtain the user's authorization before changing data. Existing Plane token scopes and tenant permissions still apply.
- The catalogue covers published **REST endpoints** only, not undocumented internal application APIs, arbitrary external signed-upload destinations, WebSockets or GraphQL. Endpoints which require a feature plan, permissions or an upgraded Plane server remain subject to those limits.
- Upstream `plane-sdk` 0.3.1 is still used for v1 typed tools. The raw v2 gateway is deliberately not forced through v1 Pydantic response models, because v2 changes verbs, pagination and field naming.

## Self-hosted v1.4.2 Pages backend compatibility

Plane Community v1.4.2 serves Pages in its internal UI API but does not
register token-authenticated public Pages endpoints. The fork includes a
**separately licensed, optional backend patch**, tested to apply cleanly to
Plane tag `v1.4.2`: [`compat/plane-v1.4.2/README.md`](../compat/plane-v1.4.2/README.md).
It adds **project pages only**, preserves role/ownership restrictions and
requires a Plane backend rebuild or reviewed source-file overlay. Installing
or restarting the MCP alone does **not** activate missing routes. The MCP's
v1 project page update now retries the backend's documented PATCH after
receiving PUT 405, and nested-page creation maps `parent_id` to `parent`.

## Other self-hosted compatibility repairs

- Redis-backed OAuth token caches **fail closed without**
  `PLANE_OAUTH_STORE_ENCRYPTION_KEYS`. Supply a persistent Fernet key or a
  comma-separated rotation list (current first) before running hosted OAuth.
  Older plaintext values remain readable for migration; new writes are encrypted.
  Local stdio with API-key authentication does not need this setting.
- Intake status updates retry the base PATCH endpoint only on dedicated-route 404.
- Project feature reads/updates fall back to the base project resource on 404;
  unsupported advanced flags are refused instead of silently ignored.
- Work-item assignee writes validate **active project membership** before
  replacing lists, avoiding a known server bug that drops existing assignments.
- Work-item relations fall back from missing `/dependencies/` to the older
  `/relations/` endpoint; unsupported removal is reported, not invented.

## Live compatibility evidence

The configured Oven MCP was probed read-only on 2026-10-24: v1 `page list` and `collection list` returned 404, while `project list` returned `403: Given API token is not valid`. The fork itself was also started as a separate MCP server: its `api.list` worked and its v2 `page list` reached the server but returned 404. These are **unresolved server/auth results**, not fixes we can honestly verify offline. Plane Community Edition may lack page API endpoints entirely (see [upstream compatibility report](https://github.com/makeplane/plane-mcp-server/issues/171)); a new MCP tool cannot create a server-side route. The fork does not automatically mutate Plane data or rotate credentials to work around them.

## Refreshing documented routes

```bash
git clone --depth 1 https://github.com/makeplane/developer-docs /tmp/plane-docs
python scripts/update_api_catalog.py --v1-docs /tmp/plane-docs/docs/api-reference
```

The generator reads v1 endpoint badges from the pinned checkout and v2 endpoints from the live official documentation sitemap/overview tables. It fails rather than silently replacing the catalogue with an unexpectedly small inventory. **New routes are callable through `api.request` even before the catalogue is refreshed**. Update the snapshot when Plane adds new docs; inspect the diff and run tests before committing.
