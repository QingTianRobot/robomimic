# GitHub Image Publishing and Feishu Notification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish `ghcr.io/qingtianrobot/robomimic` after pushes to `master` and send one signed-or-unsigned purple Feishu card after each successful image push.

**Architecture:** A GitHub Actions workflow uses official Docker actions to build and push `linux/amd64` tags to GHCR. A standard-library Python notifier owns Feishu card construction, optional signing, transport, and sanitized error handling; focused unit tests exercise it without network access.

**Tech Stack:** GitHub Actions, Docker Buildx, GHCR, Python 3.11 standard library, Feishu custom-bot webhook, unittest, actionlint

---

### Task 1: Build and test the Feishu notifier

**Files:**
- Create: `.github/scripts/notify_feishu.py`
- Create: `tests/test_notify_feishu.py`

- [ ] **Step 1: Write the failing notifier tests**

Create `tests/test_notify_feishu.py` with:

```python
import importlib.util
import json
import socket
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".github" / "scripts" / "notify_feishu.py"
SPEC = importlib.util.spec_from_file_location("notify_feishu", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
notify = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = notify
SPEC.loader.exec_module(notify)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode("utf-8")


def metadata(**overrides):
    values = {
        "image": "ghcr.io/qingtianrobot/robomimic",
        "sha_tag": "sha-1234567",
        "digest": "sha256:abc123",
        "commit_sha": "1234567890abcdef",
        "commit_message": "Fix *unsafe* [card]\ncontent",
        "commit_author": "Robot_Author",
        "trigger": "push",
        "commit_url": "https://github.com/QingTianRobot/robomimic/commit/1234567890abcdef",
        "run_url": "https://github.com/QingTianRobot/robomimic/actions/runs/42",
        "package_url": "https://github.com/QingTianRobot/robomimic/pkgs/container/robomimic",
    }
    values.update(overrides)
    return notify.PublishMetadata(**values)


class NotifyFeishuTest(unittest.TestCase):
    def test_builds_unsigned_purple_card_with_escaped_metadata(self):
        payload = notify.build_payload(metadata())

        self.assertEqual(payload["msg_type"], "interactive")
        self.assertNotIn("timestamp", payload)
        self.assertNotIn("sign", payload)
        card = payload["card"]
        self.assertEqual(card["header"]["template"], "purple")
        self.assertEqual(
            card["header"]["title"]["content"],
            "🚀 robomimic 镜像发布成功",
        )

        markdown = card["elements"][0]["content"]
        self.assertIn("`ghcr.io/qingtianrobot/robomimic:latest`", markdown)
        self.assertIn("`ghcr.io/qingtianrobot/robomimic:sha-1234567`", markdown)
        self.assertIn("`sha256:abc123`", markdown)
        self.assertIn("[1234567]", markdown)
        self.assertIn("Fix \\*unsafe\\* \\[card\\] content", markdown)
        self.assertIn("Robot\\_Author", markdown)
        self.assertIn("`push`", markdown)

        actions = card["elements"][1]["actions"]
        self.assertEqual(actions[0]["url"], metadata().run_url)
        self.assertEqual(actions[1]["url"], metadata().package_url)

    def test_markdown_fields_are_compacted_and_length_limited(self):
        escaped = notify.escape_markdown("x" * 400 + "\nignored", limit=300)
        self.assertEqual(len(escaped), 300)
        self.assertTrue(escaped.endswith("…"))
        self.assertNotIn("\n", escaped)

    def test_generates_feishu_signature_and_timestamp(self):
        self.assertEqual(
            notify.make_signature("secret", "1700000000"),
            "fiWS2+gh28DOydAv7hzONH/mDn9+b1Y4Y5ivXWXy8vA=",
        )
        payload = notify.build_payload(
            metadata(),
            signing_secret="secret",
            timestamp="1700000000",
        )
        self.assertEqual(payload["timestamp"], "1700000000")
        self.assertEqual(
            payload["sign"],
            "fiWS2+gh28DOydAv7hzONH/mDn9+b1Y4Y5ivXWXy8vA=",
        )

    def test_send_payload_accepts_both_feishu_success_shapes(self):
        for response_payload in (
            {"StatusCode": 0, "StatusMessage": "success"},
            {"code": 0, "msg": "success"},
        ):
            captured = {}

            def opener(request, timeout):
                captured["request"] = request
                captured["timeout"] = timeout
                return FakeResponse(response_payload)

            notify.send_payload(
                "https://open.feishu.cn/open-apis/bot/v2/hook/example",
                {"msg_type": "interactive"},
                opener=opener,
            )
            self.assertEqual(captured["timeout"], notify.REQUEST_TIMEOUT_SECONDS)
            self.assertEqual(
                json.loads(captured["request"].data.decode("utf-8")),
                {"msg_type": "interactive"},
            )

    def test_rejects_missing_or_non_https_webhook(self):
        for webhook in ("", "http://open.feishu.cn/hook/example", "not-a-url"):
            with self.subTest(webhook=webhook):
                with self.assertRaisesRegex(
                    notify.NotificationError,
                    "valid HTTPS URL",
                ):
                    notify.send_payload(webhook, {})

    def test_reports_http_errors_without_echoing_url(self):
        webhook = "https://open.feishu.cn/open-apis/bot/v2/hook/private"

        def opener(request, timeout):
            raise HTTPError(webhook, 500, "server error", None, None)

        with self.assertRaisesRegex(notify.NotificationError, "HTTP 500") as caught:
            notify.send_payload(webhook, {}, opener=opener)
        self.assertNotIn(webhook, str(caught.exception))

    def test_reports_timeouts(self):
        def opener(request, timeout):
            raise socket.timeout("private timeout detail")

        with self.assertRaisesRegex(notify.NotificationError, "request failed"):
            notify.send_payload(
                "https://open.feishu.cn/open-apis/bot/v2/hook/example",
                {},
                opener=opener,
            )

    def test_rejects_malformed_json_response(self):
        def opener(request, timeout):
            return FakeResponse(b"not-json")

        with self.assertRaisesRegex(notify.NotificationError, "invalid JSON"):
            notify.send_payload(
                "https://open.feishu.cn/open-apis/bot/v2/hook/example",
                {},
                opener=opener,
            )

    def test_rejects_feishu_business_error(self):
        def opener(request, timeout):
            return FakeResponse({"code": 19001, "msg": "signature rejected"})

        with self.assertRaisesRegex(
            notify.NotificationError,
            "signature rejected",
        ):
            notify.send_payload(
                "https://open.feishu.cn/open-apis/bot/v2/hook/example",
                {},
                opener=opener,
            )

    def test_redacts_all_sensitive_values_from_errors(self):
        webhook = "https://open.feishu.cn/open-apis/bot/v2/hook/private"
        secret = "private-signing-secret"
        message = notify.redact_error(
            f"request {webhook} used {secret}",
            (webhook, secret),
        )
        self.assertNotIn(webhook, message)
        self.assertNotIn(secret, message)
        self.assertEqual(message.count("[REDACTED]"), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the notifier tests and verify they fail because the module is absent**

Run:

```bash
python3 -m unittest tests/test_notify_feishu.py
```

Expected: FAIL while loading `.github/scripts/notify_feishu.py` because the notifier has not been created.

- [ ] **Step 3: Implement the notifier**

Create `.github/scripts/notify_feishu.py` with:

```python
#!/usr/bin/env python3
import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import socket
import sys
import time
from dataclasses import dataclass
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request


