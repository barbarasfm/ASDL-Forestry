import os
import matplotlib.pyplot as plt
import numpy as np
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
_TEAL    = "#2dd4bf"
_FS_TITLE = 14
_FS_LABEL = 12
_FS_TICK  = 11
_FS_ANNOT = 10

def _style_ax(fig, *axes):
    fig.patch.set_facecolor(_BG)
    for ax in axes:
        ax.set_facecolor(_BG_AX)
        ax.spines[["top","right"]].set_visible(False)
        ax.spines[["left","bottom"]].set_color(_SPINE)
        ax.tick_params(colors=_TEXT, labelsize=_FS_TICK)
        ax.xaxis.label.set_color(_TEXT); ax.xaxis.label.set_fontsize(_FS_LABEL)
        ax.yaxis.label.set_color(_TEXT); ax.yaxis.label.set_fontsize(_FS_LABEL)
        ax.title.set_color(_TEXT); ax.title.set_fontsize(_FS_TITLE)
        ax.yaxis.grid(True, linestyle="--", linewidth=0.5, color=_GRID)
        ax.set_axisbelow(True)
        for lbl in ax.get_xticklabels() + ax.get_yticklabels():
            lbl.set_color(_TEXT); lbl.set_fontsize(_FS_TICK)

def _leg(ax, **kw):
    leg = ax.legend(facecolor=_BG, edgecolor=_SPINE, fontsize=_FS_TICK, **kw)
    for t in leg.get_texts(): t.set_color(_TEXT)
    return leg


BIOMASS_ODT_YR = 100_000      # dry biomass input (odt/yr)
MOISTURE_PCT   = 40           # moisture content (%, wet basis)
RESIDUE_TYPE   = "forest"     # "forest" | "mill" | "pulp"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHART_OUTPATH = os.path.join(os.path.dirname(SCRIPT_DIR), 'LCA_plots', 'combustion_emissions_chart.png')

# =============================================================================
# CONSTANTS
# =============================================================================
# ── Carbon fractions ──────────────────────────────────────────────────────────
CF_WOOD            = 0.50     # carbon fraction, woody biomass 
CF_PULP            = 0.48     # slightly lower for pulp residues 
MW_CO2_C           = 44 / 12  # molecular weight ratio
OXIDATION          = 1.0      # complete combustion, Tier 1 

# ── Combustion emission factors ───────────────────────────────────────────────
EF_CH4_G_PER_GJ    = 30       # g CH4 / GJ heat input [R1] Table 2.5
EF_N2O_G_PER_GJ    = 4        # g N2O / GJ heat input [R1] Table 2.5

GWP_CH4            = 27.9     # IPCC AR6
GWP_N2O            = 273      # IPCC AR6

# ── GREET EF sheet values ──────────────────────────────────────────────────────
GREET_CH4_G_GJ  = 9.865 / 1.055056   # = 9.35 g/GJ  EF row 14 col 49
GREET_N2O_G_GJ  = 6.107 / 1.055056   # = 5.79 g/GJ  EF row 15 col 49

# ── GREET Bio_electricity validation targets ──────────────────────────────────
GREET_CH4_G_KWH = 0.11299  # row 405, US average
GREET_N2O_G_KWH = 0.06014  # row 406
GREET_CO2_G_KWH = 1629.42  # row 407
# FEEDSTOCK PARAMETERS BY PROCESSING OPTION
# moisture_pct   : wet-basis moisture of feedstock entering the boiler
# LHV_dry_GJ_odt : LHV of bone-dry biomass (GJ/odt)  [R4]
#
# LHV at moisture M (wet basis):
#   LHV_wet = LHV_dry x (1 - M) - 2.442 x M
#   2.442 MJ/kg = latent heat of vaporization of water  [R4]

