# Sandbox Security

Sandboxing is defense in depth, not a claim of perfect containment. Required controls include non-root identity, read-only base image, no host/container socket, minimal mounts, dropped capabilities, seccomp/AppArmor or platform equivalents, resource limits, network egress deny-by-default, ephemeral storage, image digest pinning, patching, and worker cleanup. Higher-risk arbitrary code may require VM/microVM or dedicated isolated infrastructure.

Threats include kernel/container escape, side channels, malicious image/dependency, resource exhaustion, network exfiltration, and secret discovery. Docker alone is not sufficient evidence. Security review defines supported threat level and residual risk. See [sandbox feature](../features/sandboxing.md).
