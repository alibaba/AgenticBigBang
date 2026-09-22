"""Compute and plot category gains using only bundled evaluation results."""
import csv
from pathlib import Path
from statistics import mean
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
def read(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))

tasks = {r['instance_id']: r['category'] for r in read(ROOT/'data/manifests/evaluation_tasks.csv') if r['benchmark_id']=='pro618'}
runs = {r['run_id']:r for r in read(ROOT/'data/manifests/evaluation_runs.csv') if r['benchmark_id']=='pro618' and r['included_in_paper']=='true'}
models = ['base','pooled','balanced','mopd']+[f'expert_{c}_second_repair_sft' for c in 'ABC']
scores = {rid:{} for rid,r in runs.items() if r['model_id'] in models}
for row in read(ROOT/'results/per_instance/evaluation_outcomes.csv'):
    rid = row['run_id']
    if rid not in scores:
        continue
    iid = row['instance_id']
    assert iid in tasks and iid not in scores[rid]
    score = float(row['score'])
    assert score in (0,1)
    if row['result_status']=='missing':
        assert score==0
    scores[rid][iid]=score
for result in scores.values():
    assert set(result)==set(tasks)

means={}
for model in models:
    ids=[rid for rid in scores if runs[rid]['model_id']==model]
    assert len(ids)==3
    for category in 'ABC':
        task_ids=[iid for iid,c in tasks.items() if c==category]
        means[model,category]=mean(100*sum(scores[rid][iid] for iid in task_ids)/len(task_ids) for rid in ids)

rows=[]
recovery={}
for c in 'ABC':
    base=means['base',c]
    expert_gain=means[f'expert_{c}_second_repair_sft',c]-base
    assert expert_gain>0
    recovery[c]=100*(means['mopd',c]-base)/expert_gain
    for policy,model in [('pooled','pooled'),('balanced','balanced'),('corresponding_expert',f'expert_{c}_second_repair_sft'),('mopd','mopd')]:
        rows.append(dict(category=c,policy=policy,model_id=model,base_mean_pct=base,
                         model_mean_pct=means[model,c],gain_pp=means[model,c]-base,
                         expert_gain_recovery_pct=recovery[c] if policy=='mopd' else ''))
out=ROOT/'results/aggregate/category_gains.csv'
with out.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],
                     'font.size':11,'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
fig,ax=plt.subplots(figsize=(7.2,3.6))
x=np.arange(3);width=.185
for i,(policy,label,color,hatch) in enumerate([
    ('pooled','Pooled RL','#8DAAC4',''),('balanced','Balanced RL','#C7C7C7',''),
    ('corresponding_expert','Corresponding expert','#009E73','//'),('mopd','MOPD (single model)','#D55E00','')]):
    values=[next(r['gain_pp'] for r in rows if r['category']==c and r['policy']==policy) for c in 'ABC']
    bars=ax.bar(x+(i-1.5)*width,values,width*.91,color=color,edgecolor='white',linewidth=.5,hatch=hatch,label=label,zorder=3)
    ax.bar_label(bars,labels=[f'{v:.2f}' for v in values],padding=3,fontsize=10)
ax.set_xticks(x,[f'Pro-{c}\nRecovery: {recovery[c]:.1f}%' for c in 'ABC'])
ax.tick_params(axis='x',length=0,pad=9)
ax.set_ylabel('Resolution gain over Base (pp)')
ax.set_ylim(0,9);ax.set_yticks([0,2,4,6,8]);ax.set_xlim(-.55,2.55)
ax.grid(axis='y',alpha=.20,linewidth=.6,zorder=0)
fig.legend(loc='upper center',bbox_to_anchor=(.53,1),ncol=2,frameon=False,fontsize=10.5,columnspacing=2)
fig.subplots_adjust(left=.095,right=.99,bottom=.19,top=.81)
figdir=ROOT/'results/figures';figdir.mkdir(exist_ok=True)
for suffix in ['pdf','png']:
    fig.savefig(figdir/f'fig_mopd_category_gains.{suffix}',dpi=300,bbox_inches='tight')
plt.close(fig)
print('Validated 21 Pro-618 runs; derived 12 category/policy rows.')
print('MOPD expert-gain recovery (%):',recovery)
