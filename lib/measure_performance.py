#!/usr/bin/env python3

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time

SCHEMA = 2
RSS_INTERVAL = 5.0
DISK_INTERVAL = 60.0
CHECKPOINT = '.fevir_storage_peak.json'


def read_text(path):
    try:
        return Path(path).read_text(errors='replace').strip()
    except OSError:
        return None


def json_write(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def file_identity(path, input_file=False):
    p = Path(path)
    result = {'name' if input_file else 'path': p.name if input_file else str(p.resolve())}
    try:
        info = p.stat()
        result['mtime_ns'] = info.st_mtime_ns
        if p.is_file():
            result['size_bytes'] = info.st_size
    except OSError:
        result['unavailable'] = True
    return result


def software_versions():
    env = os.environ
    specs = [('Python', env.get('PYTHON'), ['--version']), ('Bash', 'bash', ['--version']),
             ('SAMtools', env.get('SAMTOOLS'), ['--version']),
             ('Minimap2', env.get('MINIMAP2'), ['--version']),
             ('BEDTools', env.get('BEDTOOLS'), ['--version'])]
    if env.get('SKIP_PREPROCESSING') == '0':
        specs += [('Java', env.get('JAVA_BIN'), ['-version']),
                  ('Trimmomatic', env.get('JAVA_BIN'), ['-jar', env.get('TRIMMOMATIC_JAR', ''), '-version']),
                  ('cd-hit-dup', env.get('CD_HIT_DUP'), [])]
    if env.get('SKIP_HOST_DEPLETION') == '0':
        specs.append(('SNAP', env.get('SNAP_ALIGNER'), []))
    if env.get('SKIP_DENOVO', '0') == '0':
        specs += [('IDBA-UD', env.get('IDBA_UD'), ['--version']),
                  ('fq2fa', env.get('FQ2FA'), []),
                  ('BLASTx', env.get('BLASTX'), ['-version']),
                  ('blastdbcmd', env.get('BLASTDBCMD'), ['-version'])]
    versions = {}
    for label, program, arguments in specs:
        versions[label] = None
        executable = shutil.which(program or '')
        if not executable:
            continue
        try:
            result = subprocess.run([executable, *arguments], stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    universal_newlines=True, errors='replace', timeout=5)
            lines = [line.strip() for line in result.stdout.splitlines()
                     if line.strip() and 'no version information available' not in line.lower()]
            if not arguments or result.returncode:
                lines = [line for line in lines if re.search(r'\bversion\s*[:=]?\s*\d', line, re.I)]
            elif label in ('IDBA-UD', 'fq2fa'):
                lines = [line for line in lines if re.search(r'\bversion\s*[:=]?\s*\d', line, re.I)]
            if lines:
                versions[label] = lines[0]
        except (OSError, subprocess.TimeoutExpired):
            pass
    return versions


def environment():
    cpuinfo = read_text('/proc/cpuinfo') or ''
    cpu = next((line.split(':', 1)[1].strip() for line in cpuinfo.splitlines()
                if line.startswith('model name')), platform.processor())
    release = read_text('/etc/os-release') or ''
    system = next((line.split('=', 1)[1].strip('"') for line in release.splitlines()
                   if line.startswith('PRETTY_NAME=')), platform.system())
    return {'os': system, 'kernel': platform.release(), 'architecture': platform.machine(),
            'cpu_model': cpu, 'container_image': os.environ.get('APPTAINER_CONTAINER')
            or os.environ.get('SINGULARITY_CONTAINER') or os.environ.get('FEVIR_CONTAINER_IMAGE'),
            'gpu_used': False, 'software_versions': software_versions()}


def initial_report():
    env = os.environ
    root = Path(env['ROOT_DIR'])
    names = 'THREADS READ_LENGTH READ_LAYOUT SKIP_PREPROCESSING SKIP_DENOVO KEEP_INTERMEDIATE'.split()
    references = ['VIROSAURUS_FASTA', 'VIROSAURUS_METADATA', 'ACCESSION_THRESHOLDS']
    if env.get('SKIP_PREPROCESSING') == '0':
        references.append('ADAPTERS_FASTA_SE' if env.get('READ_LAYOUT') == 'single' else 'ADAPTERS_FASTA')
    if env.get('SKIP_HOST_DEPLETION') == '0':
        names.append('SNAP_USE_HUGE_PAGES')
    if env.get('SKIP_DENOVO', '0') == '0':
        names += 'MIN_CONTIG_LENGTH LONG_CONTIG_LENGTH BLAST_EVALUE BLAST_MAX_TARGETS DENOVO_FAMILY_EVALUE IDBA_MINK IDBA_MAXK IDBA_STEP'.split()
        references += ['RVDB_PROTEIN_DB', 'RVDB_FAMILY_MAP']
    databases = {key: file_identity(env[key]) for key in references if env.get(key)}
    hosts = read_text(env.get('HOST_DB_LIST', '')) or ''
    for index, path in enumerate(hosts.splitlines(), 1):
        databases['HOST_DB_{}'.format(index)] = file_identity(path)
    checksum = hashlib.sha256()
    paths = [root / 'VERSION', root / 'fevir.sh']
    for directory in ('lib', 'steps'):
        paths += sorted((root / directory).glob('*.py')) + sorted((root / directory).glob('*.sh'))
    for path in paths:
        if path.is_file():
            checksum.update(str(path.relative_to(root)).encode() + b'\0' + path.read_bytes())
    return {'schema_version': SCHEMA, 'sample': env['SAMPLE'], 'status': 'running',
            'inputs': [file_identity(env[k], input_file=True) for k in ('R1', 'R2') if env.get(k)],
            'analysis': {'fevir_version': read_text(root / 'VERSION'), 'code_sha256': checksum.hexdigest(),
                         'parameters': {k: env[k] for k in names if k in env}, 'references': databases},
            'environment': environment(), 'metrics': {}}


def footprint(root):
    """Count logical bytes in results/ and work/, counting hard links once."""
    total, seen, errors = 0, set(), []
    for subdirectory in ('results', 'work'):
        for directory, _, files in os.walk(str(root / subdirectory), followlinks=False, onerror=errors.append):
            for name in files:
                if name in (CHECKPOINT, CHECKPOINT + '.tmp'):
                    continue
                try:
                    info = os.lstat(os.path.join(directory, name))
                    if stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) not in seen:
                        total += info.st_size
                        seen.add((info.st_dev, info.st_ino))
                except FileNotFoundError:
                    pass  # The file may disappear during cleanup.
                except OSError as exc:
                    errors.append(exc)
    return None if errors else total


