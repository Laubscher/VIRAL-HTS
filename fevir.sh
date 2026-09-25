#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT_DIR/lib/common.sh"

usage() {
    cat <<'EOF'
Usage:
  fevir.sh -1 reads_R1.fastq[.gz] -2 reads_R2.fastq[.gz] -s SAMPLE [options]
  fevir.sh -U reads.fastq[.gz] -s SAMPLE [options]

Preprocessing, reference detection, IDBA-UD assembly and RVDB-prot BLASTx.

Input (choose one layout):
  -1 FILE      Paired-end Illumina R1 FASTQ (requires -2)
  -2 FILE      Paired-end Illumina R2 FASTQ (requires -1)
  -U FILE      Single-end Illumina FASTQ (cannot be combined with -1/-2)

Required:
  -s NAME      Sample name

Options:
  -o DIR       Output root (default: ./fevir_output)
  -c FILE      Configuration file (default: config/config.sh)
  -t INT       Threads (default from configuration)
  -l INT       Original read length (default from configuration)
  -k           Keep intermediate files
  -P           Skip trimming, deduplication and host depletion
  -D           Skip de novo assembly and BLASTx
  -h           Show this help
EOF
}

R1=""
R2=""
SINGLE_READS=""
SKIP_PREPROCESSING=0
SKIP_DENOVO=0
SAMPLE=""
OUTPUT_ROOT="$PWD/fevir_output"
CONFIG="$ROOT_DIR/config/config.sh"
THREADS=""
READ_LENGTH=""
KEEP_INTERMEDIATE=0

while getopts ':1:2:U:s:o:c:t:l:kPDh' option; do
    case "$option" in
        1) R1="$OPTARG" ;;
        2) R2="$OPTARG" ;;
        U) SINGLE_READS="$OPTARG" ;;
        s) SAMPLE="$OPTARG" ;;
        o) OUTPUT_ROOT="$OPTARG" ;;
        c) CONFIG="$OPTARG" ;;
        t) THREADS="$OPTARG" ;;
        l) READ_LENGTH="$OPTARG" ;;
        k) KEEP_INTERMEDIATE=1 ;;
        P) SKIP_PREPROCESSING=1 ;;
        D) SKIP_DENOVO=1 ;;
        h) usage; exit 0 ;;
        :) die "Option -$OPTARG requires a value" ;;
        \?) die "Unknown option: -$OPTARG" ;;
    esac
done

shift "$((OPTIND - 1))"
[[ "$#" -eq 0 ]] || die "Unexpected positional argument: $1"
[[ -n "$SAMPLE" ]] || { usage >&2; exit 2; }
if [[ -n "$SINGLE_READS" ]]; then
    [[ -z "$R1" && -z "$R2" ]] || die "Use either -U for single-end or -1/-2 for paired-end"
    R1="$SINGLE_READS"
    READ_LAYOUT=single
else
    [[ -n "$R1" && -n "$R2" ]] || die "Paired-end requires both -1 and -2; use -U for single-end"
    READ_LAYOUT=paired
fi
require_file "$R1"
if [[ "$READ_LAYOUT" == paired ]]; then
    require_file "$R2"
fi
require_file "$CONFIG"
safe_sample_name "$SAMPLE"

R1="$(absolute_path "$R1")"
if [[ "$READ_LAYOUT" == paired ]]; then
    R2="$(absolute_path "$R2")"
fi
CONFIG="$(absolute_path "$CONFIG")"
mkdir -p "$OUTPUT_ROOT"
OUTPUT_ROOT="$(cd -- "$OUTPUT_ROOT" && pwd)"

CLI_SKIP_DENOVO="$SKIP_DENOVO"
CLI_SKIP_PREPROCESSING="$SKIP_PREPROCESSING"
# shellcheck source=/dev/null
source "$CONFIG"
SKIP_DENOVO="$CLI_SKIP_DENOVO"
SKIP_PREPROCESSING="$CLI_SKIP_PREPROCESSING"

FQ2FA="${FQ2FA:-$ROOT_DIR/bin/fq2fa}"
IDBA_UD="${IDBA_UD:-$ROOT_DIR/bin/idba_ud}"
BLASTX="${BLASTX:-blastx}"
BLASTDBCMD="${BLASTDBCMD:-blastdbcmd}"
RVDB_PROTEIN_DB="${RVDB_PROTEIN_DB:-$ROOT_DIR/db/rvdb/C063gt100-RVDBv12.2-prot.fasta}"
MIN_CONTIG_LENGTH="${MIN_CONTIG_LENGTH:-1000}"
LONG_CONTIG_LENGTH="${LONG_CONTIG_LENGTH:-40000}"
BLAST_EVALUE="${BLAST_EVALUE:-1}"
BLAST_MAX_TARGETS="${BLAST_MAX_TARGETS:-3}"
IDBA_MINK="${IDBA_MINK:-21}"
IDBA_MAXK="${IDBA_MAXK:-75}"
IDBA_STEP="${IDBA_STEP:-20}"

