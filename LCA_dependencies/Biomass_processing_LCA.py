import os
import matplotlib.pyplot as plt
import numpy as np

#  INPUTS
BIOMASS_ODT_YR = 7370        # oven-dry tonnes per year
RESIDUE_TYPE   = "residue"

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
CHART_OUTPATH = os.path.join(SCRIPT_DIR, "processing_emissions_chart.png")

#  CONSTANTS
EF_DIESEL_CO2_KG_PER_L = 2.68   # kg CO2/L          [2]
NCV_DIESEL_MJ_PER_L    = 35.8   # MJ/L              [2]
EF_CH4_G_PER_MJ        = 0.10   # g CH4/MJ diesel   [1] Table 3.3.1
EF_N2O_G_PER_MJ        = 0.10   # g N2O/MJ diesel   [1] Table 3.3.1
GWP_CH4                = 27.9   # AR6 [R3]
GWP_N2O                = 273    # AR6 [R3]

#  FUEL CONSUMPTION RANGES  (L / odt)
FC_RANGES = {
    "disc_forest":   (3.0, 3.5),   
    "microchip":     (3.5, 4.5),   # indicative
    "grinder_sort":  (4.0, 6.0),   # 
    "grinder_none":  (6.0, 8.0),   # 
    # Star screener — Sahoo (2019) Tables 1 & 2:
    # Star screener (screener unit only, no loader)
    # All three bounds derived from Sahoo (2019) Tables 1 & 2:
    #   Power = 55 kW, Productivity = 13.40 ODMT/hr  [Table 2]
    #   Fuel use range: low = 0.09, mid = 0.12, high = 0.26 L/kWh  [Table 1]
    #   Low : 55 × 0.09 ÷ 13.40 = 0.37 L/odt
    #   Mid : 55 × 0.12 ÷ 13.40 = 0.49 L/odt
    #   High: 55 × 0.26 ÷ 13.40 = 1.07 L/odt
    "star_screener": (0.37, 1.07),
    "none":          (0.0, 0.0),
}

#  PROCESSING OPTIONS
PROCESSING_OPTIONS = {
    "1.1": {"label": "1.1 Disc chip\nat landing",     "compat": ["residue"], "fc_key": "disc_forest",  "moisture": 40},
    "1.2": {"label": "1.2 Disc chip\nat plant",       "compat": ["residue"], "fc_key": "disc_forest",  "moisture": 45},
    "1.3": {"label": "1.3 Micro-chip\nat landing",    "compat": ["residue"], "fc_key": "microchip",    "moisture": 40},
    "1.4": {"label": "1.4 Micro-chip\nat plant",      "compat": ["residue"], "fc_key": "microchip",    "moisture": 45},
    "2.1": {"label": "2.1 Grind sorted\nat landing",  "compat": ["residue"], "fc_key": "grinder_sort", "moisture": 50},
    "2.2": {"label": "2.2 Grind sorted\nat plant",    "compat": ["residue"], "fc_key": "grinder_sort", "moisture": 50},
    "2.3": {"label": "2.3 Grind all\n(no sorting)",   "compat": ["residue"], "fc_key": "grinder_none", "moisture": 55},
    "3.1": {"label": "3.1 Mill/pulp\n(no processing)","compat": ["mill","pulp"], "fc_key": "none",    "moisture": 20},
    "4.1": {"label": "4.1 Disc chip\nat landing",     "compat": ["residue"], "fc_key": "disc_forest",  "moisture": 40},
    "4.2": {"label": "4.2 Disc chip\nat plant",       "compat": ["residue"], "fc_key": "disc_forest",  "moisture": 45},
    "4.3": {"label": "4.3 Micro-chip\nat landing",    "compat": ["residue"], "fc_key": "microchip",    "moisture": 40},
    "4.4": {"label": "4.4 Micro-chip\nat plant",      "compat": ["residue"], "fc_key": "microchip",    "moisture": 45},
}

OPTION_MAP = {
    "residue": ["1.1","1.2","1.3","1.4","2.1","2.2","2.3","3.1","4.1","4.2","4.3","4.4"],
}

# Options for which a screener can be added (disc chipper family only)
# Sahoo (2019): screener used with disc chippers, NOT with grinders or micro-chippers
SCREENER_ELIGIBLE = {"1.1", "1.2","4.1","4.2"}


