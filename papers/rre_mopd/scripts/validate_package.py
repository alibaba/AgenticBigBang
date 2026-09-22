"""Read-only cross-file checks. Run from any working directory (stdlib only).

Complements the Initial/pooled validators and the numerical reproduction scripts.
Passing validates the released records, not a historical training execution.
"""
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    with (ROOT / name).open(newline='') as f:
        return list(csv.DictReader(f))


def manifest(name):
    return read('data/manifests/' + name + '.csv')


def unique(rows, key):
    out = {r[key]: r for r in rows}
    assert len(out) == len(rows), ('duplicate key', key)
    return out


def main():
    initial = unique(manifest('initial_rl_training_records'), 'anon_record_id')
    task_category = {r['anon_instance_id']: r['category'] for r in initial.values()}
    assert all(task_category[r['anon_instance_id']] == r['category'] for r in initial.values())
    pooled = unique(manifest('pooled_training_records'), 'anon_record_id')
    for r in manifest('balanced_rl_training_records'):
        s = initial[r['anon_record_id']]
        assert (r['anon_instance_id'], r['routing_group']) == (s['anon_instance_id'], s['category'])
    for rid, r in initial.items():
        assert (pooled[rid]['anon_instance_id'], pooled[rid]['routing_group']) == (r['anon_instance_id'], r['category'])

    repair = unique(manifest('rre_repair_sampling_manifest'), 'anon_instance_id')
    assert set(repair) == set(task_category)
    for c, n, slots in [('A', 571, 1623), ('B', 501, 1481), ('C', 1498, 4384)]:
        rs = [r for r in repair.values() if r['category'] == c]
        assert sum(int(r['sampled_trajectory_count']) > 0 for r in rs) == n
        assert sum(int(r['sampled_trajectory_count']) for r in rs) == slots
    for iid, r in repair.items():
        assert r['category'] == task_category[iid]
        assert (r['selected_for_sft'] == 'true') == (int(r['sampled_trajectory_count']) > 0)

    expanded = unique(manifest('rre_expansion_manifest'), 'expanded_rl_record_id')
    repair2 = unique(manifest('rre_repair_round2_sampling_manifest'), 'expanded_rl_record_id')
    assert set(expanded) == set(repair2) and len(expanded) == 2503
    assert len({r['anon_instance_id'] for r in expanded.values()}) == 2497
    assert Counter(r['category'] for r in expanded.values()) == {'A': 566, 'B': 502, 'C': 1435}
    all_categories = dict(task_category)
    for rid, r in expanded.items():
        iid, c = r['anon_instance_id'], r['category']
        assert all_categories.setdefault(iid, c) == c
        s = repair2[rid]
        assert (s['anon_instance_id'], s['category']) == (iid, c)
        n, v, wins, failed = (int(r[k]) for k in ['n_observed', 'n_valid', 'n_pass', 'infra_failure_rows'])
        assert 0 <= wins <= v <= n and n - v == failed
        for field, denom in [('current_raw_passrate', n), ('current_valid_passrate', v)]:
            if denom:
                assert abs(float(r[field]) - wins / denom) < 1e-8
        assert r['selected_for_expanded_rl'] == 'true'
    for c, n, slots in [('A', 549, 1392), ('B', 487, 1245), ('C', 1371, 3840)]:
        rs = [r for r in repair2.values() if r['category'] == c]
        assert sum(int(r['planned_trajectory_count']) > 0 for r in rs) == n
        assert sum(int(r['planned_trajectory_count']) for r in rs) == slots
        for r in rs:
            assert r['evidence_type'] == 'author_confirmed_executed_quota'
            assert r['actual_sampled_trajectory_count'] == r['planned_trajectory_count']

    mopd = manifest('mopd_training_records')
    unique(mopd, 'mopd_record_id')
    assert len(mopd) == 4956
    assert Counter(r['teacher_category'] for r in mopd) == {'A': 1652, 'B': 1652, 'C': 1652}
    assert {r['source_record_id'] for r in mopd} == set(initial)
    occurrences = defaultdict(list)
    for r in mopd:
        s = initial[r['source_record_id']]
        assert (r['anon_instance_id'], r['teacher_category']) == (s['anon_instance_id'], s['category'])
        occurrences[r['source_record_id']].append(int(r['upsample_occurrence']))
    assert all(sorted(v) == list(range(1, len(v) + 1)) for v in occurrences.values())

    mastery = read('results/per_instance/training_instance_mastery.csv')
    keys = {(r['anon_instance_id'], r['phase']) for r in mastery}
    assert len(keys) == len(mastery) == 8304
    assert keys == {(i, p) for i in task_category for p in ['base', 'initial_rl', 'repair_sft']}
    assert all(r['category'] == task_category[r['anon_instance_id']] for r in mastery)

    tasks = manifest('evaluation_tasks')
    assert len({(r['benchmark_id'], r['instance_id']) for r in tasks}) == len(tasks) == 918
    assert Counter((r['benchmark_id'], r['category']) for r in tasks) == {
        ('pro618', 'A'): 221, ('pro618', 'B'): 201, ('pro618', 'C'): 196,
        ('swebench_multilingual', 'A'): 72, ('swebench_multilingual', 'B'): 25,
        ('swebench_multilingual', 'C'): 176, ('swebench_multilingual', 'UNASSIGNED'): 27}
    runs = manifest('evaluation_runs')
    unique(runs, 'run_id')
    round_groups = defaultdict(list)
    for r in runs:
        assert r['config_id'] == {'pro618': 'pro618_eval', 'swebench_multilingual': 'multilingual_eval'}[r['benchmark_id']]
        round_groups[r['benchmark_id'], r['model_id']].append(int(r['round']))
    assert len(runs) == 60 and len(round_groups) == 20
    assert all(sorted(v) == [1, 2, 3] for v in round_groups.values())

    selection = unique(manifest('pro618_selection_manifest'), 'instance_id')
    def jsonl(name):
        return [json.loads(s) for s in (ROOT / 'data/evaluation/pro618' / name).read_text().splitlines()]
    full = unique(jsonl('swebench_pro_731.jsonl'), 'instance_id')
    subset = unique(jsonl('pro618_instances.jsonl'), 'instance_id')
    assert len(full) == 731 and set(full) == set(selection)
    assert set(subset) == {i for i, r in selection.items() if r['included_in_pro618'] == 'true'}
    assert set(subset) == {r['instance_id'] for r in tasks if r['benchmark_id'] == 'pro618'}
    mapping = unique(read('data/evaluation/pro618/verified_task_mapping.csv'), 'instance_id')
    assert set(mapping) == set(subset)
    for iid, r in subset.items():
        assert {k: v for k, v in r.items() if k != 'idx'} == {k: v for k, v in full[iid].items() if k != 'idx'}
        assert int(r['idx']) == int(selection[iid]['pro618_idx']) == int(mapping[iid]['task_idx'])
        assert int(full[iid]['idx']) == int(selection[iid]['full_idx'])
    for r in tasks:
        if r['benchmark_id'] == 'pro618':
            assert mapping[r['instance_id']]['target'] == 'Pro-' + r['category']
    reasons = Counter(r['exclusion_reason'] for r in selection.values())
    assert reasons == {'': 618, 'specification_determinacy_defect': 83,
                       'underspecified_grading_choice': 26, 'reference_patch_grader_failure': 3,
                       'prompt_test_mismatch': 1}

    limits = []
    for f in (ROOT / 'configs').rglob('*.yaml'):
        s = f.read_text()
        for match in re.finditer(r'^\s*(?:max_actions_per_traj|max_iterations):\s*(\d+)\s*$', s, re.M):
            assert int(match[1]) == 150, f.name
            limits.append(f.name)
        # Environment max_steps is distinct from optimizer max_steps.
        if 'training_environment:' in s:
            env = s.split('training_environment:', 1)[1]
            assert re.search(r'^\s+max_steps: 150$', env, re.M), f.name
    parameter_files = (list((ROOT / 'configs/training').glob('*.yaml')) +
                       list((ROOT / 'configs/evaluation').glob('*.yaml')))
    assert len(parameter_files) == 17
    assert (ROOT / 'configs/labeling.yaml').is_file()
    assert (ROOT / 'configs/evaluation/prompts/pro_r2e.yaml').is_file()
    assert len(limits) == 11  # Eight RL, one MOPD, two evaluation specifications.
    for f in (ROOT / 'configs/evaluation').glob('*.yaml'):
        config_id = re.search(r'^config_id: (\S+)', f.read_text(), re.M)[1]
        benchmark_id = re.search(r'^benchmark_id: (\S+)', f.read_text(), re.M)[1]
        assert all(r['benchmark_id'] == benchmark_id for r in runs if r['config_id'] == config_id)
    for f in (ROOT / 'data/manifests').glob('*summary.json'):
        data = json.loads(f.read_text())
        hashes = data.get('output_sha256', {})
        if 'manifest_sha256' in data:
            hashes['mopd_training_records.csv'] = data['manifest_sha256']
        for name, expected in hashes.items():
            assert hashlib.sha256((f.parent / name).read_bytes()).hexdigest() == expected, name
    figures = ROOT / 'results/figures/figure_manifest.csv'
    if figures.exists():
        entries = read('results/figures/figure_manifest.csv')
        assert len(entries) == 10
        for r in entries:
            f = ROOT / r['artifact_path']
            assert hashlib.sha256(f.read_bytes()).hexdigest() == r['sha256'], f.name
    print('PASS: cross-stage identities, record multiplicities, mastery coverage, '
          'evaluation populations/rounds, Pro filtering, interaction limits, and figure hashes.')
    print('Scope: released data consistency only; withheld annotations and runtime behavior are not certified.')


if __name__ == '__main__':
    main()
