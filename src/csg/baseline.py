"""
src/csg/baseline.py — Thermodynamic Profiling Database
- normalized_size : ukuran setelah normalisasi CRLF→LF
  - original_format : ekstensi file saat baseline dibuat
"""
import json
import math
import re
import zlib
from pathlib import Path
from datetime import datetime, timezone

_TOKEN_SPLIT = re.compile(r'[\s\'"{}\[\],:;=|<>\(\)!]+')
_KEY_PATTERN = re.compile(r'(?:["\']?[\w.-]+["\']?\s*[:=])|(?:<[\w.-]+>)')


def get_normalized_size(filepath: Path) -> int:
    try:
        content = filepath.read_bytes()
        return len(content.replace(b"\r\n", b"\n"))
    except Exception:
        try:
            return filepath.stat().st_size
        except Exception:
            return 0


def load_baseline(baseline_path: str) -> dict:
    path = Path(baseline_path)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("files", {})
    except Exception:
        return {}


def update_baseline(filepaths: list[Path], baseline_path: str) -> None:
    existing_data = load_baseline(baseline_path)

    for fp in filepaths:
        if not fp.exists() or not fp.is_file():
            continue
        try:
            content = fp.read_text(encoding="utf-8", errors="ignore")
            size_bytes = len(content)
            if size_bytes == 0:
                continue

            longest_token       = _extract_longest_token(content)
            base_entropy        = _shannon_entropy(longest_token)
            base_keycount       = len(_KEY_PATTERN.findall(content))

            # Thermodynamic Metrics
            compressed_size = len(zlib.compress(content.encode("utf-8")))
            comp_ratio      = size_bytes / max(compressed_size, 1)

            rel_path = str(fp).replace("\\", "/")
            entry    = existing_data.get(rel_path, {"size_history": []})

            entry["size_bytes"]      = size_bytes
            entry["normalized_size"] = get_normalized_size(fp)
            entry["original_format"] = fp.suffix.lower()

            history = entry["size_history"]
            history.append(size_bytes)
            entry["size_history"] = history[-5:]

            entry["base_entropy"]        = round(base_entropy, 2)
            entry["base_keycount"]       = base_keycount
            entry["compression_ratio"]   = round(comp_ratio, 2)

            existing_data[rel_path] = entry
        except Exception:
            pass

    _save_baseline(baseline_path, existing_data)


def _save_baseline(baseline_path: str, files_data: dict) -> None:
    envelope = {
        "version": "8.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": files_data,
    }
    try:
        with open(Path(baseline_path), "w", encoding="utf-8") as f:
            json.dump(envelope, f, indent=2)
    except Exception:
        pass


def _extract_longest_token(content: str) -> str:
    tokens = _TOKEN_SPLIT.split(content)
    return max(tokens, key=len, default="")


def _shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    n    = len(text)
    freq = {c: text.count(c) for c in set(text)}
    return -sum((count / n) * math.log2(count / n) for count in freq.values())
