"""Plot RRE training scores from the bundled CSV."""
from pathlib import Path
import csv, json, statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/figures'
OUT.mkdir(parents=True,exist_ok=True)
COLORS={'A':'#0072B2','B':'#D55E00','C':'#009E73'}
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],
                    'font.size':10,'pdf.fonttype':42,'mathtext.fontset':'stix'})
data={}
with (ROOT/'results/curves/rre_training_points.csv').open() as f:
    rows=list(csv.DictReader(f))
for stage in ['stage1_rl','stage3_rl']:
    for c in 'ABC':
        pts=[(int(r['plot_step']),float(r['score'])*100) for r in rows
             if r['stage']==stage and r['expert']==c]
        assert [s for s,v in pts]==list(range(len(pts)))
        assert all(0<=v<=100 for s,v in pts)
        first=statistics.mean(v for s,v in pts[:30])
        late=statistics.mean(v for s,v in pts if 221<=s<=250)
        print(f'{stage} {c}: {first:.2f} -> {late:.2f}, gain={late-first:.2f} pp')
        data[stage,c]=pts
for common in [True]:
    fig,axs=plt.subplots(1,2,figsize=(9.5,4.5 if common else 3.6),sharey=True)
    for ax,stage,title in zip(axs,['stage1_rl','stage3_rl'],['(a) Initial expert RL','(b) Expanded expert RL']):
        for c in 'ABC':
            pts=[p for p in data[stage,c] if not common or p[0]<=250]
            x,y=zip(*pts)
            smooth=[statistics.mean(y[max(0,i-19):i+1]) for i in range(len(y))]
            ax.plot(x,y,color=COLORS[c],alpha=.13,lw=.6)
            ax.plot(x,smooth,color=COLORS[c],lw=1.8,label=f'Expert {c}')
            if common:
                for boundary,marker,predicate in [(30,'v',lambda v:v<30),(70,'^',lambda v:v>70)]:
                    outside=[s for s,v in pts if predicate(v)]
                    ax.scatter(outside,[boundary]*len(outside),marker=marker,s=16,
                               color=COLORS[c],alpha=.45,clip_on=False,zorder=4)
        ax.set_title(title,fontsize=11)
        ax.set_xlabel('Training updates')
        ax.set_xlim(0,250 if common else max(data[stage,c][-1][0] for c in 'ABC'))
        ax.set_ylim((30,70) if common else (0,100))
        ax.set_yticks(range(30,71,5) if common else range(0,101,20))
        ax.grid(alpha=.17);ax.spines[['top','right']].set_visible(False)
        ax.legend(frameon=False,ncol=3,fontsize=8,loc='upper left' if common else 'lower right')
    axs[0].set_ylabel('Training rollout score (%)')
    fig.tight_layout()
    name='fig_rre_training' if common else 'fig_rre_training_full'
    fig.savefig(OUT/f'{name}.pdf',bbox_inches='tight')
    fig.savefig(OUT/f'{name}.png',dpi=300,bbox_inches='tight')
    plt.close(fig)
