#!/usr/bin/env bash
.
set -euo pipefail
source "$ROOT_DIR/lib/common.sh"

bash "$ROOT_DIR/lib/check_dependencies.sh"
if [[ "$SKIP_PREPROCESSING" -eq 1 ]]; then
    bash "$ROOT_DIR/lib/prepare_input_reads.sh"
else
    bash "$ROOT_DIR/steps/01_preprocess.sh"
    bash "$ROOT_DIR/steps/02_host_depletion.sh"
fi
bash "$ROOT_DIR/steps/03_reference_detection.sh"
if [[ "$SKIP_DENOVO" -eq 0 ]]; then
    bash "$ROOT_DIR/steps/04_denovo.sh"
else
    log "De novo assembly and BLASTx skipped (-D)"
bash "$ROOT_DIR/lib/write_manifest.sh"

"$PYTHON" "$ROOT_DIR/lib/measure_performance.py" --storage-checkpoint

if [[ "$KEEP_INTERMEDIATE" -eq 0 ]]; then
    log "Removing disposable intermediate files"
    find "$SAMPLE_DIR/work" -type f \( -name '*.sam' -o -name '*.bam' -o -name '*.unsorted.bam' \) -delete
fi

log "FEVIR analysis completed"
log "Results: $SAMPLE_DIR/results"
