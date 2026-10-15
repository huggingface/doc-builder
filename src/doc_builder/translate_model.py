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
(system prompt + block), so unchanged blocks are never sent to the model again.
"""

import hashlib
import json
import re
import time

from .translate_html import check_markup, drop_invented_tags

MODEL = "Qwen/Qwen3.8-27B"
PROVIDER = "cerebras"
# Bump to invalidate every cached translation (e.g. after a prompt change).
PROMPT_VERSION = 1
# Doc language code (the folder name moon-landing serves) -> the language the model writes.
LANGUAGE_NAMES = {
    "zh": "Simplified Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Brazilian Portuguese",
    "es": "Spanish",
    "fr": "French",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "tr": "Turkish",
    "ru": "Russian",
    "ar": "Modern Standard Arabic",
}

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

STYLE = {
    "ja": " Use the です・ます style.",
    "ko": " Use the formal 합니다 style.",
    "es": " Use neutral Spanish that reads naturally in both Latin America and Spain.",
}


class TranslationFailed(Exception):
    pass


# Frequent English function words: never part of names or code, rare in a real translation.
ENGLISH_FUNCTION_WORDS = {
    "the", "to", "of", "and", "is", "are", "for", "with", "that", "this", "by", "you", "your",
    "from", "can", "be", "an", "it", "which", "when", "will", "into", "using", "should",
}  # fmt: skip


def english_share(text):
    words = re.findall(r"[A-Za-z]+", text.lower())
    return sum(w in ENGLISH_FUNCTION_WORDS for w in words) / len(words) if len(words) >= 6 else 0.0


def check_translated(source, translation):
    """Reject an answer that is still English prose (models sometimes just reword the source)."""
    if english_share(source) >= 0.15 and english_share(translation) >= 0.15:
        raise ValueError("the answer is still in English; translate it")


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
        self._complete = complete or _inference_completion(token)
        self.model_calls = 0

    def _system(self, kind):
        name = LANGUAGE_NAMES[self.language]
        prompt = INSTRUCTIONS.format(language=name, style=STYLE.get(self.language, ""))
        return prompt + (MARKUP_PROMPT if kind == "markup" else SEGMENTS_PROMPT)

    def _key(self, system, user):
        payload = json.dumps([MODEL, PROVIDER, PROMPT_VERSION, system, user], ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _ask(self, system, user, check, response_format=None):
        """Cached, validated answer; one retry that tells the model what was wrong."""
        language = LANGUAGE_NAMES[self.language]
        # stating the task next to the text keeps instruction-like sentences ("Use X to …") from being answered in English
        user = f"Translate into {language}:\n\n{user}"
        key = self._key(system, user)
        if key in self.cache:
            return self.cache[key]
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        error = None
        for attempt in range(2):
            self.model_calls += 1
            # the retry samples: at temperature 0 the model repeats the same invalid answer
            answer = self._complete(messages, temperature=0.5 if attempt else 0, response_format=response_format)
            answer = answer.strip()
            try:
                result = check(answer)
            except ValueError as exc:
                error = str(exc)
                messages = messages[:2] + [
                    {"role": "assistant", "content": answer},
                    {"role": "user", "content": f"That answer is invalid: {error}. Answer again, in {language}."},
                ]
                continue
            self.cache[key] = result
            return result
        raise TranslationFailed(error)

    def translate_markup(self, markup):
        """Translate a static block given as markup (see `translate_html.to_markup`)."""

        def check(answer):
            answer = drop_invented_tags(markup, answer)
            check_markup(markup, answer)
            prose = re.sub(r"<c(\d+)>.*?</c\1>|</?t\d+/?>", " ", answer, flags=re.S)
            check_translated(re.sub(r"<c(\d+)>.*?</c\1>|</?t\d+/?>", " ", markup, flags=re.S), prose)
            return answer

        return self._ask(self._system("markup"), markup, check)

    def translate_segments(self, segments):
        """Translate the numbered segments of a block; returns `{id: text}`."""
        ids = {str(s["id"]) for s in segments if "id" in s}
        fixed = [s["fixed"] for s in segments if "fixed" in s and len(s["fixed"]) > 3]
        source = "".join(s["text"] for s in segments if "id" in s)

        def check(answer):
            answer = re.sub(r"^```(?:json)?\s*|\s*```$", "", answer)
            try:
                data = json.loads(answer)
            except json.JSONDecodeError as exc:
                raise ValueError(f"not valid JSON ({exc})") from None
            if not isinstance(data, dict) or set(data) != ids or not all(isinstance(v, str) for v in data.values()):
                raise ValueError(f"expected exactly the ids {sorted(ids)}")
            # a fixed string may also be part of the English prose (e.g. "-100"); only an extra copy is a repeat
            joined = "".join(data.values())
            if any(joined.count(f) > source.count(f) for f in fixed):
                raise ValueError("a fixed segment was repeated in a translation")
            check_translated(" ".join(s["text"] for s in segments if "id" in s), " ".join(data.values()))
            return data

        # the provider enforces exactly these keys; without it models return lists or split segments
        schema = {
            "type": "object",
            "properties": {i: {"type": "string"} for i in sorted(ids)},
            "required": sorted(ids),
            "additionalProperties": False,
        }
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": "translation", "strict": True, "schema": schema},
        }
        return self._ask(self._system("segments"), json.dumps(segments, ensure_ascii=False), check, response_format)


def _inference_completion(token):
    from huggingface_hub import InferenceClient
    from huggingface_hub.errors import HfHubHTTPError

    client = InferenceClient(provider=PROVIDER, token=token)

    def complete(messages, temperature=0, response_format=None):
        for attempt in range(8):
            try:
                response = client.chat_completion(
                    model=MODEL,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=4096,
                    response_format=response_format,
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
