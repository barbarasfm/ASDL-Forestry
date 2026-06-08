"""
=============================================================================
References:
  Sahoo et al.  (2019) Biofuels Bioprod. Bioref. 13:514-534
    — Truck payload (Table 3), Fuel economy (Table 3)
  GREET 2025 R&D, HDV Combination Long-Haul Truck CIDI - LS Diesel
    — Tailpipe CH4 and N2O emission factors (on-road)
  IPCC AR6      (2021) Ch.7
    — GWP100 values: CO2=1.0, CH4=27.9, N2O=273.0
=============================================================================
"""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


# =============================================================================
# OUTPUT PATHS
# =============================================================================
BASE_OUTPUT_DIR  = os.path.join(os.path.expanduser('~'), 'Downloads', 'LCA_Transport')
PLOTS_OUTPUT_DIR = os.path.join(BASE_OUTPUT_DIR, 'plots')


# =============================================================================
# USER INPUTS
# =============================================================================
TOTAL_RESIDUE_OD_KG   = 272352000   # total OD kg forest residue collected/yr
# HIGH_QUALITY_FRACTION = 0.40          # fraction of total → SAF plant (Case 1)
# LOW_QUALITY_FRACTION = 0.60         # (remainder; all residue goes to bioenergy in Case 2)

DIST        = 63.891        # km, forest → SAF plant (one-way)
# DIST_TO_BIOENERGY_KM  = 21.887         # km, forest → bioenergy plant (one-way)
TRUCK_PAYLOAD_OD_KG   = 18300        # OD kg per truck load (Sahoo 2019, Table 3)


# =============================================================================
# GWP100 — IPCC AR6, Chapter 7
# =============================================================================
GWP_CO2 = 1.0
GWP_CH4 = 27.9
GWP_N2O = 273.0


# =============================================================================
# DIESEL COMBUSTION EMISSION FACTORS — ON-ROAD TRANSPORT TRUCKS
# =============================================================================
# Source : GREET 2025 R&D, HDV Combination Long-Haul Truck CIDI - LS Diesel
#          Tailpipe screen: CH4 = 14.2800 mg/mi, N2O = 1.9166 mg/mi
#          Fuel consumption: 17,823.39 Btu/mi → L/mi = 17823.39 / 33932 = 0.52527
#
#   CO2 (kg/L) = C_fraction × (44/12) × density = 0.86 × 3.667 × 0.85 = 2.68
#                (carbon balance — same for all diesel classes)
#   CH4 = 14.2800e-6 kg/mi ÷ 0.52527 L/mi = 2.7186e-5 kg/L
#   N2O =  1.9166e-6 kg/mi ÷ 0.52527 L/mi = 3.6488e-6 kg/L
# =============================================================================
DIESEL_CO2        = 2.68        # kg CO2 / L  — carbon balance
DIESEL_CH4_ONROAD = 2.7186e-5   # kg CH4 / L  — GREET 2025 HDV Long-Haul Truck
DIESEL_N2O_ONROAD = 3.6488e-6   # kg N2O / L  — GREET 2025 HDV Long-Haul Truck

# Truck fuel economy (Sahoo 2019, Table 3)
TRUCK_L_PER_KM    = 0.35        # L/km, heavy-duty diesel


# =============================================================================
# COLOR SYSTEM  (consistent with full LCA file)
# =============================================================================
C_CO2 = '#264653'   # dark slate   — fossil CO₂
C_CH4 = '#2a9d8f'   # teal         — CH₄
C_N2O = '#e9c46a'   # amber        — N₂O
C_HQ  = '#1d3557'   # navy         — High Quality → SAF  (Case 1)
C_LQ  = '#457b9d'   # steel blue   — All residue → Bioenergy (Case 2)


# =============================================================================
# HELPERS
# =============================================================================
def calc_gwi(co2_kg, ch4_kg, n2o_kg):
    """Convert gas masses to total GWI (kg CO2e) using IPCC AR6 GWP100."""
    return co2_kg * GWP_CO2 + ch4_kg * GWP_CH4 + n2o_kg * GWP_N2O


