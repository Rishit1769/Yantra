# Context Engine

Context assembly selects system/developer instructions, current input, bounded conversation history, approved skill content, tool observations, and permitted retrieved memories. Every segment carries provenance, trust label, token estimate, and sensitivity. Ordering and priority are deterministic except where a separately evaluated research policy is selected.

The assembler reserves capacity for instructions and response, then truncates/compacts lower-priority segments with explicit omission markers. It does not treat retrieved text as instructions. Provider tokenizers differ; estimates are labeled and conservative limits are used where exact tokenization is unavailable. Compaction preserves source references and must not silently rewrite audit history. See [context management](../features/context-management.md) and [adaptive context research](../research/adaptive-context.md).
