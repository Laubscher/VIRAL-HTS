#!/usr/bin/env python3
"""Summarize repeated, comparable FEVIR runs into one TSV row per dataset/group."""
import argparse
import csv
import json
from pathlib import Path
import statistics
import sys


def summarize(paths):
    groups = {}
    seen = set()
    for path in paths:
        files = [path] if path.is_file() else sorted(path.rglob('performance.json'))
        for p in files:
            if p.resolve() in seen:
                continue
            seen.add(p.resolve())
            try:
                data = json.loads(p.read_text())
                if data['schema_version'] != 1:
                    raise ValueError('unsupported schema')
                key = (data['dataset_id'], data['comparison_group'])
                if data['status'] == 'succeeded' and 'wall_seconds' not in data['metrics']:
                    raise ValueError('successful run without runtime')
                groups.setdefault(key, []).append(data)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                print('Skipped {}: {}'.format(p, exc), file=sys.stderr)
    rows = []
    for (dataset_id, group), reports in sorted(groups.items()):
        first = reports[0]
        successful = [r for r in reports if r['status'] == 'succeeded' and r.get('exit_code') == 0]
        env = first['environment']
        row = {'dataset': first['dataset_label'], 'dataset_id': dataset_id, 'comparison_group': group,
               'samples': ','.join(r['sample'] for r in reports), 'n_runs': len(reports),
               'n_successful': len(successful), 'n_failed_or_incomplete': len(reports) - len(successful),
               'threads_requested': first['parameters'].get('THREADS'),
               'skip_preprocessing': first['parameters'].get('SKIP_PREPROCESSING'),
               'skip_host_depletion': first['parameters'].get('SKIP_HOST_DEPLETION'),
               'host_database_count': first['parameters'].get('HOST_DB_COUNT'),
               'skip_denovo': first['parameters'].get('SKIP_DENOVO'),
               'cpu_model': env.get('cpu_model'), 'hostname': env.get('hostname'),
               'os': env.get('os'), 'kernel': env.get('kernel'),
               'gpu_acceleration_requested': False, 'gpu_utilization': 'not measured',
               'container_image_declared': env.get('container_image_declared'),
               'software_versions': (first.get('software_versions') or '').replace('\n', ' | ').replace('\t', ': ')}
        for metric in ('wall_seconds', 'cpu_total_seconds', 'cpu_average_cores',
                       'peak_process_tree_rss_bytes_sampled', 'largest_process_peak_rss_bytes',
                       'input_stored_bytes', 'output_final_apparent_bytes',
                       'output_peak_apparent_bytes_sampled'):
            values = [r['metrics'].get(metric) for r in successful]
            values = [v for v in values if isinstance(v, (int, float))]
            row[metric + '_n'] = len(values)
            for label, function in [('mean', statistics.mean), ('min', min), ('max', max)]:
                row[metric + '_' + label] = function(values) if values else None
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+', type=Path, help='output directories or performance.json files')
    parser.add_argument('-o', '--output', type=Path, required=True, help='summary TSV path')
    args = parser.parse_args()
    if any(not p.exists() for p in args.paths):
        parser.error('all input paths must exist')
    rows = summarize(args.paths)
    if not rows:
        parser.error('no readable performance reports found')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter='\t')
        writer.writeheader()
        writer.writerows({k: 'NA' if v is None else v for k, v in row.items()} for row in rows)
    print('{} comparison group(s) written to {}'.format(len(rows), args.output))


if __name__ == '__main__':
    main()
