"""Reproduce record-weighted diagnostics, paired CIs, and curve summaries.

Only package-local data are read. Uses the Python standard library.
"""
import csv
import json
import random
from collections import Counter
from fractions import Fraction
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/aggregate'


def read(path):
    with (ROOT / path).open(newline='') as f:
        return list(csv.DictReader(f))


def write(name, rows):
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def training():
    records = read('data/manifests/initial_rl_training_records.csv')
    mastery = read('results/per_instance/training_instance_mastery.csv')
    repair = read('data/manifests/rre_repair_sampling_manifest.csv')
    m = {(r['anon_instance_id'], r['phase']): r for r in mastery}
    exposure = {r['anon_instance_id']: r for r in repair}
    assert len(m) == len(mastery) and len(exposure) == len(repair)
    assert len({r['anon_record_id'] for r in records}) == len(records) == 2769
    assert Counter(r['category'] for r in records) == {'A': 601, 'B': 516, 'C': 1652}
    triples = {c: [] for c in 'ABC'}
    for r in records:
        rates = []
        for phase in ('base', 'initial_rl', 'repair_sft'):
            v = m[r['anon_instance_id'], phase]
            assert v['category'] == r['category']
            n, d = int(v['n_successes']), int(v['n_attempts'])
            assert 0 <= n <= d and d > 0
            rate = Fraction(n, d)
            assert abs(float(rate) - float(v['success_rate'])) < 1e-9
            rates.append(rate)
        e = exposure[r['anon_instance_id']]
        assert e['category'] == r['category']
        triples[r['category']].append((*rates, int(e['sampled_trajectory_count']) > 0))
    triples['Total'] = sum((triples[c] for c in 'ABC'), [])
    summary, changes, cohorts = [], [], []
    for c, rs in triples.items():
        means = [mean(r[i] for r in rs) * 100 for i in range(3)]
        summary.append(dict(category=c,training_records=len(rs),base_pct=float(means[0]),
                            initial_rl_pct=float(means[1]),repair_sft_pct=float(means[2]),
                            rl_minus_base_pp=float(means[1]-means[0]),
                            sft_minus_rl_pp=float(means[2]-means[1]),
                            sft_minus_base_pp=float(means[2]-means[0])))
        for label, a, b in [('initial_rl_vs_base',1,0),('repair_sft_vs_base',2,0),('repair_sft_vs_rl',2,1)]:
            ds = [r[a]-r[b] for r in rs]
            changes.append(dict(category=c,comparison=label,training_records=len(rs),
                                higher=sum(d>0 for d in ds),equal=sum(d==0 for d in ds),lower=sum(d<0 for d in ds),
                                positive_pp=float(mean(max(d,0) for d in ds)*100),
                                negative_pp=float(mean(min(d,0) for d in ds)*100)))
        reg = [r for r in rs if r[1]<r[0] and r[3]]
        drop = [r for r in rs if r[1]>r[0] and r[2]<r[1]]
        for label, subset, counts in [
            ('regressed_and_in_repair', reg, {'at_or_above_base':sum(t>=b for b,s,t,e in reg),
              'above_rl_below_base':sum(s<t<b for b,s,t,e in reg),'at_or_below_rl':sum(t<=s for b,s,t,e in reg)}),
            ('rl_gain_then_sft_decline', drop, {'above_base':sum(t>b for b,s,t,e in drop),
              'equal_base':sum(t==b for b,s,t,e in drop),'below_base':sum(t<b for b,s,t,e in drop)})]:
            assert sum(counts.values()) == len(subset)
            for outcome,n in counts.items():
                cohorts.append(dict(category=c,cohort=label,outcome=outcome,denominator=len(subset),count=n,
                                    percent=n/len(subset)*100 if subset else ''))
    write('training_record_summary.csv', summary)
    write('training_record_changes.csv', changes)
    write('repair_record_cohorts.csv', cohorts)
    return summary


def bootstrap():
    tasks = read('data/manifests/evaluation_tasks.csv')
    ids = sorted(r['instance_id'] for r in tasks if r['benchmark_id']=='swebench_multilingual')
    assert len(ids)==len(set(ids))==300
    runs = [r for r in read('data/manifests/evaluation_runs.csv') if r['benchmark_id']=='swebench_multilingual']
    outcomes = read('results/per_instance/evaluation_outcomes.csv')
    index = {(r['run_id'],r['instance_id']):int(r['score']) for r in outcomes}
    assert len(index)==len(outcomes) and set(index.values()) <= {0,1}
    means = {}
    for model in ('base','pooled','balanced','mopd'):
        rr = [r['run_id'] for r in runs if r['model_id']==model]
        assert len(rr)==len(set(rr))==3
        for run in rr:
            assert {i for k,i in index if k==run}==set(ids)
        means[model] = {i:mean(index[run,i] for run in rr) for i in ids}
    rows=[]
    for comparator in ('base','pooled','balanced'):
        differences=[means['mopd'][i]-means[comparator][i] for i in ids]
        rng=random.Random(20260911)
        draws=sorted(mean(rng.choices(differences,k=300))*100 for _ in range(10000))
        rows.append(dict(comparison='mopd_vs_'+comparator,n_tasks=300,n_rounds=3,draws=10000,
                         seed=20260911,delta_pp=mean(differences)*100,ci95_low_pp=draws[249],ci95_high_pp=draws[9749]))
    write('multilingual_paired_bootstrap.csv',rows)
    return rows


def curves():
    scores=read('results/aggregate/evaluation_model_scores.csv')
    scores={(r['benchmark_id'],r['model_id'],r['category']):float(r['mean_pct']) for r in scores}
    base={c:scores['pro618','base',c] for c in ('Full','A','B','C')}
    points=read('results/curves/pooled_balanced_scores.csv'); outputs=[]
    for method in ('Pooled','Balanced'):
        rs=[r for r in points if r['method']==method and int(r['evaluation_index'])<=50]
        assert sorted(int(r['evaluation_index']) for r in rs)==list(range(1,51))
        full=[]; simultaneous=[]; gaps=[]
        for r in rs:
            assert int(r['round_count'])==2
            gain=float(r['Full'])-base['Full']
            worst=min(float(r[c])-base[c] for c in 'ABC')
            full.append(gain);simultaneous.append(worst);gaps.append(gain-worst)
        outputs.append(dict(method=method,displayed_points=50,rounds_per_point=2,
                            mean_full_gain_pp=mean(full),mean_gsim_pp=mean(simultaneous),mean_ssg_pp=mean(gaps),
                            final_full_gain_pp=scores['pro618',method.lower(),'Full']-base['Full']))
    write('pooled_balanced_process_summary.csv',outputs)
    return outputs


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    print(json.dumps({'training':training(),'bootstrap':bootstrap(),'curves':curves()},indent=2))
