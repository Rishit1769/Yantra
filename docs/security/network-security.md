# Network Security

Outbound network access is denied unless a tool/provider policy allows a destination. Use TLS verification, hostname and resolved-address validation, redirect revalidation, DNS rebinding defenses at connection, egress firewalling, bounded response sizes, and per-host rate limits. Block private and special-use addresses for scraping/browser/API tools unless an explicitly trusted integration is configured.

Provider endpoints require operator allowlisting; model-generated URLs never directly define arbitrary endpoints. Persistence service uses authenticated TLS/mTLS and restricted network reachability. Do not rely exclusively on preflight DNS checks; enforce at socket/network layer where possible.

The model gateway validates configured HTTP(S) endpoints, rejects redirects, bounds response sizes/timeouts, and only permits plain HTTP for loopback Ollama endpoints. Preflight validation is not a substitute for connection-time DNS/IP enforcement or an egress firewall; deployments should enforce those controls at the network boundary.
