"""
Biomass_Transport.py  (formerly Sahoo_Final.py)
=======================
Forest residue delivered cost calculator based on Sahoo et al. (2019).

All inputs and outputs use US customary / English units:
  - Distance : miles (one-way haul)
  - Speed    : mph
  - Cost     : $/ODT  (oven-dry short tons; 1 ODT = 2,000 lb)

Public API
----------
delivered_cost(option_id, distance_miles, speed_mph, cost_year) -> dict
    Single-point cost breakdown for one option.

cost_vs_distance(option_id, speed_mph, cost_year, distance_range, n_points) -> pd.DataFrame
    Delivered cost curve across a distance range (5–200 miles).

compare_options(distance_miles, speed_mph, cost_year, option_ids) -> pd.DataFrame
    Selected options at a single distance/speed, sorted by total cost.

plot_cost_vs_distance(option_id, speed_mph, cost_year, mark_distance, ax) -> Figure
    Stacked-area chart of cost components vs haul distance for one option.

plot_compare_options(distance_miles, speed_mph, cost_year, option_ids, ax) -> Figure
    Stacked horizontal bar chart comparing options at a fixed distance.
    Pass option_ids to restrict to a subset (e.g. ["1.1","1.2"] for SAF forest).

plot_cost_sensitivity(option_id, distance_miles, speed_mph, cost_year,
                      param, pct_range, n_points, ax) -> Figure
    Tornado-style sensitivity: vary one base parameter ± pct_range and show
    how total delivered cost responds.  Useful for understanding which cost
    driver matters most at a given haul distance.

plot_speed_sensitivity(option_id, distance_miles, cost_year,
                       speed_range, ax) -> Figure
    Total delivered cost vs truck speed for one option at a fixed distance.
    Shows the operating speed that minimises cost (typically 25–35 mph).

plot_multi_option_distance(option_ids, speed_mph, cost_year,
                           distance_range, ax) -> Figure
    Line chart: total delivered cost vs distance for multiple options on one
    set of axes.  Reveals the distance at which options cross over in cost
    rank — handy for choosing between chip-at-landing vs log-truck strategies.

plot_cost_breakdown_bar(option_id, distance_miles, speed_mph, cost_year,
                        ax) -> Figure
    Simple vertical stacked bar showing the three cost components as absolute
    $/ODT values with percentage annotations.  Good for a concise single-scenario
    snapshot in a report or dashboard card.

Options
-------
  1.1  Chip at landing → chip truck       (disc_chipper + star_screener, chips)
  1.2  Log truck → chip at plant          (disc_chipper + star_screener, logs)
  1.3  Micro-chip at landing → chip truck (microchipper, microchips)
  1.4  Log truck → micro-chip at plant    (microchipper, logs)
  2.1  Grind slash at landing → hog fuel  (drum_grinder, hog_fuel, +BSTP)
  2.2  Slash truck → grind at plant       (drum_grinder, slash, +BSTP)
  2.3  Grind all residues (no sorting)    (drum_grinder, hog_fuel, no BSTP)
  3.1  Mill residues — direct transport   (no processing, mill_residues)
"""

from __future__ import annotations
from functools import lru_cache
import numpy as np
import pandas as pd
import os

# ---------------------------------------------------------------------------
# Unit conversion constants
# ---------------------------------------------------------------------------

_MI_TO_KM    = 1.60934        # miles → km
_MPH_TO_KMH  = 1.60934        # mph   → km/h
_ODMT_TO_ODT = 1.10231        # 1 oven-dry metric ton = 1.10231 oven-dry short tons
                               # $/ODMT ÷ _ODMT_TO_ODT = $/ODT

_CPI = {  # CPI-U annual averages (BLS); 2024-2026 estimated/projected
    2006:201.6, 2007:207.3, 2008:215.3, 2009:214.5, 2010:218.1,
    2011:224.9, 2012:229.6, 2013:233.0, 2014:236.7, 2015:237.0,
    2016:240.0, 2017:245.1, 2018:251.1, 2019:255.7, 2020:258.8,
    2021:271.0, 2022:292.7, 2023:304.1, 2024:310.3, 2025:316.8, 2026:323.4,
}

# ---------------------------------------------------------------------------
# Constants — all from Sahoo et al. (2019) Tables 1–3
# (internal calculations remain in SI; outputs converted to $/ODT)
# ---------------------------------------------------------------------------

# Truck/tractor (Table 3)
_T = dict(
    tractor_price    = 130_000,
    trailer_log      =  38_000,
    trailer_chip_van =  80_000,
    salvage          =   0.20,
    tractor_life_km  = 1_207_008,
    tractor_life_yr  =  10,
    trailer_life_km  = 2_414_016,
    trailer_life_yr  =  20,
    utilization      =   0.85,
    driver_wage      =  20.81,
    fringe           =   0.35,
    fuel_km_per_l    =   2.17,
    fuel_price       =   0.75,   # $/L
    oil_km           =  16_000,
    oil_days         =  28,
    oil_price        = 242.89,
    n_steering       =   2,
    n_drive          =   8,
    n_trailer        =   8,
    steer_life_km    =  40_000,
    drive_life_km    =  65_000,
    trailer_life_km2 =  65_000,
    new_tire         = 465.78,
    retread          = 174.67,
    pct_new_drive    =   0.20,
    pct_new_trailer  =   0.20,
    lube_per_km      =   0.041,
    admin_per_day    =  12.5,
    license_annual   =  2_225,
    misc_annual      =  2_000,
    insurance_pct    =   0.0595,
    working_days     = 270,
    hours_per_day    =  11,
)

