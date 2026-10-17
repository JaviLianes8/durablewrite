# durablewrite 1.0.0 certification report

Progress:
- [x] Branch `release/1.0.0` created from `main` (0.2.0, 52e5cc8; PyPI has 0.2.0)
- [x] Baseline gates run on 0.2.0
- [x] Real ground truth: OS documentation, syscall traces, crash points, reference library (item 7)
- [x] API review and 1.0.0 API changes (item 1)
- [x] Errors, typing, docstrings and doctests (items 2 to 5)
- [x] Contract, fuzz and author mutation round (items 6, 9, 18)
- [x] Docs: README, GUIDE, CHANGELOG (items 11, 12)
- [x] Packaging, e2e and upgrade from PyPI 0.2.0 (items 8, 10, 13, 14), author run
- [x] Five QA lenses report PASS (item 19)
- [x] Independent reviewer reports PASS (item 16)
- [x] Gates (item 15), final run
- [ ] PR and trace guard CLEAN (item 17); merge and publish left to the maintainer

## Scorecard

| # | Item | Result |
| --- | --- | --- |
| 1 | Public API reviewed for stability | PASS: the twelve 0.2.0 names keep their parameters and defaults; every change is in the CHANGELOG and the guide's upgrade section, checked against PyPI 0.2.0 by lens a and lens d |
| 2 | `__all__` exact, no private imports in docs | PASS: twelve names, pinned by `tests/test_contract.py` |
| 3 | Docstrings with runnable examples, doctests | PASS: every public name, constants included; `tests/test_docs.py` runs them and every README example |
| 4 | Typed end to end | PASS: `mypy --strict src tests` clean on Windows and Linux, `py.typed` shipped, per-mode overloads; `Any` only where documented |
| 5 | Typed, documented, bounded errors | PASS: the guide's error table; messages never repeat the refused value; CLI messages cut to 120 characters |
| 6 | Contract tests of every public name | PASS: the contract files listed below, plus those added by every lens round |
| 7 | Real ground truth | PASS: 13 fetched OS and Python pages (manifest), real libc call traces and kills on Linux, kills at every call on Windows and POSIX, 120 scenarios recorded from atomicwrites 1.4.1 on both platforms; lens b re-derived it with its own shim, hooks and 23 scenarios |
| 8 | Real e2e from the wheel | PASS: console script and `python -m` by subprocess from a fresh venv, sabotages caught, upgrade in place from PyPI 0.2.0 |
| 9 | Seeded fuzz, no crash, hang or blowup | PASS: `tests/test_fuzz.py` and linear-time checks; lens c's 20,000 random argument sets, stress and hostile filesystems |
| 10 | Supported Pythons | PASS: CPython 3.10.19, 3.11.5, 3.12.12, 3.13.2, 3.14.2, 3.14.2 free-threaded on Windows; 3.14.4 on Linux |
| 11 | README and `twine check` | PASS |
| 12 | Dated CHANGELOG 1.0.0 section | PASS: 2026-10-16 |
| 13 | pyproject 1.0.0, Production/Stable | PASS: pinned by `tests/test_packaging.py` |
| 14 | sdist and wheel contents | PASS |
| 15 | Gates each exit 0 | PASS: fresh clone at 797a504: format, lint, `mypy --strict src` and `src tests`, `pytest` 386 passed, 79 skipped on a second Windows PC (CPython 3.14, oracles not fetched there); 443 passed, 22 skipped on WSL as `nobody`, 441 and 24 as root, with the oracles fetched (426/39 and 428/37 without) |
| 16 | Independent reviewer | PASS: round 1 FAIL at ef4eaf5, round 2 FAIL at 9fb1509, round 3 FAIL at 3355ddd, round 4 PASS at cb6c5dd |
| 17 | PR and trace guard | pending; merge and publish left to the maintainer |
| 18 | Contracts bite (mutations) | PASS: author 50 on two platforms; blind lens e 167 plus 10; reviewer 35, 5, 16 and 4; lens a 30, 25 and 5; lens b 14 and 4; lens c 40, 19 and 1; lens d 26 and 3; every survivor killed by a contract or argued equivalent |
| 19 | Five independent QA lenses | PASS: a round 4, b round 3, c round 4, d round 4, e round 3 |

