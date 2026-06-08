import numpy as np
import matplotlib.pyplot as plt

# ── Dashboard dark theme ──────────────────────────────────────────────────────
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

_FS_TITLE  = 18   # plot title
_FS_LABEL  = 15   # axis labels
_FS_TICK   = 13   # tick labels
_FS_LEGEND = 13   # legend text
_FS_ANNOT  = 13   # annotations

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
    ax.fill_between(years, cf, 0, where=(cf >= 0), color=_GREEN,  alpha=0.15, label='Positive CF')
    ax.fill_between(years, cf, 0, where=(cf <  0), color=_RED,    alpha=0.15, label='Negative CF')
    ax.plot(years, cf, color=_BLUE, linewidth=2,   label='Cumulative CF (Equity)')
    ax.axhline(0, color=_TEXT_DIM, linestyle='--', linewidth=0.8)
    pb = metrics['Payback Period (years)']
    if pb is not None:
        ax.axvline(x=pb, color=_GREEN, linestyle=':', linewidth=1.5, label=f'Payback: {pb:.1f} yrs')
    ax.set_xlabel('Year'); ax.set_ylabel('Cumulative CF ($M)')
    ax.set_title('Cumulative Cash Flow to Equity')
    _style(fig, ax); ax.yaxis.grid(True, linestyle='--', linewidth=0.5, color=_GRID); ax.set_axisbelow(True)
    _legend(ax, loc='lower right')
    plt.tight_layout()
    plt.savefig('Bioenergy_plots/plot_01_cumulative_cashflow.png', dpi=150, bbox_inches='tight')
    return fig


def plot_annual_cashflow(df, metrics):
    fig, ax = plt.subplots(figsize=(12, 5.5))
    years = df['Year'][1:].values
    x = np.arange(len(years)); w = 0.35
    ax.bar(x - w/2, df['Free CF to Equity'][1:].values / 1e6,  w, label='Free CF to Equity',  color=_BLUE,  alpha=0.9)
    ax.bar(x + w/2, df['Discounted CF'][1:].values    / 1e6,  w,
           label=f"Discounted CF ({metrics['Nominal Discount Rate']*100:.2f}% nominal)", color=_AMBER, alpha=0.9)
    ax.axhline(0, color=_TEXT_DIM, linewidth=0.8)
    ax.set_xlabel('Year'); ax.set_ylabel('Cash Flow ($M)')
    ax.set_title('Annual Free Cash Flow to Equity vs Discounted Cash Flow')
    ax.set_xticks(x[::2]); ax.set_xticklabels(years[::2], fontsize=_FS_TICK)
    _style(fig, ax); ax.yaxis.grid(True, linestyle='--', linewidth=0.5, color=_GRID); ax.set_axisbelow(True)
    _legend(ax)
    plt.tight_layout()
    plt.savefig('Bioenergy_plots/plot_02_annual_cashflow.png', dpi=150, bbox_inches='tight')
    return fig


def plot_net_income(df, metrics):
    fig, ax = plt.subplots(figsize=(12, 5.5))
    years   = df['Year'][1:].values
    net_inc = df['Net Income'][1:].values
    colors  = [_GREEN if v >= 0 else _RED for v in net_inc]
    ax.bar(years, net_inc / 1e6, color=colors, width=0.8, alpha=0.9)
    ax.axhline(0, color=_TEXT_DIM, linewidth=0.8)
    ax.set_xlabel('Year'); ax.set_ylabel('Net Income ($M)'); ax.set_title('Net Income Over Time')
    _style(fig, ax); ax.yaxis.grid(True, linestyle='--', linewidth=0.5, color=_GRID); ax.set_axisbelow(True)
    plt.tight_layout()
    plt.savefig('Bioenergy_plots/plot_03_net_income.png', dpi=150, bbox_inches='tight')
    return fig


def plot_carryforward(df, metrics):
    fig, ax = plt.subplots(figsize=(12, 5.5))
    state_balances=[]; federal_balances=[]; s_carry=0.0; f_carry=0.0
    for _, row in df[df['Year'] > 0].iterrows():
        ebt_val = row['EBT']; s_tax_val = abs(row['State Tax'])
        state_taxable = ebt_val + s_carry
        s_carry = state_taxable if state_taxable < 0 else 0.0
        state_balances.append(s_carry)
        fed_taxable = ebt_val - s_tax_val + f_carry
        f_carry = fed_taxable if fed_taxable < 0 else 0.0
        federal_balances.append(f_carry)
    op_years = df['Year'][1:].values
    ax.plot(op_years, [s/1e6 for s in state_balances],   color=_AMBER,  linewidth=2, label='State carryforward')
    ax.plot(op_years, [f/1e6 for f in federal_balances], color=_PURPLE, linewidth=2, label='Federal carryforward')
    ax.axhline(0, color=_TEXT_DIM, linewidth=0.8)
    ax.set_xlabel('Year'); ax.set_ylabel('Carryforward Balance ($M)'); ax.set_title('Tax Loss Carryforward')
    _style(fig, ax); ax.yaxis.grid(True, linestyle='--', linewidth=0.5, color=_GRID); ax.set_axisbelow(True)
    _legend(ax)
    plt.tight_layout()
    plt.savefig('Bioenergy_plots/plot_04_carryforward.png', dpi=150, bbox_inches='tight')
    return fig