# Feedstock transport config: (trailer price, load min, unload min, payload ODMT)
_FEEDSTOCK = {
    "logs":          (_T["trailer_log"],      14.0, 14.0,  17.00),
    "chips":         (_T["trailer_chip_van"], 37.0, 18.5,  18.30),
    "microchips":    (_T["trailer_chip_van"], 37.0, 18.5,  18.30 * 1.07),
    "hog_fuel":      (_T["trailer_chip_van"], 37.0, 18.5,  12.50),
    "slash":         (_T["trailer_chip_van"], 37.0, 18.5,   8.90),
    "mill_residues": (_T["trailer_chip_van"], 37.0, 18.5,  14.50),
}

# Processing equipment (Table 2)
# (kW, price, salvage, life_yr, util, repair_pct, fuel_l_kwh, prod_odmt_hr, loader_key)
_EQUIP = {
    "disc_chipper":  (650,  457_696, 0.20, 5, 0.80, 1.00, 0.12,  37.40, "jd"),
    "drum_chipper":  (570,  406_841, 0.20, 5, 0.80, 1.00, 0.11,  37.70, "jd"),
    "microchipper":  (570,  522_790, 0.20, 5, 0.80, 1.00, 0.13,  33.25, "jd"),
    "tub_grinder":   (470,  522_780, 0.20, 5, 0.90, 0.90, 0.15,  14.59, "jd"),
    "drum_grinder":  (783,  661_116, 0.20, 5, 0.85, 1.00, 0.13,  37.75, "fel"),
    "deck_screener": (95.5, 340_000, 0.20, 8, 0.85, 0.30, 0.12,  13.05, "fel"),
    "star_screener": (55,   495_000, 0.20, 8, 0.85, 1.00, 0.12,  31.10, "jd"),
}

# Loaders: (price, salvage, life_yr, util, repair_pct, fuel_l_kwh, kW)
_LOADER = {
    "fel": (104_490, 0.321, 10, 0.85, 1.00, 0.26,  76),
    "jd":  (432_268, 0.20,  10, 0.80, 0.80, 0.16, 145),
}

# Base economic params (Table 1)
_E = dict(
    r           = 0.06,
    insurance   = 0.03,
    labor_wage  = 17.73,
    fringe      = 0.35,
    fuel_price  = 0.61,   # $/L
    lube_pct    = 0.385,
    sched_hr_yr = 2_160,
    load_factor = 0.54,
)

_BSTP_2017 = 30.0   # $/ODMT in 2017 dollars (moderate-intensity sorting)
_BASE_YEAR  = 2017

# Supply chain option definitions — exposed without underscore for dashboard access
OPTIONS: dict[str, dict] = {
    "1.1": dict(label="Chip at landing → chip truck",       equip=["disc_chipper","star_screener"], transport="chips",         bstp=True),
    "1.2": dict(label="Log truck → chip at plant",          equip=["disc_chipper","star_screener"], transport="logs",          bstp=True),
    "1.3": dict(label="Micro-chip at landing → chip truck", equip=["microchipper"],                 transport="microchips",    bstp=True),
    "1.4": dict(label="Log truck → micro-chip at plant",    equip=["microchipper"],                 transport="logs",          bstp=True),
    "2.1": dict(label="Grind slash at landing → hog fuel",  equip=["drum_grinder"],                 transport="hog_fuel",      bstp=True),
    "2.2": dict(label="Slash truck → grind at plant",       equip=["drum_grinder"],                 transport="slash",         bstp=True),
    "2.3": dict(label="Grind all residues (no sorting)",    equip=["drum_grinder"],                 transport="hog_fuel",      bstp=False),
    "3.1": dict(label="Mill residues — direct transport",   equip=[],                               transport="mill_residues", bstp=False),
    "4.1": dict(label="Chip at landing → chip truck",       equip=["disc_chipper","star_screener"], transport="chips",         bstp=False),
    "4.2": dict(label="Log truck → chip at plant",          equip=["disc_chipper","star_screener"], transport="logs",          bstp=False),
    "4.3": dict(label="Micro-chip at landing → chip truck", equip=["microchipper"],                 transport="microchips",    bstp=False),
    "4.4": dict(label="Log truck → micro-chip at plant",    equip=["microchipper"],                 transport="logs",          bstp=False),
}

# Underscore alias kept for backward compatibility with any existing callers
_OPTIONS = OPTIONS

