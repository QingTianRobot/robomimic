import importlib.util
import os
import sys
import types
from pathlib import Path


def test_clip_loaders_share_hf_cache(monkeypatch, tmp_path):
    calls = {"model": [], "tokenizer": []}

    class FakeVector:
        shape = (768,)

    class FakeTextEmbeds:
        def detach(self):
            return self

        def __getitem__(self, index):
            assert index == 0
            return FakeVector()

    class FakeModel:
        eval_called = False

        @classmethod
        def from_pretrained(cls, model_id, **kwargs):
            calls["model"].append((model_id, kwargs))
            return cls()

        def eval(self):
            self.eval_called = True
            return self

        def __call__(self, **tokens):
            return {"text_embeds": FakeTextEmbeds()}

    class FakeTokenizer:
        @classmethod
        def from_pretrained(cls, model_id, **kwargs):
            calls["tokenizer"].append((model_id, kwargs))
            return cls()

        def __call__(self, **kwargs):
            return {"input_ids": object()}

    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoTokenizer = FakeTokenizer
    fake_transformers.CLIPTextModelWithProjection = FakeModel
    fake_transformers.AutoModel = object
    fake_transformers.pipeline = object

    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
    monkeypatch.setenv("HF_HOME", str(tmp_path))

    module_path = Path(__file__).parents[1] / "robomimic" / "utils" / "lang_utils.py"
    spec = importlib.util.spec_from_file_location("lang_utils_under_test", module_path)
    assert spec is not None and spec.loader is not None
    lang_utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lang_utils)

    expected_model_id = "openai/clip-vit-large-patch14"
    expected_cache_dir = os.path.join(str(tmp_path), "clip")
    assert calls["model"] == [
        (expected_model_id, {"cache_dir": expected_cache_dir})
    ]
    assert calls["tokenizer"] == [
        (
            expected_model_id,
            {
                "cache_dir": expected_cache_dir,
                "TOKENIZERS_PARALLELISM": True,
            },
        )
    ]
    assert lang_utils.CLIP_MODEL_ID == expected_model_id
    assert lang_utils.CLIP_CACHE_DIR == expected_cache_dir
    assert os.environ["TOKENIZERS_PARALLELISM"] == "true"
    assert lang_utils.lang_emb_model.eval_called
    assert lang_utils.get_lang_emb(None) is None
    assert lang_utils.get_lang_emb_shape() == [768]