def session_rss(session_id):
    total, count = 0, 0
    try:
        entries = list(Path('/proc').iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            if int(fields[3]) == session_id and fields[0] != 'Z':
                total += max(0, int(fields[21])) * os.sysconf('SC_PAGE_SIZE')
                count += 1
        except (OSError, ValueError, IndexError):
            pass
    return total if count else None


def supervise(command):
    sample_dir = Path(os.environ['SAMPLE_DIR'])
    logs = sample_dir / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    report_path = logs / 'run.json'
    report = initial_report()
    report['started_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    json_write(report_path, report)
    peak_disk = footprint(sample_dir)
    peak_rss = 0
    received, result = [], {}
    done = threading.Event()
    started = time.monotonic()
    try:
        child = subprocess.Popen(command, start_new_session=True)
    except OSError as exc:
        report.update(status='failed', exit_code=127)
        json_write(report_path, report)
        print('[FEVIR] Cannot start analysis: {}'.format(exc), file=sys.stderr, flush=True)
        return 127

    def forward(signum, _frame):
        received.append(signum)
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass

    handlers = {s: signal.signal(s, forward) for s in (signal.SIGTERM, signal.SIGINT)}

    def reap():
        _, status, usage = os.wait4(child.pid, 0)
        child.returncode = -os.WTERMSIG(status) if os.WIFSIGNALED(status) else os.WEXITSTATUS(status)
        result.update(usage=usage, elapsed=time.monotonic() - started)
        done.set()

    waiter = threading.Thread(target=reap, daemon=True)
    waiter.start()
    next_disk = time.monotonic() + DISK_INTERVAL
    while not done.is_set():
        peak_rss = max(peak_rss, session_rss(child.pid) or 0)
        if time.monotonic() >= next_disk:
            size = footprint(sample_dir)
            peak_disk = max(peak_disk, size) if peak_disk is not None and size is not None else None
            next_disk = time.monotonic() + DISK_INTERVAL
        done.wait(RSS_INTERVAL)
    waiter.join()
    usage = result['usage']
    peak_rss = max(peak_rss, usage.ru_maxrss * (1 if sys.platform == 'darwin' else 1024))
    exit_code = child.returncode if child.returncode >= 0 else 128 - child.returncode
    if received and exit_code == 0:
        exit_code = 128 + received[-1]
    checkpoint = sample_dir / 'work' / CHECKPOINT
    sizes = [peak_disk, footprint(sample_dir)]
    if checkpoint.exists():
        try:
            sizes.append(json.loads(checkpoint.read_text()))
        except (OSError, ValueError):
            sizes.append(None)
        checkpoint.unlink()
    peak_disk = max(sizes) if all(size is not None for size in sizes) else None
    if peak_disk is None:
        print('[FEVIR] Warning: storage measurement incomplete; recorded as null', flush=True)
    report.update(status='interrupted' if received or child.returncode < 0 else ('succeeded' if exit_code == 0 else 'failed'),
                  exit_code=exit_code, metrics={'wall_seconds': result['elapsed'],
                  'cpu_seconds': usage.ru_utime + usage.ru_stime,
                  'peak_rss_bytes': peak_rss or None, 'peak_working_bytes': peak_disk})
    json_write(report_path, report)
    print('[FEVIR] {} (exit {}). Results: {}; benchmark: {}'.format(
        report['status'], exit_code, sample_dir / 'results', report_path), flush=True)
    for sig, handler in handlers.items():
        signal.signal(sig, handler)
    return exit_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage-checkpoint', action='store_true')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.storage_checkpoint:
        sample_dir = Path(os.environ['SAMPLE_DIR'])
        json_write(sample_dir / 'work' / CHECKPOINT, footprint(sample_dir))
        return 0
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('analysis command required after --')
    return supervise(command)


if __name__ == '__main__':
    sys.exit(main())