# FEEDSTOCK = {
#     "1.1": {
#         "label":     "1.1 Disc chip\nat landing",
#         "LHV_dry":   19.0,     # [R4]
#         "compat":    ["forest"],
#     },
#     "1.2": {
#         "label":     "1.2 Log truck\n→ disc chip at plant",
#         "LHV_dry":   19.0,
#         "compat":    ["forest"],
#     },
#     "1.3": {
#         "label":     "1.3 Micro-chip\nat landing",
#         "LHV_dry":   19.0,
#         "compat":    ["forest"],
#     },
#     "1.4": {
#         "label":     "1.4 Log truck\n→ micro-chip at plant",
#         "LHV_dry":   19.0,
#         "compat":    ["forest"],
#     },
#     "2.1": {
#         "label":     "2.1 Grind slash\nat landing (sorted)",
#         "LHV_dry":   18.5,
#         "compat":    ["forest"],
#     },
#     "2.2": {
#         "label":     "2.2 Slash truck\n→ grind at plant (sorted)",
#         "LHV_dry":   18.5,
#         "compat":    ["forest"],
#     },
#     "2.3": {
#         "label":     "2.3 Grind all\n(no sorting)",
#         # "moisture":  55,       # worst case wet mixed residues
#         "LHV_dry":   18.0,
#         "compat":    ["forest"],
#     },
#     "3.1_mill": {
#         "label":     "3.1 Mill residues\n(direct)",
#         "LHV_dry":   19.5,
#         "compat":    ["mill"],
#     },
#     "3.1_pulp": {
#         "label":     "3.1 Pulp residues\n(direct)",
#         "LHV_dry":   18.0,
#         "compat":    ["pulp"],
#     },
# }

# ── LHV constant  ─────────────────────────────────
LHV_DRY_CONST  = 18.5        # GJ / odt  —  assumed constant for all options [R4]
KWH_PER_GJ     = 277.778     # 1 GJ = 277.778 kWh

# =============================================================================
# LHV MOISTURE CORRECTION
# =============================================================================
def calc_LHV_wet(LHV_dry, moisture_pct):
    """
    LHV_wet = LHV_dry x (1 - M) - 2.442 x M   [R4]
    """
    M = moisture_pct / 100
    return max(LHV_dry * (1 - M) - 2.442 * M, 0)

