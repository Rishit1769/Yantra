# Adaptive Context Allocation (Experimental)

## Problem statement
Fixed selection/truncation can omit useful evidence or waste context budget across tasks/providers.
## Research hypothesis
A provenance-aware allocator using task relevance and token cost can improve task success or evidence retention at fixed context budgets without increasing policy violations.
## Baseline
Deterministic priority ordering with recency and simple truncation; include full-history-with-truncation where feasible.
## Proposed method
Score candidate segments using query relevance, source reliability, recency, novelty, sensitivity, and estimated tokens; reserve instructions/output capacity; compact only selected low-priority history with source-linked summaries. Never elevate trust based on relevance.
## Experimental design
Use versioned tasks with gold evidence, multiple context budgets and provider tokenizers, randomized method order, repeated trials, and held-out domains. Compare matched token budgets and record omissions.
## Metrics
Task completion, evidence recall/precision, token usage, latency, contradiction rate, policy violations, and omission attribution.
## Ablations
Remove provenance, reliability, recency, novelty, token cost; compare generated versus extractive compaction.
## Limitations
Token estimates vary; relevance models can encode bias; summary can distort source; provider behavior is nondeterministic.
## Reproducibility requirements
Pin dataset/code/config/allocator version, model/provider, tokenizer, budgets, seeds if available, raw metric definitions, and redacted run manifests. No results are currently available.
