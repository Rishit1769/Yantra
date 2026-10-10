# Browser Automation

## Overview
Optional Playwright integration handles JavaScript-rendered pages in isolated browser contexts.
## Motivation
Some permitted content cannot be retrieved from static HTTP responses.
## Functional requirements
1. `YANTRA-BROWSER-001`: Isolate context/profile per execution and clean it on all exit paths.
2. `YANTRA-BROWSER-002`: Restrict navigation, redirects, downloads, permissions, runtime, storage, and network egress.
3. `YANTRA-BROWSER-003`: Expose bounded navigation, DOM inspection, form interaction, screenshots, and downloads as separate authorized tools.
4. `YANTRA-BROWSER-004`: Do not bypass CAPTCHA, authentication, paywalls, or access controls.
## Non-functional requirements
Security: SSRF and credential isolation. Performance: resource caps. Reliability: process cleanup. Scalability: browser concurrency quotas. Maintainability: pinned browser build.
## Architecture
Runtime tool broker -> isolated Playwright worker/context -> filtered DOM/artifact return.
## Data flow
Authorize domain/action -> provision ephemeral context -> navigate with policy interception -> interact/read -> sanitize output -> close and erase state.
## Interfaces
Browser session handle and narrow action tools; no general unrestricted browser object to model.
## Persistence
Screenshots/downloads only as classified artifacts with explicit retention.
## Configuration
Domain policy, allowed actions, navigation timeout, request/response byte limits, download types/size, context lifetime.
## Security
Block private networks and unsafe redirects; isolate cookies/credentials; treat page content as prompt-injection input; scan/reject risky downloads; disable unnecessary permissions.
## Error handling
Browser crash/timeout/download block is typed; cleanup is retried and failure audited.
## Observability
Navigation domains, action, resource count/bytes, timeout and cleanup; redact DOM/content.
## Testing
SSRF, malicious redirect, download escape, cross-context cookie, injected page prompt, resource exhaustion, cleanup.
## Acceptance criteria
Contexts share no cookies/storage; disallowed destinations remain unreachable; download restrictions enforced; cleanup is verified after cancellation; no circumvention feature exists.
## Dependencies
Playwright, isolated worker/sandbox, network policy, approval.
## Priority
P2.
## Implementation status
Proposed.
## Open questions
Browser worker isolation tier and permitted default domains.
