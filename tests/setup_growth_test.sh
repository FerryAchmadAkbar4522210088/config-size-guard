#!/usr/bin/env bash
# Bangun arena Git simulasi insiden dari tests/evaluation_dataset/{1,2,3}.
# Dijalankan dari root repo config-size-guard (folder tempat pyproject.toml berada).
set -euo pipefail

ROOT_DIR="$(pwd)"
TARGET_DIR="tests/growth_simulation_repo"
EVAL_DIR="tests/evaluation_dataset"

BENIGN_DIR="$EVAL_DIR/1_benign_standard"
DRIFT_DIR="$EVAL_DIR/2_config_drift_simulated"
POSTMORTEM_DIR="$EVAL_DIR/3_real_postmortem_replicas"

echo "[*] Membangun repositori simulasi Insiden CI/CD di $TARGET_DIR ..."

rm -rf "$TARGET_DIR"
mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

git init -q -b main
git config user.name "CI-CD Bot"
git config user.email "bot@infrastructure.local"

# -----------------------------------------------------------------------
# FASE 1 (HEAD~1): Baseline stabil
# - Salin semua file benign ke folder 1_benign_standard/
# - Untuk setiap subfolder skenario drift (S1-S4), salin versi BERSIH:
#   ambil file dari kohort-1/benign dengan nama yang sama (buang akhiran __sN)
# -----------------------------------------------------------------------
echo "[*] [HEAD~1] Menerapkan konfigurasi awal yang stabil (Baseline)..."

BENIGN_PATH="$ROOT_DIR/$BENIGN_DIR"
if [ -d "$BENIGN_PATH" ]; then
  mkdir -p "1_benign_standard"
  cp -r "$BENIGN_PATH"/. "1_benign_standard/"
fi

DRIFT_PATH="$ROOT_DIR/$DRIFT_DIR"
if [ -d "$DRIFT_PATH" ]; then
  # Iterasi setiap subfolder skenario (S1_..., S2_..., dst.)
  for scenario_subdir in "$DRIFT_PATH"/*/; do
    [ -d "$scenario_subdir" ] || continue
    scenario_name=$(basename "$scenario_subdir")
    mkdir -p "$scenario_name"
    # Untuk setiap file drift, salin versi BERSIH (tanpa __sN) dari benign
    for f in "$scenario_subdir"*; do
      [ -f "$f" ] || continue
      drift_filename=$(basename "$f")
      # Buang akhiran __s1 / __s2 / __s3 / __s4 untuk mendapatkan nama benign
      clean_name=$(echo "$drift_filename" | sed -E 's/__s[1-4]//')
      benign_file="$BENIGN_PATH/$clean_name"
      if [ -f "$benign_file" ]; then
        cp "$benign_file" "$scenario_name/$drift_filename"
      fi
    done
  done
fi

git add -A
git commit -q -m "chore: successful deployment v1.0.0"

# -----------------------------------------------------------------------
# FASE 2 (HEAD): Drift + Postmortem
# - Timpa folder skenario dengan file drift SESUNGGUHNYA
# - Tambahkan file postmortem (tidak punya baseline — dideteksi lewat
#   Internal Consistency, bukan Delta Growth)
# -----------------------------------------------------------------------
echo "[*] [HEAD] Menerapkan konfigurasi rusak (Drift) & File Baru (Zero-Day)..."

if [ -d "$DRIFT_PATH" ]; then
  for scenario_subdir in "$DRIFT_PATH"/*/; do
    [ -d "$scenario_subdir" ] || continue
    scenario_name=$(basename "$scenario_subdir")
    mkdir -p "$scenario_name"
    cp -r "$scenario_subdir". "$scenario_name/"
  done
fi

POSTMORTEM_PATH="$ROOT_DIR/$POSTMORTEM_DIR"
if [ -d "$POSTMORTEM_PATH" ]; then
  mkdir -p "3_real_postmortem_replicas"
  # Salin sub-folder R1-R4 apa adanya
  for subdir in "$POSTMORTEM_PATH"/*/; do
    [ -d "$subdir" ] || continue
    subname=$(basename "$subdir")
    mkdir -p "3_real_postmortem_replicas/$subname"
    cp -r "$subdir". "3_real_postmortem_replicas/$subname/"
  done
fi

git add -A
git commit -q -m "fix: automated config sync (BOTCHED DEPLOYMENT)"

echo "[+] Selesai! Arena insiden siap untuk dievaluasi."
cd "$ROOT_DIR"
