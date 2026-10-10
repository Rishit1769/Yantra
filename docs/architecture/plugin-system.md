# Plugin System

Plugins are optional extensions discovered through an explicit manifest and allowlist, not arbitrary import-time code. Initial plugin contracts should support declarative provider/tool/skill registrations and separately isolated executable adapters. Plugin identity, version, dependency constraints, permissions, provenance, and API compatibility are validated before activation. Untrusted plugins run out of process under a constrained worker when feasible; in-process plugins are trusted code and must be documented as such.

No plugin can modify runtime policy, access secrets outside declared secret references, or alter another tenant's registrations. See [plugin manifest](../specifications/plugin-manifest.md), [plugins feature](../features/plugins.md), and [plugin security](../security/skill-security.md).
