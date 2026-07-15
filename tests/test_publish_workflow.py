import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-image.yml"


class PublishWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text()

    def test_triggers_permissions_and_concurrency(self):
        self.assertIn("push:\n    branches:\n      - master", self.workflow)
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertIn("if: github.ref == 'refs/heads/master'", self.workflow)
        self.assertIn("contents: read", self.workflow)
        self.assertIn("packages: write", self.workflow)
        self.assertIn("cancel-in-progress: false", self.workflow)

    def test_uses_official_docker_actions_and_pushes_amd64(self):
        for action in (
            "actions/checkout@v4",
            "actions/setup-python@v5",
            "docker/setup-buildx-action@v3",
            "docker/login-action@v3",
            "docker/metadata-action@v5",
            "docker/build-push-action@v6",
        ):
            self.assertIn(action, self.workflow)
        self.assertIn("platforms: linux/amd64", self.workflow)
        self.assertIn("push: true", self.workflow)
        self.assertIn("cache-from: type=gha", self.workflow)
        self.assertIn("cache-to: type=gha,mode=max", self.workflow)

    def test_publishes_latest_and_short_sha_tags(self):
        self.assertIn("IMAGE_NAME: ghcr.io/qingtianrobot/robomimic", self.workflow)
        self.assertIn("type=raw,value=latest", self.workflow)
        self.assertIn("type=sha,format=short,prefix=sha-", self.workflow)
        self.assertIn("org.opencontainers.image.source", self.workflow)
        self.assertIn("org.opencontainers.image.revision", self.workflow)

    def test_tests_before_login_and_notifies_only_after_successful_push(self):
        tests_index = self.workflow.index("Run notifier tests")
        login_index = self.workflow.index("Log in to GHCR")
        build_index = self.workflow.index("Build and push image")
        notify_index = self.workflow.index("Send Feishu publication card")
        self.assertLess(tests_index, login_index)
        self.assertLess(login_index, build_index)
        self.assertLess(build_index, notify_index)
        self.assertIn("if: ${{ success() }}", self.workflow)
        self.assertNotIn("failure()", self.workflow)
        self.assertIn(
            "FEISHU_WEBHOOK_URL: ${{ secrets.FEISHU_WEBHOOK_URL }}",
            self.workflow,
        )
        self.assertIn(
            "FEISHU_WEBHOOK_SECRET: ${{ secrets.FEISHU_WEBHOOK_SECRET }}",
            self.workflow,
        )
        self.assertIn("steps.build.outputs.digest", self.workflow)


if __name__ == "__main__":
    unittest.main()
