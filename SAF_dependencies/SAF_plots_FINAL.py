#Codes to reference for SAF Cashflow Plots
import matplotlib.pyplot as plt
import numpy as np

# ── Dashboard dark theme (mirrors bioenergy_plots_FINAL.py) ──────────────────
_BG      = "#0e1621"
_BG_AX   = "#131f2e"
_GRID    = "#1e2d3d"
_TEXT    = "#c9d1e0"
_TEXT_DIM= "#4a5a6a"
_SPINE   = "#1e2d3d"
_GREEN   = "#22c55e"
_RED     = "#f87171"
_BLUE    = "#60a5fa"
_AMBER   = "#f59e0b"
_PURPLE  = "#a78bfa"
_TEAL    = "#2dd4bf"
_ORANGE  = "#fb923c"

_FS_TITLE  = 18
_FS_LABEL  = 15
_FS_TICK   = 13
_FS_LEGEND = 13
_FS_ANNOT  = 13

def _style(fig, *axes):
    fig.patch.set_facecolor(_BG)
    for ax in axes:
        ax.set_facecolor(_BG_AX)
        ax.spines[["top","right"]].set_visible(False)
        ax.spines[["left","bottom"]].set_color(_SPINE)
        ax.tick_params(colors=_TEXT, labelsize=_FS_TICK)
        ax.xaxis.label.set_color(_TEXT)
        ax.yaxis.label.set_color(_TEXT)
        ax.xaxis.label.set_fontsize(_FS_LABEL)
        ax.yaxis.label.set_fontsize(_FS_LABEL)
        ax.title.set_color(_TEXT)
        ax.title.set_fontsize(_FS_TITLE)
        for lbl in ax.get_xticklabels() + ax.get_yticklabels():
            lbl.set_color(_TEXT)
            lbl.set_fontsize(_FS_TICK)

def _legend(ax, **kw):
    leg = ax.legend(facecolor=_BG, edgecolor=_SPINE, fontsize=_FS_LEGEND, **kw)
    for t in leg.get_texts():
        t.set_color(_TEXT)
    return leg


def plot_cumulative_cashflow(df, metrics):
    fig, ax = plt.subplots(figsize=(12, 5.5))
    years = df['Year']
    cf    = df['Cumulative CF'] / 1e6
    ax.fill_between(years, cf, 0, where=(cf >= 0), color=_GREEN, alpha=0.15, label='Positive CF')
    ax.fill_between(years, cf, 0, where=(cf <  0), color=_RED,   alpha=0.15, label='Negative CF')
    ax.plot(years, cf, color=_BLUE, linewidth=2.5, label='Cumulative CF (Equity)')
    ax.axhline(0, color=_TEXT_DIM, linestyle='--', linewidth=0.8)
    pb = metrics['Payback Period (years)']
    if pb is not None:
        ax.axvline(x=pb, color=_GREEN, linestyle=':', linewidth=1.5, label=f'Payback: {pb:.1f} yrs')
    ax.set_xlabel('Year'); ax.set_ylabel('Cumulative CF ($M)')
    ax.set_title('Cumulative Cash Flow to Equity')
    _style(fig, ax); ax.yaxis.grid(True, linestyle='--', linewidth=0.5, color=_GRID); ax.set_axisbelow(True)
    _legend(ax)
    plt.tight_layout()
    plt.savefig('SAF_plots/plot_01_SAF_cumulative_cashflow.png', dpi=150, bbox_inches='tight')
    return fig


def plot_annual_cashflow(df, metrics):
    fig, ax = plt.subplots(figsize=(12, 5.5))
    years = df['Year'][1:].values
    x = np.arange(len(years)); w = 0.35
    ax.bar(x - w/2, df['Free CF to Equity'][1:].values / 1e6, w,
           label='Free CF to Equity', color=_BLUE, alpha=0.9)
    ax.bar(x + w/2, df['Discounted CF'][1:].values / 1e6, w,
           label=f"Discounted CF ({metrics['Nominal Discount Rate']*100:.2f}% nominal)",
           color=_AMBER, alpha=0.9)
    ax.axhline(0, color=_TEXT_DIM, linewidth=0.8)
    ax.set_xlabel('Year'); ax.set_ylabel('Cash Flow ($M)')
    ax.set_title('Annual Free Cash Flow to Equity vs Discounted Cash Flow')
    ax.set_xticks(x[::2]); ax.set_xticklabels(years[::2], fontsize=_FS_TICK)
    _style(fig, ax); ax.yaxis.grid(True, linestyle='--', linewidth=0.5, color=_GRID); ax.set_axisbelow(True)
    _legend(ax)
    plt.tight_layout()
    plt.savefig('SAF_plots/plot_02_SAF_annual_cashflow.png', dpi=150, bbox_inches='tight')
    return fig


