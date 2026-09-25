#!/usr/bin/env python3

import argparse
import csv
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
from collect_software_versions import collect

SCHEMA = 1
RSS_INTERVAL = 0.5
DISK_INTERVAL = 5.0
PARAMETERS = (
    'THREADS READ_LENGTH READ_LAYOUT SKIP_PREPROCESSING SKIP_DENOVO '
    'KEEP_INTERMEDIATE SNAP_USE_HUGE_PAGES MIN_CONTIG_LENGTH LONG_CONTIG_LENGTH '
    'BLAST_EVALUE BLAST_MAX_TARGETS IDBA_MINK IDBA_MAXK IDBA_STEP'
).split()
TOOLS = ('JAVA_BIN TRIMMOMATIC_JAR CD_HIT_DUP SNAP_ALIGNER SAMTOOLS MINIMAP2 '
         'BEDTOOLS PYTHON FQ2FA IDBA_UD BLASTX BLASTDBCMD').split()


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read_text(path):
    try:
        return Path(path).read_text(errors='replace').strip()
    except OSError:
        return None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def file_identity(path, content=False):
    if not path:
        return None
    p = Path(path).resolve()
    result = {'path': str(p)}
    try:
        s = p.stat()
        result.update(size_bytes=s.st_size, mtime_ns=s.st_mtime_ns,
                      kind='directory' if p.is_dir() else 'file')
        if content and p.is_file():
            result['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError as exc:
        result['unavailable'] = type(exc).__name__
    return result


def footprint(root):
    """Count file bytes inside this directory, once per inode; do not follow links."""
    total = allocated = count = errors = 0
    seen = set()
    def on_error(_):
        nonlocal errors
        errors += 1
    for directory, _, files in os.walk(str(root), followlinks=False, onerror=on_error):
        for name in files:
            try:
                s = os.lstat(os.path.join(directory, name))
                if not stat.S_ISREG(s.st_mode) or (s.st_dev, s.st_ino) in seen:
                    continue
                seen.add((s.st_dev, s.st_ino))
                total += s.st_size
                allocated += getattr(s, 'st_blocks', 0) * 512
                count += 1
            except OSError:
                errors += 1
    return {'apparent_bytes': total, 'allocated_bytes': allocated,
            'regular_files': count, 'scan_errors': errors}


def reference_identity(path):
    """Snapshot configured files/directories or BLAST prefixes without reading data."""
    p = Path(path).resolve()
    identity = file_identity(path)
    files = []
    errors = []
    def on_error(exc):
        errors.append(type(exc).__name__)
    if p.is_dir():
        for directory, _, names in os.walk(str(p), followlinks=False, onerror=on_error):
            files.extend(Path(directory)/name for name in names)
    else:
        try:
            # Include FASTA plus adjacent index volumes, or an index-only prefix.
            files = [q for q in p.parent.iterdir()
                     if (q.name == p.name or q.name.startswith(p.name + '.')) and q.is_file()]
        except OSError as exc:
            errors.append(type(exc).__name__)
    entries = [file_identity(str(q)) for q in sorted(files)]
    identity.update(inventory_sha256=digest(entries), file_count=len(entries),
                    inventoried_apparent_bytes=sum(e.get('size_bytes', 0) for e in entries),
                    inventory_errors=errors + [e['unavailable'] for e in entries if 'unavailable' in e],
                    inventory_scope='configured directory or prefix only; external BLAST alias targets and symlinked directories not traversed')
    return identity


def session_rss(session_id):
    """Sum concurrent RSS in the command's session, excluding zombie processes."""
    if not Path('/proc/self/stat').exists():
        return None
    total = count = 0
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
            continue  # Process may have exited between enumeration and reading.
    return total if count and total else None


def cgroup_limits():
    """Accessible v2 ancestor limits; null is unknown/unlimited, never host RAM."""
    result = {'version': None, 'cpu_quota_cores': None, 'memory_limit_bytes': None}
    cg = read_text('/proc/self/cgroup') or ''
    mount = Path('/sys/fs/cgroup')
    if not (mount / 'cgroup.controllers').exists():
        return result
    result['version'] = 2
    relative = next((s[3:] for s in cg.splitlines() if s.startswith('0::')), '/')
    # A namespaced cgroup path can contain ../; never walk outside the mount.
    candidate = (mount / relative.lstrip('/')).resolve()
    if mount not in (candidate, *candidate.parents) or not candidate.exists():
        candidate = mount
    cpu_limits, memory_limits = [], []
    while True:
        cpu = (read_text(candidate / 'cpu.max') or '').split()
        memory = read_text(candidate / 'memory.max') or ''
        if len(cpu) == 2 and cpu[0].isdigit() and cpu[1].isdigit() and int(cpu[1]):
            cpu_limits.append(int(cpu[0]) / int(cpu[1]))
        if memory.isdigit():
            memory_limits.append(int(memory))
        if candidate == mount:
            break
        candidate = candidate.parent
    result.update(cpu_quota_cores=min(cpu_limits) if cpu_limits else None,
                  memory_limit_bytes=min(memory_limits) if memory_limits else None)
    result['scope'] = 'accessible ancestors only; hidden host limits are unknown'
    return result


def environment():
    cpu = read_text('/proc/cpuinfo') or ''
    model = next((s.split(':', 1)[1].strip() for s in cpu.splitlines()
                  if s.startswith('model name')), platform.processor())
    mem = read_text('/proc/meminfo') or ''
    total = next((int(s.split()[1]) * 1024 for s in mem.splitlines()
                  if s.startswith('MemTotal:')), None)
    try:
        affinity = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        affinity = None
    gpu = {'acceleration_requested_by_pipeline': False,
           'utilization_measured': False, 'inventory_status': 'unavailable',
           'nvidia_devices': []}
    nvidia = shutil.which('nvidia-smi')
    if nvidia:
        try:
            proc = subprocess.run([nvidia, '--query-gpu=name,driver_version,memory.total',
                                   '--format=csv,noheader,nounits'],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  universal_newlines=True, timeout=3)
            if proc.returncode == 0:
                gpu['inventory_status'] = 'available'
                gpu['nvidia_devices'] = [row for row in csv.reader(proc.stdout.splitlines())]
        except (OSError, subprocess.TimeoutExpired):
            pass
    return {'os': platform.system(), 'os_release': read_text('/etc/os-release'),
            'kernel': platform.release(), 'architecture': platform.machine(),
            'hostname': platform.node(), 'cpu_model': model,
            'logical_cpus_visible': os.cpu_count(), 'cpu_affinity_count': affinity,
            'host_or_proc_memtotal_bytes': total, 'cgroup': cgroup_limits(),
            'python_version': platform.python_version(), 'gpu': gpu,
            'container_image_declared': os.environ.get('FEVIR_CONTAINER_IMAGE'),
            'apptainer_image': os.environ.get('APPTAINER_CONTAINER'),
            'conda_prefix': os.environ.get('CONDA_PREFIX')}


def json_write(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def initial_report():
    env = os.environ
    root = Path(env['ROOT_DIR'])
    inputs = [file_identity(env[key]) for key in ('R1', 'R2') if env.get(key)]
    code = {}
    paths = [root / 'fevir.sh', root / 'VERSION']
    paths += sorted((root / 'lib').glob('*.py')) + sorted((root / 'lib').glob('*.sh'))
    paths += sorted((root / 'steps').glob('*.sh'))
    for p in paths:
        if p.is_file():
            code[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    tools = {k: file_identity(shutil.which(env.get(k, '')) or env.get(k)) for k in TOOLS}
    active_references = ['VIROSAURUS_FASTA', 'VIROSAURUS_METADATA', 'ACCESSION_THRESHOLDS']
    if env.get('SKIP_PREPROCESSING', '0') == '0':
        active_references += ['ADAPTERS_FASTA', 'ADAPTERS_FASTA_SE', 'HUMAN_GENOME_DB',
                              'HUMAN_TRANSCRIPTOME_DB', 'HUMAN_EXTRA_DB']
    if env.get('SKIP_DENOVO', '0') == '0':
        active_references += ['RVDB_PROTEIN_DB']
    references = {k: reference_identity(env[k]) for k in active_references if env.get(k)}
    parameters = {k: env.get(k) for k in PARAMETERS}
    configuration = file_identity(env.get('CONFIG'), content=True)
    computational_environment = environment()
    identity = {'inputs': inputs, 'parameters': parameters, 'code': code,
                'config': configuration, 'tools': tools, 'references': references,
                'environment': computational_environment}
    return {'schema_version': SCHEMA, 'sample': env['SAMPLE'], 'status': 'running',
            'dataset_label': ' + '.join(Path(i['path']).name for i in inputs),
            'dataset_id': digest(inputs), 'comparison_group': digest(identity),
            'fevir_version': read_text(root / 'VERSION'), 'inputs': inputs,
            'parameters': parameters, 'configuration': configuration,
            'code_sha256': digest(code), 'tools': tools, 'references': references,
            'environment': computational_environment, 'metrics': {},
            'measurement': {
                'scope': 'dependency checks through analysis, manifests and intermediate cleanup',
                'excluded': 'CLI validation, module setup, inventories, supervisor CPU/RAM, log tee, final performance report, database installation, image build, scheduler queue',
                'cpu': 'wait4 user+system seconds, command and waited descendants',
                'largest_process_peak_rss': 'rusage high-water RSS of the largest child, not simultaneous tree peak',
                'tree_rss': 'sampled sum of RSS in command session; shared pages counted repeatedly; brief peaks and detached sessions may be missed',
                'rss_interval_seconds': RSS_INTERVAL,
                'storage_interval_seconds': DISK_INTERVAL,
                'storage': 'regular files under sample directory, no symlink targets, hard links once; no external scratch, shared databases or container image',
                'storage_peak': 'sampled; brief peaks between scans can be missed',
                'identity': 'inputs/tools/references use path, size and mtime, not full content hashes; config and code are hashed',
                'gpu': 'CPU workflow; no GPU utilization measurement; unavailable inventory does not mean absent hardware',
                'units': 'seconds, bytes, CPU percent with one fully occupied core = 100'}}


def supervise(command):
    sample_dir = Path(os.environ['SAMPLE_DIR'])
    logs = sample_dir / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    report = initial_report()
    versions, probes = collect(Path(os.environ['ROOT_DIR']), logs)
    report['software_versions'] = versions
    report['comparison_group'] = digest([report['comparison_group'], versions,
                                        [p.get('executable_sha256') for p in probes],
                                        [p.get('jar_sha256') for p in probes]])
    report_path = logs / 'performance.json'
    json_write(report_path, report)
    json_write(logs / 'computational_environment.json', report['environment'])
    before = footprint(sample_dir)
    peak_disk = before['apparent_bytes']
    disk_errors = before['scan_errors']
    peak_rss = None
    rss_samples = 0
    received = []
    result = {}
    done = threading.Event()
    report['started_at_utc'] = utc_now()
    json_write(report_path, report)
    started = time.monotonic()
    try:
        child = subprocess.Popen(command, start_new_session=True)
    except OSError as exc:
        report.update(status='failed', exit_code=127, error=str(exc), ended_at_utc=utc_now())
        json_write(report_path, report)
        print('[performance] Could not start analysis: {}'.format(exc), file=sys.stderr)
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
        result.update(status=status, usage=usage, elapsed=time.monotonic() - started,
                      ended_at_utc=utc_now())
        child.returncode = -os.WTERMSIG(status) if os.WIFSIGNALED(status) else os.WEXITSTATUS(status)
        done.set()

    waiter = threading.Thread(target=reap, daemon=True)
    waiter.start()
    next_disk = time.monotonic() + DISK_INTERVAL
    while not done.is_set():
        rss = session_rss(child.pid)
        if rss is not None:
            peak_rss = max(peak_rss or 0, rss)
            rss_samples += 1
        if time.monotonic() >= next_disk:
            disk = footprint(sample_dir)
            peak_disk = max(peak_disk, disk['apparent_bytes'])
            disk_errors += disk['scan_errors']
            next_disk = time.monotonic() + DISK_INTERVAL
        done.wait(RSS_INTERVAL)
    waiter.join()
    for s, handler in handlers.items():
        signal.signal(s, handler)
    usage = result['usage']
    elapsed = result['elapsed']
    cpu_seconds = usage.ru_utime + usage.ru_stime
    exit_code = child.returncode if child.returncode >= 0 else 128 - child.returncode
    # A caught cancellation must not be counted as a successful benchmark run.
    if received and exit_code == 0:
        exit_code = 128 + received[-1]
    final_disk = footprint(sample_dir)
    checkpoint_path = logs / 'storage_before_cleanup.json'
    checkpoint = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else None
    peak_disk = max(peak_disk, final_disk['apparent_bytes'],
                    checkpoint['apparent_bytes'] if checkpoint else 0)
    metrics = {
        'wall_seconds': elapsed, 'cpu_user_seconds': usage.ru_utime,
        'cpu_system_seconds': usage.ru_stime, 'cpu_total_seconds': cpu_seconds,
        'cpu_average_cores': cpu_seconds / elapsed if elapsed else None,
        'cpu_average_percent': 100 * cpu_seconds / elapsed if elapsed else None,
        'threads_requested': int(os.environ['THREADS']),
        'largest_process_peak_rss_bytes': usage.ru_maxrss * (1 if sys.platform == 'darwin' else 1024),
        'peak_process_tree_rss_bytes_sampled': peak_rss, 'rss_samples': rss_samples,
        'input_stored_bytes': sum(i.get('size_bytes', 0) for i in report['inputs']),
        'output_final_apparent_bytes': final_disk['apparent_bytes'],
        'output_final_allocated_bytes': final_disk['allocated_bytes'],
        'output_peak_apparent_bytes_sampled': peak_disk,
        'output_before_cleanup_apparent_bytes': checkpoint['apparent_bytes'] if checkpoint else None,
        'storage_scan_errors': disk_errors + final_disk['scan_errors'] + (checkpoint['scan_errors'] if checkpoint else 0)}
    report.update(status='interrupted' if received or child.returncode < 0 else ('succeeded' if exit_code == 0 else 'failed'),
                  exit_code=exit_code, signals_received=received,
                  ended_at_utc=result['ended_at_utc'], metrics=metrics)
    report['protein_database_info'] = read_text(logs / 'rvdb.info.txt')
    json_write(report_path, report)
    with (logs / 'performance.tsv').open('w', newline='') as handle:
        writer = csv.writer(handle, delimiter='\t')
        writer.writerow(['metric', 'value'])
        for key, value in [('status', report['status']), ('exit_code', exit_code), *metrics.items()]:
            writer.writerow([key, 'NA' if value is None else value])
    def gib(value):
        return 'NA' if value is None else '{:.4f} GiB'.format(value / 1024**3)
    env = report['environment']
    human = [
        'FEVIR performance — {}'.format(report['sample']),
        'Status: {} (exit {})'.format(report['status'], exit_code),
        'Runtime per dataset: {:.3f} seconds ({:.3f} minutes), one run'.format(elapsed, elapsed/60),
        'Runtime mean and range: use summarize_performance.py for comparable repeated runs',
        'CPU: {} requested threads; {:.3f} CPU seconds; {:.2f} average cores ({:.1f}%)'.format(
            metrics['threads_requested'], cpu_seconds, metrics['cpu_average_cores'], metrics['cpu_average_percent']),
        'RAM: sampled simultaneous RSS {}; largest process peak {}'.format(
            gib(peak_rss), gib(metrics['largest_process_peak_rss_bytes'])),
        'GPU: acceleration not requested by this CPU workflow; utilization not measured',
        'Storage: inputs {}; final sample directory {}; sampled peak {}'.format(
            gib(metrics['input_stored_bytes']), gib(final_disk['apparent_bytes']), gib(peak_disk)),
        'Shared reference storage: per-reference inventories in performance.json; do not sum overlapping paths',
        'Computational environment: {}; {}; {}; CPU {}'.format(env['os'], env['kernel'], env['architecture'], env['cpu_model']),
        'Software versions: software_versions.txt (details and executable fingerprints: software_versions.json)',
        'Protein database internal metadata: rvdb.info.txt when the database check succeeded',
        'Limits: sampled peaks are estimates; RSS may count shared pages more than once.',
        'Storage excludes external scratch and container image; final size is before the final performance report.',
        'Full measurement scope and environment: performance.json',
    ]
    (logs / 'performance.txt').write_text('\n'.join(human) + '\n')
    print('[performance] status={} | runtime={:.3f} s | CPU={:.3f} s ({:.1f} cores average)'.format(
        report['status'], elapsed, cpu_seconds, metrics['cpu_average_cores']), flush=True)
    print('[performance] RAM: largest process={} bytes; sampled simultaneous RSS={} bytes'.format(
        metrics['largest_process_peak_rss_bytes'], peak_rss if peak_rss is not None else 'NA'), flush=True)
    print('[performance] Storage: final={} bytes; sampled peak={} bytes (sample directory only)'.format(
        final_disk['apparent_bytes'], peak_disk), flush=True)
    print('[performance] GPU acceleration requested: no; utilization: not measured', flush=True)
    print('[performance] Full metrics and environment: {}'.format(report_path), flush=True)
    print('[software versions]\n' + versions, flush=True)
    return exit_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage-checkpoint', action='store_true')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.storage_checkpoint:
        sample_dir = Path(os.environ['SAMPLE_DIR'])
        json_write(sample_dir / 'logs/storage_before_cleanup.json', footprint(sample_dir))
        return 0
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('analysis command required after --')
    return supervise(command)


if __name__ == '__main__':
    sys.exit(main())
