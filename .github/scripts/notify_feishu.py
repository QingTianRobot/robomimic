#!/usr/bin/env python3
import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from dataclasses import dataclass
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request


REQUEST_TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 64 * 1024
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
    tokens = []
    for character in compact:
        if character == "<":
            tokens.append("＜")
        elif character == ">":
            tokens.append("＞")
        elif character in "\\`*_~[]()#":
            tokens.append(f"\\{character}")
        else:
            tokens.append(character)

    escaped = "".join(tokens)
    if len(escaped) <= limit:
        return escaped
    if limit <= 0:
        return ""

    ellipsis = "…"
    budget = limit - len(ellipsis)
    truncated = []
    used = 0
    for token in tokens:
        if used + len(token) > budget:
            break
        truncated.append(token)
        used += len(token)
    return "".join(truncated) + ellipsis


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
    try:
        parsed = urllib_parse.urlparse(webhook_url)
    except (TypeError, ValueError):
        raise NotificationError(
            "FEISHU_WEBHOOK_URL must be a valid HTTPS URL"
        ) from None
    if parsed.scheme != "https" or not parsed.netloc:
        raise NotificationError("FEISHU_WEBHOOK_URL must be a valid HTTPS URL")


def _build_request(webhook_url, payload):
    try:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return urllib_request.Request(
            webhook_url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
    except (TypeError, ValueError, UnicodeError):
        raise NotificationError("Feishu webhook request failed") from None


def _read_response(response):
    try:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    except Exception:
        raise NotificationError("Feishu webhook request failed") from None

    if not isinstance(body, (bytes, bytearray)):
        raise NotificationError("Feishu webhook returned an invalid response body")
    if len(body) > MAX_RESPONSE_BYTES:
        raise NotificationError("Feishu webhook response exceeded size limit")
    try:
        return bytes(body).decode("utf-8")
    except UnicodeDecodeError:
        raise NotificationError("Feishu webhook returned invalid UTF-8") from None


def send_payload(
    webhook_url,
    payload,
    timeout=REQUEST_TIMEOUT_SECONDS,
    opener=urllib_request.urlopen,
):
    _validate_webhook_url(webhook_url)
    request = _build_request(webhook_url, payload)
    try:
        with opener(request, timeout=timeout) as response:
            body = _read_response(response)
    except urllib_error.HTTPError as exc:
        raise NotificationError(
            f"Feishu webhook returned HTTP {exc.code}"
        ) from None
    except NotificationError:
        raise
    except Exception:
        raise NotificationError("Feishu webhook request failed") from None

    try:
        result = json.loads(body)
    except json.JSONDecodeError:
        raise NotificationError("Feishu webhook returned invalid JSON") from None

    if not isinstance(result, dict):
        raise NotificationError("Feishu webhook returned invalid JSON")

    if "StatusCode" in result:
        status = result["StatusCode"]
        response_message = result.get("StatusMessage")
    elif "code" in result:
        status = result["code"]
        response_message = result.get("msg")
    else:
        status = None
        response_message = None

    if type(status) is int and status == 0:
        return

    response_message = str(
        response_message or "unknown business error"
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
