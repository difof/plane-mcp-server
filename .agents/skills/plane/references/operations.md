# Projects, governance, releases and operational diagnosis

## Scope and identity

`workspace retrieve` gives the selected workspace slug; with environment
credentials its id/name may legitimately be null. `project list` and
`project retrieve` resolve identifiers/UUIDs. `member me`, `list_project`,
`list_workspace` expose account/member information. Read roles/permissions
before modifying restricted resources. Never infer authorization from a visible
feature name or use another account to bypass a denial.

## Tools by area

- Project settings/feature flags: `project` and `workspace`, but do not enable
  modules or reset permissions unless requested.
- Workflow states and labels: `state`, `label`; `workitem_type` governs types.
- Custom properties/values/options: `workitem_property`, `customer_property`.
  Property scope may differ for workspace, project, or work-item type.
- Planning and delivery: `cycle`, `module`, `milestone`, `initiative`, `release`,
  `release_label`, `release_tag`; verify membership with each resource's read
  actions, not merely the item's response.
- Customer/requests and support: `customer`, `customer_request`,
  `customer_property`, `intake`.
- Generic features absent from typed tools: `api list` / `describe` / `request`
  against documented v1/v2 routes, with the same credential and explicit writes.

## Diagnose by evidence

1. **MCP missing tool:** inspect the current session's discovered tool set.
   The deployed fork advertises 31 named tools including `api`; a client still
   showing 30 may be connected to an older process or stale tool listing.
2. **401 or 403:** verify the connected credential/workspace and account
   permissions without printing secrets. A 403 `Given API token is not valid`
   is an authentication problem, not evidence a route exists or that a write
   succeeded. Do not rotate tokens unless explicitly requested.
3. **404:** the route may not exist on the server's API version/edition, or
   identifiers may be wrong. Verify the documented method/path then report
   server availability. This is especially relevant for Pages and Estimates
   on older self-hosted Plane.
4. **Validation error:** compare the actual SDK and Plane version plus response
   shape. Expanded `estimate_point` may be an object; the fork preserves that
   as `estimate_point_expanded` and normalizes its identifier for the pinned SDK.
5. **Paging:** explicitly follow the server's cursor; filter locally where
   possible, but never call a sample a complete result. Cap data in agent output.
6. **Ambiguous write:** read back before repeating. Preserve exact intended
   mutation scope and report partial failures.

The MCP's route catalogue can be refreshed with
`python scripts/update_api_catalog.py --v1-docs PATH` from the repository.
Upgrading the MCP does not upgrade the Plane application itself or create
missing server-side endpoints.