# ---------------------------------------------------------------------------
# Internal helpers  (all work in SI; costs in $/ODMT until final conversion)
# ---------------------------------------------------------------------------

def _crf(r: float, n: float) -> float:
    """Capital Recovery Factor."""
    return (r * (1 + r)**n) / ((1 + r)**n - 1)


def _annual_costs_machine(price: float, salvage: float, life_yr: float,
                           kw: float, fuel_l_kwh: float, repair_pct: float,
                           util: float) -> float:
    """Total annual cost ($) for one machine — Sahoo et al. method."""
    r, E = _E["r"], _E
    n    = life_yr

    acc       = _crf(r, n) * (price * (1 - salvage)) / (1 + r)**n
    ayi       = (price * (1 - salvage) * (n + 1)) / (2 * n) + salvage * price
    fixed     = acc + ayi * E["insurance"]

    pmh       = E["sched_hr_yr"] * util
    fuel      = kw * E["load_factor"] * fuel_l_kwh * E["fuel_price"] * pmh
    oil       = fuel * E["lube_pct"]
    repair    = repair_pct * (price * (1 - salvage) / n)
    labor     = E["sched_hr_yr"] * E["labor_wage"] * (1 + E["fringe"])

    return fixed + fuel + oil + repair + labor


@lru_cache(maxsize=None)
def _processing_cost_per_odmt(equip_key: str) -> float:
    """$/ODMT for one piece of processing equipment plus its loader. Cached.

    Note — replicates original Sahoo code behaviour:
      • Loader fixed costs use the loader's purchase price but the
        *equipment's* salvage and life (not the loader's own values).
      • Loader variable costs (fuel, oil, repair, labor) are computed
        using the *equipment's* kW, fuel rate, and price — matching the
        original code's use of self.* attributes throughout.
    """
    kw, price, salvage, life, util, repair, fuel_l, prod, loader_key = _EQUIP[equip_key]
    lp  = _LOADER[loader_key]   # (price, salvage, life, util, repair, fuel, kw)
    pmh = _E["sched_hr_yr"] * util

    eq_annual = _annual_costs_machine(price, salvage, life, kw, fuel_l, repair, util)

    # Loader fixed: loader purchase price, but equipment salvage & life
    r, n         = _E["r"], life
    loader_acc   = _crf(r, n) * (lp[0] * (1 - salvage)) / (1 + r)**n
    loader_ayi   = (lp[0] * (1 - salvage) * (n + 1)) / (2 * n) + salvage * lp[0]
    loader_fixed = loader_acc + loader_ayi * _E["insurance"]

    # Loader variable: equipment kW/fuel/price (matches original self.* usage)
    loader_fuel   = kw * _E["load_factor"] * fuel_l * _E["fuel_price"] * pmh
    loader_oil    = loader_fuel * _E["lube_pct"]
    loader_repair = repair * (price * (1 - salvage) / life)
    loader_labor  = _E["sched_hr_yr"] * _E["labor_wage"] * (1 + _E["fringe"])
    loader_var    = loader_fuel + loader_oil + loader_repair + loader_labor

    return (eq_annual + loader_fixed + loader_var) / pmh / prod


def _transport_cost_per_odmt(feedstock: str, distance_km: float,
                              speed_kmh: float) -> float:
    """$/ODMT for truck transport at a given one-way distance and speed."""
    trailer_price, load_min, unload_min, payload = _FEEDSTOCK[feedstock]
    t = _T

    pmh_yr    = t["working_days"] * t["hours_per_day"] * t["utilization"]
    annual_km = pmh_yr * speed_kmh

    def _fixed(price: float, salvage: float, life_km: float,
               life_yr: float, licensed: bool) -> float:
        n   = min(life_km / annual_km, life_yr)
        r   = 0.06
        acc = _crf(r, n) * (price * (1 - salvage)) / (1 + r)**n
        ayi = (price * (1 - salvage) * (n + 1)) / (2 * n) + salvage * price
        lic = (t["license_annual"] + t["misc_annual"]) if licensed else 0.0
        return acc + ayi * t["insurance_pct"] + lic

    def _variable(is_tractor: bool) -> float:
        lube = t["lube_per_km"] * annual_km
        if is_tractor:
            fuel  = annual_km * t["fuel_price"] / (1/t["fuel_km_per_l"] + 1/t["fuel_km_per_l"])
            oil   = max(annual_km / t["oil_km"], 365 / t["oil_days"]) * t["oil_price"]
            steer = t["n_steering"] * annual_km / t["steer_life_km"] * t["new_tire"]
            d_new = t["n_drive"] * annual_km * t["pct_new_drive"] / t["drive_life_km"] * t["new_tire"]
            d_ret = t["n_drive"] * annual_km * (1 - t["pct_new_drive"]) / (t["drive_life_km"] * 0.8) * t["retread"]
            admin = t["admin_per_day"] * t["working_days"]
            labor = t["hours_per_day"] * t["working_days"] * t["driver_wage"] * (1 + t["fringe"])
            return fuel + oil + steer + d_new + d_ret + lube + admin + labor
        else:
            t_new = t["n_trailer"] * annual_km * t["pct_new_trailer"] / t["trailer_life_km2"] * t["new_tire"]
            t_ret = t["n_trailer"] * annual_km * (1 - t["pct_new_trailer"]) / (t["trailer_life_km2"] * 0.8) * t["retread"]
            return t_new + t_ret + lube

    total_annual = (
        _fixed(t["tractor_price"], t["salvage"], t["tractor_life_km"], t["tractor_life_yr"], True)  +
        _fixed(trailer_price,      t["salvage"], t["trailer_life_km"], t["trailer_life_yr"], False) +
        _variable(True) + _variable(False)
    )
    hourly = total_annual / pmh_yr
    trip_h = (load_min + unload_min) / 60.0 + 2 * distance_km / speed_kmh
    return trip_h * hourly / payload


