#!/usr/bin/env bash
set -euo pipefail

source "$ROOT_DIR/lib/common.sh"

LOGS="$SAMPLE_DIR/logs"
mkdir -p "$LOGS"

{
    printf 'parameter\tvalue\n'
    printf 'read_layout\t%s\ninput_1\t%s\ninput_2\t%s\n' "$READ_LAYOUT" "$R1" "$R2"
    printf 'threads\t%s\nread_length\t%s\nskip_denovo\t%s\n' "$THREADS" "$READ_LENGTH" "$SKIP_DENOVO"
    printf 'skip_preprocessing\t%s\nskip_host_depletion\t%s\n' \
        "$SKIP_PREPROCESSING" "$SKIP_HOST_DEPLETION"
    printf 'host_database_count\t%s\n' "$HOST_DB_COUNT"
    if [[ "$SKIP_HOST_DEPLETION" -eq 0 ]]; then
        printf 'snap_use_huge_pages\t%s\n' "$SNAP_USE_HUGE_PAGES"
        index=0
        while IFS= read -r database; do
            index=$((index + 1))
            printf 'host_db_%s\t%s\n' "$index" "$database"
        done < "$HOST_DB_LIST"
    fi
    if [[ "$SKIP_DENOVO" -eq 0 ]]; then
        printf 'assembler\t%s\nrvdb_protein_db\t%s\n' "$IDBA_UD" "$RVDB_PROTEIN_DB"
        printf 'idba_single\t%s\nidba_mink\t%s\nidba_maxk\t%s\nidba_step\t%s\n' \
            "$([[ "$READ_LAYOUT" == single ]] && printf 1 || printf 0)" "$IDBA_MINK" "$IDBA_MAXK" "$IDBA_STEP"
        printf 'min_contig_length\t%s\nlong_contig_length\t%s\nblast_evalue\t%s\nblast_max_targets\t%s\n' \
            "$MIN_CONTIG_LENGTH" "$LONG_CONTIG_LENGTH" "$BLAST_EVALUE" "$BLAST_MAX_TARGETS"
        printf 'rvdb_family_map\t%s\ndenovo_family_evalue\t%s\n' \
            "$RVDB_FAMILY_MAP" "$DENOVO_FAMILY_EVALUE"
    fi
} > "$LOGS/run_parameters.tsv"

cp "$CONFIG" "$LOGS/config.used.sh"