def plot_debt_service(df, metrics):
    fig, ax = plt.subplots(figsize=(12, 5.5))
    years     = df['Year'][1:].values
    interest  = abs(df['Interest Expense'][1:].values)    / 1e6
    principal = abs(df['Principal Repayment'][1:].values) / 1e6
    ax.bar(years, interest,  label='Interest (tax-deductible)',    color=_RED,  alpha=0.9)
    ax.bar(years, principal, bottom=interest, label='Principal (not deductible)', color=_BLUE, alpha=0.9)
    loan_term = metrics['Loan Term']
    ax.axvline(x=loan_term+0.5, color=_TEXT, linestyle='--', linewidth=1.2, label=f'Loan paid off Yr {loan_term}')
    ax.set_xlabel('Year'); ax.set_ylabel('Annual Debt Service ($M)'); ax.set_title('Debt Service: Interest vs Principal')
    _style(fig, ax); ax.yaxis.grid(True, linestyle='--', linewidth=0.5, color=_GRID); ax.set_axisbelow(True)
    _legend(ax)
    plt.tight_layout()
    plt.savefig('Bioenergy_plots/plot_05_debt_service.png', dpi=150, bbox_inches='tight')
    return fig


def plot_opex_pie(df, metrics):
    fig, ax = plt.subplots(figsize=(7, 5.5))
    fig.patch.set_facecolor(_BG); ax.set_facecolor(_BG)
    fom         = abs(df.loc[1, 'Fixed O&M'])           / 1e6
    vom         = abs(df.loc[1, 'Variable O&M'])         / 1e6
    forest_fuel = abs(df.loc[1, 'Forest Fuel Cost ($)']) / 1e6
    mill_fuel   = abs(df.loc[1, 'Mill Fuel Cost ($)'])   / 1e6
    wedge_colors = [_BLUE, _TEAL, _GREEN, _AMBER]
    wedges, texts, autotexts = ax.pie(
        [fom, vom, forest_fuel, mill_fuel],
        labels=[f'Fixed O&M\n${fom:.2f}M', f'Var O&M\n${vom:.2f}M',
                f'Forest Fuel\n${forest_fuel:.2f}M', f'Mill Fuel\n${mill_fuel:.2f}M'],
        autopct='%1.1f%%', startangle=90, colors=wedge_colors,
    )
    for t in texts + autotexts:
        t.set_color(_TEXT)
    ax.set_title('Year 1 Operating Cost Breakdown', color=_TEXT)
    plt.tight_layout()
    plt.savefig('Bioenergy_plots/plot_06_opex_pie.png', dpi=150, bbox_inches='tight')
    return fig


def plot_generation(df, metrics):
    fig, ax1 = plt.subplots(figsize=(12, 5.5))
    fig.patch.set_facecolor(_BG)
    ax1.set_facecolor(_BG_AX)

    years    = df['Year'][1:].values
    gen      = df['Annual Generation (MWh)'][1:].values / 1000
    pct_loss = (1 - gen / gen[0]) * 100

    # Generation on left axis
    ax1.fill_between(years, gen, color=_GREEN, alpha=0.08)
    ax1.plot(years, gen, color=_GREEN, linewidth=2.5,
             marker='s', markersize=4, label='Annual Generation (GWh)')

    # Style left axis
    ax1.set_xlabel('Year', fontsize=_FS_LABEL, color=_TEXT)
    ax1.set_ylabel('Annual Generation (GWh)', fontsize=_FS_LABEL, color=_GREEN)
    ax1.tick_params(axis='x', colors=_TEXT, labelsize=_FS_TICK)
    ax1.tick_params(axis='y', labelcolor=_GREEN, colors=_GREEN, labelsize=_FS_TICK)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.spines[["left", "bottom"]].set_color(_SPINE)
    ax1.yaxis.grid(True, linestyle='--', linewidth=0.5, color=_GRID)
    ax1.set_axisbelow(True)
    ax1.set_title('Electricity Generation Over Time', fontsize=_FS_TITLE, color=_TEXT)

    # Output loss on right axis
    ax2 = ax1.twinx()
    ax2.set_facecolor(_BG_AX)
    ax2.plot(years, pct_loss, color=_RED, linewidth=2, linestyle='--',
             marker='o', markersize=4, label='Output Loss (%)')
    ax2.set_ylabel('Cumulative Output Loss (%)', fontsize=_FS_LABEL, color=_RED)
    ax2.tick_params(axis='y', labelcolor=_RED, colors=_RED, labelsize=_FS_TICK)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_color(_SPINE)
    ax2.spines["left"].set_color(_SPINE)
    ax2.spines["bottom"].set_color(_SPINE)

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    leg = ax1.legend(lines1 + lines2, labels1 + labels2,
                     facecolor=_BG, edgecolor=_SPINE, fontsize=_FS_LEGEND,
                     loc='center left')
    for t in leg.get_texts():
        t.set_color(_TEXT)

    plt.tight_layout()
    plt.savefig('Bioenergy_plots/plot_07_generation.png', dpi=150, bbox_inches='tight')
    return fig


def plot_all(df, metrics):
    figs = {}
    figs['cumulative_cashflow'] = plot_cumulative_cashflow(df, metrics)
    figs['annual_cashflow']     = plot_annual_cashflow(df, metrics)
    figs['net_income']          = plot_net_income(df, metrics)
    figs['debt_service']        = plot_debt_service(df, metrics)
    figs['opex_pie']            = plot_opex_pie(df, metrics)
    figs['generation']          = plot_generation(df, metrics)
    return figs