def _inflation(from_year: int, to_year: int) -> float:
    """CPI-U inflation multiplier between two years."""
    if from_year not in _CPI or to_year not in _CPI:
        raise ValueError(f"CPI data unavailable for {from_year} or {to_year}. "
                         f"Available: {min(_CPI)}-{max(_CPI)}")
    return _CPI[to_year] / _CPI[from_year]


def _to_odt(cost_per_odmt: float) -> float:
    """Convert $/ODMT → $/ODT."""
    return cost_per_odmt / _ODMT_TO_ODT


# ---------------------------------------------------------------------------
# Public API — core calculations
# ---------------------------------------------------------------------------

def delivered_cost(
    option_id: str,
    distance_miles: float,
    speed_mph: float = 20.0,
    cost_year: int = 2025,
) -> dict:
    """
    Calculate delivered cost breakdown for one supply chain option.

    Parameters
    ----------
    option_id : str
        One of '1.1', '1.2', ..., '3.1'  (see module docstring).
    distance_miles : float
        One-way haul distance in miles.  Must be > 0.
    speed_mph : float
        Average truck speed in mph (default 20 mph ≈ 32 km/h, typical forest road).
    cost_year : int
        Dollar-year for output costs (CPI inflation from 2017 base year).

    Returns
    -------
    dict with keys:
        option_id, label, distance_miles, speed_mph, cost_year,
        bstp, processing, transportation, total   — all $/ODT
    """
    if option_id not in OPTIONS:
        raise ValueError(f"Unknown option '{option_id}'. Choose from: {list(OPTIONS)}")
    if distance_miles <= 0:
        raise ValueError(f"distance_miles must be > 0, got {distance_miles}")

    opt       = OPTIONS[option_id]
    mult      = _inflation(_BASE_YEAR, cost_year)
    dist_km   = distance_miles * _MI_TO_KM
    speed_kmh = speed_mph * _MPH_TO_KMH

    bstp           = _to_odt((_BSTP_2017 * mult) if opt["bstp"] else 0.0)
    processing     = _to_odt(sum(_processing_cost_per_odmt(eq) for eq in opt["equip"]) * mult)
    transportation = _to_odt(_transport_cost_per_odmt(opt["transport"], dist_km, speed_kmh) * mult)

    return {
        "option_id":      option_id,
        "label":          opt["label"],
        "distance_miles": distance_miles,
        "speed_mph":      speed_mph,
        "cost_year":      cost_year,
        "bstp":           round(bstp,           4),
        "processing":     round(processing,     4),
        "transportation": round(transportation, 4),
        "total":          round(bstp + processing + transportation, 4),
    }


def cost_vs_distance(
    option_id: str,
    speed_mph: float = 20.0,
    cost_year: int = 2025,
    distance_range: tuple[float, float] = (5, 200),
    n_points: int = 80,
) -> pd.DataFrame:
    """
    Delivered cost curve over a range of haul distances.

    Returns
    -------
    pd.DataFrame with columns:
        distance_miles, bstp, processing, transportation, total  — all $/ODT
    """
    distances = np.linspace(distance_range[0], distance_range[1], n_points)
    opt       = OPTIONS[option_id]
    mult      = _inflation(_BASE_YEAR, cost_year)
    speed_kmh = speed_mph * _MPH_TO_KMH

    bstp_val = _to_odt((_BSTP_2017 * mult) if opt["bstp"] else 0.0)
    proc_val = _to_odt(sum(_processing_cost_per_odmt(eq) for eq in opt["equip"]) * mult)

    trans_vals = np.array([
        _to_odt(_transport_cost_per_odmt(opt["transport"], d * _MI_TO_KM, speed_kmh) * mult)
        for d in distances
    ])

    return pd.DataFrame({
        "distance_miles": distances,
        "bstp":           bstp_val,
        "processing":     proc_val,
        "transportation": trans_vals,
        "total":          bstp_val + proc_val + trans_vals,
    })


