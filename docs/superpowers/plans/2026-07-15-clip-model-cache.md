# Persistent CLIP Model Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist `openai/clip-vit-large-patch14` on the host at `models/huggingface`, reuse it from Docker Compose, and prove it loads without network access after the first download.

**Architecture:** Bind-mount the repository-local Hugging Face cache into the Compose service and route both the CLIP model and tokenizer to one `${HF_HOME}/clip` directory. Keep the cache out of Git and the Docker build context, download it through the existing runtime image, and verify the cached model with Transformers offline mode.

**Tech Stack:** Docker Compose, Python 3.9, Transformers 4.41.2, Hugging Face Hub 0.23.4, PyTorch, pytest, unittest

---

### Task 1: Route the CLIP model and tokenizer through one cache

**Files:**
- Create: `tests/test_lang_utils_cache.py`
- Modify: `robomimic/utils/lang_utils.py:1-32`

- [ ] **Step 1: Write the failing cache-routing test**

Create `tests/test_lang_utils_cache.py` with:

```python
import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def test_clip_model_and_tokenizer_share_hf_cache(monkeypatch, tmp_path):
    calls = {"model": [], "tokenizer": []}

    class FakeLoadedModel:
        def eval(self):
            return self

    class FakeModelLoader:
        @classmethod
        def from_pretrained(cls, model_id, **kwargs):
            calls["model"].append((model_id, kwargs))
            return FakeLoadedModel()

    class FakeTokenizerLoader:
        @classmethod
        def from_pretrained(cls, model_id, **kwargs):
            calls["tokenizer"].append((model_id, kwargs))
            return object()

    fake_transformers = ModuleType("transformers")
    fake_transformers.AutoModel = object
    fake_transformers.pipeline = object
    fake_transformers.AutoTokenizer = FakeTokenizerLoader
    fake_transformers.CLIPTextModelWithProjection = FakeModelLoader
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
    monkeypatch.setenv("HF_HOME", str(tmp_path))

    module_path = Path(__file__).parents[1] / "robomimic" / "utils" / "lang_utils.py"
    spec = importlib.util.spec_from_file_location("lang_utils_cache_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    model_id = "openai/clip-vit-large-patch14"
    cache_dir = str(tmp_path / "clip")
    assert calls["model"] == [(model_id, {"cache_dir": cache_dir})]
    assert calls["tokenizer"] == [
        (
            model_id,
            {
                "cache_dir": cache_dir,
                "TOKENIZERS_PARALLELISM": True,
            },
        )
    ]
    assert module.CLIP_MODEL_ID == model_id
    assert module.CLIP_CACHE_DIR == cache_dir
```

- [ ] **Step 2: Run the test and verify it fails for the current tokenizer cache**

Run:

```bash
docker compose run --rm -T robomimic \
  python -m pytest -q tests/test_lang_utils_cache.py
```

Expected: FAIL because `AutoTokenizer.from_pretrained` does not receive `cache_dir`, and `CLIP_MODEL_ID` / `CLIP_CACHE_DIR` do not yet exist.

- [ ] **Step 3: Implement the shared CLIP cache**

Replace `robomimic/utils/lang_utils.py` with:

```python
import os

from transformers import AutoTokenizer, CLIPTextModelWithProjection


os.environ["TOKENIZERS_PARALLELISM"] = "true"

CLIP_MODEL_ID = "openai/clip-vit-large-patch14"
CLIP_CACHE_DIR = os.path.expanduser(
    os.path.join(os.environ.get("HF_HOME", "~/tmp"), "clip")
)

lang_emb_model = CLIPTextModelWithProjection.from_pretrained(
    CLIP_MODEL_ID,
    cache_dir=CLIP_CACHE_DIR,
).eval()
tz = AutoTokenizer.from_pretrained(
    CLIP_MODEL_ID,
    cache_dir=CLIP_CACHE_DIR,
    TOKENIZERS_PARALLELISM=True,
)

LANG_EMB_OBS_KEY = "lang_emb"


def get_lang_emb(lang):
    if lang is None:
        return None

    tokens = tz(
        text=lang,
        add_special_tokens=True,
        max_length=25,
        padding="max_length",
        return_attention_mask=True,
        return_tensors="pt",
    )
    lang_emb = lang_emb_model(**tokens)["text_embeds"].detach()[0]

    return lang_emb


def get_lang_emb_shape():
    return list(get_lang_emb("dummy").shape)
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
docker compose run --rm -T robomimic \
  python -m pytest -q tests/test_lang_utils_cache.py
```

