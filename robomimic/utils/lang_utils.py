import os

from transformers import AutoTokenizer, CLIPTextModelWithProjection


os.environ["TOKENIZERS_PARALLELISM"] = "true"  # suppress potential deadlock warning
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
        text=lang,  # the sentence to be encoded
        add_special_tokens=True,  # Add [CLS] and [SEP]
        max_length=25,  # maximum length of a sentence
        padding="max_length",
        return_attention_mask=True,  # Generate the attention mask
        return_tensors="pt",  # ask the function to return PyTorch tensors
    )
    lang_emb = lang_emb_model(**tokens)["text_embeds"].detach()[0]

    return lang_emb


def get_lang_emb_shape():
    return list(get_lang_emb("dummy").shape)