def compare_options(
    distance_miles: float,
    speed_mph: float = 20.0,
    cost_year: int = 2025,
    option_ids: list[str] | None = None,
) -> pd.DataFrame:
    """
    Compare supply chain options at a given distance and speed.

    Parameters
    ----------
    option_ids : list of str, optional
        Subset of option IDs to include (e.g. ["1.1","1.2","1.3","1.4"] for
        SAF forest, ["2.1","2.2","2.3"] for bioenergy forest, ["3.1"] for mill).
        If None, all eight options are included.

    Returns
    -------
    pd.DataFrame sorted by ascending total cost, with columns:
        option_id, label, bstp, processing, transportation, total  — all $/ODT
    """
    ids  = option_ids if option_ids is not None else list(OPTIONS)
    rows = [delivered_cost(oid, distance_miles, speed_mph, cost_year) for oid in ids]
    df   = pd.DataFrame(rows)[["option_id","label","bstp","processing","transportation","total"]]
    return df.sort_values("total").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

# ── Dashboard-matched dark theme ─────────────────────────────────────────────
# Colors align with the Streamlit dashboard palette:
#   bstp           → forest green  (#22c55e family)
#   processing     → amber         (#f59e0b family)
#   transportation → steel blue    (#60a5fa family)
_C = dict(bstp="#1a7a40", processing="#c97d10", transportation="#2563a8")

_BG      = "#0e1621"   # dark navy — matches dashboard background
_BG_AX   = "#131f2e"   # slightly lighter for axes area
_GRID    = "#1e2d3d"   # subtle grid lines
_TEXT    = "#c9d1e0"   # light grey text
_TEXT_DIM= "#4a5a6a"   # dimmed label text
_SPINE   = "#1e2d3d"   # spine color
_FONT    = "DejaVu Sans"  # matplotlib default; closest to dashboard sans-serif

def _apply_style(ax) -> None:
    """Apply dark dashboard theme to a matplotlib Axes."""
    fig = ax.get_figure()
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG_AX)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(_SPINE)
    ax.yaxis.grid(True, linestyle="--", linewidth=0.5, color=_GRID)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    ax.tick_params(colors=_TEXT, labelsize=9)
    ax.xaxis.label.set_color(_TEXT)
    ax.yaxis.label.set_color(_TEXT)
    ax.title.set_color(_TEXT)
    # Dollar sign labels on axes — ensure they render as plain text
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color(_TEXT)


# ---------------------------------------------------------------------------
# Plot 1 — stacked area: cost vs distance for one option
# ---------------------------------------------------------------------------

