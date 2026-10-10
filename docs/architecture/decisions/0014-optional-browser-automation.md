# ADR 0014: Optional Browser Automation

- Status: Proposed
- Context: Browser automation is useful for dynamic pages but has significant network and execution risk.
- Decision: Playwright is an optional isolated subsystem, not a core SDK requirement; no CAPTCHA/access-control circumvention.
- Alternatives: HTTP-only; mandatory browser; unrestricted local browser.
- Consequences: Lightweight core and controlled expansion; worker and SSRF defenses required.
- Tradeoffs: Browser capabilities unavailable in minimal mode and may have operational cost.
