"""Receipt model settings and child credentials remain explicit."""

import os
import unittest
from unittest.mock import patch

from configuration import SandboxConfig

from receipt_demo.configuration import InferenceConfig
from receipt_demo.inference import Models


class ReceiptConfigurationTests(unittest.IsolatedAsyncioTestCase):
    def test_child_configuration_contains_only_inference_values(self):
        values = {
            "NEBIUS_API_KEY": "inference-secret",
            "CONTREE_TOKEN": "sandbox-secret",
            "CONTREE_PROJECT": "project",
            "NEBIUS_BASE_URL": "https://inference.example/v1",
            "NEBIUS_VISION_MODEL": "vision",
            "UNRELATED_SECRET": "unrelated",
        }
        inference = InferenceConfig.from_env(values)
        sandbox = SandboxConfig.from_env(values)
        child = inference.to_env()
        self.assertEqual(child["NEBIUS_API_KEY"], "inference-secret")
        self.assertEqual(child["NEBIUS_VISION_BASE_URL"], values["NEBIUS_BASE_URL"])
        self.assertEqual(InferenceConfig.from_env(child), inference)
        self.assertEqual(sandbox.to_env()["CONTREE_TOKEN"], "sandbox-secret")
        self.assertNotIn("CONTREE_TOKEN", child)
        self.assertNotIn("UNRELATED_SECRET", child)
        self.assertNotIn("inference-secret", repr(inference))
        self.assertNotIn("sandbox-secret", repr(sandbox))

    async def test_model_construction_uses_config_without_consuming_environment(self):
        with patch.dict(os.environ, {"NEBIUS_API_KEY": "unchanged"}, clear=True):
            models = Models(
                InferenceConfig(key="explicit-key", agent_model="agent", vision_model="vision")
            )
            try:
                self.assertEqual(os.environ["NEBIUS_API_KEY"], "unchanged")
                self.assertEqual(models.clients[0].api_key, "explicit-key")
                self.assertEqual((models.agent_name, models.vision_name), ("agent", "vision"))
            finally:
                await models.close()
