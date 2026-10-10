# Evaluations

## Overview
Runs versioned datasets and policies against agents/providers to measure quality, cost, latency, safety, and recovery reproducibly.
## Motivation
Changes to prompts, routing, models, and tools need evidence beyond anecdotal examples.
## Functional requirements
1. `YANTRA-EVAL-001`: Pin dataset, code/config, provider/model, seed where supported, and evaluation protocol.
2. `YANTRA-EVAL-002`: Record task completion, tool success, latency, tokens/cost, policy violations, recovery, retrieval quality, throughput, scheduling overhead.
3. `YANTRA-EVAL-003`: Separate deterministic mock tests from live-provider evaluation and disclose nondeterminism.
4. `YANTRA-EVAL-004`: Preserve baselines and publish no result without conditions and sample size.
## Non-functional requirements
Security: dataset/license and PII controls. Performance: bounded concurrency. Reliability: resumable evaluation jobs. Scalability: worker limits. Maintainability: versioned harness.
## Architecture
Evaluation runner, dataset adapter, runtime, scoring functions, immutable result artifact.
## Data flow
Pin inputs -> execute controlled trials -> collect observations -> score -> compare baseline -> publish protocol/results.
## Interfaces
CLI/API concepts only; no commands currently exist.
## Persistence
Dataset/version manifest and result metadata; protect raw prompts and proprietary data.
## Configuration
Trials, concurrency, model, budget, scoring, timeouts, redaction.
## Security
Isolate external credentials and dataset access; test policy violation safely.
## Error handling
Failed/partial runs remain in denominator or are separately classified by declared protocol.
## Observability
All metrics above plus environment and version manifest.
## Testing
Scorer unit tests, protocol determinism, failure injection, independent reruns.
## Acceptance criteria
Two independent runs reproduce deterministic mock scores; every live report includes manifest, dataset provenance, conditions, exclusions, and uncertainty; no fabricated results.
## Dependencies
Runtime, event store, dataset governance.
## Priority
P2.
## Implementation status
Proposed.
## Open questions
Initial public benchmark datasets and scoring governance.
