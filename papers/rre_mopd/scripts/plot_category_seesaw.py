"""Validate and plot the bundled category dynamics data.
Requires numpy and matplotlib. Run from any working directory.
"""
import csv
import json
from pathlib import Path
from statistics import mean
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'results'/'figures'
HERE.mkdir(parents=True,exist_ok=True)
def read(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))
source=read(ROOT/'results/curves/category_seesaw_source.csv')
rows=read(ROOT/'results/curves/category_seesaw_motivation.csv')
for r in rows:
    for k in r:r[k]=float(r[k])
base_scores=read(ROOT/'results/aggregate/evaluation_model_scores.csv')
BASE={r['category']:float(r['mean_pct']) for r in base_scores if r['benchmark_id']=='pro618' and r['model_id']=='base'}
assert len(source)==126 and len(rows)==64
assert len({(r['plot_step'],r['round']) for r in source})==126
for point in rows:
    if point['step']==0:
        assert all(point[c]==0 for c in ['Full','A','B','C','G_sim','SSG'])
        continue
    pair=[r for r in source if float(r['plot_step'])==point['step']]
    assert len(pair)==2 and {r['round'] for r in pair}=={'1','2'}
    for c in BASE:assert abs(mean(float(r[c]) for r in pair)-BASE[c]-point[c])<1e-8
    assert abs(min(point[c] for c in 'ABC')-point['G_sim'])<1e-8
    assert abs(point['Full']-point['G_sim']-point['SSG'])<1e-8
COLORS = dict(Full='#30343B', A='#0072B2', B='#D55E00', C='#009E73', Worst='#7A3E65', Gap='#E8B28E')
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],
    'font.size':11,'axes.labelsize':11,'axes.titlesize':12,'legend.fontsize':10,
    'legend.frameon':False,'pdf.fonttype':42,'ps.fonttype':42,'savefig.bbox':'tight'})
x = np.array([r['step'] for r in rows])
def values(k): return np.array([r[k] for r in rows])
def smooth(y):
    s=np.array([mean(y[max(0,i-1):min(len(y),i+2)]) for i in range(len(y))])
    s[0]=0.
    return s

fig,axs=plt.subplots(1,2,figsize=(10.8,3.8),sharey=True)
for c,label,style in [('Full','Overall','-'),('A','Pro-A','-'),('B','Pro-B','--'),('C','Pro-C','-.')]:
    y=values(c)
    axs[0].plot(x,y,color=COLORS[c],lw=.65,alpha=.23,marker='o',markersize=2,zorder=2)
    axs[0].plot(x,smooth(y),color=COLORS[c],lw=2 if c=='Full' else 1.7,
                linestyle=style,label=label,zorder=4)
full,worst=values('Full'),values('G_sim')
assert np.allclose(smooth(full)-smooth(worst), smooth(full-worst))
axs[1].fill_between(x,smooth(worst),smooth(full),color=COLORS['Gap'],alpha=.30,label='SSG',zorder=1)
for y,color,label,style in [(full,COLORS['Full'],'Overall gain','-'),(worst,COLORS['Worst'],r'$G_{\mathrm{sim}}$','--')]:
    axs[1].plot(x,y,color=color,lw=.65,alpha=.25,zorder=2)
    axs[1].plot(x,smooth(y),color=color,lw=2,linestyle=style,label=label,zorder=4)

lower=min(min(values(c)) for c in ['Full','A','B','C','G_sim'])
upper=max(max(values(c)) for c in ['Full','A','B','C','G_sim'])
for ax,title in zip(axs,['(a) Overall and category gains','(b) Simultaneous gain and see-saw gap']):
    ax.set_title(title,pad=35)
    ax.set_xlabel('Training steps')
    ax.set_xlim(0,max(x));ax.set_xticks([0,50,100,150,200,250,300])
    ax.set_ylim(np.floor(lower)-.1,upper+.25)
    ax.set_yticks(np.arange(np.floor(lower),np.floor(upper)+1,1))
    ax.axhline(0,color='#69707A',lw=.8,ls=(0,(4,3)),zorder=1)
    ax.grid(axis='y',color='#D9DDE3',lw=.65,alpha=.75)
    ax.spines[['top','right']].set_visible(False)
    ax.spines[['left','bottom']].set_color('#8B929C')
axs[0].set_ylabel('Gain over base (percentage points)')
axs[0].legend(loc='lower center',bbox_to_anchor=(.5,1.01),ncol=4,columnspacing=1.,handlelength=1.8)
h,l=axs[1].get_legend_handles_labels();order=[1,2,0]
axs[1].legend([h[i] for i in order],[l[i] for i in order],loc='lower center',bbox_to_anchor=(.5,1.01),ncol=3)
fig.subplots_adjust(left=.075,right=.995,bottom=.17,top=.77,wspace=.16)
for ext in ['png','pdf']:
    fig.savefig(HERE/f'fig_category_seesaw_motivation.{ext}',dpi=300)
plt.close(fig)
print(json.dumps({'base':BASE,'rows':len(rows),'range':[float(lower),float(upper)],
                  'output':str(HERE/'fig_category_seesaw_motivation.png')},indent=2))
