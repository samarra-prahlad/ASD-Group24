"""Calls Ollama's OpenAI-compatible chat endpoint. Returns (text, error) - exactly one is None."""
import requests

import config


def chat(model, system_prompt, user_prompt):
    try:
        response = requests.post(
            f"{config.OLLAMA_BASE_URL}/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
            },
            timeout=config.LLM_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        return None, f"LLM unreachable: {exc}"

    if response.status_code != 200:
        return None, f"LLM returned HTTP {response.status_code}"

    try:
        text = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError):
        return None, "Unexpected LLM response format"

    return text.strip(), None
