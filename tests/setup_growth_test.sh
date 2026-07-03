#!/usr/bin/env bash
# Bangun arena Git simulasi insiden dari dataset-uji/kohort-{1,2,3}.
# Kohort-2 dan kohort-3 disimpan flat; skrip ini merutekan ke subfolder
# S*/R* yang diharapkan evaluate_csg.py dan ground truth CSV.
set -euo pipefail

ROOT_DIR="$(pwd)"
TARGET_DIR="tests/growth_simulation_repo"
BENIGN_DIR="dataset-uji/kohort-1"
DRIFT_DIR="dataset-uji/kohort-2"
POSTMORTEM_DIR="dataset-uji/kohort-3"

scenario_dir_for_suffix() {
  case "$1" in
    s1) echo "S1_cloudflare_feature_file_doubled" ;;
    s2) echo "S2_crowdstrike_field_count_anomaly" ;;
    s3) echo "S3_roblox_consul_kv_bloat" ;;
    s4) echo "S4_faa_file_truncation_anomaly" ;;
  esac
}

postmortem_dir_for_file() {
  case "$1" in
    cloudflare_*) echo "R1_cloudflare" ;;
    channel_file_*) echo "R2_crowdstrike" ;;
    consul_registry_*) echo "R3_roblox" ;;
    notam_database_*) echo "R4_faa" ;;
    *) echo "" ;;
  esac
}

echo "[*] Membangun repositori simulasi Insiden CI/CD di $TARGET_DIR ..."

rm -rf "$TARGET_DIR"
mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

git init -q -b main
git config user.name "CI-CD Bot"
git config user.email "bot@infrastructure.local"

# FASE 1 (HEAD~1): baseline stabil
echo "[*] [HEAD~1] Menerapkan konfigurasi awal yang stabil (Baseline)..."

DRIFT_PATH="$ROOT_DIR/$DRIFT_DIR"
if [ -d "$DRIFT_PATH" ]; then
  for f in "$DRIFT_PATH"/*; do
    [ -f "$f" ] || continue
    filename=$(basename "$f")
    if [[ "$filename" =~ __s([1-4]) ]]; then
      scenario_dir="$(scenario_dir_for_suffix "s${BASH_REMATCH[1]}")"
      mkdir -p "$scenario_dir"
      clean_name=$(echo "$filename" | sed -E 's/__s[1-4]//')
      benign_file="$ROOT_DIR/$BENIGN_DIR/$clean_name"
      if [ -f "$benign_file" ]; then
        cp "$benign_file" "$scenario_dir/$filename"
      fi
    fi
  done
fi

BENIGN_PATH="$ROOT_DIR/$BENIGN_DIR"
if [ -d "$BENIGN_PATH" ]; then
  mkdir -p "1_benign_standard"
  cp -r "$BENIGN_PATH"/. "1_benign_standard/"
fi

git add -A
git commit -q -m "chore: successful deployment v1.0.0"

# FASE 2 (HEAD): drift + postmortem
echo "[*] [HEAD] Menerapkan konfigurasi rusak (Drift) & File Baru (Zero-Day)..."

if [ -d "$DRIFT_PATH" ]; then
  for f in "$DRIFT_PATH"/*; do
    [ -f "$f" ] || continue
    filename=$(basename "$f")
    if [[ "$filename" =~ __s([1-4]) ]]; then
      scenario_dir="$(scenario_dir_for_suffix "s${BASH_REMATCH[1]}")"
      mkdir -p "$scenario_dir"
      cp "$f" "$scenario_dir/$filename"
    fi
  done
fi

POSTMORTEM_PATH="$ROOT_DIR/$POSTMORTEM_DIR"
if [ -d "$POSTMORTEM_PATH" ]; then
  mkdir -p "3_real_postmortem_replicas"
  for f in "$POSTMORTEM_PATH"/*; do
    [ -f "$f" ] || continue
    filename=$(basename "$f")
    dest_sub="$(postmortem_dir_for_file "$filename")"
    [ -n "$dest_sub" ] || continue
    mkdir -p "3_real_postmortem_replicas/$dest_sub"
    cp "$f" "3_real_postmortem_replicas/$dest_sub/$filename"
  done
fi

git add -A
git commit -q -m "fix: automated config sync (BOTCHED DEPLOYMENT)"

echo "[+] Selesai! Arena insiden siap untuk dievaluasi."
cd "$ROOT_DIR"
