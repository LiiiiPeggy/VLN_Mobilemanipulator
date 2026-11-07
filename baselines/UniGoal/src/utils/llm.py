import base64
import os
import time
from openai import OpenAI
from io import BytesIO


# ################################
# VLN adapt: longer timeout + retries for model8 / vision payloads
# ################################
def _openai_client(api_key, base_url):
    timeout = float(os.getenv("OPENAI_TIMEOUT", "180"))
    # max_retries=0: avoid OpenAI SDK nested 60s waits; outer loop owns retry policy
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)


def _retry_sleep_seconds(exc, attempt, backoff):
    """Honor Cloudflare/OpenAI retry_after when present; else exponential backoff."""
    msg = str(exc)
    # model8/Cloudflare 502 body often suggests retry_after: 60
    for key in ("retry_after", "Retry-After"):
        if key in msg:
            try:
                # find number after key
                import re
                m = re.search(r"retry_after['\"]?\s*[:=]\s*(\d+)", msg, re.I)
                if m:
                    return max(backoff, min(float(m.group(1)), 90.0))
            except Exception:
                pass
    # 5xx / timeout → longer wait (cap 90s)
    if any(x in msg for x in ("502", "503", "504", "timeout", "Timeout", "Bad gateway")):
        return min(backoff * (2 ** attempt) + 5.0, 90.0)
    return min(backoff * (attempt + 1), 60.0)


def _call_with_retry(fn, retries=None, backoff=None):
    retries = int(os.getenv("OPENAI_CALL_RETRIES", str(retries or 8)))
    backoff = float(os.getenv("OPENAI_RETRY_BACKOFF", str(backoff or 8.0)))
    last = None
    for i in range(retries):
        try:
            return fn()
        except Exception as e:
            last = e
            wait = _retry_sleep_seconds(e, i, backoff)
            print(
                f"[llm/vlm] attempt {i+1}/{retries} failed: {type(e).__name__}: {e}; "
                f"sleep {wait:.1f}s",
                flush=True,
            )
            if i + 1 >= retries:
                break
            time.sleep(wait)
    raise last
# ################################


class LLM:
    def __init__(self, base_url, api_key, llm_model):
        self.base_url = base_url
        self.api_key = api_key
        self.llm_model = llm_model

    def __call__(self, prompt):
        client = _openai_client(self.api_key, self.base_url)

        def _do():
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        'role': 'user',
                        'content': prompt,
                    }
                ],
                model=self.llm_model,
            )
            return chat_completion.choices[0].message.content

        return _call_with_retry(_do)


class VLM:
    def __init__(self, base_url, api_key, vlm_model):
        self.base_url = base_url
        self.api_key = api_key
        self.vlm_model = vlm_model

    def __call__(self, prompt, image):
        # ################################
        # VLN adapt: downscale + JPEG; OpenAI-compat image_url must be {"url": ...}
        # ################################
        img = image
        try:
            max_side = int(os.getenv("VLM_MAX_SIDE", "384"))
            w, h = img.size
            scale = min(1.0, float(max_side) / float(max(w, h)))
            if scale < 1.0:
                img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        except Exception:
            img = image
        buffered = BytesIO()
        img.save(buffered, format='JPEG', quality=75)
        image_bytes = base64.b64encode(buffered.getvalue())
        image_str = str(image_bytes, 'utf-8')
        # ################################

        client = _openai_client(self.api_key, self.base_url)

        def _do():
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        'role': 'user',
                        'content': [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "data:image/jpeg;base64," + image_str
                                },
                            },
                        ]
                    }
                ],
                model=self.vlm_model,
            )
            return chat_completion.choices[0].message.content

        return _call_with_retry(_do)