"""LLM provider plumbing for disruption_response.py.

One function per provider - each takes (prompt, schema) and returns
(decision_dict, label). Adding a provider never touches the harness
(detect_shortfall / validate / dispatch) - only this file and the
LLM_PROVIDER env var selecting between them.

All providers are asked for the same JSON Schema shape (a closed
`decision` enum + required `rationale` string) so the harness downstream
never has to know which one answered.
"""

import json
import os
import re


def extract_json(text):
    """Best-effort JSON object extraction from a model response that may
    wrap the object in markdown or surround it with prose. Raises ValueError
    if nothing parseable is found - the caller escalates rather than
    trusting a guess at what the model meant.

    Needed for any provider that doesn't actually enforce a JSON schema
    server-side - verified 2026-09-16 that Ollama Cloud is one of these:
    glm-5.3:cloud, gpt-oss:20b-cloud, and qwen3.5:cloud all ignored the
    native `format` constraint and returned markdown prose instead.
    """

    text = text.strip()

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"no parseable JSON object found in model response: {text[:200]!r}")


def call_gemini(prompt, schema):

    from google import genai
    from google.genai import types

    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        raise RuntimeError(
            "no Gemini credentials found - set GEMINI_API_KEY (or GOOGLE_API_KEY) in .env"
        )

    # gemini-3.8-flash/-3.7-flash both returned a persistent 503 "high
    # demand" live (2026-09-16) - likely a recent rollout still ramping
    # capacity, not a config error. gemini-3.6-flash is what Google's own
    # API error message recommends in place of the deprecated
    # gemini-2.5-flash, and it works.
    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            # response_json_schema, not response_schema (the Schema/OpenAPI-
            # subset field) - only this one supports additionalProperties and
            # a real string enum, both required by our schema.
            response_json_schema=schema,
            # LOW: this call is already gated behind detect_shortfall() and
            # fires rarely, so cost isn't the pressure - LOW is a starting
            # point for a bounded 2-3-candidate weighing, not a ceiling.
            # Raise to MEDIUM/HIGH if rationale text starts looking shallow.
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
        ),
    )
    # Gemini's response_json_schema is a genuine server-side guarantee, but
    # route through the same extractor as Ollama anyway - one failure
    # type (ValueError) for decide() to catch, regardless of provider.
    try:
        return extract_json(response.text), "Gemini"
    except ValueError as e:
        raise ValueError(f"Gemini: {e}") from e


def call_ollama_cloud(prompt, schema):

    import ollama

    if not os.environ.get("OLLAMA_API_KEY"):
        raise RuntimeError("no Ollama Cloud credentials found - set OLLAMA_API_KEY in .env")

    # `format=schema` (Ollama's native JSON-schema constraint) is NOT
    # honored by Ollama Cloud - verified 2026-09-16 against glm-5.3:cloud,
    # gpt-oss:20b-cloud, and qwen3.5:cloud, all of which returned markdown
    # prose regardless. Ask for the shape in the prompt instead and parse
    # leniently; decide() re-validates the result before trusting it.
    schema_prompt = (
        f"{prompt}\n\n"
        f"Respond with ONLY a single JSON object - no markdown, no code "
        f"fences, no other text before or after it - matching this exact "
        f"shape:\n{json.dumps(schema)}\n\n"
        f'Example shape (values illustrative only): '
        f'{{"decision": "<one of the exact names in the enum above>", "rationale": "..."}}'
    )

    # host is a fixed cloud endpoint, not a secret - OLLAMA_API_KEY is read
    # automatically by ollama.Client and sent as `Authorization: Bearer`
    # (verified against the installed ollama==0.6.2 source, _client.py).
    client = ollama.Client(host="https://ollama.com")
    response = client.chat(
        model="glm-5.3:cloud",
        messages=[{"role": "user", "content": schema_prompt}],
        think="low",
    )
    try:
        return extract_json(response.message.content), "GLM 5.3 (Ollama Cloud)"
    except ValueError as e:
        raise ValueError(f"GLM 5.3 (Ollama Cloud): {e}") from e


PROVIDERS = {
    "gemini": call_gemini,
    "ollama": call_ollama_cloud,
}


def call(provider, prompt, schema):

    try:
        fn = PROVIDERS[provider]
    except KeyError:
        raise RuntimeError(
            f"unknown LLM_PROVIDER {provider!r} - choose one of {list(PROVIDERS)}"
        )
    return fn(prompt, schema)
