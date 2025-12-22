# indepacer Roadmap

## v0.2.0 - UX Redesign (In Progress)

Major usability improvements to reduce friction and prevent cost accidents.

### Features

| Status | Feature | Description |
|--------|---------|-------------|
| In Progress | Auto-resolve doc links | Cache `docs.json` when downloading dockets so `pacer fetch doc 31` works |
| In Progress | Cost confirmation | Prompt before billable operations, `--yes` to skip |
| In Progress | Structured archive | `~/.pacer/court/case/` hierarchy replaces flat files |
| In Progress | `pacer view` | View parsed dockets without specifying full paths |
| In Progress | Interactive selection | Select from PCL results instead of copy-paste |
| In Progress | Context defaults | `pacer use` sets working court/case |
| In Progress | Better errors | Actionable error messages with next steps |

### Architecture

```
~/.pacer/
  config/
    context.json         # Active court/case
  archives/
    nysd/
      1-18-cv-08434/
        docket.html      # Raw HTML
        docs.json        # Document manifest
        documents/
          001.pdf
```

Credentials remain at `~/.config/indepacer/config.env`

### New Commands

```bash
# Fetch (replaces download)
pacer fetch docket <court> <case>
pacer fetch doc <court> <case> <doc_num>

# View
pacer view [case]
pacer view --format json

# Context
pacer use <court> <case>
pacer use --clear

# Document list
pacer docs [case]
```

### Breaking Changes

- Archive path changes from `results/local_docket_archive/` to `~/.pacer/archives/`
- `download` commands renamed to `fetch`
- `parse text` merged into `view`

### Migration

Run `pacer migrate` to move existing files to new structure.

---

## v0.1.0 - Current Release

Initial release with core functionality:

- PACER authentication with MFA support
- Docket and document downloads
- PCL (PACER Case Locator) search
- HTML parsing with selectolax
- Batch operations

---

## Future Considerations

### v0.3.0 - Analysis Features

- [ ] Full-text search across downloaded documents (PDF text extraction)
- [ ] Party/attorney relationship graphs
- [ ] Case timeline visualization
- [ ] Export to legal citation formats

### v0.4.0 - Automation

- [ ] Watch mode for case updates
- [ ] Webhook notifications
- [ ] Calendar integration for deadlines
- [ ] Slack/Teams alerts

### Infrastructure

- [ ] PyPI publication
- [ ] Docker image
- [ ] GitHub Actions CI/CD
- [ ] Test coverage reporting