def diesel_ghg(litres):
    """
    Calculate GHG mass and GWI from on-road heavy-duty diesel combustion.

    Parameters
    ----------
    litres : float — total diesel consumed (L/yr)

    Returns
    -------
    co2   : float — kg CO2/yr   (carbon balance, GREET 2025)
    ch4   : float — kg CH4/yr   (GREET 2025 Long-Haul Truck)
    n2o   : float — kg N2O/yr   (GREET 2025 Long-Haul Truck)
    gwi   : float — kg CO2e/yr  (CO2×1 + CH4×27.9 + N2O×273)
    """
    co2 = litres * DIESEL_CO2
    ch4 = litres * DIESEL_CH4_ONROAD
    n2o = litres * DIESEL_N2O_ONROAD
    return co2, ch4, n2o, calc_gwi(co2, ch4, n2o)


def hdr(title):
    print('\n' + '=' * 72)
    print(f'  {title}')
    print('=' * 72)


def sub(title):
    print(f'\n  -- {title} --')


# =============================================================================
# PHASE 2: TRANSPORT
# =============================================================================
def phase2_transport(total_kg, dist_saf):
    """
    Calculate GHG emissions from forest-residue transport to processing plants.

    METHODOLOGY:
    ────────────────────────────────────────────────────────────────────────────
    Only the ONE-WAY loaded trip is attributed to this LCA system boundary.
    The return trip (empty truck) belongs to the next delivery cycle.

      trips/yr       = Residue (OD kg/yr) ÷ Payload (OD kg/load)
      Fuel (L/trip)  = Distance (km) × Fuel economy (L/km)     [ONE-WAY]
      Fuel (L/yr)    = Fuel (L/trip) × trips/yr
      CO2 (kg/yr)    = Fuel (L/yr) × 2.68  kg CO2/L            [GREET 2025]
      CH4 (kg/yr)    = Fuel (L/yr) × 2.7186e-5 kg CH4/L        [GREET 2025]
      N2O (kg/yr)    = Fuel (L/yr) × 3.6488e-6 kg N2O/L        [GREET 2025]
      GWI (kg CO2e)  = CO2×1 + CH4×27.9 + N2O×273              [IPCC AR6]

    Cases:
      Case 1 — HQ residue (hq_frac × total_kg) → SAF plant (dist_saf km)
      Case 2 — ALL residue (total_kg)           → Bioenergy plant (dist_bio km)

    Parameters
    ----------
    total_kg : float — total annual OD kg of forest residue
    hq_frac  : float — fraction of total that is high-quality (→ SAF)
    dist_saf : float — one-way distance to SAF plant (km)
    dist_bio : float — one-way distance to bioenergy plant (km)

    Returns
    -------
    dict with keys 'saf' and 'bio', each containing full emission results.
    """
    hdr('PHASE 2 — TRANSPORT')
    print(f'  Total residue available    : {total_kg:>15,.0f} OD kg/year')
    # print(f'  HQ fraction (→ SAF)        : {hq_frac*100:.0f}%  ({total_kg*hq_frac:,.0f} OD kg/yr)')
    print(f'  Fuel basis                 : ONE-WAY loaded trip only (LCA system boundary)')
    print(f'  Truck payload              : {TRUCK_PAYLOAD_OD_KG:>10,.0f} OD kg/load  (Sahoo 2019, Table 3)')
    print(f'  Fuel economy               : {TRUCK_L_PER_KM} L/km  (Sahoo 2019, Table 3)')
    print(f'  Emission factors           : GREET 2025 R&D, HDV Long-Haul Truck (on-road)')
    print(f'  GWP100                     : CO2={GWP_CO2}  CH4={GWP_CH4}  N2O={GWP_N2O}  (IPCC AR6)')

    cases = [
        ('Case 1: Forest → SAF Plant  (HQ residue only)',
         total_kg, dist_saf, 'saf'),
    ]

    results = {}

    for label, res_kg, dist_km, key in cases:

        fuel_trip_L  = dist_km * TRUCK_L_PER_KM          # L per one-way loaded trip
        fuel_OD_kg_L = fuel_trip_L / TRUCK_PAYLOAD_OD_KG  # L per OD kg transported
        tot_fuel_L   = fuel_OD_kg_L * res_kg              # total L/yr
        trips_yr     = res_kg / TRUCK_PAYLOAD_OD_KG        # one-way loaded trips/yr

        co2, ch4, n2o, gwi = diesel_ghg(tot_fuel_L)
        gwi_co2 = co2 * GWP_CO2
        gwi_ch4 = ch4 * GWP_CH4
        gwi_n2o = n2o * GWP_N2O

        sub(label)
        print(f'    Residue transported             : {res_kg:>15,.0f} OD kg/year')
        print(f'    One-way distance                : {dist_km:>15.1f} km')
        print(f'    Truck payload                   : {TRUCK_PAYLOAD_OD_KG:>15,.0f} OD kg/load')
        print(f'    Truck trips/year (one-way loads): {trips_yr:>15,.0f}'
              f'  [= {res_kg:,.0f} ÷ {TRUCK_PAYLOAD_OD_KG:,.0f}]')
        print(f'    Fuel per trip (ONE WAY)         : {fuel_trip_L:>15.2f} L'
              f'  [= {dist_km} km × {TRUCK_L_PER_KM} L/km]')
        print(f'    Total fuel consumed             : {tot_fuel_L:>15,.1f} L/year'
              f'  [= {fuel_trip_L:.2f} L × {trips_yr:,.0f} trips]')

        print(f"""
    EQUATIONS:
      trips/yr       = Residue (OD kg/yr) ÷ Payload (OD kg/load)
                     = {res_kg:,.0f} ÷ {TRUCK_PAYLOAD_OD_KG:,.0f}
                     = {trips_yr:,.0f} trips/yr

      Fuel (L/trip)  = Distance (km) × Fuel economy (L/km)   [ONE-WAY]
                     = {dist_km} × {TRUCK_L_PER_KM}
                     = {fuel_trip_L:.2f} L/trip

      Fuel (L/yr)    = Fuel (L/trip) × trips/yr
                     = {fuel_trip_L:.2f} × {trips_yr:,.0f}
                     = {tot_fuel_L:,.1f} L/yr

      CO2 (kg/yr)    = Fuel (L/yr) × {DIESEL_CO2} kg CO2/L  (GREET 2025 — carbon balance)
                     = {tot_fuel_L:,.1f} × {DIESEL_CO2}
                     = {co2:,.2f} kg CO2/yr

      CH4 (kg/yr)    = Fuel (L/yr) × {DIESEL_CH4_ONROAD} kg CH4/L  (GREET 2025 Long-Haul Truck)
                     = {tot_fuel_L:,.1f} × {DIESEL_CH4_ONROAD}
                     = {ch4:.4f} kg CH4/yr

      N2O (kg/yr)    = Fuel (L/yr) × {DIESEL_N2O_ONROAD} kg N2O/L  (GREET 2025 Long-Haul Truck)
                     = {tot_fuel_L:,.1f} × {DIESEL_N2O_ONROAD}
                     = {n2o:.4f} kg N2O/yr

      GWI (kg CO2e)  = CO2×{GWP_CO2} + CH4×{GWP_CH4} + N2O×{GWP_N2O}
""")

        print(f'    {"Gas":<8} {"Mass emitted (kg/yr)":>22} {"GWP100":>8} {"GWI (kg CO2e/yr)":>20}')
        print(f'    {"-"*62}')
        print(f'    {"CO2":<8} {co2:>22,.2f} {"× "+str(GWP_CO2):>8} {gwi_co2:>20,.2f}')
        print(f'    {"CH4":<8} {ch4:>22.4f} {"× "+str(GWP_CH4):>8} {gwi_ch4:>20.4f}')
        print(f'    {"N2O":<8} {n2o:>22.4f} {"× "+str(GWP_N2O):>8} {gwi_n2o:>20.4f}')
        print(f'    {"-"*62}')
        print(f'    {"TOTAL GWI":<31}          {gwi:>20,.2f}  kg CO2e/year')
        print(f'    GWI per OD kg (total res.) :           {gwi/total_kg:>20.6f}  kg CO2e/OD kg')

        results[key] = dict(
            label=label,
            res_kg=res_kg,
            dist=dist_km,
            trips=trips_yr,
            fuel=tot_fuel_L,
            CO2=co2,
            CH4=ch4,
            N2O=n2o,
            GWI=gwi,
            GWI_kg=gwi / total_kg,
        )

    # ── Summary comparison ────────────────────────────────────────────────────
    sub('Phase 2 Summary — Comparison Across Cases')
    print(f'  {"Case":<48} {"GWI (kg CO2e/yr)":>18} {"GWI/OD kg":>16}')
    print(f'  {"-"*84}')
    for k in ['saf']:
        r = results[k]
        short_label = 'Case 1 — Forest → SAF Plant (HQ only)' if k == 'saf' \
                      else 'Case 2 — Forest → Bioenergy (ALL residue)'
        print(f'  {short_label:<48} {r["GWI"]:>18,.2f} {r["GWI_kg"]:>16.6f}')

    return results


