# Plugin Manifest

The proposed manifest declares schema/API range, plugin ID/version, publisher/provenance, entrypoint kind, capabilities, permissions, dependencies, supported platforms, and integrity digest. Activation requires explicit allowlisting and compatibility validation. Secret access is by named reference and granted scope only. In-process executable plugins are trusted code; isolation requires a worker boundary and still needs OS-level controls. No plugin can mutate core policy or migrations. Exact manifest format remains open pending prototype.
