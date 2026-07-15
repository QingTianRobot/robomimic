# Persistent CLIP Model Cache Design

## Goal

Persist the `openai/clip-vit-large-patch14` model, tokenizer, configuration, and Hugging Face metadata in a repository-local host directory so the Docker Compose development environment can reuse them across container runs and image rebuilds.

## Current Behavior

`robomimic/utils/lang_utils.py` loads `openai/clip-vit-large-patch14` when the module is imported. `CLIPTextModelWithProjection` converts task language into a 768-dimensional embedding used under the `lang_emb` observation key.

The model currently receives an explicit cache directory derived from `HF_HOME`, while the tokenizer relies on the Transformers default cache. This can split one model repository across separate `clip` and `hub` directories. Compose does not currently persist either location explicitly.

The required Python packages, including `transformers` and `huggingface_hub`, are already installed by the Docker image. They do not need a second host-side installation.

## Host and Container Layout

The repository-local host directory will be:

```text
models/huggingface/
```

Docker Compose will bind-mount it at:

```text
/opt/models/huggingface/
```

The service will set:

```text
HF_HOME=/opt/models/huggingface
HF_ENDPOINT=https://hf-mirror.com
```

`HF_ENDPOINT` remains overridable from the host. A user can select the official service for a single command with `HF_ENDPOINT=https://huggingface.co` if the mirror is unavailable.

The root-level `/models/` directory will be ignored by Git and excluded from the Docker build context. These root-anchored rules do not affect the tracked Python package directory at `robomimic/models/`.

## Model Cache Behavior

`robomimic/utils/lang_utils.py` will define one model identifier and one cache directory. Both `CLIPTextModelWithProjection.from_pretrained` and `AutoTokenizer.from_pretrained` will use `${HF_HOME}/clip` explicitly.

Importing `robomimic.utils.lang_utils` will retain its current eager-loading behavior. The first import downloads the model assets, and later imports reuse the host-mounted cache. Interrupted Hugging Face downloads can resume through the standard cache mechanism.

The download will be initiated through the existing Compose service rather than during `docker build`. This keeps the image independent of multi-gigabyte model weights and allows rebuilding the image without downloading the model again.

## Download Workflow

Create the host directory and trigger the same code path used by language-conditioned policies:

```bash
mkdir -p models/huggingface
docker compose run --rm -T robomimic \
  python -c "import robomimic.utils.lang_utils; print('clip-download-ok')"
```

The download includes the CLIP model weights, model configuration, tokenizer files, and Hugging Face cache metadata. Python runtime dependencies remain inside the image.

If the domestic endpoint is unavailable, use:

```bash
HF_ENDPOINT=https://huggingface.co docker compose run --rm -T robomimic \
  python -c "import robomimic.utils.lang_utils; print('clip-download-ok')"
```

## Failure Handling

- A partially completed Hugging Face download remains in the mounted cache and can be resumed by rerunning the command.
- `HF_ENDPOINT` can be overridden without editing Compose.
- Model assets remain outside the Docker image and outside Git history.
- The download command exits unsuccessfully if the model or tokenizer cannot be loaded, so a success message is only printed after both are available.

## Verification

Verification will cover five layers:

1. A focused unit test will replace the Transformers loaders with lightweight fakes, set a temporary `HF_HOME`, import `lang_utils.py`, and require the model and tokenizer to receive the same `${HF_HOME}/clip` cache directory. The test will fail against the current tokenizer behavior before the implementation is changed.
2. `docker compose config` will verify the resolved `HF_HOME`, overridable `HF_ENDPOINT`, and host-to-container bind mount.
3. `git check-ignore` will verify that a representative file below `models/huggingface/` is ignored while `robomimic/models/` remains tracked.
4. A Docker build-context check will verify that `/models/` is present in `.dockerignore`, preventing cached weights and tokenizer assets from being copied by `COPY . .`.
5. After the real download, an offline Compose run will set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, call `get_lang_emb("pick up the cube")`, and require `torch.Size([768])`.

## Files

- Modify `compose.yaml` to add the Hugging Face environment and bind mount.
- Modify `.gitignore` to ignore the root-level model cache.
- Modify `.dockerignore` to exclude the root-level model cache from the image build context.
- Modify `robomimic/utils/lang_utils.py` to share one model ID and cache directory.
- Add a focused test for CLIP cache routing.
- Modify `README.md` to document downloading, storage, mirror override, and offline verification.

## Out of Scope

- Downloading robomimic Model Zoo policy checkpoints.
- Installing or downloading R3M or MVP representations.
- Storing model weights inside the Docker image.
- Changing the eager-loading API or the language embedding dimension.
- Sharing a global Hugging Face cache across unrelated host projects.
