"""
=============================================================================
GREEN TEA LCA — AVOIDED EMISSIONS ANALYSIS
=============================================================================
Outputs
  1. Avoided Emissions — lifecycle non-biogenic GHG vs two baselines:
       (a) Open pile burning baseline        — Khatri et al. (2025) [R1]
       (b) Fossil fuel production (all liquid co-products) — CA-GREET4.0 [R7]

GHG scope  : Non-biogenic only — fossil CO2, CH4 CO2e, N2O CO2e
             Biogenic CO2 excluded per IPCC (2006) Sec 2.2 / RED II [R6]
GWP100     : CH4 = 27.9, N2O = 273  (IPCC AR6) [R4]

References
  [R1]  Khatri et al. (2025) USDA FPL — cradle-to-grave LCA forest residues
        https://www.fpl.fs.usda.gov/documnts/pdf2025/fpl_2025_khatri002.pdf
  [R2]  Springsteen et al. (2011) J. Air Waste Manag. Assoc. 61(1):63-68
        doi:10.3155/1047-3289.61.1.63
  [R4]  IPCC AR6 (2021) Ch.7 — GWP100: CH4=27.9, N2O=273
  [R5]  IPCC (2006) Vol.2 Ch.2 — biogenic CO2 accounting framework
  [R6]  Sahoo et al. (2019) Biofuels Bioprod. Bioref. 13:514-534
        Truck payload (Table 3), fuel economy (Table 3)
  [R7]  California Air Resources Board — CA-GREET4.0 (2024)
        LCFS Life Cycle Analysis, Conventional Jet Fuel lookup table
        Cradle-to-gate CI = 15.93 g CO2e/MJ (LHV, AR5 GWP100)
        https://ww2.arb.ca.gov/resources/documents/lcfs-life-cycle-analysis-models-and-documentation
=============================================================================
"""

import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import sys
import numpy as np

# Phase script imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import LCA_dependencies.Biomass_processing as PROC
import LCA_dependencies.Biomass_transport_LCA        as TRANS
import LCA_dependencies.SAF_production_LCA         as SAF
import LCA_dependencies.Bioenergy_production_LCA   as BIO

# =============================================================================
# OUTPUT DIRECTORY
# =============================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Save to project root LCA_plots/ (one level above LCA_dependencies/)
OUTPUT_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'LCA_plots')
os.makedirs(OUTPUT_DIR, exist_ok=True)


# =============================================================================
# USER INPUTS — match values used across phase scripts
# =============================================================================
BIOMASS_ODT_YR   = 100_000   # total oven-dry tonnes/yr entering the supply chain
HQ_FRACTION      = 0.40      # fraction of total → SAF plant (high-quality residue)
LQ_FRACTION      = 0.60      # fraction of total → Bioenergy plant (low-quality residue)
MOISTURE_PCT     = 40        # % wet-basis moisture entering the bioenergy boiler

DIST_SAF_KM      = 161.0     # one-way distance, forest → SAF plant (km) [Khatri 2025; Sahoo 2019]
DIST_BIO_KM      = 100.0     # one-way distance, forest → Bioenergy plant (km)
TRUCK_PAYLOAD_KG = 20_000    # OD kg per truck load [R9, Table 3]
TRUCK_L_PER_KM   = 0.32      # fuel economy, L/km [R9, Table 3]



# =============================================================================
# GWP100 — IPCC AR6 [R6]
# =============================================================================
GWP_CH4 = 27.9
GWP_N2O = 273.0


# =============================================================================
# BASELINES
# =============================================================================
# Open pile burning GWI — Khatri et al. (2025) Table 2 [R1]
OPEN_BURN_KG_CO2E_PER_KG    = 0.143   # kg CO2e / kg OD residue

