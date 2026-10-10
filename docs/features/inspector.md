# Visual Inspector

## Overview
Optional future Next.js/TypeScript/Tailwind interface for authorized execution inspection and approval.
## Motivation
Timelines and structured histories make complex runs easier to understand without coupling the headless SDK to a UI.
## Functional requirements
1. `YANTRA-INSPECTOR-001`: Display execution timeline, states, model/tool calls, sessions, workflow graph, skills, usage/cost-if-known, and errors.
2. `YANTRA-INSPECTOR-002`: Support authorized execution comparison and approval queue with decision binding.
3. `YANTRA-INSPECTOR-003`: Operate solely through versioned APIs; never access DB directly.
## Non-functional requirements
Security: tenant auth, CSP, output escaping. Performance: paginated timeline. Reliability: tolerate event gaps. Scalability: read models. Maintainability: independent release.
## Architecture
Independent web app consuming service read APIs; not required for SDK or workers.
## Data flow
Browser auth -> scoped API -> redacted event/read model -> timeline; approval posts bound decision.
## Interfaces
Future HTTP API; no frontend exists.
## Persistence
Service owns all persistence; UI state is non-authoritative.
## Configuration
API origin, auth provider, retention display and feature flags.
## Security
No secrets/full content by default; XSS defenses; audit administrative actions.
## Error handling
Show stale/gapped data and refresh state; never imply event replay performed action.
## Observability
UI API latency/errors and audited approval actions.
## Testing
Auth/tenant isolation, XSS, stale approval, API compatibility, accessibility.
## Acceptance criteria
Headless SDK works with UI absent; UI uses only documented API; cross-tenant and injection tests pass; timeline detects sequence gaps.
## Dependencies
Event schema, service APIs, authentication.
## Priority
P3.
## Implementation status
Proposed.
## Open questions
Auth provider and event read-model design.
