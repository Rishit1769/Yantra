# Tenant Isolation

Tenant identity is derived from authenticated application/service credentials, never trusted from model input or an unchecked request field. Persistence service applies tenant scoping in every repository query; unique keys and foreign keys include scope where needed. Consider PostgreSQL row-level security as defense in depth, with service role behavior tested explicitly. Worker payloads, caches, artifacts, vector filters, events, and inspector APIs all carry and verify tenant scope.

Required tests attempt cross-tenant reads/writes through every API and race/recovery path. Admin bypass is separately authenticated and audited. Global skills are explicitly public catalog records and do not reveal tenant-private metadata.
