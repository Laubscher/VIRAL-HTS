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
    if [[ "${SKIP_PREPROCESSING:-0}" -eq 0 ]]; then
        printf 'Trimmomatic\t0.36\n'
        printf 'CD-HIT/cd-hit-dup\t4.6.8\n'
        capture 'SNAP' "$SNAP_ALIGNER"
    else
        printf 'Preprocessing / host depletion\tskipped (-P)\n'
    fi
    capture 'SAMtools' "$SAMTOOLS" --version
    capture 'Minimap2' "$MINIMAP2" --version
    capture 'BEDTools' "$BEDTOOLS" --version
    if [[ "$SKIP_DENOVO" -eq 0 ]]; then
        capture 'IDBA-UD' "$IDBA_UD" --version
        capture 'NCBI BLAST+' "$BLASTX" -version
        printf 'RVDB-prot database\t%s\n' "$RVDB_PROTEIN_DB"
    else
        printf 'De novo / BLASTx\tskipped (-D)\n'
    fi
    printf 'Virosaurus\t2023\n'
} > "$MANIFEST"

{
    printf 'parameter\tvalue\n'
    printf 'read_layout\t%s\ninput_1\t%s\ninput_2\t%s\n' "$READ_LAYOUT" "$R1" "$R2"
    printf 'threads\t%s\nread_length\t%s\nskip_denovo\t%s\n' "$THREADS" "$READ_LENGTH" "$SKIP_DENOVO"
    printf 'skip_preprocessing\t%s\nskip_host_depletion\t%s\n' \
        "${SKIP_PREPROCESSING:-0}" "${SKIP_PREPROCESSING:-0}"
    if [[ "${SKIP_PREPROCESSING:-0}" -eq 0 ]]; then
        printf 'snap_use_huge_pages\t%s\n' "$SNAP_USE_HUGE_PAGES"
    fi
    if [[ "$SKIP_DENOVO" -eq 0 ]]; then
        printf 'assembler\t%s\nrvdb_protein_db\t%s\n' "$IDBA_UD" "$RVDB_PROTEIN_DB"
        printf 'idba_single\t%s\nidba_mink\t%s\nidba_maxk\t%s\nidba_step\t%s\n' \
            "$([[ "$READ_LAYOUT" == single ]] && printf 1 || printf 0)" "$IDBA_MINK" "$IDBA_MAXK" "$IDBA_STEP"
        printf 'min_contig_length\t%s\nlong_contig_length\t%s\nblast_evalue\t%s\nblast_max_targets\t%s\n' \
            "$MIN_CONTIG_LENGTH" "$LONG_CONTIG_LENGTH" "$BLAST_EVALUE" "$BLAST_MAX_TARGETS"
    fi
} > "$SAMPLE_DIR/results/run_parameters.tsv"

cp "$CONFIG" "$SAMPLE_DIR/logs/config.used.sh"
if [[ -f "$ROOT_DIR/docker/software_versions.build.txt" ]]; then
    cp "$ROOT_DIR/docker/software_versions.build.txt" "$SAMPLE_DIR/results/container_software_versions.txt"
fi
