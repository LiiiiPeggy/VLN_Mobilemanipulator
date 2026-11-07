# ################################
# VLN adapt: resolve bert-base-uncased to a local directory for offline GLIP
# ################################
import os


def resolve_bert_pretrained(name_or_path=None):
    """Return a local BERT dir when hub is unreachable; else pass through."""
    env = os.environ.get(
        "BERT_BASE_UNCASED_PATH",
        "/shared/cache/huggingface/bert-base-uncased",
    )
    if name_or_path in (None, "", "bert-base-uncased"):
        if os.path.isdir(env):
            return env
        return "bert-base-uncased"
    # Already a filesystem path
    if os.path.isdir(str(name_or_path)):
        return name_or_path
    if str(name_or_path) == "bert-base-uncased" and os.path.isdir(env):
        return env
    return name_or_path
# ################################
