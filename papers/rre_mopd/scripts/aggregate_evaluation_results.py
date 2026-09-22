"""Validate the three evaluation tables and derive per-run/category scores.

Usage: python3 scripts/aggregate_evaluation_results.py
Outputs are derived, not separately maintained source tables.
"""
import csv
import statistics
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
tasks=read(ROOT/'data/manifests/evaluation_tasks.csv')
runs=read(ROOT/'data/manifests/evaluation_runs.csv')
outcomes=read(ROOT/'results/per_instance/evaluation_outcomes.csv')
task_map={(r['benchmark_id'],r['instance_id']):r['category'] for r in tasks}
assert len(task_map)==len(tasks)
run_map={r['run_id']:r for r in runs}
assert len(run_map)==len(runs)
by_run=defaultdict(dict)
for r in outcomes:
    run=run_map[r['run_id']]
    assert (run['benchmark_id'],r['instance_id']) in task_map
    assert r['instance_id'] not in by_run[r['run_id']]
    assert r['score'] in ['0','1']
    assert r['result_status'] in ['observed','missing']
    if r['result_status']=='missing':assert r['score']=='0'
    by_run[r['run_id']][r['instance_id']]=r
result=[]
for run_id,run in run_map.items():
    expected={i:c for (b,i),c in task_map.items() if b==run['benchmark_id']}
    actual=by_run[run_id]
    assert set(actual)==set(expected)
    assert len(actual)==int(run['expected_tasks'])
    missing=sum(r['result_status']=='missing' for r in actual.values())
    assert missing==int(run['missing_tasks'])
    assert len(actual)-missing==int(run['observed_tasks'])
    for cat in ['Full']+sorted(set(expected.values())):
        ids=[i for i,c in expected.items() if cat=='Full' or c==cat]
        wins=sum(int(actual[i]['score']) for i in ids)
        result.append(dict(run_id=run_id,benchmark_id=run['benchmark_id'],model_id=run['model_id'],
                           category=cat,successes=wins,denominator=len(ids),score_pct=100*wins/len(ids)))
groups=defaultdict(list)
for r in result:
    if run_map[r['run_id']]['included_in_paper']=='true':
        groups[r['benchmark_id'],r['model_id'],r['category']].append(r['score_pct'])
means=[dict(benchmark_id=b,model_id=m,category=c,n_rounds=len(v),mean_pct=statistics.mean(v),population_sd_pct=statistics.pstdev(v))
       for (b,m,c),v in sorted(groups.items())]
target=ROOT/'results/aggregate'
target.mkdir(exist_ok=True)
for name,rows in [('evaluation_round_scores.csv',result),('evaluation_model_scores.csv',means)]:
    with (target/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(f'Validated {len(tasks)} tasks, {len(runs)} runs, {len(outcomes)} outcomes. Derived scores: {target}')
