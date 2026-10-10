# Docker Deployment

Docker images may package the TypeScript persistence service, PostgreSQL for development, and optional isolated workers. Images should be pinned by digest in controlled deployments, run as non-root, use read-only filesystems where feasible, drop capabilities, avoid host sockets, and receive secrets through a secret manager. Compose is suitable for development, not by itself a production security or availability design.

Docker is not a complete sandbox boundary against hostile code. Production isolation may require dedicated workers, VM/microVM boundaries, network policy, and platform controls. No Dockerfile currently exists.
