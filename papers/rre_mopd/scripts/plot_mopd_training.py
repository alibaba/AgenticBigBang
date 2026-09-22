"""Plot MOPD training metrics from the bundled CSV."""
from pathlib import Path
import csv
import json
import math
import statistics as st
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/figures'
OUT.mkdir(parents=True, exist_ok=True)
series = {}
with (ROOT / 'results/curves/mopd_training_points.csv').open() as f:
    for r in csv.DictReader(f):
        series.setdefault(r['metric'], []).append({'step': int(r['step']), 'value': float(r['value'])})
assert set(series) == {'score', 'kl_mean'}
for name, rows in series.items():
    assert [r['step'] for r in rows] == list(range(len(rows)))
    assert all(math.isfinite(r['value']) for r in rows)
    if name == 'score': assert all(0 <= r['value'] <= 1 for r in rows)
shared_end = min(rows[-1]['step'] for rows in series.values())
audit = {'summaries': {}}
for name, rows in series.items():
    early = st.mean(r['value'] for r in rows[:20])
    late = st.mean(r['value'] for r in rows[shared_end-19:shared_end+1])
    audit['summaries'][name] = dict(early_mean=early, late_mean=late, difference=late-early, relative_change_pct=100*(late/early-1))
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['Times New Roman', 'DejaVu Serif'],
                     'font.size': 10, 'pdf.fonttype': 42, 'mathtext.fontset': 'stix',
                     'axes.spines.top': False, 'axes.spines.right': False})
fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.5), sharex=True)
for ax, name, color, scale, title, ylabel, ylim in zip(
    axs, ['score', 'kl_mean'], ['#0072B2', '#D55E00'], [100, 1],
    ['(a) Training rollout score', '(b) Student-teacher KL'],
    ['Training rollout score (%)', 'Student-teacher KL'], [(25, 72), (.010, .0325)]):
    rows = series[name]
    steps = [r['step'] for r in rows]
    values = [r['value'] * scale for r in rows]
    smooth = [st.mean(values[max(0, i - 19):i + 1]) for i in range(len(values))]
    ax.plot(steps, values, color=color, alpha=.24, linewidth=.8, zorder=2)
    ax.plot(steps, smooth, color=color, linewidth=2, zorder=3)
    ax.set_xlim(0, 135)
    ax.set_xticks([0, 25, 50, 75, 100, 125])
    ax.set_ylim(*ylim)
    ax.set_xlabel('Training step')
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=11, loc='left', pad=29, fontweight='bold')
    ax.grid(alpha=.16, linewidth=.6)
    a = audit['summaries'][name]
    if name == 'score':
        subtitle = f"{a['early_mean']*100:.2f}% to {a['late_mean']*100:.2f}%  (+{a['difference']*100:.2f} pp)"
        ax.set_yticks([30, 40, 50, 60, 70])
    else:
        subtitle = f"{a['early_mean']:.5f} to {a['late_mean']:.5f}  ({a['relative_change_pct']:.1f}%)"
        ax.set_yticks([.010, .015, .020, .025, .030])
    ax.text(0, 1.04, subtitle, color=color, transform=ax.transAxes, fontsize=10)

fig.legend(handles=[Line2D([0], [0], color='#666666', alpha=.3, lw=1, label='Raw values'),
                    Line2D([0], [0], color='#333333', lw=2, label='20-step trailing mean')],
           loc='lower center', bbox_to_anchor=(.5, .052), frameon=False, ncol=2, fontsize=9)
fig.text(.5, .015, f'Summary windows: steps 0-19 and {shared_end-19}-{shared_end}. All available raw points are shown.',
         ha='center', fontsize=9, color='#555555')
fig.subplots_adjust(left=.075, right=.985, bottom=.25, top=.78, wspace=.28)
pdf_dir = OUT
fig.savefig(pdf_dir / 'fig_mopd_training.pdf', bbox_inches='tight')
fig.savefig(OUT / 'fig_mopd_training.png', dpi=300, bbox_inches='tight')
plt.close(fig)
print(json.dumps(audit['summaries'], indent=2))