## Baseline on 0.2.0 (before any change)

Fresh clone of `main` (52e5cc8): `ruff format --check .`, `ruff check .` and
`mypy --strict src tests` exit 0. The full suite on this PC (CPython 3.13.2) had one
failure, `test_hardening::test_a_locked_temp_file_is_still_removed_once_released`: after
its holder process was killed the removal had only zero-delay retries left, so a virus
scanner touching the fresh file made it fail. No doctests.

Defects found in 0.2.0 during this certification:

- `cleanup_temp_files(older_than=float("nan"))` removed every temp file, including those
  of running writers (the age comparison is always false with NaN).
- `RetryPolicy` accepted NaN and infinite delays (a blocked rename then failed with an
  unrelated `ValueError` or `OverflowError` from `sleep` and left its temp file),
  non-integer attempts, and grew integer delays without bound.
- `bytes` paths, paths containing NUL, `permissions` outside `0..0o7777`, unknown
  encodings and invalid `newline` values failed late or with unrelated errors, some after
  a temp file had been created.
- Error messages repeated the refused value (`mode`, `fsync`, the path, CLI values).
- With `fsync="full"` the rename itself was never made durable on Windows, and macOS
  flushes did not reach the drive (no `F_FULLFSYNC`).
- `atomic_write` was typed `IO[Any]` whatever the mode.
- `cleanup_temp_files` skipped read-only temp files on Windows.
- The README claimed `boltons.fileutils.atomic_save` has no Windows support; it uses
  `ReplaceFileW` there. The guide quoted documentation prose and cited a page whose
  certificate has expired.

## Ground truth (item 7)

Everything third party stays out of the repository: `tests/oracle/MANIFEST.json` lists
each source (URL, fetch date 2026-10-16, size, sha256, licence) and
`scripts/fetch_oracles.py` downloads it into the gitignored `tests/oracle/`.

- **OS documentation.** Thirteen pages (Microsoft `MoveFileExW`, `FlushFileBuffers`,
  `ReplaceFileW`, `_commit`, `CreateFileW`; Linux `fsync(2)`, `rename(2)`, `link(2)`;
  POSIX `rename`; Apple `fsync(2)`; Python `os`; LWN "Ensuring data reaches disk"; the
  ext4 documentation). `tests/test_sources.py` checks that each still names the flags and
  calls the guide relies on (`MOVEFILE_WRITE_THROUGH`, `F_FULLFSYNC`,
  `ERROR_UNABLE_TO_MOVE_REPLACEMENT_2`, `FILE_SHARE_DELETE`, `auto_da_alloc` and others).
  The guide paraphrases them; nothing is quoted.
- **Real system calls on Linux.** `tests/trace/dwtrace.c` (written here) is an
  `LD_PRELOAD` library that logs `open`, `write`, `fsync`, `rename`, `link` and `unlink`
  inside one folder and can `SIGKILL` the process right before or after call N.
  `tests/test_linux_trace.py` compiles it with gcc and checks, for each fsync level and
  for create-only writes, the real order the man pages ask for: `open temp O_EXCL`,
  `write`, `fsync temp`, `rename temp target`, `open . O_DIRECTORY`, `fsync .` (and
  `link`, `unlink` for create-only). It then kills the writer before and after every one
  of those calls: the target is always the old content until `rename` or `link` has
  returned and the complete new content after, and every leftover is a temp file that
  `cleanup_temp_files` reclaims. Run on WSL2 Ubuntu (kernel 6.6.87.2, ext4, gcc 15.2.0,
  CPython 3.14.4) as root and as `nobody`.
- **Crash points on Windows and POSIX.** `tests/test_crash_points.py` does the same one
  level up (wrapping `os.open`, `os.fsync`, `os.replace`, `os.link`, `os.remove` and the
  `MoveFileExW` call, killing with `TerminateProcess` or `SIGKILL`), and pins the Windows
  sequence: `fsync`, then `MoveFileExW` with `MOVEFILE_WRITE_THROUGH |
  MOVEFILE_REPLACE_EXISTING` for `"full"`, plain `os.replace` for `"file"` and `"none"`.
