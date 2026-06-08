"""
Integration — Georgia Forest Residue LCA
==========================================
Imports and calls functions from each individual module.
All calculation logic stays in its respective script.

Run: python integration.py
Requires in same directory:
  SAF_production_v2.py
  Bioenergy_production_v3.py
  Biomass_transport.py
  Biomass_processing_v2.py

Biomass split:
  Total:          1,000,000 odt/yr
  HQ (40%) → SAF:  400,000 odt → 12,000,000 L SAF/yr
  All      → Bio: 1,000,000 odt → electricity

Plot: split-scale 4-panel
  Left 2 panels  — supply chain (processing + transport)  in  t CO2e/yr
  Right 2 panels — production (SAF + bioenergy)           in  kt CO2e/yr
"""

import sys, os, io, contextlib
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from LCA_dependencies.SAF_production_LCA       import calc as saf_calc, INPUTS as SAF_INPUTS
from LCA_dependencies.Bioenergy_production_LCA import calculate_one_option
from LCA_dependencies.Biomass_transport_LCA        import phase2_transport
from LCA_dependencies.Biomass_processing_v2    import calculate_one

# =============================================================================
# INPUTS
# =============================================================================

TOTAL_ODT      = 2_00_000
HQ_FRACTION    = 0.40
HQ_ODT         = int(TOTAL_ODT * HQ_FRACTION)   # 400,000
SAF_L_YR       = 12_000_000.0
DIST_SAF_KM    = 161.0
DIST_BIO_KM    = 100.0
MOISTURE_PCT   = 40
GWP_CH4 = 27.9; GWP_N2O = 273.0

# =============================================================================
# RUN ALL MODULES  (suppress their print output)
# =============================================================================

def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)

# ── Processing ────────────────────────────────────────────────────────────────
ps_raw = calculate_one(HQ_ODT,    "1.1")["mid"]   # 400k odt, disc chip
pb_raw = calculate_one(TOTAL_ODT, "2.1")["mid"]   # 1M odt, grind sorted

def pack_proc(r):
    return {"bioCO2_t":0, "fossCO2_t":r["CO2_t"],
            "CH4_CO2e":r["CH4_CO2e"], "N2O_CO2e":r["N2O_CO2e"]}

proc_saf = pack_proc(ps_raw)
proc_bio = pack_proc(pb_raw)

# ── Transport ─────────────────────────────────────────────────────────────────
tr = quiet(phase2_transport, TOTAL_ODT * 1000, HQ_FRACTION, DIST_SAF_KM, DIST_BIO_KM)

def pack_trans(t):
    ch4_t = t["CH4"] / 1000; n2o_t = t["N2O"] / 1000
    return {"bioCO2_t":0, "fossCO2_t":t["CO2"]/1000,
            "CH4_CO2e":ch4_t*GWP_CH4, "N2O_CO2e":n2o_t*GWP_N2O}

trans_saf = pack_trans(tr["saf"])
trans_bio = pack_trans(tr["bio"])

# ── Bioenergy production ──────────────────────────────────────────────────────
br = quiet(calculate_one_option, TOTAL_ODT, "forest", "2.1", MOISTURE_PCT)

bio_prod = {
    "bioCO2_t":  br["CO2_t_yr"],
    "fossCO2_t": 0.0,
    "CH4_CO2e":  br["CH4_CO2e_t_yr"],
    "N2O_CO2e":  br["N2O_CO2e_t_yr"],
    "elec_GWh":  br["elec_GWh_yr"],
}

# ── SAF production ────────────────────────────────────────────────────────────
shared = {k: SAF_INPUTS[k] for k in [
    "biomass_odt_yr","c_liquid","lhv_saf","saf_L_yr","diesel_L_yr","naphtha_L_yr",
    "rho_saf","rho_diesel","rho_naphtha","almena_pct","greet_ng_btu",
    "greet_biomass_feed_loss_btu","ef_ng_co2","ef_ng_ch4","ef_ng_n2o",
    "ef_fr_gasifier_ch4","ef_fr_gasifier_n2o","lhv_saf_btu_per_gal","gwp_ch4","gwp_n2o",
]}
shared["biomass_odt_yr"] = HQ_ODT
shared["saf_L_yr"]       = SAF_L_YR

