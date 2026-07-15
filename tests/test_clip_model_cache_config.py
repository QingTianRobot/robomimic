import json
import os
from pathlib import Path
import subprocess
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


def resolved_service(hf_endpoint=None):
    environment = os.environ.copy()
    for key in list(environment):
        if key.startswith("COMPOSE_"):
            environment.pop(key)
    environment.pop("HF_ENDPOINT", None)
    if hf_endpoint is not None:
        environment["HF_ENDPOINT"] = hf_endpoint

    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                os.devnull,
                "-f",
                str(REPO_ROOT / "compose.yaml"),
                "config",
                "--format",
                "json",
            ],
            cwd=REPO_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise AssertionError(
            "docker compose config failed\n"
            f"stdout:\n{error.stdout}\n"
            f"stderr:\n{error.stderr}"
        ) from error
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

        model_mount = next(
            volume
            for volume in service["volumes"]
            if volume["target"] == "/opt/models/huggingface"
        )
        self.assertEqual(model_mount["type"], "bind")
        self.assertEqual(
            Path(model_mount["source"]), REPO_ROOT / "models" / "huggingface"
        )
        self.assertFalse(model_mount.get("read_only", False))

        compose_text = (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn(
            "      - type: bind\n"
            "        source: ./models/huggingface\n"
            "        target: /opt/models/huggingface\n"
            "        bind:\n"
            "          create_host_path: true\n",
            compose_text,
        )

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
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            ignored_cache.returncode,
            0,
            msg=f"stderr:\n{ignored_cache.stderr}",
        )

        python_package = subprocess.run(
            [
                "git",
                "check-ignore",
                "--no-index",
                "-q",
                "robomimic/models/base_nets.py",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            python_package.returncode,
            1,
            msg=f"stderr:\n{python_package.stderr}",
        )

    def test_huggingface_endpoint_can_be_overridden(self):
        service = resolved_service("https://huggingface.co")

        self.assertEqual(
            service["environment"]["HF_ENDPOINT"], "https://huggingface.co"
        )


if __name__ == "__main__":
    unittest.main()