MODULES_TO_LOAD=()
if declare -p FEVIR_MODULES >/dev/null 2>&1; then
    MODULES_TO_LOAD+=("${FEVIR_MODULES[@]}")
fi
if [[ "$SKIP_DENOVO" -eq 0 ]]; then
    if declare -p FEVIR_DENOVO_MODULES >/dev/null 2>&1; then
        MODULES_TO_LOAD+=("${FEVIR_DENOVO_MODULES[@]}")
    fi
    if [[ "$READ_LAYOUT" == paired ]] && declare -p FEVIR_DENOVO_PAIRED_MODULES >/dev/null 2>&1; then
        MODULES_TO_LOAD+=("${FEVIR_DENOVO_PAIRED_MODULES[@]}")
    elif [[ "$READ_LAYOUT" == single ]] && declare -p FEVIR_DENOVO_SINGLE_MODULES >/dev/null 2>&1; then
        MODULES_TO_LOAD+=("${FEVIR_DENOVO_SINGLE_MODULES[@]}")
    fi
fi
if ((${#MODULES_TO_LOAD[@]})); then
    command -v module >/dev/null 2>&1 || die "Environment modules are configured, but 'module' is unavailable"
    for module_name in "${MODULES_TO_LOAD[@]}"; do
        module add "$module_name"
    done
fi

ADAPTERS_FASTA_SE="${ADAPTERS_FASTA_SE:-${ADAPTERS_FASTA:-}}"
SNAP_USE_HUGE_PAGES="${SNAP_USE_HUGE_PAGES:-0}"
if [[ "$SKIP_PREPROCESSING" -eq 0 ]]; then
    [[ "$SNAP_USE_HUGE_PAGES" =~ ^[01]$ ]] || die "SNAP_USE_HUGE_PAGES must be 0 or 1"
fi
THREADS="${THREADS:-$DEFAULT_THREADS}"
READ_LENGTH="${READ_LENGTH:-$DEFAULT_READ_LENGTH}"
[[ "$THREADS" =~ ^[1-9][0-9]*$ ]] || die "Threads must be a positive integer"
[[ "$READ_LENGTH" =~ ^[1-9][0-9]*$ ]] || die "Read length must be a positive integer"

if [[ "$SKIP_DENOVO" -eq 0 ]]; then
    for parameter in MIN_CONTIG_LENGTH LONG_CONTIG_LENGTH BLAST_MAX_TARGETS IDBA_MINK IDBA_MAXK IDBA_STEP; do
        [[ "${!parameter}" =~ ^[1-9][0-9]*$ ]] || die "$parameter must be a positive integer"
    done
    (( IDBA_MINK <= IDBA_MAXK && IDBA_MAXK <= 124 )) || die "Require IDBA_MINK <= IDBA_MAXK <= 124"
    (( LONG_CONTIG_LENGTH >= MIN_CONTIG_LENGTH )) || die "LONG_CONTIG_LENGTH must be >= MIN_CONTIG_LENGTH"
    "$PYTHON" -c 'import math, sys; x=float(sys.argv[1]); sys.exit(not (math.isfinite(x) and x>0))' \
        "$BLAST_EVALUE" || die "BLAST_EVALUE must be a finite positive number"
fi

export ROOT_DIR CONFIG SAMPLE R1 R2 OUTPUT_ROOT THREADS READ_LENGTH KEEP_INTERMEDIATE
export READ_LAYOUT SKIP_PREPROCESSING SKIP_DENOVO ADAPTERS_FASTA_SE SNAP_USE_HUGE_PAGES
export JAVA_BIN TRIMMOMATIC_JAR CD_HIT_DUP SNAP_ALIGNER SAMTOOLS MINIMAP2 BEDTOOLS
export PYTHON ADAPTERS_FASTA HUMAN_GENOME_DB
export HUMAN_TRANSCRIPTOME_DB HUMAN_EXTRA_DB VIROSAURUS_FASTA VIROSAURUS_METADATA
export ACCESSION_THRESHOLDS
export FQ2FA IDBA_UD BLASTX BLASTDBCMD RVDB_PROTEIN_DB
export MIN_CONTIG_LENGTH LONG_CONTIG_LENGTH BLAST_EVALUE BLAST_MAX_TARGETS
export IDBA_MINK IDBA_MAXK IDBA_STEP

SAMPLE_DIR="$OUTPUT_ROOT/$SAMPLE"
export SAMPLE_DIR
[[ ! -e "$SAMPLE_DIR" ]] || die "Output already exists: $SAMPLE_DIR"
mkdir -p "$SAMPLE_DIR"/{logs,results,work}

exec > >(tee -a "$SAMPLE_DIR/logs/fevir.log") 2>&1

log "Starting FEVIR analysis for $SAMPLE"
log "Read layout: $READ_LAYOUT"
log "Output: $SAMPLE_DIR"

exec "$PYTHON" "$ROOT_DIR/lib/measure_performance.py" -- bash "$ROOT_DIR/lib/run_analysis.sh"