- **Reference library.** `atomicwrites` 1.4.1 (PyPI sdist, sha256 81b2c907...) ran 120
  scenarios (absent, file, directory, symlink, dangling link; `w` and `wb`; overwrite or
  create-only; empty, ASCII and non-ASCII payloads; a block that finishes or raises) on
  Windows 11 (CPython 3.13.2) and on WSL2 Linux (3.14.4).
  `tests/fixtures/atomicwrites-{windows,linux}.json` is its recorded output (program
  output). `tests/test_reference.py` checks that durablewrite matches it in every plain
  file scenario and every scenario where the block raises, and differs only as
  documented: a directory and an existing name are refused before the block runs,
  symlinks are written through, and new files follow the umask where atomicwrites makes
  them `0o600`. With the library fetched the recording is rerun live. Under the tracer
  both libraries make the same `fsync temp`, `rename`, `fsync dir` sequence, and
  atomicwrites also uses `MOVEFILE_WRITE_THROUGH` and `F_FULLFSYNC`, which durablewrite
  now does too.
- **Random kills** (`tests/test_crash.py`, 40 seeded kills mid-write) and four concurrent
  writer processes with a reader (`tests/test_concurrency.py`) on both platforms.

Not run: macOS. The `F_FULLFSYNC` path and its fallback are pinned by
`tests/test_contract_platform.py` with an injected `fcntl`; the guide says macOS was not
part of the test runs. No test can cut power; the guide says durability against power
loss rests on the documented calls.

## API review (item 1)

Kept from 0.2.0 with the same names, parameters and defaults: the twelve names of
`__all__`, the temp file naming scheme, the CLI options and exit statuses.