# Fossil jet fuel production-phase carbon intensity — cradle-to-gate
# Scope  : crude extraction + transport + refining only (no combustion)
# Value  : CA-GREET4.0 (CARB LCFS, 2024) cradle-to-gate = 15.93 g CO2e/MJ
#          Consistent with ICAO CORSIA-implied WTT of ~15 g CO2e/MJ
#          and Jing et al. (2022) Nature Communications global average ~14.9
# Rationale: FHR SAF GHG covers plant-gate production only (no combustion),
#          so the fossil comparator must use the same boundary. The full WTW
#          value (84–89 g CO2e/MJ) embeds ~73 g CO2e/MJ of combustion that
#          has no counterpart in a plant-gate SAF model.
FOSSIL_JF_CI_G_CO2E_PER_MJ  = 15.93   # g CO2e / MJ  [CA-GREET4.0, CARB LCFS 2024]


# =============================================================================
# NOTE ON EMISSION FACTORS
# =============================================================================
# All emission factors (CO2, CH4, N2O) are sourced directly from the phase
# scripts via import. The FHR does not re-derive any emission factors
# internally. See each phase script for full citations:
#   Biomass_processing_vfinal.py  — GREET 2025, IPCC 2006 Table 3.3.1
#   LCA_Transport_Only.py         — GREET 2025 HDV Long-Haul Truck
#   SAF_production_v2.py          — GREET R&D 2025 JetFuel_WTP FT col 96
#   Bioenergy_production_v3.py    — IPCC 2006 Table 2.5


# =============================================================================
# HELPER
# =============================================================================
def _hdr(title):
    print('\n' + '═' * 72)
    print(f'  {title}')
    print('═' * 72)

def _sub(title):
    print(f'\n  ── {title} ──')


# =============================================================================
# PHASE CALCULATIONS
# =============================================================================

def calc_processing():
    """
    Processing phase non-biogenic GHG.
    Source  : Biomass_processing_vfinal.py → calculate_one(BIOMASS_ODT_YR, '1.1')
    Uses mid-point of FC range for option 1.1 (disc chip at landing).
    CO2, CH4, N2O values read directly from phase script output — no EFs
    are re-derived here. Pathway split applied to total by mass fraction.
    """
    r     = PROC.calculate_one(BIOMASS_ODT_YR, '1.1')
    mid   = r['mid']
    total = mid['total']

    return {
        'CO2_t':    mid['CO2_t'],
        'CH4_CO2e': mid['CH4_CO2e'],
        'N2O_CO2e': mid['N2O_CO2e'],
        'total':    total,
        'saf':      total * HQ_FRACTION,   # allocated to SAF pathway
        'bio':      total * LQ_FRACTION,   # allocated to Bioenergy pathway
    }


def calc_transport():
    """
    Transport phase GHG.
    Source  : LCA_Transport_Only.py → phase2_transport()
    SAF     : HQ fraction only → SAF plant (DIST_SAF_KM, one-way loaded)
    Bio     : LQ fraction only → Bioenergy (DIST_BIO_KM, one-way loaded)
    CO2, CH4, N2O values read directly from phase script output.
    TRUCK_L_PER_KM patched to FHR value before calling; restored after.
    """
    _orig_fe          = TRANS.TRUCK_L_PER_KM
    TRANS.TRUCK_L_PER_KM = TRUCK_L_PER_KM          # patch to updated FHR value

    saf_res_kg = BIOMASS_ODT_YR * HQ_FRACTION * 1000
    bio_res_kg = BIOMASS_ODT_YR * LQ_FRACTION * 1000

    import io, contextlib
    _buf = io.StringIO()
    with contextlib.redirect_stdout(_buf):
        t_saf = TRANS.phase2_transport(saf_res_kg, 1.0, DIST_SAF_KM, DIST_BIO_KM)
        t_bio = TRANS.phase2_transport(bio_res_kg, 0.0, DIST_SAF_KM, DIST_BIO_KM)

    TRANS.TRUCK_L_PER_KM = _orig_fe                # restore original

    def _parse(t, key):
        """Convert TRANS output from kg → t and build standard dict."""
        return {
            'CO2_t':    t[key]['CO2']            / 1000,
            'CH4_CO2e': t[key]['CH4'] * GWP_CH4 / 1000,
            'N2O_CO2e': t[key]['N2O'] * GWP_N2O / 1000,
            'total':    t[key]['GWI']            / 1000,
            'fuel_L':   t[key]['fuel'],
            'trips':    t[key]['trips'],
        }

    return {
        'saf': _parse(t_saf, 'saf'),
        'bio': _parse(t_bio, 'bio'),
    }


