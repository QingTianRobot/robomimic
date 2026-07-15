import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-image.yml"

ACTION_REFS = (
    (
        "Check out repository",
        "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5",
        "v4",
    ),
    (
        "Set up Python",
        "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
        "v5",
    ),
    (
        "Set up Docker Buildx",
        "docker/setup-buildx-action@8d2750c68a42422c14e847fe6c8ac0403b4cbd6f",
        "v3",
    ),
    (
        "Log in to GHCR",
        "docker/login-action@c94ce9fb468520275223c153574b00df6fe4bcc9",
        "v3",
    ),
    (
        "Generate image metadata",
        "docker/metadata-action@c299e40c65443455700f0fdfc63efafe5b349051",
        "v5",
    ),
    (
        "Build and push image",
        "docker/build-push-action@10e90e3645eae34f1e60eeb005ba3a3d33f178e8",
        "v6",
    ),
)


def indented_block(text, marker):
    lines = text.splitlines()
    matches = [index for index, line in enumerate(lines) if line == marker]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one line {marker!r}, found {len(matches)}")

    start = matches[0]
    marker_indent = len(marker) - len(marker.lstrip())
    end = start + 1
    while end < len(lines):
        line = lines[end]
        indent = len(line) - len(line.lstrip())
        if line.strip() and indent <= marker_indent:
            break
        end += 1
    return "\n".join(lines[start:end])


class PublishWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_triggers_exact_permissions_guard_and_concurrency(self):
        trigger = indented_block(self.workflow, "on:")
        self.assertEqual(
            trigger.splitlines(),
            [
                "on:",
                "  push:",
                "    branches:",
                "      - master",
                "  workflow_dispatch:",
            ],
        )

        permissions = indented_block(self.workflow, "permissions:")
        self.assertEqual(
            permissions.splitlines(),
            ["permissions:", "  contents: read", "  packages: write"],
        )
        self.assertEqual(
            len(re.findall(r"(?m)^\s*permissions:\s*$", self.workflow)),
            1,
        )

        publish_job = indented_block(self.workflow, "  publish:")
        self.assertIn("    if: github.ref == 'refs/heads/master'", publish_job)
        self.assertNotRegex(publish_job, r"(?m)^    permissions:\s*$")

        concurrency = indented_block(self.workflow, "concurrency:")
        self.assertIn("${{ github.workflow }}", concurrency)
        self.assertIn("${{ github.ref }}", concurrency)
        self.assertIn("  cancel-in-progress: false", concurrency)

    def test_actions_are_exactly_pinned_and_checkout_drops_credentials(self):
        uses = re.findall(r"(?m)^\s+uses:\s+([^\s#]+)", self.workflow)
        self.assertEqual(uses, [reference for _, reference, _ in ACTION_REFS])

        for step_name, reference, version in ACTION_REFS:
            with self.subTest(step=step_name):
                step = indented_block(
                    self.workflow,
                    f"      - name: {step_name}",
                )
                self.assertRegex(
                    step,
                    rf"(?m)^        uses: {re.escape(reference)}\s+# {version}$",
                )

        checkout = indented_block(
            self.workflow,
            "      - name: Check out repository",
        )
        self.assertIn(
            "        with:\n          persist-credentials: false",
            checkout,
        )

    def test_metadata_tags_and_build_cache_are_scoped_to_their_steps(self):
        root_env = indented_block(self.workflow, "env:")
        self.assertIn("  IMAGE_NAME: ghcr.io/qingtianrobot/robomimic", root_env)
        length = re.search(
            r"(?m)^  DOCKER_METADATA_SHORT_SHA_LENGTH: ([0-9]+)$",
            root_env,
        )
        self.assertIsNotNone(length)
        self.assertEqual(length.group(1), "7")

        metadata = indented_block(
            self.workflow,
            "      - name: Generate image metadata",
        )
        for setting in (
            "type=raw,value=latest",
            "type=sha,format=short,prefix=sha-",
            "org.opencontainers.image.source=https://github.com/${{ github.repository }}",
            "org.opencontainers.image.revision=${{ github.sha }}",
        ):
            self.assertIn(setting, metadata)

        build = indented_block(self.workflow, "      - name: Build and push image")
        build_with = indented_block(build, "        with:")
        self.assertEqual(
            build_with.splitlines(),
            [
                "        with:",
                "          context: .",
                "          platforms: linux/amd64",
                "          push: true",
                "          tags: ${{ steps.metadata.outputs.tags }}",
                "          labels: ${{ steps.metadata.outputs.labels }}",
                "          cache-from: type=gha",
                "          cache-to: type=gha,mode=max",
            ],
        )
        for setting in (
            "platforms: linux/amd64",
            "push: true",
            "cache-from: type=gha",
            "cache-to: type=gha,mode=max",
        ):
            self.assertEqual(self.workflow.count(setting), 1)
            self.assertIn(setting, build)

    def test_notification_is_success_scoped_and_secrets_are_step_local(self):
        build_marker = "      - name: Build and push image"
        notify_marker = "      - name: Send Feishu publication card"
        self.assertLess(self.workflow.index(build_marker), self.workflow.index(notify_marker))

        notify = indented_block(self.workflow, notify_marker)
        self.assertEqual(
            re.findall(r"(?m)^        if:\s*(.+)$", notify),
            ["${{ success() }}"],
        )
        self.assertNotIn("failure()", self.workflow)

        notify_env = indented_block(notify, "        env:")
        self.assertEqual(
            notify_env.splitlines(),
            [
                "        env:",
                "          FEISHU_WEBHOOK_URL: ${{ secrets.FEISHU_WEBHOOK_URL }}",
                "          FEISHU_WEBHOOK_SECRET: ${{ secrets.FEISHU_WEBHOOK_SECRET }}",
                "          IMAGE_DIGEST: ${{ steps.build.outputs.digest }}",
                "          EVENT_NAME: ${{ github.event_name }}",
            ],
        )
        for secret in (
            "secrets.FEISHU_WEBHOOK_URL",
            "secrets.FEISHU_WEBHOOK_SECRET",
        ):
            self.assertEqual(self.workflow.count(secret), 1)
            self.assertIn(secret, notify_env)
        self.assertEqual(self.workflow.count("steps.build.outputs.digest"), 1)

    def test_notification_cli_uses_matching_sha_length_and_attached_git_values(self):
        notify = indented_block(
            self.workflow,
            "      - name: Send Feishu publication card",
        )
        cli_length = re.search(r'--sha-tag "sha-\$\{GITHUB_SHA::([0-9]+)\}"', notify)
        metadata_length = re.search(
            r"(?m)^  DOCKER_METADATA_SHORT_SHA_LENGTH: ([0-9]+)$",
            indented_block(self.workflow, "env:"),
        )
        self.assertIsNotNone(cli_length)
        self.assertIsNotNone(metadata_length)
        self.assertEqual(cli_length.group(1), metadata_length.group(1))
        self.assertEqual(cli_length.group(1), "7")
        self.assertIn(
            '--commit-message="$(git log -1 --pretty=%s)"',
            notify,
        )
        self.assertIn(
            '--commit-author="$(git log -1 --pretty=%an)"',
            notify,
        )


if __name__ == "__main__":
    unittest.main()
