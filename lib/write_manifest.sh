#!/usr/bin/env bash
set -euo pipefail

source "$ROOT_DIR/lib/common.sh"

MANIFEST="$SAMPLE_DIR/results/software_versions.txt"

capture() {
    local label="$1"
    shift
    local value
    value="$("$@" 2>&1 | head -n 1 || true)"
    printf '%s\t%s\n' "$label" "${value:-version unavailable}"
}

{
    printf 'FEVIR\t%s\n' "$(<"$ROOT_DIR/VERSION")"
    printf 'Read layout\t%s\n' "$READ_LAYOUT"
    printf 'Trimmomatic\t0.36\n'
    printf 'CD-HIT/cd-hit-dup\t4.6.8\n'
    capture 'SNAP' "$SNAP_ALIGNER"
    capture 'SAMtools' "$SAMTOOLS" --version
    capture 'Minimap2' "$MINIMAP2" --version
    capture 'BEDTools' "$BEDTOOLS" --version
    printf 'De novo / BLASTx\tdisabled in this edition\n'
    printf 'Virosaurus\t2023\n'
} > "$MANIFEST"

{
    printf 'parameter\tvalue\n'
    printf 'read_layout\t%s\ninput_1\t%s\ninput_2\t%s\n' "$READ_LAYOUT" "$R1" "$R2"
    printf 'threads\t%s\nread_length\t%s\nskip_denovo\t%s\n' "$THREADS" "$READ_LENGTH" "$SKIP_DENOVO"
    printf 'snap_use_huge_pages\t%s\n' "$SNAP_USE_HUGE_PAGES"
} > "$SAMPLE_DIR/results/run_parameters.tsv"

cp "$CONFIG" "$SAMPLE_DIR/logs/config.used.sh"
if [[ -f "$ROOT_DIR/docker/software_versions.build.txt" ]]; then
    cp "$ROOT_DIR/docker/software_versions.build.txt" "$SAMPLE_DIR/results/container_software_versions.txt"
fi
