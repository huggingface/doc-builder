"""Real extraction and in-memory Hub transfers; only inference and the network are stubbed."""

import re
from pathlib import Path
from types import SimpleNamespace

from huggingface_hub.hf_api import BucketFile

from doc_builder.translate import pipeline


def config():
    return {
        **pipeline.SETTINGS,
        "language": "ja",
        "model": "test",
        "model_revision": "a" * 40,
        "tokenizer_revision": "a" * 40,
        "glossary": {"keep": [], "pin": {}},
    }


def fake_translation(unit):
    def replace(match):
        text = match[0]
        if text.startswith("¤") or not text.strip():
            return text
        return re.match(r"\s*", text)[0] + "翻訳です。" + re.search(r"\s*$", text)[0]

    return re.sub(r"¤\d+¤|[^¤]+", replace, unit["text"])


def generate(units, config, retry=False):
    return [fake_translation(unit) for unit in units]


def files():
    return {
        "index.md": b"# Introduction\n\nRead the guide.\n",
        "guide.mdx": b"# Guide\n\nUse `code`.\n",
        "image.svg": b"<svg/>",
        "_toctree.yml": b"- title: Start\n  sections:\n  - local: index\n    title: Introduction\n  - local: guide\n    title: Guide\n",
    }


class Hub:
    def __init__(self):
        self.files, self.writes, self.fail_at = {}, [], None

    def batch_bucket_files(self, bucket_id, *, add=None, delete=None):
        self.writes.append([name for _, name in add or []] + (delete or []))
        if self.fail_at == len(self.writes):
            raise OSError("Interrupted upload")
        for name in delete or []:
            self.files.pop((bucket_id, name), None)
        for data, name in add or []:
            self.files[bucket_id, name] = data if isinstance(data, bytes) else Path(data).read_bytes()

    def list_bucket_tree(self, bucket_id, *, prefix, recursive):
        return [
            BucketFile(type="file", path=name, size=len(data), xetHash="test")
            for (bucket, name), data in self.files.items()
            if bucket == bucket_id and name.startswith(prefix)
        ]

    def download_bucket_files(self, bucket_id, files, *, raise_on_missing_files):
        for remote, local in files:
            Path(local).write_bytes(self.files[bucket_id, remote])


def job_info(id="job1", state="COMPLETED"):
    return SimpleNamespace(id=id, status=SimpleNamespace(stage=state), url=f"https://huggingface.co/jobs/test/{id}")