sr = saf_calc(cf=SAF_INPUTS["cf_forest"], **shared)

saf_prod = {
    "bioCO2_t":  sr["bioCO2_kt"] * 1000,
    "fossCO2_t": sr["fossCO2_t"],
    "CH4_CO2e":  sr["CH4_CO2e_t"],
    "N2O_CO2e":  sr["N2O_CO2e_t"],
}

# =============================================================================
# PRINT TABLE
# =============================================================================

def tot(r): return r["bioCO2_t"]+r["fossCO2_t"]+r["CH4_CO2e"]+r["N2O_CO2e"]

print("\n" + "="*82)
print(f"  LCA SUMMARY  |  {TOTAL_ODT:,} odt/yr  |  {SAF_L_YR/1e6:.0f}M L SAF/yr")
print("="*82)
print(f"  {'Stage':<35} {'Biomass (odt)':>14} {'Biogenic CO2':>14} {'Fossil CO2':>11} "
      f"{'CH4 CO2e':>10} {'N2O CO2e':>10} {'Total CO2e':>12}")
print(f"  {'':35} {'':>14} {'(t/yr)':>14} {'(t/yr)':>11} "
      f"{'(t/yr)':>10} {'(t/yr)':>10} {'(t/yr)':>12}")
print(f"  {'-'*110}")
rows = [
    ("Processing — SAF (disc chip 1.1)",   HQ_ODT,    proc_saf),
    ("Processing — Bioenergy (grind 2.1)", TOTAL_ODT, proc_bio),
    ("Transport — SAF (161 km)",           HQ_ODT,    trans_saf),
    ("Transport — Bioenergy (100 km)",     TOTAL_ODT, trans_bio),
    ("SAF Production",                     HQ_ODT,    saf_prod),
    ("Bioenergy Production",               TOTAL_ODT, bio_prod),
]
for name, bm, r in rows:
    print(f"  {name:<35} {bm:>14,} {r['bioCO2_t']:>14,.0f} {r['fossCO2_t']:>11,.0f} "
          f"{r['CH4_CO2e']:>10,.0f} {r['N2O_CO2e']:>10,.0f} {tot(r):>12,.0f}")

print(f"\n  Bioenergy electricity output : {bio_prod['elec_GWh']:,.1f} GWh/yr")

# =============================================================================
# PLOT — split scale: supply chain (t) | production (kt)
# =============================================================================

C_BIO  = "#2471A3"
C_FOSS = "#A93226"
C_CH4  = "#E67E22"
C_N2O  = "#1E8449"

fig = plt.figure(figsize=(16, 7))
fig.patch.set_facecolor("white")

# axes positions: [left, bottom, width, height]
ax1 = fig.add_axes([0.05, 0.13, 0.17, 0.72])   # supply chain SAF
ax2 = fig.add_axes([0.27, 0.13, 0.17, 0.72])   # supply chain Bio
# ax3 = fig.add_axes([0.55, 0.13, 0.19, 0.72])   # production SAF
# ax4 = fig.add_axes([0.77, 0.13, 0.19, 0.72])   # production Bio
ax3 = fig.add_axes([0.55, 0.13, 0.25, 0.72])

def draw_bars(ax, stages, unit_div=1, ylabel=""):
    """stages = [(xlabel, result_dict), ...]"""
    x = np.arange(len(stages)); w = 0.45
    bio_v  = [s[1]["bioCO2_t"]  / unit_div for s in stages]
    foss_v = [s[1]["fossCO2_t"] / unit_div for s in stages]
    ch4_v  = [s[1]["CH4_CO2e"]  / unit_div for s in stages]
    n2o_v  = [s[1]["N2O_CO2e"]  / unit_div for s in stages]

    b0 = [0]*len(stages)
    b1 = [bio_v[i]+foss_v[i] for i in range(len(stages))]
    b2 = [b1[i]+ch4_v[i]     for i in range(len(stages))]

    ax.bar(x, bio_v,  w, color=C_BIO,  bottom=b0)
    ax.bar(x, foss_v, w, color=C_FOSS, bottom=bio_v)
    ax.bar(x, ch4_v,  w, color=C_CH4,  bottom=b1)
    ax.bar(x, n2o_v,  w, color=C_N2O,  bottom=b2)

    totals = [b2[i]+n2o_v[i] for i in range(len(stages))]
    for i, t in enumerate(totals):
        ax.text(x[i], t + max(totals)*0.025,
                f"{t:,.0f}", ha="center", va="bottom", fontsize=9.5, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([s[0] for s in stages], fontsize=9)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.spines[["top","right"]].set_visible(False)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,_: f"{v:,.0f}"))

