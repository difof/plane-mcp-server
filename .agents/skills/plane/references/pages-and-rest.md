# Pages, collections and the full REST surface

## First-class Pages tool

The `page` resource covers workspace and project pages, creation/retrieval, updates,
archive/restore, deletion, collection membership and work-item page links.

- Without `project_id` it targets workspace pages; with `project_id` it targets
  that project's pages.
- Default `api_version="v1"` is compatible with previous clients. Specify
  `api_version="v2"` to use current Plane v2 routes. v2 changes `PUT` to `PATCH`
  and uses `POST .../unarchive/`, not v1 `DELETE .../archive/`.
- `description_html` replaces the **whole page body**. Read the current page
  first before a partial edit, and preserve content outside the requested change.
- New nested pages take `parent_id`; workspace collections take `collection_id`.
  Do not combine those on creation. Project pages cannot be filed in collections.
- Linking to a work item is separate: `list_workitem_pages`, `attach_to_workitem`,
  `detach_from_workitem`. For unlinking, use `workitem_page_id` returned by the
  link list, *not* the page ID. Archive a page before deletion if required by
  the specific endpoint/version.

**Unavailability:** older/community self-hosted Plane editions may return 404
for v1 and v2 page routes. A 404 is not permission to use undocumented internal
paths. Preserve server status; report it and explain that a supported server API
or edition upgrade may be required.

## Route discovery and generic operations

Use the typed tools first. Otherwise search the packaged documentation snapshot:

```js
const routes=await tools.plane.api({action:"list",query:"page",version:"v2",limit:20});
return {total:routes.total,next_offset:routes.next_offset,items:routes.items};
```

`api describe` returns `{count,routes,source}` for a route template or a concrete path.
Each route carries method/name/path and a link to the official documentation.
Check the exact payload requirements before writes.

`api request` accepts:

| Input | Meaning |
| --- | --- |
| `method` | `GET`, `POST`, `PUT`, `PATCH`, `DELETE` |
| `path` | Concrete `/api/v1/...` or `/api/v2/...` path on the configured Plane server |
| `params` | JSON object string, for filter/limit/cursor query parameters |
| `body` | JSON string (array or object as required by the endpoint) |
| `file_base64`, `filename`, `file_field`, `form` | Optional multipart file bytes, filename, field name, extra form JSON object |

`body` and `file_base64` are mutually exclusive. `api.request` returns
`{status,ok,data,headers}`; **a 404/403/500 with `ok:false` is not success**.
Native downloads may return `data.content_base64`, and all responses and uploads
have an 8 MiB limit. For local file uploads, the `api` tool has *no file-path*
input. Do not dump confidential file contents through shell/base64 to work
around a no-content boundary. Use a supported confidential upload bridge or
report the limitation.

Paths cannot select a different host, override the connected workspace, carry
query strings, or ask the tool to follow redirects. The underlying Plane token
still controls permissions. An arbitrary documented route might be available
only on a different Plane version/plan.

## Common non-typed areas

Use `api list` with focused queries to locate the v2 endpoints for workspace
pages/attachments, recurring work items, project automations, audit logs,
permissions, webhooks, workspace views, template categories, and bulk operations.
These endpoints have different payloads. **Do not infer an endpoint contract
from its name alone.** Only use a write after the user authorized the effect.

The fork's published coverage snapshot, refresh instructions, and caveats are at
`docs/API_COVERAGE.md` in the same repository.
