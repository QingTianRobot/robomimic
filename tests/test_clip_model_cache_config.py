import json
import os
from pathlib import Path
import subprocess
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


def resolved_service(hf_endpoint=None):
    environment = os.environ.copy()
    environment.pop("HF_ENDPOINT", None)
    if hf_endpoint is not None:
        environment["HF_ENDPOINT"] = hf_endpoint

    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=REPO_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)["services"]["robomimic"]


class ClipModelCacheConfigTest(unittest.TestCase):
    def test_default_environment_mount_and_ignore_rules(self):
        service = resolved_service()

        self.assertEqual(
            service["environment"]["HF_HOME"], "/opt/models/huggingface"
        )
        self.assertEqual(
            service["environment"]["HF_ENDPOINT"], "https://hf-mirror.com"
        )

        cache_mount = next(
            volume
            for volume in service["volumes"]
            if volume["target"] == "/opt/models/huggingface"
        )
        self.assertEqual(cache_mount["type"], "bind")
        self.assertEqual(
            Path(cache_mount["source"]), REPO_ROOT / "models" / "huggingface"
        )
        self.assertFalse(cache_mount.get("read_only", False))

        for ignore_file in (".gitignore", ".dockerignore"):
            lines = (REPO_ROOT / ignore_file).read_text(encoding="utf-8").splitlines()
            self.assertIn("/models/", lines)

        ignored_cache = subprocess.run(
            [
                "git",
                "check-ignore",
                "--no-index",
                "-q",
                "models/huggingface/clip/model.safetensors",
            ],
            cwd=REPO_ROOT,
        )
        self.assertEqual(ignored_cache.returncode, 0)

        python_package = subprocess.run(
            [
                "git",
                "check-ignore",
                "--no-index",
                "-q",
                "robomimic/models/base_nets.py",
            ],
            cwd=REPO_ROOT,
        )
        self.assertNotEqual(python_package.returncode, 0)

    def test_huggingface_endpoint_can_be_overridden(self):
        service = resolved_service("https://huggingface.co")

        self.assertEqual(
            service["environment"]["HF_ENDPOINT"], "https://huggingface.co"
        )


if __name__ == "__main__":
    unittest.main()