def plot_cost_vs_distance(
    option_id: str,
    speed_mph: float = 20.0,
    cost_year: int = 2025,
    mark_distance: float | None = None,
    ax=None,
):
    """
    Stacked-area chart of BSTP / processing / transportation vs haul distance
    for a single supply-chain option.

    Parameters
    ----------
    mark_distance : float, optional
        Draw a vertical dashed reference line at this distance (miles).
        Annotated with the total $/ODT at that distance.
    ax : matplotlib Axes, optional
        Axes to draw on; creates a new figure if None.

    Returns
    -------
    matplotlib.figure.Figure
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    df  = cost_vs_distance(option_id, speed_mph, cost_year)
    opt = OPTIONS[option_id]

    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        fig.patch.set_facecolor(_BG)
    else:
        fig = ax.get_figure()
    ax.set_facecolor(_BG_AX)

    x     = df["distance_miles"].values
    bstp  = df["bstp"].values
    proc  = df["processing"].values
    trans = df["transportation"].values

    ax.fill_between(x, 0,           bstp,                color=_C["bstp"],          alpha=0.85)
    ax.fill_between(x, bstp,        bstp + proc,         color=_C["processing"],    alpha=0.85)
    ax.fill_between(x, bstp + proc, bstp + proc + trans, color=_C["transportation"],alpha=0.85)

    for bottom, top, color in [
        (np.zeros_like(x), bstp,           _C["bstp"]),
        (bstp,             bstp + proc,     _C["processing"]),
        (bstp + proc,      bstp+proc+trans, _C["transportation"]),
    ]:
        if np.any(top - bottom > 0.01):
            ax.plot(x, top, color=color, linewidth=1.2)

    if mark_distance is not None:
        idx   = int(np.argmin(np.abs(x - mark_distance)))
        total = bstp[idx] + proc[idx] + trans[idx]
        ax.axvline(mark_distance, color=_TEXT, linewidth=1.4, linestyle="--", zorder=5)
        ax.text(mark_distance + 1.5, ax.get_ylim()[1] * 0.97,
                f"{mark_distance:.0f} mi\n${total:.1f}/ODT",
                fontsize=8.5, color=_TEXT, va="top", linespacing=1.4)

    ax.set_xlabel("Haul distance (miles)", fontsize=10)
    ax.set_ylabel(rf"Delivered cost (\$/ODT, {cost_year} \$)", fontsize=10)
    ax.set_title(
        f"Option {option_id} — {opt['label']}\nAvg speed {speed_mph:.0f} mph",
        fontsize=11, fontweight="bold", pad=10,
    )
    ax.set_xlim(x[0], x[-1])
    ax.set_ylim(0)
    ax.legend(
        handles=[
            mpatches.Patch(color=_C["bstp"],          label="Sorting (BSTP)"),
            mpatches.Patch(color=_C["processing"],     label="Processing"),
            mpatches.Patch(color=_C["transportation"], label="Transportation"),
        ],
        fontsize=9, framealpha=0.85, facecolor=_BG, edgecolor=_SPINE, labelcolor=_TEXT, loc="lower right",
    )
    _apply_style(ax)
    if standalone:
        fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Plot 2 — horizontal stacked bar: compare options at a fixed distance
# ---------------------------------------------------------------------------

def plot_compare_options(
    distance_miles: float,
    speed_mph: float = 20.0,
    cost_year: int = 2025,
    option_ids: list[str] | None = None,
    ax=None,
):
    """
    Horizontal stacked bar chart comparing supply-chain options at a fixed distance.
    Bars sorted by ascending total cost.

    Parameters
    ----------
    option_ids : list of str, optional
        Restrict chart to this subset of options.  If None, all eight options
        are shown.  Pass e.g. ["1.1","1.2","1.3","1.4"] when comparing SAF
        forest options, or ["2.1","2.2","2.3"] for bioenergy forest.
    ax : matplotlib Axes, optional
        Axes to draw on; creates a new figure if None.

    Returns
    -------
    matplotlib.figure.Figure
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    df = compare_options(distance_miles, speed_mph, cost_year, option_ids)

    standalone = ax is None
    if standalone:
        n_bars = len(df)
        fig, ax = plt.subplots(figsize=(9, 1.5 + n_bars * 0.65))
        fig.patch.set_facecolor(_BG)
    else:
        fig = ax.get_figure()
    ax.set_facecolor(_BG_AX)

    y_labels = [f"Opt {r.option_id}" for r in df.itertuples()]
    y        = np.arange(len(df))
    bstp     = df["bstp"].values
    proc     = df["processing"].values
    trans    = df["transportation"].values
    totals   = df["total"].values

    bar_h = 0.55
    ax.barh(y, bstp,  bar_h,                  color=_C["bstp"],          edgecolor="white", linewidth=0.7)
    ax.barh(y, proc,  bar_h, left=bstp,        color=_C["processing"],    edgecolor="white", linewidth=0.7)
    ax.barh(y, trans, bar_h, left=bstp + proc, color=_C["transportation"],edgecolor="white", linewidth=0.7)

    for i, total in enumerate(totals):
        ax.text(total + 0.3, i, f"${total:.1f}", va="center", ha="left",
                fontsize=9, fontweight="bold", color=_TEXT)

    ax.set_yticks(y)
    ax.set_yticklabels(y_labels, fontsize=9)
    ax.set_xlabel(f"Delivered cost ($/ODT, {cost_year} $)", fontsize=10)
    ax.set_title(
        f"Supply Chain Option Comparison\n"
        f"{distance_miles:.0f}-mile haul · {speed_mph:.0f} mph avg speed",
        fontsize=11, fontweight="bold", pad=10,
    )
    ax.set_xlim(0, totals.max() * 1.15)
    ax.legend(
        handles=[
            mpatches.Patch(color=_C["bstp"],          label="Sorting (BSTP)"),
            mpatches.Patch(color=_C["processing"],     label="Processing"),
            mpatches.Patch(color=_C["transportation"], label="Transportation"),
        ],
        fontsize=9, framealpha=0.85, facecolor=_BG, edgecolor=_SPINE, labelcolor=_TEXT, loc="lower right",
    )
    _apply_style(ax)
    ax.xaxis.grid(True, linestyle="--", linewidth=0.6, color=_GRID)
    ax.yaxis.grid(False)
    if standalone:
        fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Plot 3 — multi-option line chart: total cost vs distance
# ---------------------------------------------------------------------------