# =============================================================================
# MAIN CALCULATION
# =============================================================================
def calculate_one_option(biomass_odt_yr, residue_type,
                         moisture_pct_override=None,
                         elec_GWh_yr_override=None):
    """
    Calculate CO2, CH4, N2O from combustion for one processing option.

    Parameters
    ----------
    biomass_odt_yr      : float  -- dry biomass burned (odt/yr)
    residue_type        : str    -- 'forest', 'mill', or 'pulp'
    moisture_pct_override : float | None  -- overrides default 40%
    elec_GWh_yr_override  : float | None
        If provided (from the bioenergy economics tab), this value is used
        directly as the annual electricity output.  The function no longer
        calculates electricity internally — it is always 0 if no override
        is given (the placeholder kWh = 1000 has been removed).
        The bioenergy economics tab is the authoritative source for kWh/yr.

    Returns dict of all results.
    """
    moisture_pct = moisture_pct_override if moisture_pct_override is not None else 40
    M = moisture_pct / 100

    # ── Carbon fraction ───────────────────────────────────────────────────────
    CF = CF_PULP if residue_type == "pulp" else CF_WOOD

    # ── Heat input to boiler ─────────────────────────────────────────────────
    # LHV_DRY_CONST used for all options — does not vary with processing choice
    wet_mass       = biomass_odt_yr / (1 - M)
    LHV_wet        = calc_LHV_wet(LHV_DRY_CONST, moisture_pct)
    heat_GJ_yr     = wet_mass * LHV_wet

    # ── CO2 (biogenic) ───────────────────────────────────────────────────────
    CO2_t_yr       = biomass_odt_yr * CF * MW_CO2_C * OXIDATION

    # ── CH4 (IPCC EF) ────────────────────────────────────────────────────────
    CH4_t_yr       = heat_GJ_yr * EF_CH4_G_PER_GJ / 1e6
    CH4_CO2e_t_yr  = CH4_t_yr * GWP_CH4

    # ── N2O (IPCC EF) ────────────────────────────────────────────────────────
    N2O_t_yr       = heat_GJ_yr * EF_N2O_G_PER_GJ / 1e6
    N2O_CO2e_t_yr  = N2O_t_yr * GWP_N2O

    # ── GREET EF sheet parallel ───────────────────────────────────────────────
    CH4_greet_t           = heat_GJ_yr * GREET_CH4_G_GJ / 1e6
    CH4_CO2e_t_yr_greet   = CH4_greet_t * GWP_CH4
    N2O_greet_t           = heat_GJ_yr * GREET_N2O_G_GJ / 1e6

    # ── Electricity output ───────────────────────────────────────────────────
    # If not supplied, elec_GWh_yr = 0 (do not estimate internally).
    if elec_GWh_yr_override is not None:
        elec_GWh_yr  = float(elec_GWh_yr_override)
        elec_kWh_yr  = elec_GWh_yr * 1e6
    else:
        elec_GWh_yr  = 0.0
        elec_kWh_yr  = 0.0

    # ── g/kWh (only meaningful when electricity is provided) ──────────────────
    if elec_kWh_yr > 0:
        CO2_g_kWh_ipcc  = CO2_t_yr  * 1e6 / elec_kWh_yr
        CH4_g_kWh_ipcc  = CH4_t_yr  * 1e6 / elec_kWh_yr
        N2O_g_kWh_ipcc  = N2O_t_yr  * 1e6 / elec_kWh_yr
        CH4_g_kWh_greet = CH4_greet_t * 1e6 / elec_kWh_yr
        N2O_g_kWh_greet = N2O_greet_t * 1e6 / elec_kWh_yr
    else:
        CO2_g_kWh_ipcc = CH4_g_kWh_ipcc = N2O_g_kWh_ipcc = 0.0
        CH4_g_kWh_greet = N2O_g_kWh_greet = 0.0

    # ── Totals ────────────────────────────────────────────────────────────────
    nonbio_CO2e = CH4_CO2e_t_yr_greet + N2O_CO2e_t_yr
    total_CO2e  = CO2_t_yr + nonbio_CO2e

    return {
        "residue_type":   residue_type,
        "biomass_odt_yr": biomass_odt_yr,
        # intermediates
        "moisture_pct":   moisture_pct,
        "LHV_dry":        LHV_DRY_CONST,   # constant for all options
        "LHV_wet":        round(LHV_wet, 3),
        "heat_GJ_yr":     round(heat_GJ_yr, 1),
        "CF":             CF,
        # emissions — raw units
        "CO2_t_yr":       round(CO2_t_yr, 1),
        "CH4_t_yr":       round(CH4_t_yr, 4),
        "N2O_t_yr":       round(N2O_t_yr, 5),
        # emissions — CO2e (IPCC EF)
        "CH4_CO2e_t_yr":        round(CH4_CO2e_t_yr, 2),
        "CH4_CO2e_t_yr_greet":  round(CH4_CO2e_t_yr_greet, 2),
        "N2O_CO2e_t_yr":        round(N2O_CO2e_t_yr, 2),
        "nonbio_CO2e":          round(nonbio_CO2e, 2),
        "total_CO2e":           round(total_CO2e, 1),
        # electricity (from economics tab override, or 0)
        "elec_GWh_yr":   round(elec_GWh_yr, 3),
        "elec_kWh_yr":   round(elec_kWh_yr, 1),
        # g/kWh
        "CO2_g_kWh":        round(CO2_g_kWh_ipcc, 1),
        "CH4_g_kWh":        round(CH4_g_kWh_ipcc, 5),
        "N2O_g_kWh":        round(N2O_g_kWh_ipcc, 6),
        "CH4_greet_t":      round(CH4_greet_t, 4),
        "N2O_greet_t":      round(N2O_greet_t, 5),
        "CH4_g_kWh_greet":  round(CH4_g_kWh_greet, 5),
        "N2O_g_kWh_greet":  round(N2O_g_kWh_greet, 6),
    }


