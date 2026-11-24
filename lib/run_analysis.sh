#!/usr/bin/env bash
set -euo pipefail
source "$ROOT_DIR/lib/common.sh"

run_step() {
    local label="$1" script="$2" code
    log "$label"
    if bash "$ROOT_DIR/$script"; then
        return 0
    else
        code=$?
        log "Failed step: $label (exit $code)"
        return "$code"
    fi
}

run_step "Checking dependencies" lib/check_dependencies.sh
if [[ "$SKIP_PREPROCESSING" -eq 1 ]]; then
    run_step "Preparing input reads" lib/prepare_input_reads.sh
else
    run_step "Preprocessing reads" steps/01_preprocess.sh
    run_step "Host depletion" steps/02_host_depletion.sh
fi
run_step "Reference detection" steps/03_reference_detection.sh
if [[ "$SKIP_DENOVO" -eq 0 ]]; then
    run_step "De novo analysis" steps/04_denovo.sh
else
    log "De novo assembly and BLASTx skipped (-D)"
fi

"$PYTHON" "$ROOT_DIR/lib/measure_performance.py" --storage-checkpoint
if [[ "$KEEP_INTERMEDIATE" -eq 0 ]]; then
    log "Removing disposable intermediate files"
    find "$SAMPLE_DIR/work" -type f \( -name '*.sam' -o -name '*.bam' -o -name '*.unsorted.bam' \) -delete
fi
