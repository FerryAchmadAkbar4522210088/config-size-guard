"""
"""
import argparse
import sys
import time
import json
import re
from datetime import datetime
from pathlib import Path

from csg.config import load_config
from csg.collector import collect_files
from csg.scorer import evaluate_risk
from csg.reporter.text import TextReporter
from csg.reporter.json_reporter import JsonReporter
from csg.ignore import IgnoreRules
from csg.baseline import load_baseline, update_baseline
from csg.git_tracker import get_renamed_files, get_previous_size_from_git
from csg.repo_stats import RepoStatsManager

from csg.models import FileResult, CheckResult
from csg.analyzer.growth import analyze_growth
from csg.analyzer.structural import analyze_structural
from csg.analyzer.entropy import analyze_entropy, extract_longest_token
from csg.analyzer.keycount import analyze_keycount
from csg.analyzer.absolute import build_peer_stats, analyze_absolute
from csg.analyzer.consistency import analyze_consistency

# --- DEV AUDIT LOGGER (SRE drift false-negative tuning) ---
_DRIFT_PATH_MARKERS = (
    "config_drift_simulated",
    "S1_cloudflare", "S2_crowdstrike", "S3_roblox", "S4_faa",
    "__s1.", "__s2.", "__s3.", "__s4.",
)
def write_dev_audit_log(filepath, final_score, checks, output_file="csg_dev_audit.log"):
    """
    Mencatat blind spot CSG: spesimen config drift yang lolos tanpa peringatan.
    Hanya untuk debugging threshold selama pengembangan — bukan deteksi malware/IoC.
    """
    path_norm = str(filepath).replace("\\", "/")
    is_drift_specimen = any(m in path_norm for m in _DRIFT_PATH_MARKERS)

    if is_drift_specimen and final_score == 0:
        entropy_val = next((c.value for c in checks if c.check == "entropy_anomaly"), "N/A")

        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "file_bypassed": str(filepath),
            "vulnerability_type": "CONFIG_DRIFT_FALSE_NEGATIVE",
            "analysis": {
                "entropy_detected": entropy_val,
                "reason_for_bypass": "Threshold YAML terlalu tinggi atau eksploitasi blind spot matematis."
            },
            "status": "🚨 BLIND SPOT DETECTED - NEEDS PATCHING!"
        }
        
        try:
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, indent=2) + ",\n")
        except IOError:
            pass
# -------------------------------------

def _try_parse_for_consistency(filepath: Path, content: str):
    """
    Coba parse file ke struktur data (dict/list) untuk consistency analyzer.
    Mendukung JSON, JSONC, JSON5 (strip komentar), dan YAML.
    Return None jika format tidak dikenali atau parse gagal — silent skip.
    """
    import json as _json
    ext = filepath.suffix.lower()

    # ── JSON / JSONC / JSON5 ───────────────────────────────────────────────
    if ext in (".json", ".jsonc", ".json5"):
        try:
            # Strip komentar // sebelum parse (JSONC/JSON5)
            clean = "\n".join(
                line for line in content.splitlines()
                if not line.strip().startswith("//")
            )
            return _json.loads(clean)
        except Exception:
            return None

    # ── YAML / YML ────────────────────────────────────────────────────────
    if ext in (".yaml", ".yml"):
        try:
            import yaml
            result = yaml.safe_load(content)
            return result if isinstance(result, (dict, list)) else None
        except Exception:
            return None

    # Format lain: tidak di-parse, consistency analyzer akan silent skip
    return None