def calc_saf_production():
    """
    SAF production non-biogenic GHG — plant gate only, no supply chain.
    Source  : SAF_production_LCA.py → calc() at full plant scale.
    Scope   : fossil CO2 + CH4 CO2e + N2O CO2e.  Biogenic CO2 excluded [R8].

    The SAF plant receives ALL residue (HQ + LQ from all sources) and produces
    SAF, diesel, and naphtha as co-products. The module defaults (biomass_odt_yr,
    saf_L_yr, etc.) already represent the full plant — no HQ_FRACTION scaling.
    SAF_MJ is the full plant SAF energy output, used as the basis for the
    fossil JF avoided emissions comparison (same MJ of jet fuel, produced from
    petroleum instead).
    """
    I      = SAF.INPUTS
    shared = {k: I[k] for k in [
        'biomass_odt_yr', 'c_liquid', 'lhv_saf',
        'saf_L_yr', 'diesel_L_yr', 'naphtha_L_yr',
        'rho_saf', 'rho_diesel', 'rho_naphtha', 'almena_pct',
        'greet_ng_btu', 'greet_biomass_feed_loss_btu',
        'ef_ng_co2', 'ef_ng_ch4', 'ef_ng_n2o',
        'ef_fr_gasifier_ch4', 'ef_fr_gasifier_n2o',
        'lhv_saf_btu_per_gal', 'gwp_ch4', 'gwp_n2o',
    ]}
    r = SAF.calc(cf=I['cf_forest'], **shared)

    return {
        'fossCO2_t':  r['fossCO2_t'],
        'CH4_CO2e_t': r['CH4_CO2e_t'],
        'N2O_CO2e_t': r['N2O_CO2e_t'],
        'total':      r['fossCO2_t'] + r['CH4_CO2e_t'] + r['N2O_CO2e_t'],
        'SAF_MJ':     r['SAF_MJ_yr'],
        'saf_L':      I['saf_L_yr'],
    }


def calc_bio_production():
    """
    Bioenergy production non-biogenic GHG.
    Source  : Bioenergy_production_v3.py → calculate_one_option() at LQ biomass.
    Scope   : CH4 CO2e + N2O CO2e only (IPCC 2006 Table 2.5 EFs).
    Biogenic CO2 excluded per IPCC (2006) Sec 2.2 / RED II [R8].
    NOTE: The phase script carries two CH4 EF sets (IPCC and GREET). FHR reads
    CH4_CO2e_t_yr (IPCC 30 g/GJ) + N2O_CO2e_t_yr (IPCC 4 g/GJ) for consistency.
    """
    bio_odt = int(BIOMASS_ODT_YR * LQ_FRACTION)
    import io, contextlib
    _buf = io.StringIO()
    with contextlib.redirect_stdout(_buf):
        r = BIO.calculate_one_option(bio_odt, 'forest', '1.1',
                                     moisture_pct_override=MOISTURE_PCT)
    return {
        'CH4_CO2e': r['CH4_CO2e_t_yr'],
        'N2O_CO2e': r['N2O_CO2e_t_yr'],
        'total':    r['CH4_CO2e_t_yr'] + r['N2O_CO2e_t_yr'],
        'heat_GJ':  r['heat_GJ_yr'],
    }



def calc_baselines(SAF_MJ):
    """
    Two comparison baselines for net climate impact.

    (a) Open pile burning — same OD biomass, if pile-burned instead of utilized.
        EF: 0.143 kg CO2e/kg OD residue [R1] Khatri et al. (2025) Table 2.

    (b) Fossil jet fuel production phase — same energy output, if produced
        from conventional petroleum (cradle-to-gate, no combustion).
        CI: 15.93 g CO2e/MJ [CA-GREET4.0, CARB LCFS 2024; CORSIA ~15 g CO2e/MJ]
        Scope: crude extraction + transport + refining only.
        This matches the SAF plant-gate boundary used in the FHR model.
        Full WTW value (~84–89 g CO2e/MJ) is NOT used because it embeds
        ~73 g CO2e/MJ of combustion that is outside the SAF scope here.
    """
    open_burn = (BIOMASS_ODT_YR * 1000 * OPEN_BURN_KG_CO2E_PER_KG) / 1000  # tCO2e/yr
    fossil_jf = FOSSIL_JF_CI_G_CO2E_PER_MJ * SAF_MJ / 1e6                  # tCO2e/yr
    return {'open_burn': open_burn, 'fossil_jf': fossil_jf}


