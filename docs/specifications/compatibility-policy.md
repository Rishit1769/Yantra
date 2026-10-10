# Compatibility Policy

Public SDK types, RPC schemas, event envelopes, persisted checkpoint formats, and skill/plugin manifests are independently versioned. Compatible additions are preferred; removing/renaming fields, changing semantics, or tightening validation in a breaking way requires a major version or migration. Deprecated APIs receive a documented window and replacement. Persisted data has explicit readers/migrations and rollback constraints; binary compatibility is not assumed across Python/TypeScript services.

Provider capability changes are data and may vary per deployment. Runtime must reject unsupported required features clearly. Checkpoints include producer schema/runtime version and cannot be resumed by an incompatible reader without an explicit migration. Release notes document schema/API impact and supported compatibility matrix. Policy becomes effective only after maintainers adopt a release process and test it.
