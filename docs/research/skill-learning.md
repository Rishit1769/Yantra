# Skill Learning Research (Experimental)

## Problem statement
Successful traces may contain repeatable procedures that could become reusable skills, but traces may include secrets, tenant data, errors, or unsafe behavior.
## Research hypothesis
Human-reviewed candidate skills distilled from eligible traces can improve held-out task efficiency without increasing leakage or policy violations versus manually authored skills.
## Baseline
Manually authored skills and no-skill condition.
## Proposed method
Select consented traces, redact and generalize, extract instruction/resource candidates, validate declared capabilities, run held-out evaluation, and submit for human review. Never activate or escalate permissions automatically.
## Experimental design
Use synthetic and consented datasets separated by tenant/task family; blind reviewers where practical; evaluate candidate utility and leakage before/after redaction.
## Metrics
Held-out success, steps/tokens/cost, reviewer acceptance, secret leakage, cross-tenant leakage, harmful instruction rate, regression rate.
## Ablations
Remove redaction, provenance, human review (offline analysis only), held-out testing; never deploy unsafe ablation.
## Limitations
Selection bias, trace contamination, overfitting, reviewer burden, model memorization and unclear ownership.
## Reproducibility requirements
Record consent/provenance, source selection, redaction version, candidate digest, evaluator/model, reviewer protocol and deletion lineage. No skill-learning functionality exists.
