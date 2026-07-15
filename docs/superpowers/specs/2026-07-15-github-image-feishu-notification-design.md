# GitHub Image Publishing and Feishu Notification Design

## Goal

Build and publish the repository Docker image after every push to `master`, retain a manual publishing trigger, and send one purple Feishu interactive Markdown card after the image has been pushed successfully.

The published image will be available from GitHub Container Registry at:

```text
ghcr.io/qingtianrobot/robomimic
```

Build failures will remain visible in GitHub Actions and will not send a Feishu card.

## Current State

The repository contains one root `Dockerfile` and a Compose development service, but no `.github` workflows or registry publishing automation. The fork lives at `QingTianRobot/robomimic`, and `master` is the branch used for direct changes.

The Docker image can be built on a standard Linux AMD64 GitHub-hosted runner. Runtime NVIDIA devices and X11 access are not required for an image build.

## Selected Approach

Use official Docker GitHub Actions for metadata, authentication, Buildx, caching, building, and pushing. Keep Feishu card construction, optional webhook signing, request handling, and response validation in a small Python standard-library script stored in the repository.

This separates image publication from messaging concerns, avoids granting webhook secrets to a third-party Feishu Action, and makes card behavior testable without sending a real message.

## Workflow Trigger and Permissions

Create `.github/workflows/publish-image.yml` with these triggers:

- `push` to `master`
- `workflow_dispatch`

The publishing job will also require `github.ref == 'refs/heads/master'`, so a manually dispatched run cannot select a feature branch and overwrite the release tags.

The workflow will use one job on `ubuntu-latest` with minimum repository permissions:

```yaml
permissions:
  contents: read
  packages: write
```

The built-in `GITHUB_TOKEN` will authenticate to GHCR. No Docker Hub username, password, or personal access token is required.

The workflow will use a concurrency group derived from the workflow and Git ref. Active image publications will not be cancelled halfway through a registry push; later runs will wait for the current run.

## Image Build and Metadata

The workflow will:

1. Check out the triggering commit.
2. Set up Python and run the Feishu notifier unit tests before building.
3. Set up Docker Buildx.
4. Authenticate to `ghcr.io` using `${{ github.actor }}` and `GITHUB_TOKEN`.
5. Generate Docker tags and OCI labels.
6. Build `linux/amd64` from the root `Dockerfile`.
7. Push the image and expose the image digest as a step output.
8. Send the Feishu card only after every earlier step succeeds.

The image will receive these tags:

```text
ghcr.io/qingtianrobot/robomimic:latest
ghcr.io/qingtianrobot/robomimic:sha-<short-commit-sha>
```

The digest reported by Buildx provides an immutable identifier such as `sha256:...`. OCI labels will record the source repository URL, Git revision, and creation time. GitHub Actions cache storage will be used for Buildx layer caching.

The root `/models/` directory is already excluded by `.dockerignore`, so the host-only CLIP cache cannot enter the CI build context.

## Public GHCR Package

GHCR generally creates a newly published package as private. After the first successful workflow run, a repository administrator must open the package settings and change the package visibility to **Public**. This is a one-time GitHub configuration step; subsequent versions retain the package visibility.

Once public, users can pull without registry authentication:

```bash
docker pull ghcr.io/qingtianrobot/robomimic:latest
```

## Feishu Webhook Integration

The target is a Feishu group custom bot using an incoming webhook. Configure these GitHub Actions repository secrets:

- `FEISHU_WEBHOOK_URL` — required
- `FEISHU_WEBHOOK_SECRET` — optional; required only when the custom bot has signature verification enabled

The workflow passes both values to the notifier as environment variables. They will not be placed in command-line arguments, card content, or diagnostic output.

If `FEISHU_WEBHOOK_SECRET` is present, the notifier will generate the Feishu timestamp and HMAC-SHA256 signature required by the custom bot. If it is absent, the notifier will send an unsigned custom-bot request.

