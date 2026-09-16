"""Configuration is loaded once and passed without hidden environment mutation."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from configuration import load_env


class ConfigurationTests(unittest.IsolatedAsyncioTestCase):
    def test_local_file_preserves_environment_precedence_without_mutating_it(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"NEBIUS_API_KEY": "shell-key"}, clear=True),
        ):
            path = Path(directory) / ".env"
            path.write_text("# local\nNEBIUS_API_KEY=file-key\nCONTREE_PROJECT=project\n")
            values = load_env(path)
            self.assertEqual(values["NEBIUS_API_KEY"], "shell-key")
            self.assertEqual(values["CONTREE_PROJECT"], "project")
            self.assertNotIn("CONTREE_PROJECT", os.environ)
