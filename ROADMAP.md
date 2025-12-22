# indepacer Roadmap

## v0.2.0 - UX Redesign (Complete)

Major usability improvements to reduce friction and prevent cost accidents.

| Status | Feature |
|--------|---------|
| Done | Auto-resolve doc links (docs.json caching) |
| Done | Cost confirmation with --yes flag |
| Done | Structured archive (~/.pacer/archives/) |
| Done | `pacer view` command |
| Done | Interactive selection (-i flag) |
| Done | Context defaults (`pacer use`) |
| Done | Actionable error messages |
| Done | Command aliases (docket, doc, grep, cases, parties) |
| Done | `pacer migrate` for legacy archives |

---

## v0.2.1 - Polish

- [ ] Version bump to 0.2.0 in pyproject.toml
- [ ] Complete party/attorney extraction in fast parser
- [ ] `pacer stats` - Archive statistics
- [ ] `pacer cache clear/size` - Cache management
- [ ] CHANGELOG.md

---

## v0.3.0 - Analysis Features

- [ ] Full-text search across downloaded documents (PDF text extraction)
- [ ] Party/attorney relationship graphs
- [ ] Case timeline visualization
- [ ] Export to legal citation formats (BibTeX, Westlaw)
- [ ] Judge/court analytics
- [ ] Case outcome dashboard
- [ ] Docket diff/comparison

---

## v0.4.0 - Automation

- [ ] Watch mode for case updates
- [ ] Docket change detection (diff algorithm)
- [ ] Webhook notifications
- [ ] Calendar integration for deadlines (.ics export)
- [ ] Slack/Teams alerts
- [ ] Email alerts
- [ ] Digest batching (daily/weekly summaries)

---

## v0.5.0 - Integrations

- [ ] Browser extension (Chrome/Firefox)
- [ ] API server mode (`pacer serve`)
- [ ] LLM tool integration (structured output for function calling)

---

## Infrastructure

### Build/Release
- [ ] PyPI publication
- [ ] Docker image
- [ ] GitHub Actions CI/CD
- [ ] Release automation workflow

### Quality
- [ ] Test coverage reporting
- [ ] Pre-commit hooks (ruff, mypy)
- [ ] Security scanning (dependabot, bandit)
- [ ] Type checking (mypy strict)

### Documentation
- [ ] ReadTheDocs setup
- [ ] API reference (Sphinx/mkdocs)
- [ ] Man page for CLI