def calc_lifecycle(proc, transp, saf_prod, bio_prod):
    """
    Aggregate lifecycle non-biogenic GHG across all phases.

    In the standalone module, all residue goes through processing and transport
    (split between SAF and bioenergy paths), then through the respective
    production plants. Since the SAF plant processes all incoming biomass,
    lc["saf"] uses the combined processing + transport + full SAF production.
    lc["bio"] covers the bioenergy path only.
    lc["combined"] is the total across both paths.
    """
    saf_total  = proc['total'] + transp['saf']['total'] + transp['bio']['total'] + saf_prod['total']
    bio_total  = bio_prod['total']
    combined   = proc['total'] + transp['saf']['total'] + transp['bio']['total'] + saf_prod['total'] + bio_prod['total']
    return {'saf': saf_total, 'bio': bio_total, 'combined': combined}


# =============================================================================
# TERMINAL REPORT
# =============================================================================

def print_report(proc, transp, saf_prod, bio_prod, baselines, lc):

    # column widths used throughout
    W_PARAM  = 26   # parameter label
    W_VAL    = 14   # value
    W_PHASE  = 52   # phase label  (longest: "Transport — GREET 2025 HDV, Sahoo 2019  [R7, R9]" = 49)
    W_NUM    = 12   # numeric columns in phase table
    W_SCEN   = 44   # scenario label in climate impact table
    W_IMPACT = 12   # value column in climate impact table
    W_WF     = 12   # retained for formatting consistency
    W_EF     = 20
    W_AVD    = 20
    DIV_MAIN = W_PHASE + (W_NUM + 1) * 3
    DIV_CLIM = W_SCEN + W_IMPACT + 2 + 26

    _hdr('AVOIDED EMISSIONS ANALYSIS — GREEN TEA LCA')
    print(f'  {"Biomass throughput":<{W_PARAM}} {BIOMASS_ODT_YR:>{W_VAL},.0f}  odt/yr')
    print(f'  {"SAF pathway (HQ)":<{W_PARAM}} {HQ_FRACTION*100:.0f}%  '
          f'→ {BIOMASS_ODT_YR*HQ_FRACTION:,.0f} odt/yr  |  {DIST_SAF_KM:.0f} km to plant')
    print(f'  {"Bioenergy pathway (LQ)":<{W_PARAM}} {LQ_FRACTION*100:.0f}%  '
          f'→ {BIOMASS_ODT_YR*LQ_FRACTION:,.0f} odt/yr  |  {DIST_BIO_KM:.0f} km to plant')
    print(f'  {"GHG scope":<{W_PARAM}} Non-biogenic only  (fossil CO2, CH4 CO2e, N2O CO2e)')
    print(f'  {"Biogenic CO2":<{W_PARAM}} Excluded — IPCC (2006) Sec 2.2 / RED II  [R8]')
    print(f'  {"GWP100 (IPCC AR6)":<{W_PARAM}} CH4 = {GWP_CH4}   N2O = {GWP_N2O}  [R6]')

    # ── Phase-by-phase breakdown ──────────────────────────────────────────────
    _sub('PHASE-BY-PHASE BREAKDOWN  (tCO2e/yr, non-biogenic)')
    print(f'  {"Phase":<{W_PHASE}} {"SAF (40%)":>{W_NUM}} {"Bio (60%)":>{W_NUM}} {"Combined":>{W_NUM}}')
    print('  ' + '─' * DIV_MAIN)
    print(f'  {"Processing — option 1.1 mid FC  [R9, IPCC 2006]":<{W_PHASE}}'
          f' {proc["saf"]:>{W_NUM},.1f}'
          f' {proc["bio"]:>{W_NUM},.1f}'
          f' {proc["total"]:>{W_NUM},.1f}')
    print(f'  {"Transport — GREET 2025 HDV, Sahoo 2019  [R7, R9]":<{W_PHASE}}'
          f' {transp["saf"]["total"]:>{W_NUM},.2f}'
          f' {transp["bio"]["total"]:>{W_NUM},.2f}'
          f' {transp["saf"]["total"]+transp["bio"]["total"]:>{W_NUM},.2f}')
    print(f'  {"Production — GREET 2025 / IPCC 2006  [R7, R8]":<{W_PHASE}}'
          f' {saf_prod["total"]:>{W_NUM},.2f}'
          f' {bio_prod["total"]:>{W_NUM},.2f}'
          f' {saf_prod["total"]+bio_prod["total"]:>{W_NUM},.2f}')
    print('  ' + '─' * DIV_MAIN)
    print(f'  {"TOTAL LIFECYCLE GHG":<{W_PHASE}}'
          f' {lc["saf"]:>{W_NUM},.1f}'
          f' {lc["bio"]:>{W_NUM},.1f}'
          f' {lc["combined"]:>{W_NUM},.1f}')

    # ── Baseline methodology notes ────────────────────────────────────────────
    _sub('FOSSIL JET FUEL BASELINE — METHODOLOGY NOTE')

    W_N = 72   # note line width


    print(f'\n  ┌─ (b) FOSSIL JET FUEL BASELINE ────────────────────────────────────────┐')
    print(f'  │  Factor    : {FOSSIL_JF_CI_G_CO2E_PER_MJ} g CO2e / MJ (LHV basis)                           │')
    print(f'  │  Source    : CA-GREET4.0, CARB LCFS (2024)  [R7]                        │')
    print(f'  │  Scope     : Cradle-to-gate ONLY — crude extraction + transport +        │')
    print(f'  │              refining. Combustion (tank-to-wake) is EXCLUDED.            │')
    print(f'  │  Breakdown : Crude recovery + transport  12.61 g CO2e/MJ (79%)          │')
    print(f'  │              Refining                     3.32 g CO2e/MJ (21%)          │')
    print(f'  │              Distribution                 0.29 g CO2e/MJ  (2%)          │')
    print(f'  │              Total cradle-to-gate        15.93 g CO2e/MJ               │')
    print(f'  │  GWP basis : IPCC AR5                                                    │')
    print(f'  │  Why not   : Full WTW (84–89 g CO2e/MJ) includes ~73 g CO2e/MJ of      │')
    print(f'  │  84 g/MJ?    combustion that has no counterpart in a plant-gate SAF     │')
    print(f'  │              model. Comparing production-only SAF against a WTW fossil  │')
    print(f'  │              baseline inflates the apparent reduction to ~99% — a        │')
    print(f'  │              scope mismatch. Cradle-to-gate gives the fair comparison.   │')
    print(f'  │  Literature: ICAO CORSIA implied WTT: ~15.0 g CO2e/MJ                  │')
    print(f'  │              Jing et al. (2022) Nature Comms global avg: ~14.9          │')
    print(f'  │              NETL Petroleum Baseline (2008): 14.3 g CO2e/MJ             │')
    print(f'  │              GREET R&D (US-specific): ~11–13 g CO2e/MJ                  │')
    print(f'  └───────────────────────────────────────────────────────────────────────────┘')

    # ── Net climate impact ────────────────────────────────────────────────────
    _sub('NET CLIMATE IMPACT  (tCO2e/yr)')
    print(f'  {"Scenario":<{W_SCEN}} {"tCO2e/yr":>{W_IMPACT}}  {"Source"}')
    print('  ' + '─' * DIV_CLIM)
    print(f'  {"(a) Open pile burning  [Khatri 2025, R1]":<{W_SCEN}}'
          f' {baselines["open_burn"]:>{W_IMPACT},.1f}  open pile burning baseline')
    print(f'  {"(b) Fossil JF — production phase  [CA-GREET4.0]":<{W_SCEN}}'
          f' {baselines["fossil_jf"]:>{W_IMPACT},.1f}  cradle-to-gate, no combustion')
    print(f'  {"This project — combined lifecycle GHG":<{W_SCEN}}'
          f' {lc["combined"]:>{W_IMPACT},.1f}  non-biogenic, all phases')
    print('  ' + '─' * DIV_CLIM)

    avd_burn = baselines['open_burn'] - lc['combined']
    avd_jf   = baselines['fossil_jf'] - lc['combined']
    pct_burn = avd_burn / baselines['open_burn'] * 100
    pct_jf   = avd_jf  / baselines['fossil_jf']  * 100

    print(f'\n  {"Avoided vs open burning":<{W_SCEN}} {avd_burn:>{W_IMPACT},.1f}  '
          f'({pct_burn:.1f}% reduction)  [R1, R2]')
    print(f'  {"Avoided vs fossil JF production":<{W_SCEN}} {avd_jf:>{W_IMPACT},.1f}  '
          f'({pct_jf:.1f}% reduction)  [CA-GREET4.0]')

    print(f'\n  NOTE: Fossil JF comparison: same MJ of SAF from petroleum vs this project.')
    print(f'  Scope: production phase only (no combustion) — CA-GREET4.0 cradle-to-gate')
    print(f'  {"This project lifecycle GHG":<{W_SCEN}} {lc["combined"]:>{W_IMPACT},.1f}  tCO2e/yr')
    print(f'  {"Equiv. fossil JF production GHG":<{W_SCEN}} {baselines["fossil_jf"]:>{W_IMPACT},.1f}  tCO2e/yr')


