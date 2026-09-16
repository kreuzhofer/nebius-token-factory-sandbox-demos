"""Token Factory model construction from explicit configuration."""

from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider


class Models:
    def __init__(self, config):
        key, base, vision_base = config.key, config.base_url, config.vision_base_url
        if not all(url.startswith("https://") for url in (base, vision_base)):
            raise ValueError("HTTPS Token Factory endpoints required")
        self.clients = [
            AsyncOpenAI(api_key=key, base_url=url, timeout=90, max_retries=1)
            for url in (base, vision_base)
        ]
        self.agent_name = config.agent_model
        self.vision_name = config.vision_model
        # Explicit capabilities avoid applying OpenAI-specific reasoning defaults to third-party IDs.
        self.agent = OpenAIChatModel(
            self.agent_name,
            provider=OpenAIProvider(openai_client=self.clients[0]),
            profile=OpenAIModelProfile(supports_tools=True, openai_supports_reasoning=False),
        )
        self.vision = OpenAIChatModel(
            self.vision_name,
            provider=OpenAIProvider(openai_client=self.clients[1]),
            profile=OpenAIModelProfile(
                supports_json_object_output=True, openai_supports_reasoning=False
            ),
        )

    async def close(self):
        for client in self.clients:
            await client.close()