# =============================================================================
# CHART HELPERS
# =============================================================================
def _gas_legend(ax):
    """Compact shared gas-color legend for GWI gas-wise plots."""
    handles = [
        mpatches.Patch(color=C_CO2, label=f'GWI_CO₂  (×GWP {GWP_CO2})'),
        mpatches.Patch(color=C_CH4, label=f'GWI_CH₄  (×GWP {GWP_CH4})'),
        mpatches.Patch(color=C_N2O, label=f'GWI_N₂O  (×GWP {GWP_N2O})'),
    ]
    leg = ax.legend(handles=handles, loc='lower right', fontsize=_FS_TICK,
                   facecolor=_BG, edgecolor=_SPINE)
    for t in leg.get_texts(): t.set_color(_TEXT)


# ── Dark theme ───────────────────────────────────────────────────────────────
_BG     = "#0e1621"; _BG_AX = "#131f2e"; _GRID = "#1e2d3d"
_TEXT   = "#c9d1e0"; _TEXT_DIM = "#4a5a6a"; _SPINE = "#1e2d3d"
_FS_TITLE = 14; _FS_LABEL = 12; _FS_TICK = 11; _FS_ANNOT = 10

def style_axis(ax, ylabel=None, title=None, xticks=None, xticklabels=None,
               rotation=0, ha='center', grid_axis='y'):
    """Apply dark dashboard styling to an axis."""
    ax.set_facecolor(_BG_AX)
    ax.spines[["top","right"]].set_visible(False)
    ax.spines[["left","bottom"]].set_color(_SPINE)
    ax.tick_params(colors=_TEXT, labelsize=_FS_TICK)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color(_TEXT)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=_FS_LABEL, color=_TEXT)
    if title:
        ax.set_title(title, fontsize=_FS_TITLE, fontweight='bold', color=_TEXT)
    if xticks is not None:
        ax.set_xticks(xticks)
    if xticklabels is not None:
        ax.set_xticklabels(xticklabels, fontsize=_FS_TICK, rotation=rotation,
                           ha=ha, color=_TEXT)
    ax.grid(axis=grid_axis, linestyle='--', linewidth=0.5, color=_GRID)
    ax.set_axisbelow(True)