REQUEST_TIMEOUT_SECONDS = 15
MAX_MARKDOWN_FIELD_LENGTH = 300


class NotificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PublishMetadata:
    image: str
    sha_tag: str
    digest: str
    commit_sha: str
    commit_message: str
    commit_author: str
    trigger: str
    commit_url: str
    run_url: str
    package_url: str


def escape_markdown(value, limit=MAX_MARKDOWN_FIELD_LENGTH):
    compact = " ".join(value.split())
    if len(compact) > limit:
        compact = compact[: limit - 1] + "…"
    return re.sub(r"([\\`*_~\[\]])", r"\\\1", compact)


def make_signature(secret, timestamp):
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(string_to_sign, digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def build_payload(metadata, signing_secret="", timestamp=None):
    short_sha = metadata.commit_sha[:7]
    markdown = "\n".join(
        (
            "**镜像地址**",
            f"`{metadata.image}:latest`",
            "**SHA 标签**",
            f"`{metadata.image}:{metadata.sha_tag}`",
            "**Digest**",
            f"`{metadata.digest}`",
            "**提交**",
            f"[{short_sha}]({metadata.commit_url})",
            "**提交信息**",
            escape_markdown(metadata.commit_message),
            "**提交作者**",
            escape_markdown(metadata.commit_author),
            "**触发方式**",
            f"`{escape_markdown(metadata.trigger)}`",
        )
    )
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "purple",
                "title": {
                    "tag": "plain_text",
                    "content": "🚀 robomimic 镜像发布成功",
                },
            },
            "elements": [
                {"tag": "markdown", "content": markdown},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看 Workflow"},
                            "type": "primary",
                            "url": metadata.run_url,
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看 GHCR 镜像"},
                            "url": metadata.package_url,
                        },
                    ],
                },
            ],
        },
    }
    if signing_secret:
        signed_at = str(timestamp if timestamp is not None else int(time.time()))
        payload["timestamp"] = signed_at
        payload["sign"] = make_signature(signing_secret, signed_at)
    return payload


