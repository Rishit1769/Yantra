# YANTRA-005 GitHub Actions CI and Release Verification Repair

**Status: CONDITIONAL PASS for workflow cleanup; hosted verification NOT VERIFIED; EXTERNAL BLOCKER for runner execution.** This report distinguishes the confirmed redundant scheduling from the still-unexplained GitHub-hosted runner queue. No run was marked failed merely because it remained queued.

## Investigation evidence

PR #5 merged on 2026-10-19 at 15:45:24 UTC. Its merge commit is `eff3c0818811da1053b565ce7fdcae46fce66d7a`; its final head was `8707f06fb6af2b78bb85eee08bf49018111878a6`.

At the 16:01 UTC status check:

- [Release Candidate Verification run 39280055530](https://github.com/Rishit1769/Yantra/actions/runs/39280055530), for PR #5/head `8707f06`, was `queued`. All nine Ubuntu/macOS/Windows × Python 3.12/3.13/3.14 matrix jobs had no steps and no runner assignment. The dependent “Build, install, and verify distributions” job was also listed as queued; it had not started.
- [Main CI run 39280384178](https://github.com/Rishit1769/Yantra/actions/runs/39280384178), for merge commit `eff3c08`, was `queued`; all nine jobs had no steps and no runner assignment.
- [Push CI run 39280049955](https://github.com/Rishit1769/Yantra/actions/runs/39280049955) and [pull-request CI run 39280055540](https://github.com/Rishit1769/Yantra/actions/runs/39280055540) both targeted `8707f06` and each scheduled the same nine-job matrix. This confirms redundant push-plus-PR CI on a feature branch.
- Earlier runs 39279409953 (push CI), 39279429896 (PR CI), and 39279429972 (release-candidate PR workflow) were also queued. The PR-only report commit `8707f06` triggered another release-candidate matrix because the workflow matched all `docs/**` changes.
- Repository API reported public visibility, `actions.enabled: true`, and `allowed_actions: all`. Both workflows use `contents: read`; neither declares a concurrency group. GitHub's public status endpoint last updated at 15:29 UTC reported all systems operational, but that status predates these queued runs and does not explain their lack of runner assignment.

No job entered `in_progress`; there are no failed steps or failed-job logs to inspect. No evidence points to YAML rejection, Python installation, uv resolution, test hangs, package build, or artifact upload failure. The exact scheduler cause (runner capacity, an account-level constraint, or another GitHub orchestration issue) is **not exposed by the run/job data**. Treat this as a hosted-runner scheduling blocker, not a diagnosed GitHub outage or code failure.

## Confirmed workflow inefficiencies and minimal repairs

1. `.github/workflows/ci.yml` previously ran `push` for every branch and also `pull_request`, producing two identical nine-job CI matrices for a feature branch. Push validation is now limited to `main`; PRs still receive the full existing matrix, and every merge to `main` still receives push validation.
2. `.github/workflows/release-candidate.yml` previously matched every `docs/**` change and launched the entire release matrix even for engineering audit/report-only edits. Its path list now covers user-facing getting-started, feature, guide, release-policy, and artifact-verification documentation, while excluding roadmap and audit-report-only edits. Source, tests, examples, lockfile, package metadata, scripts, README, and the workflow itself remain covered.

These reduce avoidable queued work without weakening the OS/Python matrix, tests, package checks, audit, artifact verification, or release security. The `package` job still depends on the complete `validate` matrix. It builds/installs locally in CI and uploads a short-lived Actions artifact only; it has no publication credentials or release/tag action.

## Workflow and platform review

- The matrix defines exactly nine combinations with stable job names: `<runner> / Python <version>`.
- `needs: validate` correctly gates packaging on all matrix jobs. The package job builds its own distributions; it does not depend on matrix artifacts, so no inter-job artifact download is missing.
- The package job is Ubuntu-only and explicitly uses Bash. The matrix command blocks use each runner's default shell and do not contain Bash-only syntax.
- Python versions are quoted strings, `uv sync --locked --all-groups` installs test/type/lint dependencies, and both workflows have bounded timeouts.
- GitHub created the original workflow runs, which is evidence that the committed workflow definitions were accepted for dispatch. Locally, Ruby Psych parses both edited YAML files. `actionlint` is not installed in this environment.
- No runner ever executed these steps during the investigation, so Windows-specific behavior, Python 3.14 CI, artifact upload, and release-candidate packaging remain **NOT VERIFIED**.

## Local validation

The repairs change workflow triggers/path filters and this report only; application source and tests are unchanged. On macOS/Python 3.12, the YANTRA-005 implementation had already passed 247 tests, Ruff lint/format, Pyright, `uv lock --check`, `uv audit --locked`, offline examples, package artifact verification, and clean wheel/sdist installation as recorded in the [YANTRA-005 engineering report](yantra-005-developer-preview.md). This repair turn additionally parses both edited workflow YAML files and checks the staged diff. These local results do not replace the missing hosted run.

## Verdict and next action

**Release readiness: NOT VERIFIED. External blocker: GitHub Actions jobs remain queued without runner assignment.** The confirmed duplicate triggers are corrected, but hosted CI cannot be called successful until the latest repair PR's nine CI jobs and release-candidate matrix plus package verification actually start and pass.

Retry/check from an authenticated terminal:

```sh
gh run list --repo Rishit1769/Yantra --branch main --limit 10
gh run view <run-id> --repo Rishit1769/Yantra --json status,conclusion,jobs
gh run watch <release-candidate-run-id> --repo Rishit1769/Yantra --exit-status
```

If jobs remain queued with no runner assignment, retain the run IDs and contact GitHub Support or the organization administrator to inspect Actions concurrency/runner scheduling and account-level limits. Do not rerun repeatedly while the queue remains stalled. Once a run starts, inspect actual failed logs and repair only demonstrated failures. No workflow was marked `continue-on-error`; tests and security checks remain enabled.