def plot_single(r, outpath):
    co2   = r["CO2_t_yr"]
    ch4e  = r["CH4_CO2e_t_yr_greet"]
    n2oe  = r["N2O_CO2e_t_yr"]
    total = r["total_CO2e"]

    fig, ax = plt.subplots(figsize=(6, 5.5))
    colors  = [_BLUE, _AMBER, _GREEN]
    segs    = [co2, ch4e, n2oe]
    labels  = ["Biogenic CO₂", "CH₄ (as CO₂e)", "N₂O (as CO₂e)"]
    bot     = 0

    for seg, col, lbl in zip(segs, colors, labels):
        ax.bar(0, seg, 0.4, bottom=bot, color=col, label=lbl)
        if seg > total * 0.02:
            ax.text(0, bot + seg / 2, f"{seg:,.1f} tCO₂e/yr",
                    ha="center", va="center",
                    fontsize=_FS_ANNOT, color=_TEXT, fontweight="bold")
        bot += seg

    ax.text(0, total * 1.01, f"Total: {total:,.1f} tCO₂e/yr",
            ha="center", va="bottom", fontsize=_FS_ANNOT, fontweight="bold", color=_TEXT)

    ax.text(0, -total * 0.08,
            f"      CH₄ = {r['CH4_t_yr']:.4f} tCH₄/yr\n"
            f"      N₂O = {r['N2O_t_yr']:.5f} tN₂O/yr",
            ha="center", va="top", fontsize=_FS_ANNOT, color=_TEXT_DIM)

    ax.set_xticks([0])
    # ax.set_xticklabels("Emissions", fontsize=_FS_TICK, color=_TEXT)
    ax.set_xticklabels(["Emissions"], fontsize=_FS_TICK, color=_TEXT)
    ax.set_ylabel("Emissions (tCO₂e / yr)", fontsize=_FS_LABEL, color=_TEXT)
    ax.set_title(
        f"Bioenergy Combustion\n"
        f"{r['residue_type'].capitalize()}  |  {r['biomass_odt_yr']:,.0f} odt/yr  "
        f"|  Moisture: {r['moisture_pct']}%  |  LHV dry: {LHV_DRY_CONST} GJ/odt (constant)",
        fontsize=_FS_TITLE, fontweight="bold", pad=10, color=_TEXT
    )
    ax.set_xlim(-0.5, 0.5)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    _style_ax(fig, ax)
    _leg(ax, loc="lower right")

    plt.tight_layout()
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    plt.savefig(outpath, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Chart saved: {outpath}")


if __name__ == "__main__":
    residue_type = RESIDUE_TYPE.lower().strip()
    r = calculate_one_option(BIOMASS_ODT_YR, residue_type, MOISTURE_PCT)
    print(f" {r['biomass_odt_yr']:,} odt/yr  |  moisture {r['moisture_pct']}%")
    print(f"  LHV dry (constant): {r['LHV_dry']} GJ/odt")
    print(f"  LHV wet:            {r['LHV_wet']:.3f} GJ/odt")
    print(f"  Heat input:         {r['heat_GJ_yr']:,.1f} GJ/yr")
    print(f"  Biogenic CO2:       {r['CO2_t_yr']:,.1f} t/yr")
    print(f"  CH4 CO2e (GREET):   {r['CH4_CO2e_t_yr_greet']:,.2f} t/yr")
    print(f"  N2O CO2e:           {r['N2O_CO2e_t_yr']:,.2f} t/yr")
    print(f"  Non-biogenic total: {r['nonbio_CO2e']:,.2f} t/yr")
    print(f"  Total CO2e:         {r['total_CO2e']:,.1f} t/yr")
    print(f"  Electricity:        {r['elec_GWh_yr']:.3f} GWh/yr  (0 unless overridden from economics)")
    plot_single(r, CHART_OUTPATH)