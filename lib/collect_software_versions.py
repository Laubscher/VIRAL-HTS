#!/usr/bin/env python3
"""Record observed software versions"""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def collect(root, logs):
    env = os.environ
    rows, probes = [], []
    def add(label, value):
        rows.append((label, value))
    def probe(label, executable, arguments=(), banner=False):
        executable = executable or ''
        path = shutil.which(executable)
        record = {'software': label, 'command': [executable, *arguments],
                  'resolved_executable': path, 'status': 'unavailable'}
        if path:
            try:
                process = subprocess.run([path, *arguments], stdin=subprocess.DEVNULL,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         universal_newlines=True, errors='replace', timeout=5)
                record.update(exit_code=process.returncode, output=process.stdout[:16000])
                lines = [s.strip() for s in process.stdout.splitlines() if s.strip()]
                # Conda loader warnings can precede the version; keep them in raw output.
                lines = [s for s in lines if 'no version information available' not in s.lower()]
                # Help banners may return nonzero, but only a version banner is usable.
                if banner:
                    lines = [s for s in lines if re.search(r'\bversion\s*[:=]?\s*\d', s, re.I)]
                elif process.returncode:
                    lines = []
                if lines:
                    record.update(status='observed', version=lines[0])
            except (OSError, subprocess.TimeoutExpired) as exc:
                record['error'] = type(exc).__name__
            try:
                # These are executables/JARs, not large reference databases.
                with open(path, 'rb') as handle:
                    checksum = hashlib.sha256()
                    for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                        checksum.update(chunk)
                record['executable_sha256'] = checksum.hexdigest()
            except OSError:
                pass
        probes.append(record)
        add(label, record.get('version', 'version unavailable (see software_versions.json)'))
    add('FEVIR', (root / 'VERSION').read_text().strip())
    add('Read layout', env.get('READ_LAYOUT', 'unknown'))
    probe('Python', env.get('PYTHON'), ['--version'])
    probe('Bash', 'bash', ['--version'])
    if env.get('SKIP_PREPROCESSING', '1') == '0':
        add('Preprocessing', 'enabled (--preprocess)')
        probe('Java', env.get('JAVA_BIN'), ['-version'])
        probe('Trimmomatic', env.get('JAVA_BIN'), ['-jar', env.get('TRIMMOMATIC_JAR', ''), '-version'])
        jar = env.get('TRIMMOMATIC_JAR', '')
        try:
            probes[-1]['jar_sha256'] = hashlib.sha256(Path(jar).read_bytes()).hexdigest()
        except OSError:
            pass
        probe('CD-HIT/cd-hit-dup', env.get('CD_HIT_DUP'), banner=True)
    else:
        add('Preprocessing', 'disabled')
    if env.get('SKIP_HOST_DEPLETION', '1') == '0':
        probe('SNAP', env.get('SNAP_ALIGNER'), banner=True)
        host_databases = Path(env['HOST_DB_LIST']).read_text().splitlines()
        for index, database in enumerate(host_databases, 1):
            add('SNAP host database {}'.format(index), database)
    else:
        add('Host depletion', 'disabled (no host database selected)')
    for label, key in [('SAMtools', 'SAMTOOLS'), ('Minimap2', 'MINIMAP2'), ('BEDTools', 'BEDTOOLS')]:
        probe(label, env.get(key), ['--version'])
    if env.get('SKIP_DENOVO', '0') == '0':
        probe('IDBA-UD', env.get('IDBA_UD'), ['--version'])
        probe('fq2fa', env.get('FQ2FA'), banner=True)
        probe('NCBI BLAST+', env.get('BLASTX'), ['-version'])
        probe('blastdbcmd', env.get('BLASTDBCMD'), ['-version'])
        add('RVDB-prot database path', env.get('RVDB_PROTEIN_DB', 'unknown'))
        family_map = env.get('RVDB_FAMILY_MAP', '')
        add('RVDB family map', family_map if family_map and Path(family_map).is_file()
            else 'unavailable; no de novo family assignments')
    else:
        add('De novo / BLASTx', 'skipped (-D)')
    add('Virosaurus FASTA path', env.get('VIROSAURUS_FASTA', 'unknown'))
    buffer = io.StringIO()
    csv.writer(buffer, delimiter='\t', lineterminator='\n').writerows(rows)
    summary = buffer.getvalue()
    (logs / 'software_versions.txt').write_text(summary)
    (logs / 'software_versions.json').write_text(json.dumps(probes, indent=2) + '\n')
    build = root / 'docker/software_versions.build.txt'
    if build.is_file():
        shutil.copyfile(str(build), str(logs / 'container_software_versions.txt'))
    return summary, probes
