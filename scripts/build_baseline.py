#!/usr/bin/env python3
"""
scripts/build_baseline.py

FUNGSI: membuat file .csg-baseline.json berisi "catatan riwayat" ukuran,
jumlah key, dan entropy setiap file pada kondisi commit SEBELUMNYA (HEAD~1),
supaya CSG bisa membandingkan kondisi file sekarang vs kemarin.

Tanpa file ini, Delta Growth Analyzer (KF01) tidak pernah aktif -- dia
diam-diam skip semua file karena tidak tahu ukurannya kemarin.

PERUBAHAN: main() sekarang cek dulu apakah --config-src dan file tujuan
(<repo>/csg.config.yaml) itu SAMA PERSIS (kasus production guardrail, yang
men-scan repo aslinya sendiri -- bukan repo simulasi). Kalau sama, proses
copy dilewati (tidak perlu disalin ke dirinya sendiri) alih-alih crash
dengan shutil.SameFileError.

Pemakaian:
    python scripts/build_baseline.py --repo . --ref HEAD~1
    python scripts/build_baseline.py --repo tests/growth_simulation_repo --ref HEAD~1
"""
import argparse
import json
import math
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

KEY_PATTERN = re.compile(r'(?:["\']?[\w.-]+["\']?\s*[:=])|(?:<[\w.-]+>)')
TOKEN_SPLIT = re.compile(r'[\s\'"{}\[\],:;=|<>\(\)!]+')


def shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    n = len(text)
    freq = {c: text.count(c) for c in set(text)}
    return -sum((count / n) * math.log2(count / n) for count in freq.values())


def build_baseline_files(repo: Path, ref: str) -> dict:
    try:
        ls = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", ref],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            cwd=repo,
        )
    except subprocess.CalledProcessError:
        print(f"[!] Tidak ada commit '{ref}' di {repo}.")
        print("    (Wajar kalau ini commit pertama repo -- baseline akan kosong,")
        print("     artinya Delta Growth silent-skip untuk semua file kali ini.)")
        return {}

    files_in_prev = [l.strip() for l in ls.stdout.splitlines() if l.strip()]
    baseline_files: dict = {}

    for rel_path in files_in_prev:
        try:
            r_size = subprocess.run(
                ["git", "cat-file", "-s", f"{ref}:{rel_path}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
                cwd=repo,
            )
            size = int(r_size.stdout.strip())

            r_content = subprocess.run(
                ["git", "cat-file", "blob", f"{ref}:{rel_path}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=repo,
            )
            content = r_content.stdout if r_content.returncode == 0 else ""

            base_keycount = len(KEY_PATTERN.findall(content))
            tokens = TOKEN_SPLIT.split(content)
            longest_token = max(tokens, key=len, default="")
            base_entropy = shannon_entropy(longest_token)

            baseline_files[rel_path] = {
                "size_bytes": size,
                "size_history": [size],
                "base_keycount": base_keycount,
                "base_entropy": round(base_entropy, 2),
            }
        except Exception:
            continue

    return baseline_files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="Path ke repo yang akan discan CSG")
    ap.add_argument("--ref", default="HEAD~1", help="Commit acuan baseline (default: HEAD~1)")
    ap.add_argument("--config-src", default=None, help="Path csg.config.yaml untuk disalin ke --repo (opsional)")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    baseline_files = build_baseline_files(repo, args.ref)

    envelope = {
        "version": "7.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": baseline_files,
    }
    baseline_path = repo / ".csg-baseline.json"
    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2)

    print(f"[+] Baseline dibangun: {len(baseline_files)} file dari '{args.ref}' -> {baseline_path}")

    if args.config_src:
        src_cfg = Path(args.config_src).resolve()
        dst_cfg = (repo / "csg.config.yaml").resolve()

        if src_cfg == dst_cfg:
            # Kasus production guardrail: --repo adalah repo aslinya sendiri,
            # jadi csg.config.yaml SUDAH ada di lokasi yang benar -- tidak
            # perlu (dan tidak boleh) disalin ke dirinya sendiri.
            print(f"    [i] csg.config.yaml sudah berada di lokasi target, tidak perlu disalin.")
        elif src_cfg.exists():
            shutil.copy2(src_cfg, dst_cfg)
            print(f"    csg.config.yaml disalin ke {repo}")
        else:
            print(f"    [!] --config-src '{src_cfg}' tidak ditemukan, dilewati.")


if __name__ == "__main__":
    main()