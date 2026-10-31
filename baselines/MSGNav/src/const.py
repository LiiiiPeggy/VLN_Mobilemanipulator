# about habitat scene
INVALID_SCENE_ID = []

import os

# Prefer environment / Compose env_file (.env is gitignored). Never hardcode secrets.
API_MODE = os.getenv("API_MODE", "gpt")  # "gpt" or "qwen"

Qwen_END_POINT = os.getenv(
    "Qwen_END_POINT", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
Qwen_OPENAI_KEY = os.getenv("Qwen_OPENAI_KEY", os.getenv("QWEN_OPENAI_KEY", ""))
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-vl-max")

GPT_END_POINT = os.getenv(
    "GPT_END_POINT", os.getenv("OPENAI_BASE_URL", "https://model8.run/v1")
)
GPT_OPENAI_KEY = os.getenv("GPT_OPENAI_KEY", os.getenv("OPENAI_API_KEY", ""))
GPT_MODEL = os.getenv("GPT_MODEL", "gpt-5.6-sol")
