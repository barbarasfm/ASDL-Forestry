"""
  Biomass → Gasifier → Syngas → FT Synthesis → SAF

Three emission streams:

  1. Biogenic CO2     — carbon mass balance [R1]
  2. CH4 + N2O CO2e  — biomass combustion in gasifier/CCGT [R7]
  3. Fossil CO2       — NG process heat inside plant [R7]

GREET source for in-plant values (JetFuel_WTP, Forest Residue FT col 96):
  NG process heat: 2,304 BTU/mmBtu SAF  (row 347)
  Biomass feed loss: 1,000,000 BTU/mmBtu SAF  (row 333)
    = the 50% of input biomass combusted for process energy
  Grid electricity: 0  (row 336) — plant is self-sufficient

GREET EFs for Forest Residue — Gasifier sub-type [R7]:
  EF sheet row 14 col 53: CH4 = 1.100 g/mmBtu biomass
  EF sheet row 15 col 53: N2O = 1.100 g/mmBtu biomass

References:
  [R1] IPCC (2006) Vol.2 Ch.2 — E = (C_in − C_products) × 44/12
  [R2] ORNL/NC State (2019) — CF = 0.50 forest/mill, 0.48 pulp
  [R3] IPCC (2006) Vol.2 Table 1.2 — C_liquid = 0.842 kg C/kg
  [R4] Almena et al. (2024) Energy Conv. Mgmt. 303:118186
       Table 6: fossil 9.9 g/MJ, biogenic 15.7 g/MJ (conversion stage)
       Fig.6: 60% C airborne (no CCS)
  [R5] Mousavi-Avval et al. (2024) Sustainable Energy & Fuels
       24.56 gCO2e/MJ cradle-to-gate (fossil only)
  [R6] IPCC AR6 — GWP100: CH4=27.9, N2O=273
  [R7] GREET R&D 2025, Argonne National Lab
       JetFuel_WTP Forest Residue FT col 96
       EF sheet: NG CO2=58020, CH4=1.06, N2O=0.75 g/mmBtu (row 14-16 col 1)
       EF sheet: Forest Residue Gasifier CH4=1.1, N2O=1.1 g/mmBtu (row 14-15 col 53)
"""

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
_FS_TITLE = 16
_FS_LABEL = 13
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


MMBtu_per_MJ = 1 / 1055.056   # conversion: 1 mmBtu = 1055.056 MJ


