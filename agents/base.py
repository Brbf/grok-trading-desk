"""Optional language-model calls.

The paper desk does not import a client and does not need a key. A call happens
only when ask_model() is used and XAI_API_KEY is set to a real value.
"""

from __future__ import annotations

import os

# grok-beta is retired. Override with XAI_MODEL to match the key's current model.
DEFAULT_MODEL = "grok-4"
_PLACEHOLDERS = {
    "",
    "your_xai_api_key_here",
    "your_key",
    "changeme",
}


def model_name() -> str:
    return (os.getenv("XAI_MODEL") or DEFAULT_MODEL).strip()


def llm_available() -> bool:
    key = (os.getenv("XAI_API_KEY") or "").strip()
    if key.lower() in _PLACEHOLDERS or key.lower().startswith("your_"):
        return False
    return True


def call_agent(system_prompt: str, user_prompt: str) -> str:
    if not llm_available():
        raise RuntimeError(
            "XAI_API_KEY is not set. The paper desk does not call a language model. "
            "Set XAI_API_KEY and, if needed, XAI_MODEL to ask for an advisory comment."
        )
    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ["XAI_API_KEY"],
        base_url=os.getenv("XAI_BASE_URL", "https://api.x.ai/v1"),
    )
    response = client.chat.completions.create(
        model=model_name(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
    )
    content = response.choices[0].message.content
    return content or ""