Changed for 1.0.0 (CHANGELOG and the guide's upgrade section): write-through rename on
Windows and `F_FULLFSYNC` on macOS for `"full"`; every argument checked when a writer is
called, before any I/O (`TypeError`, `ValueError`, `LookupError`); stricter
`RetryPolicy` and `cleanup_temp_files` arguments; messages that never repeat the refused
value (the CLI quotes at most 40 characters); `atomic_write` overloads typed `IO[str]`
for `"w"` and `IO[bytes]` for `"wb"`; read-only temp files removed by cleanup on Windows;
the `dev` extra replaced by `requirements-dev.txt`.

Kept on purpose: truthy values for the on/off options (not forced to `bool`); the legacy
`durable` and `fsync_dir` flags (documented as legacy); exit status 1 for usage errors;
`MoveFileExW` rather than `ReplaceFileW` (the guide gives the documented reason).

## Errors, typing, docs (items 2 to 5)

- `__all__` has twelve names; `tests/test_contract.py` pins it.
- Every public name has a docstring with a doctest, including the constants
  (`FsyncLevel`, `DEFAULT_RETRY`, `NO_RETRY`), whose attribute docstrings
  `tests/test_docs.py` extracts and runs. Every README Python block runs in order in a
  temp folder.
- `mypy --strict src tests` clean on Windows and on Linux; `py.typed` shipped;
  `tests/test_contract_platform.py` holds a strictly typed client of the overloads. `Any`
  appears only in the documented `IO[Any]` fallback for a non-literal mode and in
  `write_json_atomic(obj: Any)`.
- Errors: the table in the guide; `tests/test_contract_api.py` checks that 21 refused
  arguments raise at call time, touch nothing and give messages under 100 characters that
  never contain the refused value.

## Contracts, fuzz and mutations (items 6, 9, 18)

New contract files: `test_contract_api.py`, `test_contract_platform.py`,
`test_contract_edges.py`, `test_crash_points.py`, `test_linux_trace.py`,
`test_reference.py`, `test_sources.py`, `test_docs.py`, `test_packaging.py`,
`test_e2e_upgrade.py`. `test_fuzz.py`: 300 seeded write sequences against a model
(random sizes up to 70 KB, create-only, failing blocks, every fsync level), 150 hostile
Unicode names, the longest names the filesystem accepts, 200 random JSON values, 300
random `--json` inputs to the CLI, and linear-time checks for writes (4 against 32 MiB)
and cleanup (4,000 against 16,000 entries).

Author mutation round: 50 mutations over every module, each applied alone to a fresh
clone, suite with `-x` (wheel and upgrade tests excluded), file restored after, baseline
green before and after. Linux: WSL2, CPython 3.14.4, as `nobody` and as root. Windows:
a second Windows PC, CPython 3.14.2. A mark `*` means the mutant survived the first run and was
killed by a contract added after it, confirmed by rerunning that mutant.

| # | Module | Mutation | Linux | Windows |
| --- | --- | --- | --- | --- |
| 1 | `_write` | file fsync dropped | test_crash_points::test_the_call_sequence_is_flush_then_rename_then_directory[create] | test_contract_edges::test_legacy_flags_choose_the_file_and_directory_syncs[True-False-0] |
| 2 | `_write` | flush before metadata dropped | test_linux_trace::test_the_real_system_calls_come_in_the_documented_order[create] | survived |
| 3 | `_write` | directory fsync condition inverted | test_cli::test_an_unsynced_directory_exits_with_status_three | test_contract_edges::test_legacy_flags_choose_the_file_and_directory_syncs[True-False-0] |
| 4 | `_write` | write-through tied to the file level | survived | test_contract_platform::test_only_full_writes_the_rename_through_on_windows[file-True-None] |
| 5 | `_write` | temp removed only after publishing | test_atomic::test_error_removes_the_temp_file | test_atomic::test_error_removes_the_temp_file |
| 6 | `_write` | create-only check ignores links and directories | test_contract_edges::test_create_only_refuses_a_dangling_link_before_the_block * | test_contract_edges::test_create_only_refuses_a_dangling_link_before_the_block |
| 7 | `_write` | replaced private file gets a world-readable temp | test_hardening::test_temp_file_is_private_when_replacing_a_private_file | survived |
| 8 | `_write` | default text encoding is the locale | survived | test_contract_edges::test_text_mode_defaults_to_utf8_whatever_the_locale |
| 9 | `_write` | temp beside the link instead of the target | test_metadata::test_symlink_into_another_directory_keeps_the_temp_beside_the_target | test_metadata::test_symlink_into_another_directory_keeps_the_temp_beside_the_target |
| 10 | `_write` | directory sync error names the file | test_hardening::test_directory_sync_failure_is_reported_after_the_replace | survived |
| 11 | `_atomic` | append mode accepted | test_atomic::test_invalid_mode_is_rejected | test_atomic::test_invalid_mode_is_rejected |
| 12 | `_atomic` | retry type unchecked | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs16-TypeError] | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs16-TypeError] |
| 13 | `_atomic` | overwrite flag ignored | test_cli::test_no_overwrite_fails_on_an_existing_file | test_cli::test_no_overwrite_fails_on_an_existing_file |
| 14 | `_atomic` | follow_symlinks ignored | test_hardening::test_no_follow_replaces_a_symlink_to_a_directory | test_contract_edges::test_create_only_refuses_a_dangling_link_before_the_block |
| 15 | `_atomic` | preserve_owner ignored | test_contract_edges::test_preserve_owner_restores_another_users_file (root run) * | survived |
| 16 | `_check` | NUL check misses NUL | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs20-ValueError] | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs20-ValueError] |
| 17 | `_check` | permission range too wide | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs11-ValueError] | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs11-ValueError] |
| 18 | `_check` | bool permissions accepted | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs13-TypeError] | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs13-TypeError] |
| 19 | `_check` | tab newline accepted | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs6-ValueError] | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs6-ValueError] |
| 20 | `_check` | infinity accepted | test_contract_api::test_retry_policy_rejects_values_that_cannot_wait[kwargs4-ValueError] | test_contract_api::test_retry_policy_rejects_values_that_cannot_wait[kwargs4-ValueError] |
| 21 | `_check` | minimum made exclusive | test_contract_api::test_retry_delays_are_floats_capped_even_for_huge_budgets | test_contract_api::test_retry_delays_are_floats_capped_even_for_huge_budgets |
| 22 | `_check` | bytes paths accepted | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs17-TypeError] * | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs17-TypeError] |
| 23 | `_options` | zero attempts accepted | test_contract_api::test_retry_policy_rejects_values_that_cannot_wait[kwargs0-ValueError] | test_contract_api::test_retry_policy_rejects_values_that_cannot_wait[kwargs0-ValueError] |
| 24 | `_options` | shrinking multiplier accepted | test_contract_api::test_retry_policy_rejects_values_that_cannot_wait[kwargs9-ValueError] | test_contract_api::test_retry_policy_rejects_values_that_cannot_wait[kwargs9-ValueError] |
| 25 | `_options` | cap not applied to the first delay | test_contract_edges::test_the_first_delay_is_capped_too * | test_contract_edges::test_the_first_delay_is_capped_too |
| 26 | `_options` | one delay too many | test_contract_api::test_retry_delays_are_floats_capped_even_for_huge_budgets | test_contract_api::test_retry_delays_are_floats_capped_even_for_huge_budgets |
| 27 | `_options` | file level also syncs the directory | test_crash_points::test_the_call_sequence_is_flush_then_rename_then_directory[replace-file] | test_contract_platform::test_only_full_writes_the_rename_through_on_windows[file-True-None] |
| 28 | `_options` | legacy fsync_dir ignored | test_contract_edges::test_legacy_flags_choose_the_file_and_directory_syncs[True-False-0] * | test_contract_edges::test_legacy_flags_choose_the_file_and_directory_syncs[True-False-0] |
| 29 | `_replace` | sharing violation not retried | survived | test_hardening::test_a_locked_temp_file_is_still_removed_once_released |
| 30 | `_replace` | read-only target retried | survived | test_sharing::test_read_only_target_is_not_retried |
| 31 | `_replace` | attempt count off by one | survived | test_sharing::test_exhausted_retry_raises_and_leaves_target_and_no_temp |
| 32 | `_replace` | write-through never used on Windows | test_atomic::test_write_text_atomic_creates_the_file | test_contract_platform::test_only_full_writes_the_rename_through_on_windows[full-True-9] |
| 33 | `_replace` | temp name kept after create-only link | test_crash_points::test_the_call_sequence_is_flush_then_rename_then_directory[exclusive] | survived |
| 34 | `_replace` | create-only ignored without write-through | test_crash_points::test_the_call_sequence_is_flush_then_rename_then_directory[exclusive] | test_overwrite::test_no_overwrite_detects_a_file_created_during_the_write[none]* |
| 35 | `_win` | flags swapped | survived | test_contract_platform::test_only_full_writes_the_rename_through_on_windows[full-False-8] |
| 36 | `_win` | error names swapped | survived | test_contract_platform::test_write_through_errors_look_like_os_replace_errors |
| 37 | `_fs` | stem limit off | test_contract_edges::test_names_up_to_48_characters_appear_whole_in_the_temp_name[30] * | test_contract_edges::test_names_up_to_48_characters_appear_whole_in_the_temp_name[30] |
| 38 | `_fs` | new files ignore the group write bit of the umask | test_contract_edges::test_new_files_take_every_bit_the_umask_allows * | survived |
| 39 | `_fs` | no fsync when F_FULLFSYNC fails | test_contract_platform::test_full_fsync_is_used_where_the_platform_has_it[True] | test_contract_platform::test_full_fsync_is_used_where_the_platform_has_it[True] |
| 40 | `_fs` | preserve_mode ignored | test_metadata::test_preserve_mode_can_be_turned_off | equivalent here (mode bits are not applied on Windows); the run stopped on a transient process-test failure |
| 41 | `_fs` | replaced link inherits the mode | test_hardening::test_no_follow_replaces_a_symlink_to_a_directory | survived |
| 42 | `_fs` | locked temp treated as read-only | survived | survived |
| 43 | `_cleanup` | age cutoff loosened | test_contract_edges::test_cleanup_respects_the_exact_age_boundary * | test_contract_edges::test_cleanup_respects_the_exact_age_boundary |
| 44 | `_cleanup` | pattern without the leading dot | test_json_cleanup::test_cleanup_never_touches_other_files | run stopped on a transient process-test failure; name matching is the same on both platforms, so the Linux kill applies |
| 45 | `_cleanup` | links to files are removed | test_contract_edges::test_cleanup_never_follows_a_link_named_like_a_temp_file * | test_contract_edges::test_cleanup_never_follows_a_link_named_like_a_temp_file |
| 46 | `_cli` | cli mode range narrowed | test_contract_edges::test_cli_accepts_special_permission_bits * | test_contract_edges::test_cli_accepts_special_permission_bits |
| 47 | `_cli` | unsynced directory exit status | test_cli::test_an_unsynced_directory_exits_with_status_three | survived |
| 48 | `_cli` | append swallows read errors | test_contract_edges::test_cli_append_fails_when_the_current_content_cannot_be_read * | survived |
| 49 | `_helpers` | json without trailing newline | test_contract::test_every_writer_replaces_completely_and_leaves_no_temp[json] | test_contract::test_every_writer_replaces_completely_and_leaves_no_temp[json] |
| 50 | `_helpers` | NaN allowed in json | test_hardening::test_json_refuses_nan_unless_allowed | test_hardening::test_json_refuses_nan_unless_allowed |