def cmd_check(args):
    # Mulai menghitung Latency (Metrik Empiris)
    start_time = time.time()
    
    # 🔥 [FITUR BARU] Hapus log audit lama setiap kali run baru dimulai
    audit_log = Path("csg_dev_audit.log")
    if audit_log.exists():
        try:
            audit_log.unlink() # Menghapus file log sisa run kemarin
        except OSError:
            pass
    
    if args.format == 'text':
        print(f"[*] Memulai pemindaian anomali di: {args.paths}")
    cfg = load_config("csg.config.yaml")
    baseline_data = load_baseline(".csg-baseline.json") if not args.full_scan else {}
    
    stats_manager = RepoStatsManager(".csg-repo-stats.json")
    cfg.update(stats_manager.load()) 
    
    rename_map = get_renamed_files()
    ignore_rules = IgnoreRules(".csgignore")
    collected_files = list(collect_files([args.paths], cfg.get("extensions", []), ignore_rules))

    # Layer 2: statistik peer (lintas file dalam scan ini)
    peer_stats = build_peer_stats(collected_files)


    results = []

    for filepath in collected_files:
        file_result = FileResult(filepath=str(filepath))
        try:
            file_result.size_bytes = filepath.stat().st_size
        except OSError:
            continue
            
        # 1. Cari berdasarkan Path lengkap (Akurat)
        base_path_key = rename_map.get(filepath.as_posix(), filepath.as_posix())
        base_entry = baseline_data.get(base_path_key)
        
        # 🔥 ZERO-DAY PATCH 2: Fuzzy Filename Matching
        # Jika path lengkap tidak ketemu (karena beda folder tes), cari berdasarkan NAMA FILE saja!
        if not base_entry:
            stem = filepath.stem
            cleaned = re.sub(r'__s\d+$', '', stem)
            candidate_name = cleaned + filepath.suffix

            for bl_path, bl_data in baseline_data.items():
                if Path(bl_path).name == filepath.name or Path(bl_path).name == candidate_name:
                    base_entry = bl_data
                    break # Langsung pakai data ini jika nama filenya cocok

        # 2. Jika masih tidak ketemu juga, baru tanya ke Git
        if not base_entry:
            prev_size = get_previous_size_from_git(filepath.as_posix())
            if prev_size is not None:
                base_entry = {"size": prev_size}
        else:
            # Pastikan fallback base_entry punya struktur dict yang benar meskipun None
            pass
            
        if not base_entry:
             base_entry = {} # Fallback final agar analyzer tidak crash
        
        try:
            file_result.checks.extend(analyze_growth(file_result.size_bytes, base_entry, cfg, filepath) or [])

            if args.strict_format:
                file_result.checks.extend(analyze_structural(filepath, base_entry, cfg) or [])

            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
                longest_token = extract_longest_token(content)
            except OSError:
                content       = ""
                longest_token = ""

            file_result.checks.extend(analyze_entropy(longest_token, cfg, base_entry, filepath.suffix) or [])
            file_result.checks.extend(analyze_keycount(filepath, base_entry, cfg) or [])
            file_result.checks.extend(
                analyze_absolute(filepath, peer_stats, cfg) or []
            )

            # ── Consistency Analyzer (Layer 4 — intrinsik, zero-day) ──────
            # Parse file ke struktur data untuk pemeriksaan konsistensi internal.
            # Silent skip jika format tidak dikenali atau parse gagal.
            parsed_data = _try_parse_for_consistency(filepath, content)
            file_result.checks.extend(analyze_consistency(parsed_data) or [])

        except Exception as e:
            import traceback
            import sys
            print(f"[!] Error processing {filepath}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            continue

        evaluate_risk(file_result)
        write_dev_audit_log(filepath, file_result.total_score, file_result.checks)

        results.append(file_result)

    # Hitung total waktu pemindaian
    execution_time = time.time() - start_time
        
    if args.format == 'json':
        JsonReporter().report(results)
    else:
        TextReporter().print_report(results=results, verbose=args.verbose, env='local')
        # Cetak metrik Latency ke console lokal
        print(f"[*] Pemindaian selesai dalam {execution_time:.3f} detik.")
    
    if any(r.verdict == "CRITICAL" for r in results):
        sys.exit(1)

def cmd_update_baseline(args):
    cfg = load_config("csg.config.yaml")
    collected_files = list(collect_files([args.paths], cfg.get("extensions", []), IgnoreRules(".csgignore")))
    update_baseline(collected_files, ".csg-baseline.json")
    RepoStatsManager(".csg-repo-stats.json").calculate_and_save(".csg-baseline.json")
    print("[+] Baseline & IQR Statistik berhasil diperbarui.")

def main():
    parser = argparse.ArgumentParser(description="Config Size Guard (CSG) - SRE CI/CD Guardrail (config drift & structural anomaly)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="Jalankan pemindaian konfigurasi")
    check_parser.add_argument("--paths", required=True)
    check_parser.add_argument("--verbose", action="store_true")
    check_parser.add_argument("--full-scan", action="store_true")
    check_parser.add_argument("--format", choices=['text', 'json'], default='text')
    check_parser.add_argument("--strict-format", action="store_true", help="Aktifkan parser sintaksis (YAML/JSON)")

    baseline_parser = subparsers.add_parser("update-baseline", help="Perbarui baseline")
    baseline_parser.add_argument("--paths", required=True)

    args = parser.parse_args()
    if args.command == "check":
        cmd_check(args)
    elif args.command == "update-baseline":
        cmd_update_baseline(args)

if __name__ == "__main__":
    main()