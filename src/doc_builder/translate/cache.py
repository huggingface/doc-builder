"""
Remembers paragraphs we have already translated, so we only pay for new ones.

Every paragraph gets an ID worked out from the English text itself (plus the model, the
prompt and the glossary). Same English in, same ID out. So to find out whether we have
already translated something, we work out its ID and look for it -- there is no separate
list mapping pages to paragraphs to keep in step.

What lives on disk:

    cache/index.json                  a list of every ID we have stored
    cache/blobs/<first 2 of ID>/<ID>.txt   one translated paragraph per file

The index file is just a shortcut. Without it, working out what is already translated
would mean listing roughly 20,000 files over the network; with it, that is a single read.

Two habits borrowed from build_cache.py, for the same reasons it has them:

  - A plain folder works just as well as a bucket, so tests never touch the network.
  - Nothing here is ever allowed to crash the run. If the cache misbehaves, the worst
    that happens is we translate the paragraph again.
"""

import hashlib
import json
import os
import traceback
from pathlib import Path


def segment_key(masked_text, model_id, prompt_version, glossary_sha, language):
    """Work out the ID for one paragraph.

    Two things are deliberately left out of the ID.

    The surrounding paragraphs: if the translation depended on its neighbours but the ID
    did not, then a paragraph pulled from the cache could differ from the same paragraph
    translated fresh, and we would have no way to tell which one we were looking at.

    The heading it sits under: including that would mean renaming one section throws away
    the translation of everything below it.
    """
    sha = hashlib.sha256()
    for part in (masked_text, model_id, prompt_version, glossary_sha, language):
        sha.update(part.encode("utf-8"))
        sha.update(b"\0")
    return sha.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SegmentCache:
    """Reads and writes translated paragraphs, filed under their ID.

    `root` can be an ordinary folder or a storage bucket mounted as one. Jobs mount
    buckets so they look like normal folders, so either way this is just reading and
    writing files -- there is no separate network path to write or test.
    """

    def __init__(self, root):
        self.root = Path(root) / "cache"
        self.blobs = self.root / "blobs"
        self.index_path = self.root / "index.json"
        self._known = None

    # -- the list of what we have --------------------------------------------------

    def load_index(self):
        """Which paragraphs do we already have? An unreadable index means we assume none."""
        if self._known is not None:
            return self._known
        try:
            self._known = set(json.loads(self.index_path.read_text(encoding="utf-8")))
        except FileNotFoundError:
            self._known = set()
        except Exception:
            traceback.print_exc()
            print("[cache] could not read the index; carrying on as if nothing is cached")
            self._known = set()
        return self._known

    def save_index(self):
        """Rebuild the index by looking at what is actually on disk.

        It is written to a temporary file and then moved into place. If we wrote it
        directly and the run died halfway through, we would be left with a half-written
        list, and every translation missing from it would be quietly redone.
        """
        try:
            keys = sorted(p.stem for p in self.blobs.rglob("*.txt"))
            self.root.mkdir(parents=True, exist_ok=True)
            tmp = self.index_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(keys), encoding="utf-8")
            os.replace(tmp, self.index_path)
            self._known = set(keys)
            return len(keys)
        except Exception:
            traceback.print_exc()
            print("[cache] could not write the index; the translations are still saved")
            return 0

    # -- the translations themselves ------------------------------------------------

    def _blob_path(self, key):
        return self.blobs / key[:2] / f"{key}.txt"

    def get(self, key):
        """The translation for this ID, or None if we do not have it or cannot read it."""
        try:
            return self._blob_path(key).read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except Exception:
            traceback.print_exc()
            return None

    def get_many(self, keys):
        """Look up several IDs at once. Anything we do not have is simply left out."""
        found = {}
        for key in keys:
            text = self.get(key)
            if text is not None:
                found[key] = text
        return found

    def put(self, key, text):
        """Save one translated paragraph. Says whether it worked."""
        try:
            path = self._blob_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".txt.tmp")
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, path)
            return True
        except Exception:
            traceback.print_exc()
            return False

    def put_many(self, items):
        """Save a batch of translations and report how many were written.

        Remember to call save_index() afterwards, or the next run will not know they exist.
        """
        return sum(1 for key, text in items.items() if self.put(key, text))
