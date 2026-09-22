"""Reproduce descriptive annotation statistics, not annotation generation.

Requires PyYAML. Reads only files inside this package.
"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def write_csv(name, rows):
    path = ROOT / 'results/aggregate' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    rows = [json.loads(s) for s in (ROOT / 'data/labeling/benchmark_labels.jsonl').read_text().splitlines() if s.strip()]
    expected = {'swe_bench_verified_500': 500, 'swe_bench_pro': 731,
                'swe_bench_multilingual': 300}
    assert Counter(r['corpus_id'] for r in rows) == expected
    indexed = {(r['corpus_id'], r['instance_id']): r for r in rows}
    assert len(indexed) == len(rows)
    taxonomy = ROOT / 'data/taxonomy'
    definitions = {axis: yaml.safe_load((taxonomy / filename).read_text()) for axis, filename in
                   [('task_type', 'task_type_l2.yaml'), ('domain', 'domain_l2.yaml')]}
    audit = []
    def metric(name, count, denominator=None):
        audit.append({'metric': name, 'count': count,
                      'denominator': '' if denominator is None else denominator,
                      'percentage': '' if denominator is None else round(100 * count / denominator, 6)})
    illegal = 0
    for axis, definition in definitions.items():
        allowed = {l1: {v['name'] for v in (data.get('l2') or [])} for l1, data in definition.items()}
        metric(axis + '_l1_inventory', len(allowed))
        metric(axis + '_l2_inventory', sum(map(len, allowed.values())))
        metric(axis + '_l2_unspecified', sum('unspecified' in r['labels'][axis + '_l2'] for r in rows), len(rows))
        for row in rows:
            l1, l2 = row['labels'][axis + '_l1'], row['labels'][axis + '_l2']
            assert isinstance(l1, str) and isinstance(l2, list)
            assert not l1 or l1 in allowed, (row['instance_id'], axis, l1)
            illegal += sum(v not in allowed.get(l1, set()) for v in l2 if v and v != 'unspecified')
    repos = defaultdict(set)
    for row in rows:
        if row['labels']['domain_l1']:
            repos[row['repo']].add(row['labels']['domain_l1'])
    metric('tasks', len(rows))
    metric('empty_domain_l1', sum(not r['labels']['domain_l1'] for r in rows))
    metric('repository_consistent_nonempty_domain_l1', sum(len(v) == 1 for v in repos.values()), len(repos))
    metric('repository_multiple_nonempty_domain_l1', sum(len(v) > 1 for v in repos.values()))
    metric('illegal_concrete_l1_l2_assignments', illegal)
    assert illegal == 0
    orthogonal = yaml.safe_load((taxonomy / 'orthogonal.yaml').read_text())
    metric('orthogonal_dimensions', len(orthogonal))
    metric('orthogonal_levels', sum(len(v['levels']) for v in orthogonal.values()))
    profiles = []
    for corpus in expected:
        subset = [r for r in rows if r['corpus_id'] == corpus]
        for field in ('code_language', 'task_type_l1', 'domain_l1', 'scope'):
            counts = Counter(r['labels'][field] for r in subset if r['labels'][field])
            for label, count in sorted(counts.items()):
                profiles.append({'corpus_id': corpus, 'field': field, 'label': label,
                                 'count': count, 'total_tasks': len(subset),
                                 'nonempty_outputs': sum(counts.values()),
                                 'percentage_total': round(100 * count / len(subset), 6),
                                 'percentage_nonempty': round(100 * count / sum(counts.values()), 6)})
    route = json.loads((taxonomy / 'routing.json').read_text())
    lookup = {label: category for category, labels in route['routes'].items() for label in labels}
    corpora = {'pro618': 'swe_bench_pro', 'swebench_multilingual': 'swe_bench_multilingual'}
    with (ROOT / 'data/manifests/evaluation_tasks.csv').open() as handle:
        tasks = list(csv.DictReader(handle))
    # Explicit aliases are checked below; no identifier-only cross-corpus joins.
    for task in tasks:
        corpus = corpora[task['benchmark_id']]
        row = indexed[corpus, task['instance_id']]
        actual = lookup.get(row['labels']['domain_l1'], route['unassigned_category'])
        assert actual == task['category'], (task['instance_id'], actual, task['category'])
    metric('evaluation_task_category_matches', len(tasks), len(tasks))
    write_csv('labeling_structural_audit.csv', audit)
    write_csv('labeling_benchmark_profiles.csv', profiles)
    print(f'Validated {len(rows)} annotations; {len(tasks)} evaluation category joins; {illegal} illegal concrete assignments.')


if __name__ == '__main__':
    main()