def calc(biomass_odt_yr, cf, c_liquid, lhv_saf,
         saf_L_yr, diesel_L_yr, naphtha_L_yr,
         rho_saf, rho_diesel, rho_naphtha,
         almena_pct,
         # GREET in-plant energy inputs (BTU / mmBtu SAF)
         greet_ng_btu,
         greet_biomass_feed_loss_btu,
         # GREET EFs
         ef_ng_co2, ef_ng_ch4, ef_ng_n2o,
         ef_fr_gasifier_ch4, ef_fr_gasifier_n2o,
         # LHV for energy conversion
         lhv_saf_btu_per_gal,
         # GWPs
         gwp_ch4, gwp_n2o):

    L_per_gal = 3.78541

    # ── SAF energy ────────────────────────────────────────────────────────────
    lhv_MJ_per_L    = (lhv_saf_btu_per_gal / L_per_gal) / 1055.056 * 1e6 / 1e6
    # simpler: BTU/gal ÷ (BTU/MJ × L/gal)
    lhv_MJ_per_L    = lhv_saf_btu_per_gal / (1055.056 * L_per_gal / 1e6) / 1e6
    lhv_MJ_per_L    = (lhv_saf_btu_per_gal / L_per_gal) / (1055.056 / 1e6) / 1e6
    # cleanest:
    BTU_per_MJ      = 947.817
    lhv_MJ_per_L    = (lhv_saf_btu_per_gal / L_per_gal) / BTU_per_MJ
    SAF_MJ_yr       = saf_L_yr * lhv_MJ_per_L
    SAF_mmBtu_yr    = SAF_MJ_yr * BTU_per_MJ / 1e6

    # ── Product masses ────────────────────────────────────────────────────────
    B          = biomass_odt_yr * 1e3
    SAF_kg     = saf_L_yr     * rho_saf
    diesel_kg  = diesel_L_yr  * rho_diesel
    naphtha_kg = naphtha_L_yr * rho_naphtha

    # ── BIOGENIC CO2 — carbon mass balance [R1] ───────────────────────────────
    C_in      = B * cf
    C_liq     = (SAF_kg + diesel_kg + naphtha_kg) * c_liquid
    C_rel     = C_in - C_liq
    pct_rel   = C_rel / C_in * 100
    bioCO2_t  = C_rel * (44/12) / 1e3
    bioCO2_kt = bioCO2_t / 1e3
    bioCO2_gMJ = bioCO2_t * 1e6 / SAF_MJ_yr

    # ── FOSSIL CO2 — NG process heat only [R7] ────────────────────────────────
    # E = NG_BTU/mmBtu × EF_NG_CO2 / 1e6  → g/mmBtu SAF → g/MJ SAF
    fossCO2_g_mmBtu = greet_ng_btu * ef_ng_co2 / 1e6
    fossCO2_g_MJ    = fossCO2_g_mmBtu / 1055.056
    fossCO2_t       = fossCO2_g_MJ * SAF_MJ_yr / 1e6

    # ── CH4 — biomass combustion in gasifier/CCGT [R7] ───────────────────────
    # E = feed_loss_BTU × EF_FR_gasifier_CH4 / 1e6  → g/mmBtu SAF
    CH4_g_mmBtu  = greet_biomass_feed_loss_btu * ef_fr_gasifier_ch4 / 1e6
    CH4_g_MJ     = CH4_g_mmBtu / 1055.056
    CH4_t        = CH4_g_MJ * SAF_MJ_yr / 1e6
    CH4_CO2e_t   = CH4_t * gwp_ch4
    CH4_CO2e_gMJ = CH4_g_MJ * gwp_ch4

    # Also add CH4 from NG combustion (minor)
    CH4_ng_g_mmBtu = greet_ng_btu * ef_ng_ch4 / 1e6
    CH4_ng_g_MJ    = CH4_ng_g_mmBtu / 1055.056

    # ── N2O — biomass combustion in gasifier/CCGT [R7] ───────────────────────
    N2O_g_mmBtu  = greet_biomass_feed_loss_btu * ef_fr_gasifier_n2o / 1e6
    N2O_g_MJ     = N2O_g_mmBtu / 1055.056
    N2O_t        = N2O_g_MJ * SAF_MJ_yr / 1e6
    N2O_CO2e_t   = N2O_t * gwp_n2o
    N2O_CO2e_gMJ = N2O_g_MJ * gwp_n2o

    # Also add N2O from NG combustion (minor)
    N2O_ng_g_mmBtu = greet_ng_btu * ef_ng_n2o / 1e6
    N2O_ng_g_MJ    = N2O_ng_g_mmBtu / 1055.056

    # ── Almena reference ──────────────────────────────────────────────────────
    CO2_alm_kt = C_in * (almena_pct/100) * (44/12) / 1e6

    return {
        "SAF_t":       SAF_kg / 1e3,
        "SAF_MJ_yr":   SAF_MJ_yr,
        "SAF_yield":   SAF_kg / B,
        # Carbon fate
        "C_in_kt":   C_in / 1e6,
        "pct_saf":   (SAF_kg * c_liquid) / C_in * 100,
        "pct_diesel":(diesel_kg * c_liquid) / C_in * 100,
        "pct_naphtha":(naphtha_kg * c_liquid) / C_in * 100,
        "pct_liq":   C_liq / C_in * 100,
        "pct_rel":   pct_rel,
        # Biogenic CO2
        "bioCO2_kt":  bioCO2_kt,
        "bioCO2_gMJ": bioCO2_gMJ,
        "CO2_alm_kt": CO2_alm_kt,
        "almena_pct": almena_pct,
        # Fossil CO2 (NG only)
        "fossCO2_t":   fossCO2_t,
        "fossCO2_gMJ": fossCO2_g_MJ,
        # CH4
        "CH4_t":       CH4_t,
        "CH4_gMJ":     CH4_g_MJ,
        "CH4_CO2e_t":  CH4_CO2e_t,
        "CH4_CO2e_gMJ":CH4_CO2e_gMJ,
        # N2O
        "N2O_t":       N2O_t,
        "N2O_gMJ":     N2O_g_MJ,
        "N2O_CO2e_t":  N2O_CO2e_t,
        "N2O_CO2e_gMJ":N2O_CO2e_gMJ,
        # Totals
        "total_fossil_gMJ": fossCO2_g_MJ + CH4_CO2e_gMJ + N2O_CO2e_gMJ,
        "total_all_gMJ":    bioCO2_gMJ + fossCO2_g_MJ + CH4_CO2e_gMJ + N2O_CO2e_gMJ,
        "total_ton": N2O_CO2e_t + CH4_CO2e_t + fossCO2_t + bioCO2_kt*1000
    }

