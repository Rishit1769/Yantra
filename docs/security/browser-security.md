# Browser Security

Browser workers are isolated per run/context, ephemeral, and restricted by a domain and network policy. Validate canonical URLs and DNS resolution at connection time; block private, loopback, link-local, multicast, reserved, and metadata-service addresses. Revalidate redirects and subresources; network egress firewall is required because browser-level checks alone are insufficient.

Do not import application cookies or credentials by default. Downloads have MIME/size/path limits and scanning where appropriate. Page DOM, screenshots, and downloads are untrusted; do not execute page instructions as policy. No CAPTCHA bypass, access-control circumvention, or stealth evasion is designed. Cleanup browser storage/processes on every exit path.
