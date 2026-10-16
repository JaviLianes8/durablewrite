# Contributing

Thanks for taking the time. This project keeps a small, predictable shape.

## Setup

```
pip install -r requirements-dev.txt
python scripts/fetch_oracles.py   # optional: reference library and cited pages
```

## Before you open a pull request

- Keep public API in `src/durablewrite/__init__.py`; internals live in `_`-prefixed modules.
- Add a test for the behaviour you change. Tests run against the real filesystem and
  real child processes; only the retry `sleep` and, in a few contract tests, single
  OS calls are replaced to observe what is asked of the operating system.
- Run the gate: `ruff format --check .`, `ruff check .`, `mypy --strict src tests` and
  `pytest` (the repository has `scripts/check.ps1` for this). The multi-process and
  packaging tests are marked `slow`; `pytest -m "not slow"` skips them while
  iterating, but the full suite must pass before a commit. Run it on Windows and on
  Linux; the system call tests need Linux and `gcc`.
- The crash and fuzz tests are seeded: set `DURABLEWRITE_CRASH_SEED`,
  `DURABLEWRITE_CRASH_ITERATIONS` or `DURABLEWRITE_FUZZ_SEED` to explore further.
- Material fetched by `scripts/fetch_oracles.py` stays out of the repository; only
  `tests/oracle/MANIFEST.json` is tracked.
- One logical change per commit, imperative subject line.

Open an issue first if the change is large or shifts the public API.