Result: every mutation is killed on at least one platform where its code runs.
Platform-specific code accounts for the one-sided survivors: 4, 29 to 31, 35 and 36 touch
Windows-only branches (no effect on Linux); 2, 7, 10, 15, 33, 38, 41, 47 and 48 touch
POSIX-only behaviour (the flush order is only visible in the system call trace;
permission bits, owners, hard links and the directory fsync do not exist on Windows).
Mutant 8 is equivalent on Linux, where the locale is UTF-8. Mutant 15 needs root and is
killed in the root run; 48 needs a non-root user. One equivalent on both platforms: 42 (a
temp file locked by another process goes through the read-only branch, which clears the
attribute, fails to delete and reports it as locked: the same outcome). The thirteen
first-run survivors (6, 8, 15, 22, 25, 28, 34, 37, 38, 43, 45, 46, 48) led to
`tests/test_contract_edges.py`, the path message check in `test_contract_api.py` and the
fsync-level parametrisation in `test_overwrite.py`.

The first Windows runs also showed test weaknesses, fixed before the final round: the
random-kill test read and cleaned the target while a virus scanner held it for a moment;
the locked-temp test left its holder process running when it failed; four concurrent
writers on a slow third Windows machine outlasted the default retry budget (documented behaviour; the
test now gives its writers a larger budget and the guide says when to); and a 240
character name failed on that machine, whose Windows has no long path support, for
`os.replace` and `MoveFileExW` alike (the test now accepts that clean refusal).

