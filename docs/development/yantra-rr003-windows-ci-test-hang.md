# YANTRA RR-003: Windows CI Test Hang

**Engineering verification: INCOMPLETE. Windows CI: INCOMPLETE. Public release readiness: NO-GO.**

RR-003 diagnosed and corrected a deterministic test-design race seen in all
three Windows matrix jobs. The corrected test and local validation pass on
Python 3.12, 3.13, and 3.14 on macOS. The patched code has not yet run on a
Windows GitHub runner; no push or workflow trigger was made.

## 1. Baseline and CI evidence

- Fix branch: `fix/yantra-rr003-windows-test-hang`, based on
  `chore/yantra-rr002-packaging-validation` at `d31cd34`.
- Package version remains `0.2.0`; the worktree was clean at task start.
- The failing workflow was run `39000189856` on PR #1, head `d31cd34`.
- In that run, all macOS and Ubuntu Python 3.12/3.13/3.14 jobs succeeded.
  All three Windows jobs remained in the `Test` step and ended canceled.
- The earlier run `39000171783` also ended with all Windows jobs canceled.
  Its retained logs show the same last passing test and same next test for
  Windows Python 3.12, 3.13, and 3.14.
- In both attempts, pytest printed
  `test_worker_completion_racing_cancellation_does_not_leak_child PASSED`
  (about 36%), then began
  `test_timeout_racing_completed_worker_has_deterministic_timeout_result`.
  The test did not finish; each job had 83 passing tests before cancellation
  after about 29.5 minutes. The workflow's job timeout was 30 minutes.
- Logs were available for the canceled runs. The currently patched branch has
  not been pushed and therefore has no corresponding Windows CI result.

## 2. Root cause

This was a **test synchronization race**, not an established defect in the
production worker implementation. In the old test,
`tests/unit/test_execution_boundary.py`, a real subprocess was started with an
execution deadline of only 50 ms. The `completed` event was set only after
`super()._run_worker()` returned, but the test then awaited
`completed.wait()` without any bound.

If subprocess startup and execution did not finish within that 50 ms deadline,
the boundary could time out/cancel the worker before the event was set. The
test would then wait forever for an event that could no longer be set. This
control-flow failure is consistent with the same test being stuck across three
Windows/Python combinations; the specific suspension point is inferred because
the old CI invocation did not dump a test stack. macOS runs happened to
complete the subprocess before the very short deadline, masking the flaw.

Collection order confirms this was the test immediately following the last
visible passing test. No evidence implicated shared state, a persistent worker
leak, authorization, or worker protocol behavior.

## 3. Fix and security impact

The timeout-result test now uses a deterministic boundary fixture that produces
a successful `ExecutionResult` immediately, signals completion, then suspends
before returning it. This isolates its actual assertion—that the enclosing
execution deadline wins while a ready result is pending return—from
platform-dependent process startup. Its event wait is bounded to one second.

Real subprocess startup, timeout, cancellation, completion/cancellation race,
capacity release, cleanup, and repeated execution remain covered by neighboring
tests that use the actual worker. No production runtime code, authorization
checks, approvals, signing, replay protection, protocol validation, or worker
capacity behavior was changed.

## 4. CI hang diagnostics

- Pytest's built-in `faulthandler_timeout` is set to 120 seconds in
  `pyproject.toml`. With the existing verbose `pytest -v` command, a stuck test
  will retain its test identifier and emit Python thread stack traces rather
  than leaving only a silent test line.
- The workflow job-level limit was reduced from 30 to 15 minutes as a final
  runner safety net. The stack dump is diagnostic; the job timeout remains the
  eventual hard stop.
- No additional test dependency was added and `uv.lock` was not changed. The
  package index exposed `pytest-timeout` 2.5.0 as yanked for an accidental
  breaking change; that option was rejected rather than locking a yanked
  release. Pytest's built-in faulthandler support requires no plugin.

## 5. Local verification

Executed on macOS arm64:

| Python | Full suite | Focused security tests | Four offline examples | Ruff / format / Pyright |
|---|---:|---:|---|---|
| 3.12.15 | 229 passed | 45 passed | 4/4 passed | PASS |
| 3.13.15 | 229 passed | 45 passed | 4/4 passed | PASS (shared Python 3.12 static tooling) |
| 3.14.7 | 229 passed | 45 passed | 4/4 passed | PASS (shared Python 3.12 static tooling) |

Also passed: focused execution-boundary module (15 tests),
`uv lock --check` (35 packages resolved; lock unchanged), and `git diff
--check`. No warnings or skips were reported. The worker process lifecycle was
not reproduced on Windows locally; macOS success is not Windows evidence.

## 6. Platform matrix and remaining work

| Platform | Python 3.12 | Python 3.13 | Python 3.14 |
|---|---|---|---|
| macOS, existing RR-002 Actions run | PASS | PASS | PASS |
| Ubuntu, existing RR-002 Actions run | PASS | PASS | PASS |
| Windows, pre-fix Actions runs | CANCELLED at identified test | CANCELLED at identified test | CANCELLED at identified test |
| Windows, patched branch | NOT RUN | NOT RUN | NOT RUN |

The accepted fix is locally verified but Windows CI must run on the patched
commit before engineering verification can be PASS. Because the task forbids
push or billable workflow triggers without maintainer authorization, RR-003 did
not publish the branch or start a new run. After the maintainer pushes the fix
branch, the workflow's `push`/PR triggers will exercise all three Windows
versions; review the completed Test, build, and CLI steps before changing the
Windows status to PASS.

**Engineering verification: INCOMPLETE. Windows CI: INCOMPLETE. Public release
readiness: NO-GO.** No release, merge, tag, push, or publication occurred.
