"""
src/csg/repo_stats.py — Robust IQR Statistics & Minimum Sample Guard
"""
import json
import statistics
from pathlib import Path

class RepoStatsManager:
    def __init__(self, stats_file: str | Path):
        self.path = Path(stats_file)
        self._data: dict = self.load()

    def load(self) -> dict:
        if not self.path.exists(): return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return {}

    def calculate_and_save(self, baseline_path: str | Path) -> None:
        base_path = Path(baseline_path)
        if not base_path.exists(): return

        try:
            with open(base_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception: return

        files = data.get("files", {})
        if not files: return

        entropies = sorted([info.get("base_entropy", 0.0) for info in files.values() if info.get("base_entropy", 0.0) > 0.0])

        # PENYIMPANAN JUMLAH POPULASI (Untuk Minimum Sample Guard)
        stats = {"sample_size": len(files)}
        
        # FUNGSI MATEMATIKA IQR (Standar Analisis Skewed Data)
        def get_iqr_stats(dataset):
            if len(dataset) < 4:
                return {"median": statistics.median(dataset) if dataset else 0, "iqr": 0, "q3": 0}
            q1 = statistics.quantiles(dataset, n=4)[0]
            q3 = statistics.quantiles(dataset, n=4)[2]
            return {"median": statistics.median(dataset), "iqr": q3 - q1, "q3": q3}

        ent_stats = get_iqr_stats(entropies)
        stats["entropy_median"] = ent_stats["median"]
        stats["entropy_iqr"] = ent_stats["iqr"]
        stats["entropy_q3"] = ent_stats["q3"]

        self._data = stats
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=4)