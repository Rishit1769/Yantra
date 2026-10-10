# Evidence-Guided Recovery (Experimental)

## Problem statement
Generic retries may repeat unsafe operations, while conservative manual recovery can stall recoverable runs.
## Research hypothesis
Classifying failures from typed events and reconciliation evidence can select safer recovery actions and improve recovery success over fixed retry policy without increasing duplicate effects.
## Baseline
No automatic retry for ambiguous effects; bounded static retry for known transient read-only operations.
## Proposed method
Use explicit evidence features (error class, operation semantics, provider acceptance ID, external state probe, checkpoint sequence) to classify safe retry, reconcile, hold, or fail. Human approval for uncertain irreversible effects. Any learned component proposes; deterministic policy gates action.
## Experimental design
Fault-injection matrix across crash windows, timeouts and duplicate delivery; compare recovery choices against ground truth with mock external systems, then controlled integration tests.
## Metrics
Recovery success, duplicate effect rate, false-safe classification, time to recovery, manual intervention, cost.
## Ablations
Remove operation semantics, external reconciliation, checkpoint/event evidence; compare heuristic versus classifier.
## Limitations
External truth may be unavailable; failure logs can be incomplete; false-safe recovery is high impact.
## Reproducibility requirements
Pin fault schedule, fake service state, classifier/policy, event corpus and decision thresholds. No autonomous recovery release without security review; no current results.
