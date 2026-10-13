# Copyright 2026 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Translate one block of a built doc page with an LLM served by HF Inference Providers.

Every answer is validated before it is used and cached by the exact request that produced it
(system prompt + block), so unchanged blocks are never sent to the model again, and editing the
glossary only invalidates the blocks whose prompt contains the edited terms.
"""

import hashlib
import json
import re
import time
from pathlib import Path

import yaml

from .translate_html import check_markup

MODEL = "Qwen/Qwen3.8-27B"
PROVIDER = "cerebras"
# Bump to invalidate every cached translation (e.g. after a prompt change).
PROMPT_VERSION = 1
LANGUAGE_NAMES = {"ja": "Japanese"}
GLOSSARY_DIR = Path(__file__).parent / "translation_glossaries"

INSTRUCTIONS = """You translate Hugging Face documentation from English into natural, professional {language}, as written by an experienced {language} ML engineer.{style}

Keep these in English: product, library and model names (Transformers, Accelerate, PyTorch, FSDP, DeepSpeed, Llama, ...), and class, function, parameter and file names.
Headings, labels and short phrases are prose: translate them too ("Next steps", "Get started", "Hydration check"). Only text that consists solely of names stays unchanged.
Do not add Markdown, quotes or explanations."""

MARKUP_PROMPT = """
The input is one block of a web page in a light markup:
- <tN>…</tN> marks a link or formatting. Translate the text inside it and keep the tag.
- <cN>…</cN> is code. Copy it exactly, including its content.
- <tN/> is a line break or an image; keep it.
- Text is HTML-escaped (&lt; &gt; &amp;); keep it escaped.

Use natural word order and move tags (with their content) wherever the sentence needs them. Every tag must appear exactly once, with the same nesting as in the input. Never write a code name outside its tag.

Return only the translated block."""

SEGMENTS_PROMPT = """
The input is one block of a web page, split into segments in reading order:
- {"id": N, "text": ...} segments are English prose to translate.
- {"fixed": ...} segments are code, identifiers or markup. They stay exactly where they are; you cannot move, change, or repeat them.

Because the fixed segments cannot move, write each translated segment so the whole block reads naturally with the fixed segments in their original order. You may shift meaning between neighbouring translated segments, and a segment may become very short, but every id must be present. A segment that is only a name stays unchanged.

Return only a JSON object mapping every id (as a string) to its translation."""

STYLE = {"ja": " Use the です・ます style."}


def load_glossary(language):
    path = GLOSSARY_DIR / f"{language}.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def glossary_hint(text, glossary):
    terms = {
        term: target
        for term, target in (glossary.get("terms") or {}).items()
        if re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", text, re.I)
    }
    if not terms:
        return ""
    return "\n\nUse this terminology where the meaning fits: " + json.dumps(terms, ensure_ascii=False)


class TranslationFailed(Exception):
    pass


class Translator:
    """
    Translates blocks into `language`. `cache` maps request keys to validated answers and is
    updated in place; `complete` performs the chat completion (injectable for tests).
    """

    def __init__(self, language, cache, complete=None, token=None):
        if language not in LANGUAGE_NAMES:
            raise ValueError(f"No translation settings for language {language!r}; add it to LANGUAGE_NAMES")
        self.language = language
        self.cache = cache
        self.glossary = load_glossary(language)
        self._complete = complete or _inference_completion(token)
        self.model_calls = 0

    def _system(self, kind, text):
        name = LANGUAGE_NAMES[self.language]
        prompt = INSTRUCTIONS.format(language=name, style=STYLE.get(self.language, ""))
        prompt += MARKUP_PROMPT if kind == "markup" else SEGMENTS_PROMPT
        return prompt + glossary_hint(text, self.glossary)

    def _key(self, system, user):
        payload = json.dumps([MODEL, PROVIDER, PROMPT_VERSION, system, user], ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _ask(self, system, user, check):
        """Cached, validated answer; one retry that tells the model what was wrong."""
        key = self._key(system, user)
        if key in self.cache:
            return self.cache[key]
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        error = None
        for _ in range(2):
            self.model_calls += 1
            answer = self._complete(messages).strip()
            try:
                result = check(answer)
            except ValueError as exc:
                error = str(exc)
                messages = messages[:2] + [
                    {"role": "assistant", "content": answer},
                    {"role": "user", "content": f"That answer is invalid: {error}. Answer again."},
                ]
                continue
            self.cache[key] = result
            return result
        raise TranslationFailed(error)

    def translate_markup(self, markup):
        """Translate a static block given as markup (see `translate_html.to_markup`)."""

        def check(answer):
            check_markup(markup, answer)
            return answer

        return self._ask(self._system("markup", markup), markup, check)

    def translate_segments(self, segments):
        """Translate the numbered segments of a block; returns `{id: text}`."""
        ids = {str(s["id"]) for s in segments if "id" in s}
        fixed = [s["fixed"] for s in segments if "fixed" in s and len(s["fixed"]) > 3]

        def check(answer):
            answer = re.sub(r"^```(?:json)?\s*|\s*```$", "", answer)
            try:
                data = json.loads(answer)
            except json.JSONDecodeError as exc:
                raise ValueError(f"not valid JSON ({exc})") from None
            if not isinstance(data, dict) or set(data) != ids or not all(isinstance(v, str) for v in data.values()):
                raise ValueError(f"expected exactly the ids {sorted(ids)}")
            joined = "".join(data.values())
            if any(f in joined for f in fixed):
                raise ValueError("a fixed segment was repeated in a translation")
            return data

        text = " ".join(s.get("text") or s.get("fixed") for s in segments)
        user = json.dumps(segments, ensure_ascii=False)
        return self._ask(self._system("segments", text), user, check)


def _inference_completion(token):
    from huggingface_hub import InferenceClient
    from huggingface_hub.errors import HfHubHTTPError

    client = InferenceClient(provider=PROVIDER, token=token)

    def complete(messages):
        for attempt in range(8):
            try:
                response = client.chat_completion(
                    model=MODEL,
                    messages=messages,
                    temperature=0,
                    max_tokens=4096,
                    # the model reasons by default, which only adds latency for translation
                    extra_body={"reasoning_effort": "none"},
                )
                return response.choices[0].message.content or ""
            except HfHubHTTPError as exc:
                status = getattr(exc.response, "status_code", None)
                if status not in (429, 500, 502, 503, 504) or attempt == 7:
                    raise
                time.sleep(min(60, 2**attempt))

    return complete