def _validate_webhook_url(webhook_url):
    parsed = urllib_parse.urlparse(webhook_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise NotificationError("FEISHU_WEBHOOK_URL must be a valid HTTPS URL")


def send_payload(
    webhook_url,
    payload,
    timeout=REQUEST_TIMEOUT_SECONDS,
    opener=urllib_request.urlopen,
):
    _validate_webhook_url(webhook_url)
    request = urllib_request.Request(
        webhook_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with opener(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        raise NotificationError(
            f"Feishu webhook returned HTTP {exc.code}"
        ) from None
    except (urllib_error.URLError, TimeoutError, socket.timeout):
        raise NotificationError("Feishu webhook request failed") from None

    try:
        result = json.loads(body)
    except json.JSONDecodeError:
        raise NotificationError("Feishu webhook returned invalid JSON") from None

    if not isinstance(result, dict):
        raise NotificationError("Feishu webhook returned invalid JSON")
    if result.get("StatusCode") == 0 or result.get("code") == 0:
        return

    response_message = str(
        result.get("msg")
        or result.get("StatusMessage")
        or "unknown business error"
    )
    response_message = " ".join(response_message.split())[:200]
    raise NotificationError(f"Feishu rejected notification: {response_message}")


def redact_error(message, sensitive_values):
    redacted = message
    for value in sensitive_values:
        if value:
            redacted = redacted.replace(value, "[REDACTED]")
    return redacted


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Send a Feishu card for a published robomimic image."
    )
    parser.add_argument("--image", required=True)
    parser.add_argument("--sha-tag", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--commit-message", required=True)
    parser.add_argument("--commit-author", required=True)
    parser.add_argument("--trigger", required=True)
    parser.add_argument("--commit-url", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--package-url", required=True)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL", "")
    signing_secret = os.environ.get("FEISHU_WEBHOOK_SECRET", "")
    metadata = PublishMetadata(
        image=args.image,
        sha_tag=args.sha_tag,
        digest=args.digest,
        commit_sha=args.commit_sha,
        commit_message=args.commit_message,
        commit_author=args.commit_author,
        trigger=args.trigger,
        commit_url=args.commit_url,
        run_url=args.run_url,
        package_url=args.package_url,
    )
    try:
        payload = build_payload(metadata, signing_secret=signing_secret)
        send_payload(webhook_url, payload)
    except NotificationError as exc:
        safe_message = redact_error(
            str(exc),
            (webhook_url, signing_secret),
        )
        print(f"Feishu notification failed: {safe_message}", file=sys.stderr)
        return 1

    print("Feishu notification sent successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the notifier tests and verify they pass**

Run:

```bash
python3 -m unittest tests/test_notify_feishu.py
```

Expected: `Ran 10 tests` followed by `OK`, with no network requests.

- [ ] **Step 5: Verify CLI validation does not expose credentials**

Run:

```bash
FEISHU_WEBHOOK_URL= FEISHU_WEBHOOK_SECRET=private-secret \
  python3 .github/scripts/notify_feishu.py \
  --image ghcr.io/qingtianrobot/robomimic \
  --sha-tag sha-1234567 \
  --digest sha256:abc123 \
  --commit-sha 1234567890abcdef \
  --commit-message test \
  --commit-author tester \
  --trigger push \
  --commit-url https://github.com/QingTianRobot/robomimic/commit/1234567890abcdef \
  --run-url https://github.com/QingTianRobot/robomimic/actions/runs/42 \
  --package-url https://github.com/QingTianRobot/robomimic/pkgs/container/robomimic
```

Expected: exit 1 with `FEISHU_WEBHOOK_URL must be a valid HTTPS URL`; output does not contain `private-secret`.

- [ ] **Step 6: Commit the notifier and its tests**

```bash
git add .github/scripts/notify_feishu.py tests/test_notify_feishu.py
git commit -m "feat: add Feishu image notification card"
```

### Task 2: Add and validate the image publishing workflow

**Files:**
- Create: `.github/workflows/publish-image.yml`
- Create: `tests/test_publish_workflow.py`

- [ ] **Step 1: Write the failing workflow contract tests**

Create `tests/test_publish_workflow.py` with:

```python
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
```

- [ ] **Step 2: Run the workflow contract tests and verify they fail because the workflow is absent**

Run:

```bash
python3 -m unittest tests/test_publish_workflow.py
```

Expected: FAIL with `FileNotFoundError` for `.github/workflows/publish-image.yml`.

- [ ] **Step 3: Implement the publishing workflow**

Create `.github/workflows/publish-image.yml` with:

```yaml
name: Publish Docker image

on:
  push:
    branches:
      - master
  workflow_dispatch:

permissions:
  contents: read
  packages: write

concurrency:
  group: publish-image-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: false

env:
  IMAGE_NAME: ghcr.io/qingtianrobot/robomimic

jobs:
  publish:
    if: github.ref == 'refs/heads/master'
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Run notifier tests
        run: |
          python -m unittest tests/test_notify_feishu.py
          python -m unittest tests/test_publish_workflow.py

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Generate image metadata
        id: metadata
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.IMAGE_NAME }}
          tags: |
            type=raw,value=latest
            type=sha,format=short,prefix=sha-
          labels: |
            org.opencontainers.image.title=robomimic
            org.opencontainers.image.description=robomimic GPU/X11 development image
            org.opencontainers.image.source=https://github.com/${{ github.repository }}
            org.opencontainers.image.revision=${{ github.sha }}

      - name: Build and push image
        id: build
        uses: docker/build-push-action@v6
        with:
          context: .
          platforms: linux/amd64
          push: true
          tags: ${{ steps.metadata.outputs.tags }}
          labels: ${{ steps.metadata.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Send Feishu publication card
        if: ${{ success() }}
        env:
          FEISHU_WEBHOOK_URL: ${{ secrets.FEISHU_WEBHOOK_URL }}
          FEISHU_WEBHOOK_SECRET: ${{ secrets.FEISHU_WEBHOOK_SECRET }}
          IMAGE_DIGEST: ${{ steps.build.outputs.digest }}
          EVENT_NAME: ${{ github.event_name }}
        run: |
          python .github/scripts/notify_feishu.py \
            --image "$IMAGE_NAME" \
            --sha-tag "sha-${GITHUB_SHA::7}" \
            --digest "$IMAGE_DIGEST" \
            --commit-sha "$GITHUB_SHA" \
            --commit-message "$(git log -1 --pretty=%s)" \
            --commit-author "$(git log -1 --pretty=%an)" \
            --trigger "$EVENT_NAME" \
            --commit-url "https://github.com/$GITHUB_REPOSITORY/commit/$GITHUB_SHA" \
            --run-url "https://github.com/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID" \
            --package-url "https://github.com/$GITHUB_REPOSITORY/pkgs/container/robomimic"
```

- [ ] **Step 4: Run the workflow contract tests and notifier tests**

Run:

```bash
python3 -m unittest tests/test_notify_feishu.py
python3 -m unittest tests/test_publish_workflow.py
```

Expected: `Ran 10 tests ... OK` and `Ran 4 tests ... OK`.

- [ ] **Step 5: Run actionlint against the workflow**

Run:

```bash
docker run --rm \
  -v "$PWD:/repo" \
  -w /repo \
  rhysd/actionlint:1.7.7
```

Expected: exit 0 with no workflow syntax or expression errors.

- [ ] **Step 6: Commit the publishing workflow**

```bash
git add .github/workflows/publish-image.yml tests/test_publish_workflow.py
git commit -m "ci: publish image and notify Feishu"
```

### Task 3: Document GHCR publication and Feishu setup

**Files:**
- Modify: `README.md:74-80`

- [ ] **Step 1: Verify the publication documentation is absent**

Run:

```bash
rg -n "ghcr.io/qingtianrobot/robomimic|FEISHU_WEBHOOK_URL|Package Settings|purple" README.md
```

Expected: FAIL with exit 1 because image publication and Feishu setup are not documented.

- [ ] **Step 2: Add publication documentation after the local build command**

Insert this section immediately after the `docker compose build` code block:

````markdown
### Published image and Feishu notifications

Pushes to `master` publish a Linux AMD64 image to GitHub Container Registry. The workflow can also be started manually from `master` with **Actions → Publish Docker image → Run workflow**.

After the first successful publication, open the GHCR Package Settings and change the package visibility to **Public**. Public images can then be pulled without authentication:

```bash
docker pull ghcr.io/qingtianrobot/robomimic:latest
```

Each publication also creates an immutable traceable tag in the form `ghcr.io/qingtianrobot/robomimic:sha-<short-sha>` and records the image digest in the workflow output.

To enable the success notification, configure repository secrets under **Settings → Secrets and variables → Actions**:

- `FEISHU_WEBHOOK_URL` — required custom-bot webhook URL
- `FEISHU_WEBHOOK_SECRET` — optional signing secret when signature verification is enabled

Only a successfully pushed image sends a purple Feishu card. The card includes the image references, digest, commit subject and author, and links to the workflow run and GHCR package. Build failures do not send a card.
````

- [ ] **Step 3: Verify the documentation and Markdown formatting**

Run:

```bash
rg -n "ghcr.io/qingtianrobot/robomimic|FEISHU_WEBHOOK_URL|FEISHU_WEBHOOK_SECRET|Package Settings|purple" README.md
git diff --check
```

Expected: every setup pattern is found and `git diff --check` exits 0.

- [ ] **Step 4: Commit the documentation**

```bash
git add README.md
git commit -m "docs: explain image publishing notifications"
```

### Task 4: Verify configuration, push, and observe the first workflow

**Files:**
- Test: `.github/scripts/notify_feishu.py`
- Test: `.github/workflows/publish-image.yml`
- Test: `tests/test_notify_feishu.py`
- Test: `tests/test_publish_workflow.py`
- Test: `README.md`

- [ ] **Step 1: Run the complete focused verification suite**

Run:

```bash
python3 -m unittest tests/test_notify_feishu.py
python3 -m unittest tests/test_publish_workflow.py
docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.7
docker build --check .
git diff --check
```

Expected: 14 unit tests pass, actionlint exits 0, Docker build checks pass, and the Git whitespace check exits 0.

- [ ] **Step 2: Verify no credential or model files are tracked**

Run:

```bash
rg -n "open-apis/bot/v2/hook/[A-Za-z0-9_-]+|FEISHU_WEBHOOK_SECRET=.*[^}]" .github README.md tests || true
git ls-files models
git status --short --branch
```

Expected: no literal webhook token or secret assignment is found, `git ls-files models` is empty, and `MUJOCO_LOG.TXT` remains the only unrelated untracked file.

- [ ] **Step 3: Require the Feishu webhook repository secret before pushing**

Open this repository settings page in GitHub:

```text
https://github.com/QingTianRobot/robomimic/settings/secrets/actions
```

Add `FEISHU_WEBHOOK_URL`. Add `FEISHU_WEBHOOK_SECRET` only if the group custom bot has signature verification enabled. Confirm that the required secret exists before continuing. Do not paste either secret into tracked files, terminal history, test output, or chat messages.

Expected: the user explicitly confirms that `FEISHU_WEBHOOK_URL` has been configured. Stop before pushing if it is not configured.

- [ ] **Step 4: Push master to the fork**

Use the existing authenticated remote. In the current proxied environment, run:

```bash
GIT_SSH_COMMAND="ssh -p 443 -o HostName=ssh.github.com -o HostKeyAlias=github.com -o BatchMode=yes -o ConnectTimeout=20 -o ProxyCommand='nc -X 5 -x 127.0.0.1:17891 %h %p'" \
  git push origin master
```

Expected: Git pushes the notifier, workflow, tests, and documentation without force-pushing or adding `MUJOCO_LOG.TXT`.

- [ ] **Step 5: Observe the workflow through the public GitHub API**

Poll:

```text
https://api.github.com/repos/QingTianRobot/robomimic/actions/workflows/publish-image.yml/runs?per_page=1
```

Use the host HTTP proxy and `jq` to read `.workflow_runs[0].status`, `.workflow_runs[0].conclusion`, `.workflow_runs[0].html_url`, and `.workflow_runs[0].head_sha`. Continue until the run is completed while keeping the user updated at least once per minute.

Expected: the run's `head_sha` matches local `HEAD`, status becomes `completed`, and conclusion is `success`. A successful notification step means Feishu explicitly accepted the purple card.

- [ ] **Step 6: Make the first GHCR package public**

After the first successful workflow, open the package from:

```text
https://github.com/QingTianRobot/robomimic/pkgs/container/robomimic
```

Open **Package settings → Change visibility → Public** and confirm the change. This one-time action cannot be performed by the workflow.

Expected: the user confirms the package visibility is Public.

- [ ] **Step 7: Verify anonymous image metadata and remote Git state**

Run:

```bash
docker buildx imagetools inspect ghcr.io/qingtianrobot/robomimic:latest
```

Then compare the GitHub `master` SHA with `git rev-parse HEAD` and run:

```bash
git status --short --branch
```

Expected: anonymous image inspection succeeds, remote and local commit hashes match, `master` tracks `origin/master`, and only `MUJOCO_LOG.TXT` remains untracked.