`FEISHU_WEBHOOK_URL` must be non-empty and use HTTPS. A missing or invalid URL causes the notification step to fail without printing the URL.

## Feishu Card

The notifier sends an `interactive` card with a Markdown body and a purple header. Its title will be:

```text
🚀 robomimic 镜像发布成功
```

The card body will include:

- `ghcr.io/qingtianrobot/robomimic:latest`
- the `sha-<short-sha>` image reference
- the immutable image digest
- a short commit SHA linked to the GitHub commit
- the commit subject
- the Git author
- the trigger type (`push` or `workflow_dispatch`)

The card will include buttons linking to the current GitHub Actions run and the repository's GHCR package page.

Commit subjects and author names will be length-limited and escaped before being embedded in Feishu Markdown. JSON encoding will be handled by the Python standard library rather than shell string interpolation.

## Notifier Structure

Create `.github/scripts/notify_feishu.py` with focused units for:

- escaping untrusted Markdown fields;
- constructing the purple interactive card;
- generating an optional deterministic signature from a supplied timestamp;
- validating required configuration and HTTPS webhook URLs;
- sending a JSON request with a bounded timeout;
- accepting both documented Feishu custom-bot success response shapes;
- returning a non-zero exit code for HTTP, timeout, malformed JSON, or Feishu business errors.

The script will accept only non-secret publication metadata as command-line arguments. Webhook credentials come exclusively from environment variables.

## Failure Behavior

The Feishu step uses normal success gating and appears after the registry push. Therefore:

- checkout, tests, login, build, or push failure: the workflow fails and no Feishu request is made;
- successful registry push and successful webhook: the workflow succeeds and one purple card is sent;
- successful registry push but missing required webhook URL configuration or Feishu request failure: the image remains published, but the workflow ends as failed with a sanitized notification error;
- no red failure card is sent in any case.

No retry will blindly duplicate cards. The HTTP request will have a bounded timeout, and a response is considered successful only when Feishu explicitly returns a success status.

## Testing

Create `tests/test_notify_feishu.py` and `tests/test_publish_workflow.py` using the Python standard library. Tests will not access the network or require real secrets.

Coverage will include:

1. A purple header and all expected Markdown fields and links.
2. `latest`, SHA-tag, digest, commit, author, trigger, workflow, and package metadata.
3. Markdown escaping and length limits for commit subjects and authors.
4. No `timestamp` or `sign` fields when the signing secret is absent.
5. Deterministic timestamp and signature fields when a signing secret is supplied.
6. Both Feishu success response formats.
7. HTTP errors, timeouts, malformed JSON, and Feishu business errors.
8. Sanitized errors that never include webhook URLs or signing secrets.
9. The workflow trigger, permissions, concurrency, tags, official Docker actions, success-only notification ordering, and secret references.

Verification commands will include:

```bash
python -m unittest tests/test_notify_feishu.py
docker build --check .
```

The workflow YAML will also receive a static Action syntax check. The notifier unit tests will run inside the publishing workflow before registry authentication and image building.

## Documentation

Update `README.md` with:

- the GHCR image address and pull command;
- automatic and manual publishing triggers;
- required and optional GitHub Secrets;
- the one-time GHCR Public visibility step;
- the fact that only successful publications send a purple Feishu card.

## Files

- Create `.github/workflows/publish-image.yml`.
- Create `.github/scripts/notify_feishu.py`.
- Create `tests/test_notify_feishu.py`.
- Create `tests/test_publish_workflow.py`.
- Modify `README.md`.
- Add the implementation plan under `docs/superpowers/plans/` after this design is approved.

## Out of Scope

- Docker Hub publication.
- Multi-architecture images.
- Pull-request or feature-branch image publication.
- Failure cards.
- Feishu application-bot credentials and chat APIs.
- Automatically changing GHCR package visibility.
- Embedding model weights in the published image.
