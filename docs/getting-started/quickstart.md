# Core Contracts Quickstart

For the complete offline agent demonstration from an installed package, run
`yantra quickstart`; it exercises a bounded model → tool → model cycle without
network or credentials. See the [CLI reference](../features/cli.md).

This core-contract example uses the deterministic mock provider and exercises
a provider call only. For the implemented bounded model/tool/model cycle, see
the [agent runtime quickstart](../guides/agent-quickstart.md) and
`examples/agent_loop_offline.py`.

```python
import asyncio

from yantra.core.messages import Message, MessageRole, TextContent
from yantra.providers import MockProvider, ModelRequest

request = ModelRequest(
    model_id="mock-small",
    messages=(Message(role=MessageRole.USER, content=(TextContent(text="hello"),)),),
)
provider = MockProvider([MockProvider.text_response(request, "hello back")])
response = asyncio.run(provider.complete(request))
assert response.message.content[0].text == "hello back"
```

This mock-only example requires no credentials, network, database, or service.
It is not itself an agent example and does not imply broad live provider
compatibility.
