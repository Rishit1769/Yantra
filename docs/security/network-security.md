# Network Security

Outbound network access is denied unless a tool/provider policy allows a destination. Use TLS verification, hostname and resolved-address validation, redirect revalidation, DNS rebinding defenses at connection, egress firewalling, bounded response sizes, and per-host rate limits. Block private and special-use addresses for scraping/browser/API tools unless an explicitly trusted integration is configured.

Provider endpoints require operator allowlisting; model-generated URLs never directly define arbitrary endpoints. Persistence service uses authenticated TLS/mTLS and restricted network reachability. Do not rely exclusively on preflight DNS checks; enforce at socket/network layer where possible.

The default model-gateway transport validates configured HTTP(S) endpoints, rejects redirects, bounds response sizes/timeouts, and checks resolved addresses at each TCP connection. It connects to a selected allowed IP while retaining the configured hostname for TLS verification. Loopback endpoints remain loopback-only; other private/special-use addresses require an explicit trusted private-network configuration. Caller-injected HTTPX clients own their transport and must enforce equivalent DNS/IP, redirect, TLS, proxy, egress, and credential-forwarding controls. An egress firewall remains recommended for deployments.