def add_phase_footer(fig, text, y=-0.01, fontsize=8.5, color=_TEXT_DIM, fontweight=None):
    """Add a centered italic footer below a chart."""
    fig.text(0.5, y, text, ha='center', fontsize=fontsize, color=color,
             fontweight=fontweight,
             style='italic' if fontweight is None else 'normal')


def ensure_plot_output_dir():
    os.makedirs(PLOTS_OUTPUT_DIR, exist_ok=True)
    return PLOTS_OUTPUT_DIR


def save_phase_figure(fig, filename, dpi=300):
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    # If this file lives inside LCA_dependencies/, save to the parent's LCA_plots/
    parent_dir = os.path.dirname(SCRIPT_DIR)
    parent_lca = os.path.join(parent_dir, "LCA_plots")
    if os.path.isdir(parent_lca):
        output_dir = parent_lca
    else:
        output_dir = os.path.join(SCRIPT_DIR, "LCA_plots")
    os.makedirs(output_dir, exist_ok=True)
    file_path  = os.path.join(output_dir, filename)
    fig.savefig(file_path, dpi=dpi, bbox_inches='tight')
    plt.close(fig)
    print(f'  Saved → {file_path}')
    return file_path


# =============================================================================
# PLOT: PHASE 2 TRANSPORT
# =============================================================================
def plot_transport(t, total_kg):
    keys   = ['saf']
    # Short x-axis labels — no need for full sentences
    cases = ['Processing Plant']
    # cases  = ['SAF Plant\n(HQ only)', 'Bioenergy\n(All residue)']
    pclrs  = [C_CO2, C_CH4, C_N2O]

    co2_v  = [t[k]['CO2']           for k in keys]
    ch4_v  = [t[k]['CH4'] * GWP_CH4 for k in keys]
    n2o_v  = [t[k]['N2O'] * GWP_N2O for k in keys]
    gwi_v  = [t[k]['GWI']           for k in keys]
    fuel_v = [t[k]['fuel']          for k in keys]
    trip_v = [t[k]['trips']         for k in keys]
    dist_v = [t[k]['dist']          for k in keys]

    fig, ax = plt.subplots(figsize=(14, 5.5))
    fig.patch.set_facecolor(_BG)
    # Single-line title — concise
    fig.suptitle('Transport GHG Emissions  |  Heavy-Duty Diesel Truck  |  GREET 2025',
                 fontsize=_FS_TITLE, fontweight='bold', color=_TEXT, y=0.98)

    x  = np.arange(1)
    w  = 0.45
    w3 = 0.25

    # ── Panel 1: Gas-wise GWI ─────────────────────────────────────────────────
    # ax = axes[0]
    ax.bar(x - w3, co2_v, w3, label=f'CO₂  (GWP {GWP_CO2})',
           color=C_CO2, edgecolor='none')
    ax.bar(x,      ch4_v, w3, label=f'CH₄  (GWP {GWP_CH4})',
           color=C_CH4, edgecolor='none')
    ax.bar(x + w3, n2o_v, w3, label=f'N₂O  (GWP {GWP_N2O})',
           color=C_N2O, edgecolor='none')
    for xi, v in zip(x - w3, co2_v):
        ax.text(xi, v * 1.02, f'{v:,.0f}', ha='center',
                fontsize=_FS_ANNOT, fontweight='bold', color=_TEXT)
    style_axis(ax, ylabel='GWI (kg CO₂e / yr)', title='Gas-Wise GWI',
               xticks=x, xticklabels=cases)
    _gas_legend(ax)

    # ── Panel 2: Total GWI ────────────────────────────────────────────────────
    # Inside plot_transport function, Panel 1
    # ax = axes[0]
    # # Use divide by 1000 here as well to show Tons in the plot
    # ax.bar(x - w3, [v / 1000 for v in co2_v], w3, label='CO2', color=C_CO2)
    # ax.bar(x,      [v / 1000 for v in ch4_v], w3, label='CH4 (CO2e)', color=C_CH4)
    # ax.bar(x + w3, [v / 1000 for v in n2o_v], w3, label='N2O (CO2e)', color=C_N2O)
    # ax = axes[1]
    # bars = ax.bar(x, gwi_v, w, color=pclrs, edgecolor='none')
    # for b, v, d in zip(bars, gwi_v, dist_v):
    #     ax.text(b.get_x() + b.get_width()/2, v * 1.02,
    #             f'{v:,.0f}', ha='center', fontsize=_FS_ANNOT, fontweight='bold', color=_TEXT)
    #     ax.text(b.get_x() + b.get_width()/2, v * 0.50,
    #             f'{d:.0f} km', ha='center', fontsize=_FS_ANNOT, color=_TEXT, fontweight='bold')
    # style_axis(ax, ylabel='Total GWI (kg CO₂e / yr)', title='Total GWI by Case',
    #            xticks=x, xticklabels=cases)
    # leg = ax.legend(handles=[mpatches.Patch(color=C_HQ, label='→ SAF Plant'),
    #                           mpatches.Patch(color=C_LQ, label='→ Bioenergy')],
    #                 fontsize=_FS_TICK, facecolor=_BG, edgecolor=_SPINE)
    # for t in leg.get_texts(): t.set_color(_TEXT)

    # # ── Panel 3: Diesel & Trips ───────────────────────────────────────────────
    # ax = axes[2]
    # bars2 = ax.bar(x, fuel_v, w, color=pclrs, edgecolor='none')
    # for b, fv, tv in zip(bars2, fuel_v, trip_v):
    #     ax.text(b.get_x() + b.get_width()/2, fv * 1.02,
    #             f'{fv:,.0f} L', ha='center', fontsize=_FS_ANNOT, fontweight='bold', color=_TEXT)
    #     ax.text(b.get_x() + b.get_width()/2, fv * 0.50,
    #             f'{tv:,.0f} trips/yr', ha='center', fontsize=_FS_ANNOT, color=_TEXT)
    # style_axis(ax, ylabel='Diesel Consumed (L / yr)', title='Diesel & Truck Trips',
    #            xticks=x, xticklabels=cases)
    # leg = ax.legend(handles=[mpatches.Patch(color=C_HQ, label='→ SAF Plant'),
    #                           mpatches.Patch(color=C_LQ, label='→ Bioenergy')],
    #                 fontsize=_FS_TICK, facecolor=_BG, edgecolor=_SPINE)
    # for t in leg.get_texts(): t.set_color(_TEXT)

    plt.tight_layout()
    save_phase_figure(fig, 'phase2_transport.png')