Expected: `1 passed` with no model download because the test supplies fake Transformers loaders.

- [ ] **Step 5: Commit the shared cache behavior**

```bash
git add tests/test_lang_utils_cache.py robomimic/utils/lang_utils.py
git commit -m "fix: unify clip model cache"
```

### Task 2: Persist and exclude the host model cache

**Files:**
- Create: `tests/test_clip_model_cache_config.py`
- Modify: `compose.yaml:14-42`
- Modify: `.gitignore:1-8`
- Modify: `.dockerignore:1-25`

- [ ] **Step 1: Write the failing Compose and ignore-rule tests**

Create `tests/test_clip_model_cache_config.py` with:

```python
import json
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def resolved_service(hf_endpoint=None):
    env = os.environ.copy()
    env.pop("HF_ENDPOINT", None)
    if hf_endpoint is not None:
        env["HF_ENDPOINT"] = hf_endpoint
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)["services"]["robomimic"]


class ClipModelCacheConfigTest(unittest.TestCase):
    def test_compose_mounts_an_overridable_huggingface_cache(self):
        service = resolved_service()
        self.assertEqual(
            service["environment"]["HF_HOME"],
            "/opt/models/huggingface",
        )
        self.assertEqual(
            service["environment"]["HF_ENDPOINT"],
            "https://hf-mirror.com",
        )

        model_mount = next(
            volume
            for volume in service["volumes"]
            if volume["target"] == "/opt/models/huggingface"
        )
        self.assertEqual(model_mount["type"], "bind")
        self.assertEqual(
            Path(model_mount["source"]),
            (ROOT / "models" / "huggingface").resolve(),
        )
        self.assertFalse(model_mount.get("read_only", False))

        official = resolved_service("https://huggingface.co")
        self.assertEqual(
            official["environment"]["HF_ENDPOINT"],
            "https://huggingface.co",
        )

    def test_root_model_cache_is_ignored_but_python_models_are_not(self):
        self.assertIn("/models/", (ROOT / ".gitignore").read_text().splitlines())
        self.assertIn("/models/", (ROOT / ".dockerignore").read_text().splitlines())

        cache_check = subprocess.run(
            [
                "git",
                "check-ignore",
                "--no-index",
                "-q",
                "models/huggingface/clip/model.safetensors",
            ],
            cwd=ROOT,
        )
        package_check = subprocess.run(
            [
                "git",
                "check-ignore",
                "--no-index",
                "-q",
                "robomimic/models/base_nets.py",
            ],
            cwd=ROOT,
        )
        self.assertEqual(cache_check.returncode, 0)
        self.assertNotEqual(package_check.returncode, 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the configuration test and verify it fails**

Run:

```bash
python3 tests/test_clip_model_cache_config.py
```

Expected: FAIL because the Compose environment and volume are absent and neither ignore file contains `/models/`.

- [ ] **Step 3: Add the Compose environment and bind mount**

Add these entries after `ZSH_CACHE_DIR` in `compose.yaml`:

```yaml
      HF_HOME: /opt/models/huggingface
      HF_ENDPOINT: ${HF_ENDPOINT:-https://hf-mirror.com}
```

Add this writable mount immediately after the repository bind mount:

```yaml
      - type: bind
        source: ./models/huggingface
        target: /opt/models/huggingface
```

- [ ] **Step 4: Exclude the root model directory from Git and Docker builds**

Add this block near the top of `.gitignore`, after the local test dataset entries:

```gitignore
# repository-local model and Hugging Face cache
/models/
```

Add this block near the cache entries in `.dockerignore`:

```dockerignore
# repository-local model and Hugging Face cache
/models/
```

- [ ] **Step 5: Run the configuration test and verify it passes**

Run:

```bash
python3 tests/test_clip_model_cache_config.py
```

Expected: `Ran 2 tests` followed by `OK`.

- [ ] **Step 6: Verify the resolved Compose service directly**

Run:

```bash
docker compose config --format json
```

Expected: the `robomimic` service contains `HF_HOME=/opt/models/huggingface`, `HF_ENDPOINT=https://hf-mirror.com`, and a writable bind mount from `<repository>/models/huggingface` to `/opt/models/huggingface`.

- [ ] **Step 7: Commit the Compose persistence configuration**

```bash
git add tests/test_clip_model_cache_config.py compose.yaml .gitignore .dockerignore
git commit -m "feat: persist clip model cache"
```

### Task 3: Document the CLIP download and offline workflow

**Files:**
- Modify: `README.md:108-112`

- [ ] **Step 1: Verify the documentation is currently absent**

Run:

```bash
rg -n "models/huggingface|clip-download-ok|HF_HUB_OFFLINE" README.md
```

Expected: FAIL with exit code 1 because the CLIP cache workflow is not documented.

- [ ] **Step 2: Add the persistent CLIP cache documentation**

Insert this section after the warning that the development container runs as root:

````markdown
### Persist the CLIP language model

Language-conditioned policies use `openai/clip-vit-large-patch14` to convert task instructions into 768-dimensional embeddings. The Compose service stores the model weights, configuration, tokenizer, and Hugging Face metadata in the host directory `models/huggingface`, mounted at `/opt/models/huggingface` in the container.

Create the host directory and download the model through the runtime image:

```bash
mkdir -p models/huggingface
docker compose run --rm -T robomimic \
  python -c "import robomimic.utils.lang_utils; print('clip-download-ok')"
```

The default endpoint is the domestic mirror `https://hf-mirror.com`. Override it for one command if the mirror is unavailable:

```bash
HF_ENDPOINT=https://huggingface.co docker compose run --rm -T robomimic \
  python -c "import robomimic.utils.lang_utils; print('clip-download-ok')"
```

After the first successful download, verify that the cache works without network access:

```bash
docker compose run --rm -T \
  -e HF_HUB_OFFLINE=1 \
  -e TRANSFORMERS_OFFLINE=1 \
  robomimic python -c \
  "from robomimic.utils.lang_utils import get_lang_emb; embedding = get_lang_emb('pick up the cube'); print('clip-offline-ok', embedding.shape)"
```

Expected output ends with `clip-offline-ok torch.Size([768])`. The root `models/` directory is excluded from both Git and the Docker build context, so the downloaded assets remain host-only.
````

- [ ] **Step 3: Verify all documented commands and paths are present**

Run:

```bash
rg -n "models/huggingface|clip-download-ok|HF_ENDPOINT=https://huggingface.co|HF_HUB_OFFLINE|clip-offline-ok" README.md
git diff --check
```

Expected: all five documentation patterns are found and `git diff --check` exits 0.

- [ ] **Step 4: Commit the user documentation**

```bash
git add README.md
git commit -m "docs: explain persistent clip model cache"
```

### Task 4: Download and verify the real CLIP model

**Files:**
- Create locally but do not commit: `models/huggingface/**`

- [ ] **Step 1: Create the host cache as the current host user**

Run:

```bash
mkdir -p models/huggingface
```

Expected: `models/huggingface` exists on the host and remains ignored by Git.

- [ ] **Step 2: Download CLIP through the configured domestic endpoint**

Run:

```bash
docker compose run --rm -T robomimic \
  python -c "import robomimic.utils.lang_utils; print('clip-download-ok')"
```

Expected: Transformers downloads `openai/clip-vit-large-patch14` and the final line is `clip-download-ok`.

- [ ] **Step 3: Use the official endpoint only if the mirror reports a network or repository error**

Run only if Step 2 failed because of the mirror:

```bash
HF_ENDPOINT=https://huggingface.co docker compose run --rm -T robomimic \
  python -c "import robomimic.utils.lang_utils; print('clip-download-ok')"
```

Expected: the standard Hugging Face cache resumes any reusable partial files and the final line is `clip-download-ok`.

- [ ] **Step 4: Confirm that model assets exist and remain ignored**

Run:

```bash
test -n "$(find models/huggingface/clip -type f -print -quit)"
du -sh models/huggingface
git check-ignore -v models/huggingface/clip/model.safetensors
git status --short
```

Expected: the cache contains files, `git check-ignore` reports the root `/models/` rule, and `git status` does not list `models/`. The unrelated `MUJOCO_LOG.TXT` remains untracked.

- [ ] **Step 5: Load the downloaded model in offline mode**

Run:

```bash
docker compose run --rm -T \
  -e HF_HUB_OFFLINE=1 \
  -e TRANSFORMERS_OFFLINE=1 \
  robomimic python -c \
  "from robomimic.utils.lang_utils import get_lang_emb; embedding = get_lang_emb('pick up the cube'); assert tuple(embedding.shape) == (768,); print('clip-offline-ok', embedding.shape)"
```

Expected: `clip-offline-ok torch.Size([768])` without any network request.

### Task 5: Run final regressions and push master

**Files:**
- Test: `tests/test_lang_utils_cache.py`
- Test: `tests/test_clip_model_cache_config.py`
- Test: `compose.yaml`
- Test: `.gitignore`
- Test: `.dockerignore`
- Test: `README.md`

- [ ] **Step 1: Run the focused test suite again**

Run:

```bash
docker compose run --rm -T robomimic \
  python -m pytest -q tests/test_lang_utils_cache.py
python3 tests/test_clip_model_cache_config.py
git diff --check
```

Expected: pytest reports `1 passed`, unittest reports `Ran 2 tests` and `OK`, and the whitespace check exits 0.

- [ ] **Step 2: Rebuild after the model download to verify the cache is excluded from context**

Run:

```bash
env -u DISPLAY -u XAUTHORITY docker compose build
```

Expected: the build succeeds using the existing domestic package mirrors, the context transfer remains small, and no file below `models/huggingface` appears in a `COPY` layer.

- [ ] **Step 3: Verify the existing shell imports and Lift simulation**

Run:

```bash
docker compose run --rm -T robomimic \
  python -c "import mujoco, robomimic, robosuite, torch; print('runtime-imports-ok')"
docker compose run --rm -T -e MUJOCO_GL=osmesa robomimic \
  python -c "import numpy as np, robosuite as suite; env = suite.make(env_name='Lift', robots='Panda', has_renderer=False, has_offscreen_renderer=False, use_camera_obs=False); env.reset(); low, high = env.action_spec; [env.step(np.zeros_like(low)) for _ in range(20)]; print('simulation-ok', env.action_dim); env.close()"
```

Expected: `runtime-imports-ok` and `simulation-ok 7`.

- [ ] **Step 4: Verify NVIDIA GLFW rendering is unchanged**

Run:

```bash
docker compose run --rm -T robomimic /bin/bash -lc \
  'python -c "import glfw; from OpenGL.GL import GL_RENDERER, glGetString; assert glfw.init(); glfw.window_hint(glfw.VISIBLE, glfw.FALSE); window = glfw.create_window(64, 64, \"probe\", None, None); assert window; glfw.make_context_current(window); renderer = glGetString(GL_RENDERER); assert renderer is not None; renderer = renderer.decode(); print(renderer); assert \"NVIDIA\" in renderer; glfw.destroy_window(window); glfw.terminate()"'
```

Expected: the host NVIDIA renderer is printed without an `nvidia-drm` loader error.

- [ ] **Step 5: Review tracked and ignored state**

Run:

```bash
git status --short --branch
git log --oneline -8
git check-ignore -v models/huggingface/clip/model.safetensors
```

Expected: `master` contains the three implementation commits, model assets are ignored, and `MUJOCO_LOG.TXT` remains the only unrelated untracked file.

- [ ] **Step 6: Push master to the configured fork through the local SOCKS5 proxy**

Run:

```bash
GIT_SSH_COMMAND="ssh -o ProxyCommand='nc -X 5 -x 127.0.0.1:17891 %h %p' -o ConnectTimeout=15" \
  git push origin master
```

Expected: Git updates `git@github.com:QingTianRobot/robomimic.git` on `master` without force-pushing.

- [ ] **Step 7: Confirm the remote and local commit hashes match**

Run:

```bash
local_head=$(git rev-parse HEAD)
remote_head=$(GIT_SSH_COMMAND="ssh -o ProxyCommand='nc -X 5 -x 127.0.0.1:17891 %h %p' -o ConnectTimeout=15" git ls-remote origin refs/heads/master | awk '{print $1}')
test "$local_head" = "$remote_head"
```

Expected: the command exits 0 because the local and remote hashes are identical.
