#!/usr/bin/env bash

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >&2
}

require_file() {
    [[ -f "$1" ]] || die "File not found: $1"
}

require_path() {
    [[ -e "$1" ]] || die "Path not found: $1"
}

require_program() {
    local program="$1"
    if [[ "$program" == */* ]]; then
        [[ -x "$program" ]] || die "Executable not found: $program"
    else
        command -v "$program" >/dev/null 2>&1 || die "Program not found in PATH: $program"
    fi
}

absolute_path() {
    local path="$1"
    local directory
    directory="$(cd -- "$(dirname -- "$path")" && pwd)"
    printf '%s/%s\n' "$directory" "$(basename -- "$path")"
}

open_fastq() {
    case "$1" in
        *.gz) gzip -dc -- "$1" ;;
        *) cat -- "$1" ;;
    esac
}

safe_sample_name() {
    [[ "$1" =~ ^[A-Za-z0-9._-]+$ ]] || die "Invalid sample name: $1"
}

