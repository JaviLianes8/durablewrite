# Contributing

Thanks for taking the time. This project keeps a small, predictable shape.

## Setup

```
pip install -r requirements-dev.txt
```

## Before you open a pull request

- Keep public API in `src/durablewrite/__init__.py`; internals live in `_`-prefixed modules.
- Add a test for the behaviour you change. Tests run against the real filesystem and
  real child processes; nothing on the write path is mocked. Only the retry `sleep` is
  injected.
- Run `scripts/check.ps1` (format, lint, types, tests) and make sure it passes. The
  multi-process and packaging tests are marked `slow`; `pytest -m "not slow"` skips
  them while iterating, but the full suite must pass before a commit.
- The crash test is seeded: set `DURABLEWRITE_CRASH_SEED` and
  `DURABLEWRITE_CRASH_ITERATIONS` to explore other interleavings.
- One logical change per commit, imperative subject line.

Open an issue first if the change is large or shifts the public API.