def print_results(label, r):
    print(f"\n  [{label}]")
    print(f"  {'─'*65}")
    print(f"  SAF: {r['SAF_t']:,.1f} t/yr  |  yield {r['SAF_yield']:.3f} kg/kg dry  |  {r['SAF_MJ_yr']/1e6:.1f} TJ/yr")
    print()
    print(f"  CARBON FATE (% of input C = {r['C_in_kt']:.1f} kt C/yr)")
    print(f"    → All liquids:   {r['pct_liq']:>5.1f}%   (Almena 2024: 36%)")
    print(f"    → CO2 released:  {r['pct_rel']:>5.1f}%   (Almena 2024: {r['almena_pct']}%)")
    print()
    print(f"  BIOGENIC CO2  [R1] carbon mass balance")
    print(f"    {r['bioCO2_kt']:>8.1f} kt/yr  |  {r['bioCO2_gMJ']:>7.1f} g CO2/MJ")
    print(f"    Almena 2024 [R4]: {r['CO2_alm_kt']:.1f} kt/yr  |  15.7 g CO2/MJ (energy-allocated)")
    print()
    print(f"  FOSSIL CO2  [R7] NG process heat inside plant")
    print(f"    {r['fossCO2_t']:>8.1f} t/yr   |  {r['fossCO2_gMJ']:>7.4f} g CO2/MJ")
    print(f"    GREET reported:                 2.035 g CO2/MJ (incl. supply chain)")
    print(f"    Almena 2024 [R4]:               9.9   g CO2/MJ (full process model)")
    print()
    print(f"  CH4  [R7] biomass gasification + CCGT combustion inside plant")
    print(f"    {r['CH4_t']:>8.4f} t CH4/yr   |  {r['CH4_gMJ']:>9.6f} g CH4/MJ")
    print(f"    CO2e: {r['CH4_CO2e_t']:>6.3f} t/yr     |  {r['CH4_CO2e_gMJ']:>9.6f} g CO2e/MJ")
    print()
    print(f"  N2O  [R7] biomass gasification + CCGT combustion inside plant")
    print(f"    {r['N2O_t']:>8.4f} t N2O/yr   |  {r['N2O_gMJ']:>9.6f} g N2O/MJ")
    print(f"    CO2e: {r['N2O_CO2e_t']:>6.3f} t/yr     |  {r['N2O_CO2e_gMJ']:>9.6f} g CO2e/MJ")
    print()
    print(f"  ── TOTALS (plant gate only) ────────────────────────────────")
    print(f"  Fossil CI (CO2+CH4+N2O):  {r['total_fossil_gMJ']:>7.4f} g CO2e/MJ")
    print(f"  Total incl. biogenic:     {r['total_all_gMJ']:>7.2f} g CO2e/MJ")
    print(f"  Total incl. biogenic:     {r['total_ton']:>7.2f} t CO2e/year")
    