# =============================================================================
# CHARTS

# =============================================================================
# CHARTS
# =============================================================================
# Colour palette — consistent with other phase scripts
C_SAF    = '#1d3557'   # navy          — SAF pathway
C_BIO    = '#457b9d'   # steel blue    — Bioenergy pathway
C_COMB   = '#2a9d8f'   # teal          — combined lifecycle
C_BURN   = '#e76f51'   # burnt orange  — open burning baseline
C_FOSSIL = '#264653'   # dark slate    — fossil jet fuel baseline


def _style_ax(ax):
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='y', color='#ddd', linewidth=0.6, zorder=0)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f'{v:,.0f}'))


def plot_net_climate_impact(lc, baselines, outdir):
    """
    Panel 1 — GHG side-by-side: open burning | fossil JF | this project (combined)
    Panel 2 — Avoided GHG: vs open burning (all residue) and vs fossil JF (full lifecycle)
    """
    fig, axes = plt.subplots(1, 2, figsize=(15, 7))
    fig.suptitle(
        'AVOIDED EMISSIONS ANALYSIS — Lifecycle GHG vs Baselines\n'
        'Non-biogenic GHG only (fossil CO₂ + CH₄ + N₂O as CO₂e)  |  '
        'Biogenic CO₂ excluded per IPCC (2006) Sec 2.2 / RED II  |  GWP100 IPCC AR6',
        fontsize=11, fontweight='bold', y=1.01
    )

    # ── Panel 1: GHG comparison ───────────────────────────────────────────────
    ax = axes[0]
    labels1 = [
        'Open Pile\nBurning\n(baseline)',
        'Fossil Jet Fuel\n(production phase\ncradle-to-gate)',
        'This Project\n(combined lifecycle\nnon-biogenic GHG)',
    ]
    vals1  = [baselines['open_burn'], baselines['fossil_jf'], lc['combined']]
    cols1  = [C_BURN, C_FOSSIL, C_COMB]

    bars1 = ax.bar(range(3), vals1, color=cols1, width=0.52,
                   edgecolor='white', linewidth=0.8, zorder=3)
    for b, v in zip(bars1, vals1):
        ax.text(b.get_x() + b.get_width() / 2, v + max(vals1) * 0.015,
                f'{v:,.0f}', ha='center', fontsize=9, fontweight='bold')

    ax.set_xticks(range(3))
    ax.set_xticklabels(labels1, fontsize=9)
    ax.set_ylabel('GHG Emissions (tCO₂e / yr)', fontsize=11)
    ax.set_title(
        'GHG Comparison vs Baselines\n[Khatri et al. 2025, R1]',
        fontsize=10, fontweight='bold'
    )
    ax.legend(handles=[
        mpatches.Patch(color=C_BURN,   label='Open pile burning baseline [R1]'),
        mpatches.Patch(color=C_FOSSIL, label='Fossil JF — production phase [CA-GREET4.0]'),
        mpatches.Patch(color=C_COMB,   label='This project — lifecycle non-biogenic GHG'),
    ], fontsize=8, loc='upper right', framealpha=0.85)
    _style_ax(ax)

    # ── Panel 2: Avoided emissions ────────────────────────────────────────────
    ax2 = axes[1]
    avd_burn = baselines['open_burn'] - lc['combined']
    avd_jf   = baselines['fossil_jf'] - lc['combined']
    pct_burn = avd_burn / baselines['open_burn'] * 100
    pct_jf   = avd_jf  / baselines['fossil_jf']  * 100

    labels2 = [
        'Avoided vs\nOpen Burning\n(all residue, all pathways)',
        'Avoided vs\nFossil Fuel Production\n(same MJ SAF from petroleum)',
    ]
    vals2 = [avd_burn, avd_jf]
    cols2 = [C_BURN, C_FOSSIL]
    pcts  = [pct_burn, pct_jf]

    bars2 = ax2.bar(range(2), vals2, color=cols2, width=0.42,
                    edgecolor='white', linewidth=0.8, zorder=3)
    for b, v, p in zip(bars2, vals2, pcts):
        ax2.text(b.get_x() + b.get_width() / 2, v + max(vals2) * 0.015,
                 f'{v:,.0f}\n({p:.1f}% reduction)',
                 ha='center', fontsize=9, fontweight='bold')

    ax2.set_xticks(range(2))
    ax2.set_xticklabels(labels2, fontsize=9)
    ax2.set_ylabel('Avoided Emissions (tCO₂e / yr)', fontsize=11)
    ax2.set_title(
        'Avoided Emissions vs Baselines\n[Khatri 2025; CA-GREET4.0]',
        fontsize=10, fontweight='bold'
    )
    _style_ax(ax2)

    fig.text(
        0.5, -0.03,
        'Non-biogenic GHG = fossil CO₂ (NG process heat) + CH₄ CO₂e + N₂O CO₂e across all phases  |  '
        'Open burning EF: 0.143 kg CO₂e / kg OD residue [Khatri 2025]  |  '
        'Fossil JF CI: 15.93 g CO₂e / MJ — cradle-to-gate, no combustion [CA-GREET4.0, CARB LCFS 2024]',
        ha='center', fontsize=7.5, color='gray', style='italic'
    )

    plt.tight_layout()
    os.makedirs(outdir, exist_ok=True)   # ensure output dir exists
    path = os.path.join(outdir, "fhr_net_climate_impact.png")
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  Saved → {path}')


# =============================================================================
# MAIN
# =============================================================================
if __name__ == '__main__':

    # ── Phase calculations ────────────────────────────────────────────────────
    proc     = calc_processing()
    transp   = calc_transport()
    saf_prod = calc_saf_production()
    bio_prod = calc_bio_production()
    lc       = calc_lifecycle(proc, transp, saf_prod, bio_prod)

    # ── Baselines ─────────────────────────────────────────────────────────────
    baselines = calc_baselines(SAF_MJ=saf_prod['SAF_MJ'])

    # ── Terminal report ───────────────────────────────────────────────────────
    print_report(proc, transp, saf_prod, bio_prod, baselines, lc)

    # ── Charts ────────────────────────────────────────────────────────────────
    _hdr('GENERATING CHARTS')
    plot_net_climate_impact(lc, baselines, OUTPUT_DIR)

    print('\n  Forest Health Report — complete.')
    print(f'  Charts saved in: {OUTPUT_DIR}\n')