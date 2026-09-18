#!/usr/bin/env bash

FEVIR_DIR="${ROOT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"

# Software
JAVA_BIN="java"
TRIMMOMATIC_JAR="$FEVIR_DIR/bin/trimmomatic-0.36.jar"
CD_HIT_DUP="$FEVIR_DIR/bin/cd-hit-dup"
SNAP_ALIGNER="$FEVIR_DIR/bin/snap-aligner"
SAMTOOLS="samtools"
MINIMAP2="$FEVIR_DIR/bin/minimap2"
BEDTOOLS="bedtools"
PYTHON="python3"

FEVIR_MODULES=()
SNAP_USE_HUGE_PAGES=0

# Reference databases
ADAPTERS_FASTA="$FEVIR_DIR/db/fasta/TruSeqNexteraAdaptersAll.fa"
# Optional single-end adapter file. Empty uses ADAPTERS_FASTA.
ADAPTERS_FASTA_SE=""
#HUMAN_GENOME_DB="$FEVIR_DIR/db/GRCh38_p14_genome" 
HUMAN_GENOME_DB="$FEVIR_DIR/db/gencode_v43_transcripts" # for local test
HUMAN_TRANSCRIPTOME_DB="$FEVIR_DIR/db/gencode_v43_transcripts"
HUMAN_EXTRA_DB="$FEVIR_DIR/db/moreHuman"
VIROSAURUS_FASTA="$FEVIR_DIR/db/virosaurus2023/Virosaurus2023.fasta"
VIROSAURUS_METADATA="$FEVIR_DIR/db/virosaurus2023/ref.txt"

# Optional accession-specific minimum covered-nucleotide thresholds.
# Format: accession<TAB>minimum_covered_nt
# Leave empty to disable.
ACCESSION_THRESHOLDS=""

# Defaults 75-bp workflow.
DEFAULT_THREADS=20
DEFAULT_READ_LENGTH=75
