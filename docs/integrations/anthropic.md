# Anthropic Integration (YANTRA-002)

The Anthropic Messages adapter is implemented with normalized messages/content blocks, tool-use lifecycle, streaming, usage, model listing, credential validation, and typed errors. Current protocol tests use mocked HTTP only; live compatibility and account access are unverified. Capability overrides are per model, unsupported output modes fail explicitly, and credentials remain external secrets.
