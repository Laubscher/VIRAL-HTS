#!/usr/bin/env python3
"""Summarize repeated, comparable FEVIR runs into one TSV row per dataset/group."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys


def normalize(data):
    if data['schema_version'] == 2:
        identity = {key: data[key] for key in ('sample', 'inputs', 'analysis', 'environment')}
        environment = dict(data['environment'], fevir_version=data['analysis']['fevir_version'])
        return identity, data['analysis']['parameters'], environment, data['metrics']
    if data['schema_version'] == 1:
        old = data['metrics']
        memory = [old.get(key) for key in ('peak_process_tree_rss_bytes_sampled', 'largest_process_peak_rss_bytes')]
        memory = [value for value in memory if value is not None]
        env = data['environment']
        environment = {key: env.get(key) for key in ('os', 'kernel', 'architecture', 'cpu_model')}
        environment.update(fevir_version=data.get('fevir_version'),
                           container_image=env.get('container_image_declared'), gpu_used=False,
                           software_versions=data.get('software_versions'))
        return {'legacy_dataset': data['dataset_id'], 'legacy_group': data['comparison_group']}, data['parameters'], environment, {
            'wall_seconds': old.get('wall_seconds'), 'cpu_seconds': old.get('cpu_total_seconds'),
            'peak_rss_bytes': max(memory) if memory else None,
            'peak_working_bytes': old.get('output_peak_apparent_bytes_sampled')}
    raise ValueError('unsupported schema')


def summarize(paths):
    groups, seen = {}, set()
    for path in paths:
        files = [path] if path.is_file() else sorted([*path.rglob('run.json'), *path.rglob('performance.json')])
        for report in files:
            if report.name == 'performance.json' and (report.parent / 'run.json').exists():
                continue
            if report.resolve() in seen:
                continue
            seen.add(report.resolve())
            try:
                data = json.loads(report.read_text())
                identity, parameters, environment, metrics = normalize(data)
                successful = data['status'] == 'succeeded' and data.get('exit_code') == 0
                if successful:
                    for key in ('wall_seconds', 'cpu_seconds', 'peak_rss_bytes', 'peak_working_bytes'):
                        value = metrics.get(key)
                        if value is None and key not in ('wall_seconds', 'cpu_seconds'):
                            continue
                        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                            raise ValueError('invalid ' + key)
                group = json.dumps(identity, sort_keys=True)
                groups.setdefault(group, []).append((data['sample'], parameters, environment, metrics, successful))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                print('Skipped {}: {}'.format(report, exc), file=sys.stderr)
    rows = []
    for group, reports in sorted(groups.items()):
        sample, parameters, environment, _, _ = reports[0]
        measurements = [r[3] for r in reports if r[4]]
        times = [m['wall_seconds'] for m in measurements]
        ram = [m['peak_rss_bytes'] for m in measurements if m.get('peak_rss_bytes') is not None]
        disk = [m['peak_working_bytes'] for m in measurements if m.get('peak_working_bytes') is not None]
        total_time = sum(times)
        rows.append({
            'dataset': sample, 'group': hashlib.sha256(group.encode()).hexdigest()[:12],
            'successful_runs': len(times), 'failed_or_incomplete_runs': len(reports) - len(times),
            'runtime_mean_s': statistics.mean(times) if times else None,
            'runtime_min_s': min(times) if times else None, 'runtime_max_s': max(times) if times else None,
            'threads_requested': parameters.get('THREADS'),
            'cpu_mean_cores': sum(m['cpu_seconds'] for m in measurements) / total_time if total_time else None,
            'ram_peak_gib': max(ram) / 1024**3 if ram and len(ram) == len(times) else None,
            'gpu_used': environment.get('gpu_used'),
            'storage_peak_gib': max(disk) / 1024**3 if disk and len(disk) == len(times) else None,
            'computational_environment': json.dumps({key: value for key, value in environment.items() if key != 'gpu_used'}, sort_keys=True, ensure_ascii=False),
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+', type=Path, help='output directories, run.json or legacy performance.json')
    parser.add_argument('-o', '--output', type=Path, required=True, help='benchmark TSV')
    args = parser.parse_args()
    if any(not path.exists() for path in args.paths):
        parser.error('all input paths must exist')
    rows = summarize(args.paths)
    if not rows:
        parser.error('no readable run reports found')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter='\t')
        writer.writeheader()
        writer.writerows({key: 'NA' if value is None else value for key, value in row.items()} for row in rows)
    print('{} dataset/configuration group(s) written to {}'.format(len(rows), args.output))


if __name__ == '__main__':
    main()