def plot_debt_service(df, metrics):
    fig, ax = plt.subplots(figsize=(12, 5.5))
    years     = df['Year'][1:].values
    interest  = abs(df['Interest Expense'][1:].values)    / 1e6
    principal = abs(df['Principal Repayment'][1:].values) / 1e6
    ax.bar(years, interest,  label='Interest (tax-deductible)',    color=_RED,  alpha=0.9)
    ax.bar(years, principal, bottom=interest, label='Principal (not deductible)', color=_BLUE, alpha=0.9)
    loan_term = metrics['Loan Term']
    ax.axvline(x=loan_term + 0.5, color=_TEXT, linestyle='--', linewidth=1.2,
               label=f'Loan paid off Yr {loan_term}')
    ax.set_xlabel('Year'); ax.set_ylabel('Annual Debt Service ($M)')
    ax.set_title('Debt Service: Interest vs Principal')
    _style(fig, ax); ax.yaxis.grid(True, linestyle='--', linewidth=0.5, color=_GRID); ax.set_axisbelow(True)
    _legend(ax)
    plt.tight_layout()
    plt.savefig('SAF_plots/plot_05_SAF_debt_service.png', dpi=150, bbox_inches='tight')
    return fig


def plot_opex_pie(df, metrics):
    fig, ax = plt.subplots(figsize=(7, 5.5))
    fig.patch.set_facecolor(_BG); ax.set_facecolor(_BG)
    utilities     = abs(metrics['Total Utilities ($, Yr1)'])              / 1e6
    catalyst      = abs(metrics['Catalyst Replacement Cost (3yr)'])       / 1e6
    forest        = abs(metrics['Forest Residue Cost ($, Yr1)'])          / 1e6
    pulpwood      = abs(metrics['Pulpwood Cost ($, Yr1)'])                / 1e6
    sawmill       = abs(metrics['Sawmill Cost ($, Yr1)'])                 / 1e6
    indirect_opex = abs(metrics['Indirect OPEX ($, Yr1)'])               / 1e6
    wedge_colors  = [_BLUE, _TEAL, _GREEN, _AMBER, _PURPLE, _ORANGE]
    wedges, texts, autotexts = ax.pie(
        [utilities, catalyst, forest, pulpwood, sawmill, indirect_opex],
        labels=[f'Utilities\n${utilities:.2f}M',
                f'Catalyst\n${catalyst:.2f}M',
                f'Forest\n${forest:.2f}M',
                f'Pulpwood\n${pulpwood:.2f}M',
                f'Sawmill\n${sawmill:.2f}M',
                f'Indirect OPEX\n${indirect_opex:.2f}M'],
        autopct='%1.1f%%', startangle=90, colors=wedge_colors,
    )
    for t in texts + autotexts:
        t.set_color(_TEXT)
        t.set_fontsize(_FS_TICK)
    ax.set_title('Year 1 Operating Cost Breakdown', color=_TEXT, fontsize=_FS_TITLE)
    plt.tight_layout()
    plt.savefig('SAF_plots/plot_06_SAF_opex_pie.png', dpi=150, bbox_inches='tight')
    return fig


def plot_generation(df, metrics):
    fig, ax = plt.subplots(figsize=(12, 5.5))
    fig.patch.set_facecolor(_BG); ax.set_facecolor(_BG_AX)
    years     = df['Year'][1:].values
    saf       = df['Annual SAF Generation (L/yr)'][1:].values      / 1e6
    biodiesel = df['Annual Biodiesel Generation (L/yr)'][1:].values / 1e6
    naptha    = df['Annual Naptha Generation (L/yr)'][1:].values    / 1e6
    ax.fill_between(years, saf,       color=_BLUE,   alpha=0.08)
    ax.fill_between(years, biodiesel, color=_GREEN,  alpha=0.08)
    ax.fill_between(years, naptha,    color=_ORANGE, alpha=0.08)
    ax.plot(years, saf,       color=_BLUE,   linewidth=2.5, marker='s', markersize=4, label='SAF (ML/yr)')
    ax.plot(years, biodiesel, color=_GREEN,  linewidth=2.5, marker='s', markersize=4, label='Biodiesel (ML/yr)')
    ax.plot(years, naptha,    color=_ORANGE, linewidth=2.5, marker='s', markersize=4, label='Naphtha (ML/yr)')
    ax.set_xlabel('Year'); ax.set_ylabel('Annual Fuel Production (ML/yr)')
    ax.set_title('Fuel Production Over Time')
    # Set y-axis floor near the data to avoid large empty space below the lines
    _all_vals = np.concatenate([saf, biodiesel, naptha])
    _ymin = max(0, _all_vals.min() * 0.85)
    _ymax = _all_vals.max() * 1.10
    ax.set_ylim(_ymin, _ymax)
    _style(fig, ax); ax.yaxis.grid(True, linestyle='--', linewidth=0.5, color=_GRID); ax.set_axisbelow(True)
    _legend(ax)
    plt.tight_layout()
    plt.savefig('SAF_plots/plot_07_SAF_generation.png', dpi=150, bbox_inches='tight')
    return fig


def plot_all(df, metrics):
    # 2-column grid pairing:
    # Row 1: cumulative CF      |  annual CF
    # Row 2: opex pie           |  fuel generation
    # Row 3: debt service       |  (empty — half width)
    figs = {}
    figs['cumulative_cashflow'] = plot_cumulative_cashflow(df, metrics)
    figs['annual_cashflow']     = plot_annual_cashflow(df, metrics)
    figs['generation']          = plot_generation(df, metrics)
    figs['debt_service']        = plot_debt_service(df, metrics)
    figs['opex_pie']            = plot_opex_pie(df, metrics)
    return figs