draw_bars(ax1,
    [("Processing\n(disc chip)", proc_saf),
     ("Transport\n(161 km)",     trans_saf)],
    unit_div=1, ylabel="t CO₂e / yr")

draw_bars(ax2,
    [("Processing\n(grind sort)", proc_bio),
     ("Transport\n(100 km)",      trans_bio)],
    unit_div=1, ylabel="t CO₂e / yr")

# draw_bars(ax3,
#     [("SAF\nProduction", saf_prod)],
#     unit_div=1000, ylabel="kt CO₂e / yr")

# draw_bars(ax4,
#     [("Bioenergy\nProduction", bio_prod)],
#     unit_div=1000, ylabel="kt CO₂e / yr")

draw_bars(ax3,
    [("SAF\nProduction", saf_prod),
     ("Bioenergy\nProduction", bio_prod)],
    unit_div=1000, ylabel="kt CO₂e / yr")

# panel titles
ax1.set_title(f"SAF supply chain\n(HQ {HQ_ODT//1000}k odt)",
              fontsize=9.5, fontweight="bold", pad=6)
ax2.set_title(f"Bioenergy supply chain\n({TOTAL_ODT//1000}k odt)",
              fontsize=9.5, fontweight="bold", pad=6)
ax3.set_title(f"SAF and Bioenergy production\n({SAF_L_YR/1e6:.0f}M L/yr)",
              fontsize=9.5, fontweight="bold", pad=6)
# ax4.set_title(f"Bioenergy production\n({bio_prod['elec_GWh']:,.0f} GWh/yr)",
#               fontsize=9.5, fontweight="bold", pad=6)

# scale divider
fig.add_artist(plt.Line2D([0.485, 0.485], [0.08, 0.96],
               transform=fig.transFigure, color="#bbbbbb", lw=1.5, ls="--"))
fig.text(0.25,  0.02, "Supply chain  (t CO₂e / yr)",
         ha="center", fontsize=9, color="#666", style="italic")
fig.text(0.675, 0.02, "Production  (kt CO₂e / yr)",
         ha="center", fontsize=9, color="#666", style="italic")

# legend
patches = [mpatches.Patch(color=c, label=l) for c, l in [
    (C_BIO,"Biogenic CO₂"), (C_FOSS,"Fossil CO₂"),
    (C_CH4,"CH₄ CO₂e"), (C_N2O,"N₂O CO₂e")]]
fig.legend(handles=patches, loc="upper center", ncol=4,
           fontsize=9.5, framealpha=0.9, bbox_to_anchor=(0.4, 1.02))

fig.suptitle(
    f"Georgia Forest Residue: LCA Emissions by Stage\n"
    f"Total: {TOTAL_ODT/1e6:.1f}M odt/yr  |  "
    f"High Quality (HQ) SAF: {HQ_ODT/1e3:.0f}k odt ({int(HQ_FRACTION*100)}%)  |  "
    f"Bioenergy: {TOTAL_ODT/1e6:.1f}M odt",
    fontsize=10.5, fontweight="bold", x = 0.4,y=1.06)
# fig.suptitle(
#     f"Georgia Forest Residue: LCA Emissions by Stage\n"
#     f"Total: {TOTAL_ODT/1e6:.1f}M odt/yr  |  "
#     f"High Quality (HQ) SAF: {HQ_ODT/1e3:.0f}k odt ({int(HQ_FRACTION*100)}%)  |  "
#     f"Bioenergy: {TOTAL_ODT/1e6:.1f}M odt",
#     fontsize=10.5,
#     fontweight="bold",
#     x=0.5,          # <-- force horizontal centering
#     y=0.98,         # <-- slightly below top (cleaner than 1.06)
#     ha="center"     # <-- ensure alignment
# )

outpath = "LCA_plots/integration_emissions.png"
plt.savefig(outpath, dpi=150, bbox_inches="tight")
plt.close()
print(f"\n  Chart saved: {outpath}")