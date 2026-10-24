# Work items, estimates, planning and search

## Resolve targets first

- `workspace retrieve` identifies the connection; `project list` resolves its UUID.
- `workitem retrieve_by_identifier` accepts a human identifier such as `DEV-268`.
- `member me` identifies the authenticated user; `member list_project` resolves other assignees.
- `label list`, `state list`, and `workitem_type list` resolve IDs before writing.
- Creating an epic requires a type ID; there is no separate `epic` tool in this MCP.

## Create and verify concise subtasks

Use `workitem create` with `project_id`, `name`, and only requested fields:
`parent` (parent work-item UUID), `assignees` (UUID array), `labels` (UUID array),
`description_stripped` (plain text), optional `estimate_point` (point UUID), `state`,
`target_date` and priority. Missing fields must remain unset. Then separately add it to a
cycle via `cycle manage_workitems` and verify membership. A parent-child relation does
not automatically prove a task belongs to the parent's sprint.

`assignees` and `labels` **replace** entire lists on `update`; for small changes use
`manage_assignee` and `manage_label` which merge or remove IDs. `start_date` and
`target_date` are `YYYY-MM-DD`. There is no `due_date` parameter. Do not invent
priorities, labels or deadlines. On ambiguous create failure read existing children
before retrying, since repeated POSTs may create duplicate work items.

## Native estimates

Call `project_estimate retrieve` for the active scale and `list_points` for its
point options. On self-hosted Plane versions whose estimate endpoints return 404,
`list_points` falls back to observing assigned values in work items:
`{estimate_id,points,complete:false,source:"observed_workitems",scanned_workitems,truncated}`.
This is *not* a complete set of possible values; unused choices remain unknown.
`estimate_point` stores an ID; an expanded response may also include
`estimate_point_expanded` with its label/key. Never equate the UUID itself with hours
without reading the corresponding point value.

## PQL and pagination

Always obtain the live syntax with `get_pql_reference`. `workitem list` accepts `pql`
with project scoping, plus `per_page`/`cursor`. `workitem count` has count-only
`group_by` and `sub_group_by` keys; those are **not** general PQL filter keys.
Follow `next_page_results` and pass back `next_cursor`. For 1,000 records, a first
100-item page is not complete. For other relationships (`cycle list_workitems`,
`module list_workitems`), use the resource's own paging action.

## Related resources

- Sprint/cycle: `cycle list`, `retrieve`, `list_workitems`, `manage_workitems`.
- Release or milestone membership: separate `release`/`milestone` actions.
- Comments, relations, external links: `workitem_comment`, `workitem_relation`,
  `workitem_link`. For files use `workitem_attachment`, respecting sizes/URL limits.
- Work logs: `work_log`; do not invent time entries or equate a task estimate with logged time.
- Work-item custom fields: `workitem_property` and `workitem_type`, scoped to project
  or workspace as the action specifies.

Read a resource after write, and separately verify its sprint, release, module or
label memberships if those were changed.