## Packaging and end-to-end (items 8, 10, 13, 14), author run

- `python -m build` and `twine check --strict` on a clean clone: both PASSED.
- Wheel: the package modules, `py.typed`, LICENSE, metadata and the console script.
  Sdist: `src`, `tests` (fixtures, manifest and tracer source, not the fetched material),
  the two oracle scripts, README, GUIDE, CHANGELOG, CONTRIBUTING, LICENSE,
  `requirements-dev.txt`, pyproject and `.gitignore`; no report, round notes or scratch.
- Every interpreter on this PC, the wheel installed in a fresh venv and the sdist's
  suite run with `src` removed: CPython 3.10.19 (323 passed, 67 skipped: no `tomllib`),
  3.11.5, 3.12.12, 3.13.2, 3.14.2 and 3.14.2 free-threaded (326 passed, 66 skipped
  each), plus the wheel and upgrade tests from the sdist, 5 passed on each. Linux:
  CPython 3.14.4 on WSL2. 3.8 and 3.9 are below `requires-python`.
- Upgrade: PyPI 0.2.0 installed in a fresh venv and upgraded in place to the 1.0.0 wheel
  (`tests/test_e2e_upgrade.py`): same exported names and written content; NaN delays and
  NaN cleanup ages accepted before and refused after; `bytes` paths refused.
- Full suite on the second Windows PC three times in a row: 333 passed, 66 skipped each
  time; green on the third machine and on WSL as root and as `nobody`.

## Independent QA lenses (item 19)

Each lens was a fresh reviewer that read the certification rules and CERT-1.0.md first,
ran the code rather than only reading it, reported only to the author and posted nothing
to GitHub. Lenses ran one at a time. Later rounds were bounded to confirming earlier
findings plus one sweep of at most 40 mutations on the code changed since.

