"""Receipt extraction and interpretation model settings."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class InferenceConfig:
    key: str = field(repr=False)
    base_url: str = "https://api.tokenfactory.nebius.com/v1"
    vision_base_url: str = "https://api.tokenfactory.nebius.com/v1"
    agent_model: str = "Qwen/Qwen3-30B-A3B-Instruct-2507"
    vision_model: str = "openbmb/MiniCPM-V-4_5"

    @classmethod
    def from_env(cls, values):
        if not values.get("NEBIUS_API_KEY"):
            raise RuntimeError("Set NEBIUS_API_KEY for Token Factory inference")
        base = values.get("NEBIUS_BASE_URL", cls.base_url)
        return cls(
            values["NEBIUS_API_KEY"],
            base,
            values.get("NEBIUS_VISION_BASE_URL", base),
            values.get("NEBIUS_AGENT_MODEL", cls.agent_model),
            values.get("NEBIUS_VISION_MODEL", cls.vision_model),
        )

    def to_env(self):
        return {
            "NEBIUS_API_KEY": self.key,
            "NEBIUS_BASE_URL": self.base_url,
            "NEBIUS_VISION_BASE_URL": self.vision_base_url,
            "NEBIUS_AGENT_MODEL": self.agent_model,
            "NEBIUS_VISION_MODEL": self.vision_model,
        }