def calculate_one(biomass, code, include_screener=False):
    """
    Calculate processing emissions for one option.

    Parameters
    ----------
    biomass         : float  -- odt/yr
    code            : str    -- option code from PROCESSING_OPTIONS
    include_screener: bool   -- if True AND option is disc chipper (1.1/1.2),
                                add star screener fuel consumption on top.
                                This reproduces the old 1.1S / 1.2S behaviour.
                                Dashboard shows a checkbox for this when 1.1 or
                                1.2 is selected.

    Returns dict of results (same structure as before).
    """
    opt        = PROCESSING_OPTIONS[code]
    fc_l, fc_h = FC_RANGES[opt["fc_key"]]

    # Add screener if requested AND this option supports it
    _screener_added = False
    if include_screener and code in SCREENER_ELIGIBLE:
        sc_l, sc_h = FC_RANGES["star_screener"]
        fc_l += sc_l
        fc_h += sc_h
        _screener_added = True

    fc_m = (fc_l + fc_h) / 2

    rows = {}
    for tag, fc in [("low", fc_l), ("mid", fc_m), ("high", fc_h)]:
        diesel_L  = fc * biomass
        CO2_t     = diesel_L * EF_DIESEL_CO2_KG_PER_L / 1000
        diesel_MJ = diesel_L * NCV_DIESEL_MJ_PER_L
        CH4_t     = diesel_MJ * EF_CH4_G_PER_MJ / 1e6
        CH4_CO2e  = CH4_t * GWP_CH4
        N2O_t     = diesel_MJ * EF_N2O_G_PER_MJ / 1e6
        N2O_CO2e  = N2O_t * GWP_N2O
        rows[tag] = {
            "fc": fc, "CO2_t": CO2_t,
            "CH4_t": CH4_t, "CH4_CO2e": CH4_CO2e,
            "N2O_t": N2O_t, "N2O_CO2e": N2O_CO2e,
            "total": CO2_t + CH4_CO2e + N2O_CO2e,
        }

    # Build display label — append "+screener" if applicable
    label = opt["label"]
    if _screener_added:
        label = label + "\n+screener"

    return {
        "code":            code,
        "label":           label,
        "screener_added":  _screener_added,
        "fc_range":        (fc_l, fc_m, fc_h),
        **rows,
    }


def print_results(all_r):
    print(f"\n  RESULTS — MID FC ESTIMATE")
    print("-" * 72)
    print(f"  {'Opt':<8} {'Label':<34} {'CO2 (t)':>10} {'CH4 CO2e':>10} {'N2O CO2e':>10} {'Total (t)':>10}")
    print("-" * 72)
    for r in all_r:
        m   = r["mid"]
        lbl = r["label"].replace("\n", " ")
        print(f"  {r['code']:<8} {lbl:<34} {m['CO2_t']:>10,.2f} {m['CH4_CO2e']:>10,.3f} {m['N2O_CO2e']:>10,.3f} {m['total']:>10,.2f}")
    print("-" * 72)
    print(f"  Units: tCO2e/yr")


def plot_all(all_r, biomass, residue, outpath):
    n       = len(all_r)
    colors  = ["#2563EB", "#D97706", "#16A34A"]
    glabels = ["CO2", "CH4 (as CO2e)", "N2O (as CO2e)"]
    x       = np.arange(n)
    w       = 0.55

    def kt(v): return v / 1000

    fig, ax = plt.subplots(figsize=(11, 6))
    fig.patch.set_facecolor("#FAFAFA")
    ax.set_facecolor("#FAFAFA")

    for i, r in enumerate(all_r):
        m    = r["mid"]
        segs = [kt(m["CO2_t"]), kt(m["CH4_CO2e"]), kt(m["N2O_CO2e"])]
        tot  = sum(segs)
        bot  = 0
        for seg, col, lbl in zip(segs, colors, glabels):
            ax.bar(x[i], seg, w, bottom=bot, color=col,
                   label=lbl if i == 0 else "_nolegend_",
                   edgecolor="white", linewidth=0.6)
            if seg > tot * 0.04:
                ax.text(x[i], bot + seg / 2, f"{seg:.3f}",
                        ha="center", va="center",
                        fontsize=7.5, color="white", fontweight="bold")
            bot += seg
        ax.text(x[i], tot + tot * 0.025, f"{tot:.3f}",
                ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#111")

    ax.set_xticks(x)
    ax.set_xticklabels([r["label"] for r in all_r], fontsize=8.5)
    ax.set_ylabel("Emissions (kt CO2e / yr)", fontsize=11)
    ax.set_title(
        f"Processing Emissions (Average FC estimate)\n"
        f"{residue.capitalize()} residues  |  {biomass:,.0f} odt/yr",
        fontsize=10, fontweight="bold", pad=10
    )
    ax.legend(fontsize=9, loc="upper left", framealpha=0.85)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.3f}"))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#ddd", linewidth=0.6)

    plt.tight_layout()
    plt.savefig(outpath, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  Chart saved -> {outpath}")


if __name__ == "__main__":
    residue = RESIDUE_TYPE.lower().strip()
    codes   = OPTION_MAP.get(residue, OPTION_MAP["residue"])

    print(f"\nResidueType={residue}, Biomass={BIOMASS_ODT_YR:,} odt/yr")
    print("Running all options (no screener):")
    all_r = [calculate_one(BIOMASS_ODT_YR, c) for c in codes]
    print_results(all_r)

    if residue == "residue":
        print("\nRunning 1.1 and 1.2 WITH screener (checkbox=True):")
        for c in ["1.1", "1.2"]:
            r = calculate_one(BIOMASS_ODT_YR, c, include_screener=True)
            m = r["mid"]
            print(f"  {r['code']} +screener: {m['total']:.2f} t CO2e/yr  "
                  f"(vs {calculate_one(BIOMASS_ODT_YR, c)['mid']['total']:.2f} without)")

    plot_all(all_r, BIOMASS_ODT_YR, residue, CHART_OUTPATH)