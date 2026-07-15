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
