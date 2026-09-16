"""Reusable runtime images are built without task credentials."""

import json
import tempfile
import unittest
from pathlib import Path

from nebius_sandbox import Operation

from codingagent_demo.runtime import build_runtime


class ImageService:
    def __init__(self):
        self.submitted = []

    def submit(self, image, **options):
        self.submitted.append((image, options))
        return "build-job"

    def wait(self, operation, seconds):
        return Operation.from_response(
            operation,
            {
                "status": "SUCCESS",
                "result_image_uuid": "runtime-image",
                "metadata": {"result": {"state": {"exit_code": 0}}},
            },
        )


class RuntimeTests(unittest.TestCase):
    def test_build_returns_reusable_image_and_saves_its_identity_without_credentials(self):
        service = ImageService()
        with tempfile.TemporaryDirectory() as directory:
            image = build_runtime(service, Path(directory), base_image="python-image")
            manifest = json.loads((Path(directory) / "runtime.json").read_text())
            self.assertEqual(image, "runtime-image")
            self.assertEqual(manifest["image"], image)
            self.assertEqual(manifest["operation_id"], "build-job")
            self.assertEqual(manifest["opencode_version"], "1.18.31")
            self.assertFalse(service.submitted[0][1].get("env"))
            self.assertFalse(service.submitted[0][1]["disposable"])