def plot_multi_option_distance(
    option_ids: list[str] | None = None,
    speed_mph: float = 20.0,
    cost_year: int = 2025,
    distance_range: tuple[float, float] = (5, 200),
    mark_distance: float | None = None,
    ax=None,
):
    """
    Total delivered cost vs haul distance for multiple options on one axes.

    Useful for identifying the distance breakeven point between options —
    e.g. at what haul distance does chipping at landing become cheaper than
    sending whole logs to the plant.

    Parameters
    ----------
    option_ids : list of str, optional
        Options to plot.  Defaults to all eight.  Pass a subset for clarity
        (e.g. ["1.1","1.2","2.1"] to compare the main forest options).
    mark_distance : float, optional
        Draw a vertical reference line at this distance (weighted avg haul).
    ax : matplotlib Axes, optional

    Returns
    -------
    matplotlib.figure.Figure
    """
    import matplotlib.pyplot as plt

    ids = option_ids if option_ids is not None else list(OPTIONS)

    # Colour cycle — enough for up to 8 lines
    _line_colors = [
        "#2e5fa3", "#c9782a", "#4a7c59", "#8b3a8b",
        "#c94040", "#3a8ba0", "#a08b3a", "#555555",
    ]

    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(9, 5))
        fig.patch.set_facecolor(_BG)
    else:
        fig = ax.get_figure()
    ax.set_facecolor(_BG_AX)

    for idx, oid in enumerate(ids):
        df    = cost_vs_distance(oid, speed_mph, cost_year, distance_range)
        color = _line_colors[idx % len(_line_colors)]
        ax.plot(df["distance_miles"], df["total"],
                color=color, linewidth=2.0,
                label=f"{oid} — {OPTIONS[oid]['label']}")

    if mark_distance is not None:
        ax.axvline(mark_distance, color="#333333", linewidth=1.3,
                   linestyle="--", zorder=5)
        ax.text(mark_distance + 1.5, ax.get_ylim()[1] * 0.98,
                f"{mark_distance:.0f} mi",
                fontsize=8.5, color="#333333", va="top")

    ax.set_xlabel("Haul distance (miles)", fontsize=10)
    ax.set_ylabel(f"Total delivered cost ($/ODT, {cost_year} $)", fontsize=10)
    ax.set_title(
        f"Cost vs Distance — {speed_mph:.0f} mph avg speed",
        fontsize=11, fontweight="bold", pad=10,
    )
    ax.set_xlim(distance_range[0], distance_range[1])
    ax.set_ylim(0)
    ax.legend(fontsize=9, framealpha=0.85, facecolor=_BG, edgecolor=_SPINE, labelcolor=_TEXT,
              loc="upper left", ncol=1)
    _apply_style(ax)
    if standalone:
        fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Plot 4 — speed sensitivity: total cost vs truck speed at fixed distance
# ---------------------------------------------------------------------------

def plot_speed_sensitivity(
    option_id: str,
    distance_miles: float,
    cost_year: int = 2025,
    speed_range: tuple[float, float] = (10, 50),
    mark_speed: float | None = None,
    n_points: int = 60,
    ax=None,
):
    """
    Total delivered cost vs average truck speed for one option at a fixed distance.

    Shows how sensitive the economics are to road conditions / speed restrictions.
    The transportation component is the only one that varies with speed; BSTP and
    processing are drawn as a flat reference band at the bottom.

    Parameters
    ----------
    distance_miles : float
        Fixed one-way haul distance (miles).
    speed_range : (min_mph, max_mph)
        Speed range to sweep.
    mark_speed : float, optional
        Draw a vertical marker at this speed (e.g. the current slider value).
    ax : matplotlib Axes, optional

    Returns
    -------
    matplotlib.figure.Figure
    """
    import matplotlib.pyplot as plt

    opt    = OPTIONS[option_id]
    mult   = _inflation(_BASE_YEAR, cost_year)
    dist_km = distance_miles * _MI_TO_KM

    speeds      = np.linspace(speed_range[0], speed_range[1], n_points)
    bstp_val    = _to_odt((_BSTP_2017 * mult) if opt["bstp"] else 0.0)
    proc_val    = _to_odt(sum(_processing_cost_per_odmt(eq) for eq in opt["equip"]) * mult)
    fixed_floor = bstp_val + proc_val

    trans_vals = np.array([
        _to_odt(_transport_cost_per_odmt(opt["transport"], dist_km, s * _MPH_TO_KMH) * mult)
        for s in speeds
    ])
    totals = fixed_floor + trans_vals

    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        fig.patch.set_facecolor(_BG)
    else:
        fig = ax.get_figure()
    ax.set_facecolor(_BG_AX)

    # Shaded band for fixed (non-speed-sensitive) costs
    ax.axhspan(0, fixed_floor, color="#d8e8d8", alpha=0.55, zorder=0)
    ax.text(speed_range[0] + 0.5, fixed_floor * 0.5,
            f"Fixed (BSTP + Processing)\n${fixed_floor:.1f}/ODT",
            fontsize=8, color="#3a6a3a", va="center")

    ax.plot(speeds, totals, color=_C["transportation"], linewidth=2.2, zorder=3)
    ax.fill_between(speeds, fixed_floor, totals,
                    color=_C["transportation"], alpha=0.20, zorder=2)

    if mark_speed is not None:
        idx   = int(np.argmin(np.abs(speeds - mark_speed)))
        total = totals[idx]
        ax.axvline(mark_speed, color="#333333", linewidth=1.3, linestyle="--", zorder=5)
        ax.text(mark_speed + 0.4, total * 1.01,
                f"{mark_speed:.0f} mph\n${total:.1f}/ODT",
                fontsize=8.5, color="#333333", va="bottom", linespacing=1.4)

    ax.set_xlabel("Average truck speed (mph)", fontsize=10)
    ax.set_ylabel(f"Total delivered cost ($/ODT, {cost_year} $)", fontsize=10)
    ax.set_title(
        f"Speed Sensitivity — Option {option_id}\n"
        f"{distance_miles:.0f}-mile haul",
        fontsize=11, fontweight="bold", pad=10,
    )
    ax.set_xlim(speed_range[0], speed_range[1])
    ax.set_ylim(0)
    _apply_style(ax)
    if standalone:
        fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Plot 5 — cost breakdown vertical bar (snapshot card)
