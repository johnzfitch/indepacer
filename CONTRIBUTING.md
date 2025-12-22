# Contributing to indepacer

## Development Setup

```bash
# Clone the repo
git clone git@github.com:johnzfitch/indepacer.git
cd indepacer

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e '.[dev,full]'

# Run tests
pytest

# Lint
ruff check src/
```

## Project Structure

```
src/indepacer/
  __init__.py
  cli.py           # Click CLI commands
  config.py        # PacerConfig, credentials
  auth.py          # PACER authentication, TOTP
  downloader.py    # DocketDownloader, DocumentDownloader
  pcl.py           # PACER Case Locator REST client
  parser.py        # Fast selectolax HTML parser
  reader.py        # BeautifulSoup parser, batch CSV
  docket_types.py  # ParsedDocket dataclasses
  courts.py        # Court ID mappings
  models.py        # Pydantic API models
  errors.py        # Error catalog (v0.2)
  selection.py     # Interactive selection (v0.2)
  data/
    court-lookup.json  # Federal court data
```

## Adding Commands

CLI commands go in `cli.py`. Use Click's group/command pattern:

```python
@cli.group()
def mygroup():
    """Group description."""
    pass

@mygroup.command("subcommand")
@click.argument("arg")
@click.option("--flag", is_flag=True)
@click.pass_context
def my_command(ctx, arg: str, flag: bool):
    """Command description.

    \b
    Examples:
      pacer mygroup subcommand foo
      pacer mygroup subcommand bar --flag
    """
    config: PacerConfig = ctx.obj["config"]
    # Implementation
```

Use Rich for output:
- `console.print()` for stdout
- `err_console.print()` for stderr
- `Panel()` for boxed content
- `Table()` for tabular data
- `Progress()` for spinners

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=indepacer

# Run specific test
pytest tests/test_parser.py -v

# Run tests matching pattern
pytest -k "test_parse"
```

## Code Style

- Python 3.10+ with type hints
- Line length: 100 chars
- Format: ruff
- Docstrings: Google style

```bash
# Check style
ruff check src/

# Fix auto-fixable issues
ruff check src/ --fix
```

## Parser Performance

The parser uses selectolax (C extension) for speed. If selectolax unavailable, falls back to regex. BeautifulSoup is optional (`[full]` extra).

Benchmark on 300KB docket HTML:
- selectolax: ~5ms
- BeautifulSoup: ~500ms

## PACER API Notes

### Authentication
- CSO login at `https://pacer.uscourts.gov/pscof/cso/login`
- Returns `PacerSession` cookie
- MFA via TOTP (RFC 6238)

### PCL REST API
- Base: `https://pcl.uscourts.gov/pcl-public-api/rest`
- Search: `POST /cases/find`, `POST /parties/find`
- Pagination: 54 results per page
- Cost: $0.10 per page

### ECF Document Download
- URLs like `https://ecf.{court}.uscourts.gov/doc1/{id}`
- Requires authenticated session
- Returns PDF or receipt page

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Commit: `git commit -m "Release v0.x.x"`
4. Tag: `git tag v0.x.x`
5. Push: `git push origin dev --tags`

## Issue Labels

- `bug` - Something broken
- `enhancement` - New feature
- `ux` - User experience improvement
- `docs` - Documentation
- `blocked` - Waiting on external dependency
