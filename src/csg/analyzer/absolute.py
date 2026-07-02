"""
analyzer/absolute.py — Layer 2 (peer) absolute size guards

Melengkapi analyzer relatif (growth vs baseline/Git) dengan perbandingan
lintas-file dalam satu scan.
"""
import statistics
from collections import defaultdict
from pathlib import Path

from ..models import CheckResult


def _iqr_stats(values: list[int]) -> dict:
    if len(values) < 4:
        med = statistics.median(values) if values else 0
        return {"median": med, "iqr": 0.0, "q3": med, "count": len(values)}
    q1, _, q3 = statistics.quantiles(values, n=4)
    return {
        "median": statistics.median(values),
        "iqr": q3 - q1,
        "q3": q3,
        "count": len(values),
    }


def build_peer_stats(files: list[Path]) -> dict:
    """Layer 2: agregat ukuran per ekstensi dan per subfolder."""
    by_group: dict[tuple[str, str], list[int]] = defaultdict(list)
    for filepath in files:
        try:
            size = filepath.stat().st_size
        except OSError:
            continue
        ext = filepath.suffix.lower() or ".unknown"
        subfolder = filepath.parent.name
        by_group[(ext, subfolder)].append(size)
        by_group[(ext, "*")].append(size)

    stats = {key: _iqr_stats(sorted(sizes)) for key, sizes in by_group.items()}
    return {"by_ext": by_group, "stats": stats}


def analyze_absolute(
    filepath: Path,
    peer_stats: dict,
    cfg: dict,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    try:
        size = filepath.stat().st_size
    except OSError:
        return checks

    ext = filepath.suffix.lower() or ".unknown"
    subfolder = filepath.parent.name
    min_peer = int(cfg.get("absolute_min_peer_count", 4))
    min_bytes = int(cfg.get("absolute_peer_min_bytes", 1024))
    floor = cfg.get("static_floor") or {}
    warn_bytes = int(floor.get("size_warn_kb", 500)) * 1024
    fail_bytes = int(floor.get("size_fail_kb", 10240)) * 1024

    # Static floor (batas absolut keras dari config)
    if size >= fail_bytes:
        checks.append(CheckResult(
            check="absolute_size_floor_critical",
            score=2,
            detail=f"Size {size} B >= fail floor {fail_bytes} B",
            value=size,
        ))
    elif size >= warn_bytes:
        checks.append(CheckResult(
            check="absolute_size_floor_warn",
            score=1,
            detail=f"Size {size} B >= warn floor {warn_bytes} B",
            value=size,
        ))

    # Layer 2: outlier vs peer dalam scan yang sama
    stats_dict = peer_stats.get("stats", {})
    peer = stats_dict.get((ext, subfolder)) or stats_dict.get((ext, "*"))
    source = f"subfolder '{subfolder}'" if (ext, subfolder) in stats_dict else "global repo"

    if peer and peer.get("count", 0) >= min_peer:
        iqr = peer["iqr"] or 1.0
        threshold = peer["q3"] + (1.5 * iqr)
        if size > threshold and size > min_bytes:
            score = 2 if size > threshold * 2 else 1
            checks.append(CheckResult(
                check="absolute_peer_size_outlier",
                score=score,
                detail=f"Size {size} B > peer P95-ish {round(threshold)} B ({ext} in {source})",
                value=size,
            ))

    return checks
