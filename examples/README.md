# Example configuration

Copy these into `~/.pacer/config/` and edit. Both are **human-edited surfaces** — the
CLI's agent mode and the MCP server only ever *read* them, never write them, so a capped
agent can't widen its own limits.

## `policy.csv` — the spend cap

```
cp examples/policy.csv ~/.pacer/config/policy.csv
```

| Setting | Meaning |
|---------|---------|
| `Max spend per search ($)` | Hard stop for a single billable call (per-op cap). |
| `Max spend per day ($)` | Hard stop for cumulative spend over the UTC calendar day. |
| `Require client/matter code` | `Yes` blocks billable ops that have no `--matter` code. |

Fail-closed: a missing file uses conservative built-in caps; a blank cell keeps the safe
default (never "unlimited"); an unparseable value refuses billable ops (read-only still
works) and names the offending row.

## `courts.csv` — search scoping

Generated/edited via `pacer courts` (`enable-all`, `disable-all`, `invert`,
`enable <ids…>`, `disable <ids…>`), or by hand:

```csv
court_id,enabled
cand,1
nysd,1
txnd,0
```

Enabled courts scope `pacer pcl cases` / `pacer pcl parties` (an explicit `--court`
wins). No file, or all courts enabled, means nationwide.
