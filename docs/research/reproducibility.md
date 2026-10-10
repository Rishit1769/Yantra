# Reproducibility

Each evaluation run pins source revision, dependency lock, runtime/API schema versions, agent/config/skill digests, provider/model/deployment, capability snapshot, dataset/split, tool versions, random seeds where supported, budget, environment, and scoring code. Provider nondeterminism and drift are reported, not concealed.

Artifacts include immutable manifest, redacted event observations, metric outputs, and provenance. Secrets and restricted data are not archived. Independent reruns quantify variance. Replay uses observations and mocks and never repeats external side effects automatically.
