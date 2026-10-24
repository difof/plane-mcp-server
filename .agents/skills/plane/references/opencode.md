# OpenCode v2 Code Mode

Use these examples only in OpenCode's `execute` context. `search` is synchronous; each
`execute` block is isolated (no cross-call variables). The Code Mode sandbox has no general
filesystem/network imports; all Plane access goes through configured MCP tools. In other
harnesses, discover and call native tool signatures instead.

## Discover only what you need

```js
return search({namespace:"plane",query:"workitem",limit:5});
```

For generic v1/v2 APIs:

```js
return search({namespace:"plane",query:"api",limit:4});
```

`search()` discovers **MCP tools**; `tools.plane.api({action:"list",...})`
discovers **REST routes**. Do not confuse the two namespaces.

Once the tool schema is available, read only the needed object:

```js
const result = await tools.plane.workitem({
  action:"retrieve_by_identifier",workitem_identifier:"DEV-268"
});
if (!result?.id) throw new Error("Work item unresolved");
return {id:result.id,name:result.name,project:result.project,estimate:result.estimate_point};
```

## Batched, bounded reads

```js
const ids = ["DEV-268","DEV-363"];
const results = await Promise.allSettled(ids.map(workitem_identifier =>
  tools.plane.workitem({action:"retrieve_by_identifier",workitem_identifier})
));
return results.map((result,i) => result.status === "fulfilled"
  ? {identifier:ids[i],id:result.value?.id,name:result.value?.name}
  : {identifier:ids[i],error:String(result.reason)});
```

Only batch *independent* reads. Honor `next_cursor`, `next_page_results` and the
server's output limit. Never skip records you did not inspect. For dependent writes
or tasks with ordered side effects, resolve and execute sequentially, then verify.

## REST route lookup and one read

```js
const routes = await tools.plane.api({action:"list",version:"v2",query:"pages",limit:10});
return routes.items.map(({method,path,name,url})=>({method,path,name,url}));
```

Use the **connected** workspace slug, not a guessed hardcoded one:

```js
const ctx=await tools.plane.workspace({action:"retrieve"});
if (!ctx?.slug) throw new Error("No connected workspace");
const response=await tools.plane.api({
  action:"request",method:"GET",
  path:`/api/v2/workspaces/${ctx.slug}/pages/`,
  params:JSON.stringify({per_page:20})
});
if (response?.ok !== true) throw new Error(`Plane HTTP ${response?.status}: ${JSON.stringify(response?.data).slice(0,240)}`);
return {status:response.status,data:response.data};
```

REST path strings accept no arbitrary origin, query suffix, encoded traversal, or other
workspace. Pagination and filters belong in the `params` JSON string. A documented route
may still answer 404/403 because of Plane edition, permission, version or a bad token.

## Returned values and uncertain writes

Successful resource tools usually return a decoded object. Do not assume
`result.content[0].text` or always call `JSON.parse(result)`. For a raw MCP transport,
check its `isError` first and decode text once. For the generic `api` tool,
`{status,ok,data,headers}` is **the tool's actual HTTP result**, not another MCP envelope.

On a timeout, transport reset, or unreadable create response, query the intended target
for duplicates before retrying. Do not replay a batch of writes. Never dump opaque
credentials, full responses or unrelated records into Code Mode output.