| Lens | Round | Head | Verdict | Findings and outcome |
| --- | --- | --- | --- | --- |
| a. API and docs | 1 | bb5fd47 | FAIL | on/off options took any value by truthiness although the docs promised `TypeError` for a wrong type (`overwrite="no"` overwrote); `mode` and `fsync` of the wrong type gave `ValueError`; CLI usage errors repeated long values in full; the upgrade notes missed `permissions=True`, `bool` attempts and a non-callable `sleep`; the directory sync message repeated the path. Fixed in 2f4c22a. Information only: `atomic_write(p, "wb", encoding=...)` type-checks through the `str` fallback overload and fails at runtime |
| a | 2 | 2f4c22a | FAIL | `durable` and `fsync_dir` were not checked when `fsync` was given; runtime CLI errors were not cut while the docs said every line was; 30 mutations, 8 survivors (option name in the message, cut boundary and marker, directory sync message, cause and errno). Fixed in 95effab with contracts |
| a | 3 | 95effab | FAIL | 25 mutations, 3 survivors: the 120/121 boundary and the exit-3 warning (not cut, target dropped). Pinned in `tests/test_contract_cli.py` (6d57c4f) |
| a | 4 | 6d57c4f | PASS | the five remaining mutants killed on Windows; external `mypy --strict` client of all twelve names clean; every README example and CLI line run on Windows and WSL; API dump identical to PyPI 0.2.0 apart from the documented changes |
| b. Correctness and ground truth | 1 | ed5e0a7 | FAIL | own LD_PRELOAD shim on WSL (18 cases, 436 kills at call boundaries, root and `nobody`), own Windows import-table hooks (observed flags 0x9, 0x8, 0x1, 0x0 per level and mode; 92 kills), 13 pages fetched and compared, 23 own scenarios against atomicwrites 1.4.1. Blocking: with a relative target, a `chdir` during the block moved the rename to the new directory while the old one was fsynced. Nits: README called Windows atomic without qualification; two GUIDE claims were observed, not on the cited pages. Fixed in 8638c49 |
| b | 2 | 8638c49 | FAIL | fix confirmed by trace; 14 mutations, 4 survivors (lexical normalisation through a symlinked directory, the old directory line, `realpath` with a relative link). Pinned in `tests/test_contract_paths.py` (9a17c2f) |
| b | 3 | 86c6f7f | PASS | fresh reviewer with the same lens; all four round-2 mutants killed on WSL as root and as `nobody` by `tests/test_contract_paths.py` |
| c. Adversarial and robustness | 1 | 864097f | FAIL | FIFO, socket and device targets were replaced by a regular file (`--append` on a FIFO hung); permission bits were set by name, so a temp name swapped for a symlink redirected the `chmod`; a failing text wrapper closed the descriptor twice and hid its error behind `EBADF`, and non-text codecs passed the up-front check; `--json` refused integers over 4300 digits; an interrupt between creating and wrapping the temp file leaked the descriptor (temp file stuck on Windows); Windows `name:stream` paths left an empty file; delays long enough to overflow `sleep`. Fixed in 46a7255. Held up: no torn target in thread, process and reader stress; 20,000 random argument sets; full and tiny filesystems; 2 GB stdin in 22 MB of memory; cleanup linear to 80,000 files |
| c | 2 | 46a7255 | FAIL | fixes confirmed; the descriptor could still be closed twice after a wrapper failure and the interrupt window moved by one line; 40 mutations, 5 survivors (sockets and devices, special mode bits, `closefd=False`, the descriptor reset). Fixed in e138c5a with a single owner for the descriptor and `tests/test_contract_descriptors.py` |
| c | 3 | e138c5a | FAIL | both confirmed fixed by exceptions injected at every line on both platforms; 19 mutations, 1 survivor (the close when an interrupt lands before the descriptor is wrapped). Pinned in c6e43bc |
| c | 4 | c6e43bc | PASS | the survivor killed on Windows and WSL |
| d. Packaging and real e2e | 1 | 27ec22b | FAIL | build and `twine check --strict` passed; wheel (19 entries, RECORD verified) and sdist contents clean; metadata complete; installed-wheel suites on CPython 3.10.19 to 3.14.2t and WSL 3.14.4 (root and `nobody`); 7 sabotages caught; upgrade from PyPI 0.2.0 compared. Blocking: `cleanup_temp_files(older_than=0)` skipped a just-written temp file on Windows with 3.10 to 3.12 (coarse `time.time()`, about 11% of tries), making the suite flaky there; `FileExistsError.filename` became absolute (undocumented) and the CLI cut hid the file name. Minor: the retry `TypeError` missing from the CHANGELOG. Fixed in 9ba5c95 |
| d | 2 | 9ba5c95 | FAIL | fixes confirmed (0 of 2000 left behind, 45 of 45 repeat runs green on 3.10 to 3.12); new: a Windows reader racing four writers got `FileNotFoundError` about once in 1,000 to 2,000 opens (0.2.0 too) while the guide said never, which also made `test_concurrency` flaky; 26 mutations, 3 survivors (small positive ages, the name of a followed link, the errno). Fixed in 1c45e45 |
| d | 3 | 1c45e45 | FAIL | wording and the test confirmed (20 of 20 runs); the followed-link contract resolved the name before comparing, so it could not fail. Fixed in fed6063 |
| d | 4 | fed6063 | PASS | the last survivor killed on WSL and on Windows |
| e. Contract strength (blind) | 1 | d7c84c3 | FAIL | 167 mutations of its own over all eleven modules (Windows 3.13.2; survivors rerun on WSL as `nobody` and as root): 131 killed, 8 equivalent, 28 missing contracts (temp name collisions, symlink loops, distinct uid and gid, directory descriptor leaks, cleanup reporting a file someone else removed, POSIX permission errors waited out, lock violation retries, error errno and filename, `remove_temp` raising, `write_json_atomic` pass-through, `write_bytes_atomic(p, 3)`, cleanup defaults, pattern, order, held files and newlines, and the CLI options reaching the library, Ctrl-C status, `--json` UTF-8). One was a code bug: cleanup listed files that vanished before it removed them. Fixed and pinned in 1de1c6e (`tests/test_contract_blind*.py`) |
| e | 2 | 1de1c6e | FAIL | the 28 killed on their platforms; 10 mutations of the fix, 3 survivors (a vanished temp waited out on an error path; the Windows read-only branch reporting a vanished file). Pinned in c4cae3f |
| e | 3 | c4cae3f | PASS | the three killed; equivalents over all rounds: `O_BINARY` and `O_CLOEXEC` flags, winerror 33 in the delete-lock set, the `PermissionError` check on Windows lock errors, the redundant `raw.close()` in `_wrap`, an extra flush, `match` versus `search` on an anchored pattern, the regular-file check in the CLI redirect test, and two `missing_ok` defaults no caller observes |

