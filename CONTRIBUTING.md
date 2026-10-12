# Contributing

YANTRA-001 provides the Python contract foundation and YANTRA-002 the model gateway foundation. Start with [documentation index](docs/index.md), [core API reference](docs/specifications/core-runtime-api.md), [contribution workflow](docs/development/contribution-workflow.md), and [coding standards](docs/development/coding-standards.md). Set up with `uv sync --all-groups`; before submitting, run Ruff check/format, Pyright, pytest, and `uv build --wheel`. For code changes, include tests, public contract impacts, threat/retention considerations, and docs; do not claim live provider behavior without live verification.

YANTRA is licensed under the Apache License, Version 2.0; see [LICENSE](LICENSE). Contributions intentionally submitted for inclusion are governed by Section 5 of that license unless explicitly designated otherwise. This repository does not establish a separate contributor license agreement.
