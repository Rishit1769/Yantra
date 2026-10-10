# Prompt Injection

Prompt injection is an expected property of processing untrusted text, not a problem solved by a prompt template. User input, web pages, tool results, imported skills, and retrieved memory are labeled by origin and remain data. Runtime permissions, endpoint allowlists, output filtering, and approval are enforced outside the model. Secrets are not placed in context unless necessary, and then only scoped/minimized.

Tests include direct and indirect malicious instructions, encoded content, tool-result substitution, cross-document injection, and attempts to solicit secrets or broaden permissions. Evaluations measure policy violation but do not establish immunity. No design promises that model reasoning reliably distinguishes malicious content.