## Independent review (item 16)

Fresh reviewers that read the certification rules and CERT-1.0.md first, ran every gate
alone on fresh clones on Windows and WSL, re-derived the report's claims, ran their own
mutations and posted nothing to GitHub. Round 3 was relaunched with a fresh reviewer after
a usage limit cut the previous one.

| Round | Head | Verdict | Findings and outcome |
| --- | --- | --- | --- |
| 1 | ef4eaf5 | FAIL (6, 18) | gates, claims, packaging, ground truth and house rules confirmed; 35 mutations, 5 survivors: the long-name temp stem (`- 9` and the 8-character digest), the CLI 40-character quote boundary, `write_json_atomic` dropping `fsync`, and the drive handling of the stream check, which exposed that a drive-relative target on another drive was not pinned on Windows. Nits: docstring `Raises` and the 130 exit status missing in places; report counts depend on the fetched oracles; machine names in the report. Fixed in 9fb1509 |
| 2 | 9fb1509 | FAIL (5, 6, 18) | the five confirmed killed; the new Windows pin had no contract (2 survivors), and `ntpath.basename` dropped a drive-like prefix so `C:a:s` slipped past the stream check and left an empty file. Fixed in 3355ddd |
| 3 | 3355ddd | FAIL (6, 18) | both confirmed; 16 mutations, 3 survivors (splitting on one separator only); an invalid escape in a test. Fixed in cb6c5dd, with ruff's W rules enabled |
| 4 | cb6c5dd | PASS | the four remaining mutants killed on their platforms; `-W error::SyntaxWarning` clean; every gate exits 0 alone on Windows and WSL |