def make_plot(r_forest, r_pulp, outpath):
    # Single panel: absolute kt CO2e/yr for Forest vs Pulp
    fig, ax = plt.subplots(figsize=(6, 5.5))

    x = np.arange(2); w = 0.4
    scenarios = ["Forest\n(CF=0.50)", "Pulp\n(CF=0.48)"]

    bio_kt  = [r_forest["bioCO2_kt"],      r_pulp["bioCO2_kt"]]
    foss_kt = [r_forest["fossCO2_t"]/1e3,  r_pulp["fossCO2_t"]/1e3]
    ch4_kt  = [r_forest["CH4_CO2e_t"]/1e3, r_pulp["CH4_CO2e_t"]/1e3]
    n2o_kt  = [r_forest["N2O_CO2e_t"]/1e3, r_pulp["N2O_CO2e_t"]/1e3]

    ax.bar(x, bio_kt,  w, color=_BLUE,  label="Biogenic CO₂")
    ax.bar(x, foss_kt, w, bottom=bio_kt, color=_RED, label="Fossil CO₂")
    ax.bar(x, ch4_kt,  w,
           bottom=[bio_kt[i]+foss_kt[i] for i in range(2)],
           color=_AMBER, label="CH₄ CO₂e")
    ax.bar(x, n2o_kt,  w,
           bottom=[bio_kt[i]+foss_kt[i]+ch4_kt[i] for i in range(2)],
           color=_GREEN, label="N₂O CO₂e")

    totals = [sum(v) for v in zip(bio_kt, foss_kt, ch4_kt, n2o_kt)]
    for i, t in enumerate(totals):
        ax.text(x[i], t + max(totals)*0.02, f"{t:,.1f}",
                ha="center", va="bottom", fontweight="bold")

    ax.axhline(r_forest["CO2_alm_kt"], color=_RED, linestyle="--", lw=1.5,
               label=f"Almena 2024: {r_forest['CO2_alm_kt']:.0f} kt/yr")

    ax.set_xticks(x)
    ax.set_xticklabels(scenarios)
    ax.set_xlim(-0.5, 1.5)
    ax.set_ylabel("kt CO₂e / yr")
    ax.set_title("SAF Production Emissions\nForest vs Pulp feedstock", fontweight="bold", pad=10)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    _style_ax(fig, ax)
    _leg(ax, loc="lower right")
    plt.tight_layout()
    plt.savefig(outpath, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  Chart: {outpath}")

INPUTS = {
    # ── Biomass ──────────────────────────────────────────────────────────────
    "biomass_odt_yr":   272350,

    # ── Carbon fractions  [R2] ────────────────────────────────────────────────
    "cf_forest":        0.50,
    "cf_pulp":          0.48,

    # ── Liquid product C content and SAF LHV  [R3, R4] ───────────────────────
    "c_liquid":         0.842,
    "lhv_saf":          43.8,      # MJ/kg SAF

    # ── Volumes from distillate code (L/yr) ──────────────────────────────────
    "saf_L_yr":         33075900.0,
    "diesel_L_yr":       16818254.237288132,
    "naphtha_L_yr":      13168905.10948905,

    # ── Densities (kg/L) ─────────────────────────────────────────────────────
    "rho_saf":          0.75,     
    "rho_diesel":       0.89,     
    "rho_naphtha":      0.75,

    # ── Almena reference  [R4 Fig.6] ─────────────────────────────────────────
    "almena_pct":       60,

    # ── GREET in-plant energy inputs (BTU per mmBtu SAF)  [R7] ───────────────
    # Source: JetFuel_WTP, Forest Residue FT, col 96
    # SUPPLY CHAIN EXCLUDED — only in-plant energy:
    "greet_ng_btu":              2_304.3,    # row 347 — NG for process heat
    "greet_biomass_feed_loss_btu": 1_000_000, # row 333 — 50% of biomass combusted in CCGT/gasifier
    # Note: grid electricity = 0 (row 336) — plant self-sufficient

    # ── GREET Emission Factors  [R7] ─────────────────────────────────────────
    # NG combustion (EF sheet, utility boiler, row 14-16, col 1)
    "ef_ng_co2":        58_020.1,  # g CO2/mmBtu NG
    "ef_ng_ch4":            1.06,  # g CH4/mmBtu NG
    "ef_ng_n2o":            0.75,  # g N2O/mmBtu NG
    # Forest Residue in Gasifier (EF sheet row 14-15, col 53)
    "ef_fr_gasifier_ch4":   1.100, # g CH4/mmBtu biomass
    "ef_fr_gasifier_n2o":   1.100, # g N2O/mmBtu biomass

    # ── SAF LHV for energy conversion  [R7] ──────────────────────────────────
    "lhv_saf_btu_per_gal":  119_776.6,  # Fuel_Specs row 49

    # ── GWPs  [R6] ────────────────────────────────────────────────────────────
    "gwp_ch4":   27.9,
    "gwp_n2o":  273.0,
}

if __name__ == "__main__":
    shared = {k: INPUTS[k] for k in [
        "biomass_odt_yr", "c_liquid", "lhv_saf",
        "saf_L_yr", "diesel_L_yr", "naphtha_L_yr",
        "rho_saf", "rho_diesel", "rho_naphtha", "almena_pct",
        "greet_ng_btu", "greet_biomass_feed_loss_btu",
        "ef_ng_co2", "ef_ng_ch4", "ef_ng_n2o",
        "ef_fr_gasifier_ch4", "ef_fr_gasifier_n2o",
        "lhv_saf_btu_per_gal", "gwp_ch4", "gwp_n2o",
    ]}

    r_forest = calc(cf=INPUTS["cf_forest"], **shared)
    r_pulp   = calc(cf=INPUTS["cf_pulp"],   **shared)

    print("=" * 68)
    print("  SAF PRODUCTION ONLY — Gasification + FT (no supply chain)")
    print("=" * 68)
    print_results("Forest residues", r_forest)
    print_results("Pulp residues",   r_pulp)

    make_plot(r_forest, r_pulp,
              "LCA_plots/saf_production_plantonly.png")

    print("\n  INPUT TABLE")
    print("  " + "─"*68)
    rows = [
        ("Biomass input",                f"{INPUTS['biomass_odt_yr']:,} odt/yr",         "User defined"),
        ("CF forest/mill",               f"{INPUTS['cf_forest']}",                       "[R2]"),
        ("CF pulp",                      f"{INPUTS['cf_pulp']}",                         "[R2]"),
        ("C content all liquids",        f"{INPUTS['c_liquid']} kg C/kg",                "[R3]"),
        ("LHV FT-SPK",                   f"{INPUTS['lhv_saf']} MJ/kg",                   "[R4]"),
        ("SAF volume",                   f"{INPUTS['saf_L_yr']:,.0f} L/yr",              "Distillate code"),
        ("Diesel volume",                f"{INPUTS['diesel_L_yr']:,.1f} L/yr",           "Distillate code"),
        ("Naphtha volume",               f"{INPUTS['naphtha_L_yr']:,.1f} L/yr",          "Distillate code"),
        ("Density SAF",                  f"{INPUTS['rho_saf']} kg/L",                    "ASTM D7566"),
        ("Density Diesel",               f"{INPUTS['rho_diesel']} kg/L",                 "FT diesel"),
        ("Density Naphtha",              f"{INPUTS['rho_naphtha']} kg/L",                "Standard"),
        ("Almena % C airborne (no CCS)", f"{INPUTS['almena_pct']}%",                     "[R4] Fig.6"),
        ("NG process heat",              f"{INPUTS['greet_ng_btu']:,.0f} BTU/mmBtu SAF", "[R7] row 347"),
        ("Biomass feed loss",            f"{INPUTS['greet_biomass_feed_loss_btu']:,} BTU/mmBtu SAF","[R7] row 333"),
        ("Grid electricity",             "0 BTU/mmBtu (excluded)",                       "[R7] row 336"),
        ("EF NG — CO2/CH4/N2O",          f"{INPUTS['ef_ng_co2']:,.0f}/{INPUTS['ef_ng_ch4']}/{INPUTS['ef_ng_n2o']} g/mmBtu","[R7] EF col 1"),
        ("EF FR Gasifier — CH4/N2O",     f"{INPUTS['ef_fr_gasifier_ch4']}/{INPUTS['ef_fr_gasifier_n2o']} g/mmBtu","[R7] EF row 14-15 col 53"),
        ("LHV SAF (GREET SPK)",          f"{INPUTS['lhv_saf_btu_per_gal']:,.0f} BTU/gal","[R7] Fuel_Specs row 49"),
        ("GWP CH4 / N2O",               f"{INPUTS['gwp_ch4']} / {INPUTS['gwp_n2o']}",   "[R6] IPCC AR6"),
    ]
    print(f"  {'Parameter':<32} {'Value':>26}  Source")
    print("  " + "─"*68)
    for name, val, src in rows:
        print(f"  {name:<32} {val:>26}  {src}")