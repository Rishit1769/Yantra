# Core Contracts Quickstart

This example uses implemented contracts and the deterministic mock provider. It exercises a provider call only; YANTRA-001 does not implement an agent execution loop.

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

This mock-only example requires no credentials, network, database, or service. It is not an autonomous agent example and does not imply real providers are integrated.
