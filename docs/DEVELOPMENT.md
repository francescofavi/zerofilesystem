# Development

## Purpose

Contributor setup guide for `zerofilesystem`: prerequisites, local install, test/lint/type commands, pre-commit hooks, commit conventions, and the release process.

## Scope

Covers everything a contributor needs to build, test, and submit changes locally. Does not duplicate user-facing usage (see [USER_GUIDE.md](USER_GUIDE.md)) or internal architecture (see [ARCHITECTURE.md](ARCHITECTURE.md)).

---

## 1. Prerequisites

- **Python 3.12 or newer.** The `pyproject.toml` declares `requires-python = ">=3.12"`.
- **[uv](https://github.com/astral-sh/uv).** Used for dependency resolution, virtualenv management, and running tools.
- **git.** Standard.
- A POSIX shell on Linux/macOS or PowerShell/Cmd on Windows.

## 2. Clone and setup

```bash
git clone https://github.com/francescofavi/zerofilesystem.git
cd zerofilesystem
uv sync
```

`uv sync` reads `pyproject.toml` + `uv.lock`, creates `.venv/`, installs the package in editable mode together with the `dev` dependency group (`pytest`, `pytest-cov`, `pytest-mock`, `ruff`, `mypy`, `bandit`, `vulture`, `pre-commit`).

## 3. Running tests

Full suite (currently 207 tests across 9 modules):

```bash
uv run pytest
```

With coverage:

```bash
uv run pytest --cov=src/zerofilesystem --cov-report=term-missing
```

A single file or test:

```bash
uv run pytest tests/test_finder.py
uv run pytest tests/test_finder.py::TestFinderBasic::test_patterns
```

Quiet collection check (does not run tests):

```bash
uv run pytest --collect-only -q
```

## 4. Quality pipeline

All four tools are configured in `pyproject.toml`. Run them from the repo root.

```bash
uv run ruff check .
uv run ruff format .
uv run mypy src
uv run bandit -r src
uv run vulture src
```

Notes derived from `pyproject.toml`:

- **ruff:** `target-version = "py312"`, `line-length = 100`, lint selection `E, F, W, I, N, UP, B, C4, SIM`, ignores `E501`.
- **mypy:** `strict_optional`, `warn_return_any`, `warn_redundant_casts`, `warn_no_return`, `warn_unreachable`, `ignore_missing_imports`, `namespace_packages`, `explicit_package_bases`. `disallow_untyped_defs` and `disallow_incomplete_defs` are off (the codebase predates a strict-typing migration).
- **bandit:** scans `src/`, skips `B101`, `B403`, `B110`, excludes `tests/`, `examples/`, `scripts/`, `check_quality.py`.
- **vulture:** scans `src/` with `min_confidence = 80`.

## 5. Pre-commit hooks

The repo ships a `.pre-commit-config.yaml`. Install hooks once per clone:

```bash
uv run pre-commit install
```

Run all hooks against the full repo (useful before opening a PR):

```bash
uv run pre-commit run --all-files
```

Hooks run on every `git commit`. Do not bypass with `--no-verify` — fix the issue, re-stage, and commit again.

## 6. Commit conventions

The project uses **[Conventional Commits](https://www.conventionalcommits.org/)** because `release-please` derives the next version and changelog entry from commit messages.

| Prefix      | Meaning                                                      | Triggers release |
|-------------|--------------------------------------------------------------|------------------|
| `feat:`     | New user-visible feature                                     | minor bump       |
| `fix:`      | Bug fix                                                      | patch bump       |
| `docs:`     | Documentation only                                           | no               |
| `chore:`    | Build, tooling, dependencies, repo housekeeping              | no               |
| `refactor:` | Internal change, no behavior delta                           | no               |
| `test:`     | Tests added or modified                                      | no               |
| `perf:`     | Performance improvement                                      | patch bump       |
| `BREAKING CHANGE:` (in body) or `feat!:` / `fix!:` | Breaking API change | major bump       |

Commit messages should be in **English** and describe the **why**, not just the **what** — the diff already shows the what.

## 7. Running examples

Each script under `examples/` is self-contained:

```bash
uv run python examples/01_basic_io.py
uv run python examples/02_json_operations.py
uv run python examples/03_file_discovery.py
uv run python examples/04_file_locking.py
uv run python examples/05_transactions.py
uv run python examples/06_archives.py
uv run python examples/07_directory_ops.py
uv run python examples/08_complete_example.py
uv run python examples/09_finder.py
uv run python examples/10_watcher.py
```

Examples write to `tempfile.TemporaryDirectory()`; nothing leaks into the working tree.

## 8. Release process

The project uses **[release-please](https://github.com/googleapis/release-please)** + a manual PyPI publish via Trusted Publishing (OIDC).

1. Land conventional commits on `main`.
2. `release-please` opens or updates a "release PR" that bumps `src/zerofilesystem/__init__.py`'s `__version__` (Hatch reads it via `[tool.hatch.version]`), updates `CHANGELOG.md`, and updates `.release-please-manifest.json`.
3. Merging the release PR creates the `vX.Y.Z` tag.
4. The maintainer manually dispatches the `publish.yml` workflow in GitHub Actions, which builds with `uv build` and uploads to PyPI via OIDC. There is no `~/.pypirc`; no API token is stored.

`release-please` configuration: `release-please-config.json` + `.release-please-manifest.json`. CI configuration: `.github/workflows/`.

## 9. Project conventions

- **No runtime dependencies.** New external dependencies need explicit justification — stdlib first.
- **`Pathish` type alias** (`str | Path`) for every public path argument.
- **Atomic-by-default** for write operations; opt-out via `atomic=False`.
- **Static-method classes** for namespaces; instantiable classes only when state is genuinely needed (`FileLock`, `FileTransaction`, `Finder`, `Watcher`, `FileWatcher`).
- **One exception hierarchy** rooted at `ZeroFSError`. Stdlib errors propagate directly when they are the root cause.
- **`__all__`** in every public module; symbols outside `__all__` are private.
- **Modern type hints** (`X | None`, `list[X]`, `dict[str, Y]`) — `from __future__ import annotations` at the top of every module.

## 10. Layout reference

```
zerofilesystem/
├── src/zerofilesystem/        # Library source
├── tests/                     # 207 pytest tests
├── examples/                  # 10 runnable scripts
├── docs/                      # Public docs (this directory)
├── .internal_docs/            # Maintainer-only docs (gitignored exception, not shipped to PyPI)
├── pyproject.toml             # Project + tooling config
├── .pre-commit-config.yaml    # Pre-commit hooks
├── release-please-config.json # release-please config
└── .github/workflows/         # CI + publish workflows
```