# ---------------------------------------------------------------------------

def plot_cost_breakdown_bar(
    option_id: str,
    distance_miles: float,
    speed_mph: float = 20.0,
    cost_year: int = 2025,
    ax=None,
):
    """
    Vertical stacked bar showing BSTP / processing / transportation as $/ODT
    with percentage labels inside each segment.

    Intended as a compact single-scenario snapshot — fits neatly in a dashboard
    column next to a metric card.

    Returns
    -------
    matplotlib.figure.Figure
    """
    import matplotlib.pyplot as plt

    r = delivered_cost(option_id, distance_miles, speed_mph, cost_year)
    components = [
        ("Sorting\n(BSTP)",      r["bstp"],           _C["bstp"]),
        ("Processing",           r["processing"],      _C["processing"]),
        ("Transportation",       r["transportation"],  _C["transportation"]),
    ]
    total = r["total"]

    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(3.5, 5))
        fig.patch.set_facecolor(_BG)
    else:
        fig = ax.get_figure()
    ax.set_facecolor(_BG_AX)

    bottom = 0.0
    for label, value, color in components:
        if value <= 0:
            continue
        ax.bar(0, value, bottom=bottom, color=color, width=0.5,
               edgecolor="white", linewidth=0.8)
        pct = value / total * 100
        if pct >= 5:   # only annotate segments large enough to read
            ax.text(0, bottom + value / 2,
                    f"${value:.1f}\n({pct:.0f}%)",
                    ha="center", va="center",
                    fontsize=9, color="white", fontweight="bold")
        bottom += value

    # Total label above bar
    ax.text(0, total + total * 0.02, f"${total:.1f}/ODT",
            ha="center", va="bottom", fontsize=10, fontweight="bold", color=_TEXT)

    ax.set_xlim(-0.6, 0.6)
    ax.set_ylim(0, total * 1.18)
    ax.set_xticks([])
    ax.set_ylabel(f"Delivered cost ($/ODT, {cost_year} $)", fontsize=9)
    ax.set_title(
        f"Option {option_id}\n{distance_miles:.0f} mi · {speed_mph:.0f} mph",
        fontsize=10, fontweight="bold", pad=8,
    )

    # Custom legend below the bar
    import matplotlib.patches as mpatches
    ax.legend(
        handles=[mpatches.Patch(color=c, label=l) for l, _, c in components if _ > 0],
        fontsize=9, framealpha=0.85, facecolor=_BG, edgecolor=_SPINE, labelcolor=_TEXT,
        loc="lower center", bbox_to_anchor=(0.5, -0.18), ncol=1,
    )
    _apply_style(ax)
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color=_GRID)
    if standalone:
        fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import matplotlib.pyplot as plt
    os.makedirs("Transport_plots", exist_ok=True)

    print("=== Single option ===")
    r = delivered_cost("1.1", distance_miles=20, speed_mph=20, cost_year=2025)
    for k, v in r.items():
        print(f"  {k:<18} {v}")

    print("\n=== Cost vs distance — first 5 rows ===")
    df = cost_vs_distance("1.1", speed_mph=20)
    print(df.head().to_string(index=False))

    print("\n=== SAF forest options @ 20 miles, 20 mph ===")
    print(compare_options(20, speed_mph=20, option_ids=["1.1","1.2","1.3","1.4",'4.1','4.2','4.3','4.4']).to_string(index=False))

    print("\n=== All options @ 20 miles, 20 mph ===")
    print(compare_options(20, speed_mph=20).to_string(index=False))

    print("\nGenerating plots...")

    fig1 = plot_cost_vs_distance("1.1", speed_mph=20, mark_distance=20)
    fig1.savefig("LCA_plots/plot_cost_vs_distance.png", dpi=150, bbox_inches="tight")

    fig2 = plot_compare_options(20, speed_mph=20)
    fig2.savefig("LCA_plots/plot_compare_options_all.png", dpi=150, bbox_inches="tight")

    fig2f = plot_compare_options(20, speed_mph=20, option_ids=["1.1","1.2","1.3","1.4",'4.1','4.2','4.3','4.4'])
    fig2f.savefig("LCA_plots/plot_compare_options_saf_forest.png", dpi=150, bbox_inches="tight")

    fig3 = plot_multi_option_distance(["1.1","1.2","2.1","2.3"], speed_mph=20, mark_distance=40)
    fig3.savefig("LCA_plots/plot_multi_option_distance.png", dpi=150, bbox_inches="tight")

    fig4 = plot_speed_sensitivity("1.1", distance_miles=40, mark_speed=20)
    fig4.savefig("LCA_plots/plot_speed_sensitivity.png", dpi=150, bbox_inches="tight")

    fig5 = plot_cost_breakdown_bar("1.1", distance_miles=40, speed_mph=20)
    fig5.savefig("LCA_plots/plot_cost_breakdown_bar.png", dpi=150, bbox_inches="tight")

    plt.close("all")
    print("Done.  Plots written to Transport_plots/")