# =============================================================================
# MAIN
# =============================================================================
def main():
    ensure_plot_output_dir()
    print(f'\nPlots will be saved in: {PLOTS_OUTPUT_DIR}\n')

    # ── Run transport phase ───────────────────────────────────────────────────
    t = phase2_transport(
        total_kg = TOTAL_RESIDUE_OD_KG,
        # hq_frac  = HIGH_QUALITY_FRACTION,
        dist_saf = DIST,
        # dist_bio = DIST_TO_BIOENERGY_KM,
    )

    # ── Print standalone summary table ───────────────────────────────────────
    hdr('TRANSPORT PHASE — STANDALONE SUMMARY')
    saf = t['saf']
    # bio = t['bio']

    # Summary Table - Single Case (Tons)
    print(f"""
            ┌─────────────────────────────────────────────────────────────────────────┐
            │  PHASE 2: TRANSPORT GWI  (kg CO2e per OD kg total residue)              │
            ├───────────────────────────────────────────┬─────────────────────────────┤
            │  Parameter                                │           Case 1            │
            │                                           │           → Plant           │
            ├───────────────────────────────────────────┼─────────────────────────────┤
            │  Residue transported (OD kg/yr)           │{saf["res_kg"]:>24,.0f}     │
            │  One-way distance (km)                    │{saf["dist"]:>24.1f}     │
            │  Truck trips/yr (one-way loads)           │{saf["trips"]:>24,.0f}     │
            │  Total diesel consumed (L/yr)             │{saf["fuel"]:>24,.1f}     │
            ├───────────────────────────────────────────┼─────────────────────────────┤
            │  CO2 emitted (t CO2e/yr)                  │{saf["CO2"]/1000:>24,.2f}     │
            │  CH4 emitted (t CO2e/yr)                  │{(saf["CH4"]*GWP_CH4)/1000:>24,.2f}     │
            │  N2O emitted (t CO2e/yr)                  │{(saf["N2O"]*GWP_N2O)/1000:>24,.2f}     │
            ├───────────────────────────────────────────┼─────────────────────────────┤
            │  Total GWI  (t CO2e/yr)                   │{saf["GWI"]/1000:>24,.2f}     │
            │  GWI per OD kg residue  (kg CO2e/OD kg)  │{saf["GWI_kg"]:>24.6f}     │
            └───────────────────────────────────────────┴─────────────────────────────┘
            """)
    # ── Generate plot ─────────────────────────────────────────────────────────
    print('=' * 72)
    print('  GENERATING TRANSPORT CHART')
    print('=' * 72)
    plot_transport(t, TOTAL_RESIDUE_OD_KG)

    print('\n  Phase 2 Transport — complete.\n')


if __name__ == '__main__':
    main()