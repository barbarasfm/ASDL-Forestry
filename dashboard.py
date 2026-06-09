"""
dashboard.py  ─  Georgia Biomass Bioenergy & SAF Dashboard
===========================================================
Two operating modes selectable at the top of the page:

    Bioenergy   stoker-boiler + steam turbine power plant
                   Sources: Forest residues (2.x transport options)
                            Mill residues  (3.x transport options)

    SAF         Fischer-Tropsch sustainable aviation fuel plant
                   Sources: Forest HQ (69.2 % of forest, 1.x options)
                            Mill residues (3.x options)
                            Pulpwood (4.x options)

PRE-REQUISITES:
    1. Run  python preload.py  once to build cache/mill_distances.csv
    2. Put all Python modules (BioEnergy_Economics.py, SAF_Economics.py,
       Biomass_Transport.py, and their dependencies) in the same folder.
    3. streamlit run dashboard.py
"""

# ─── stdlib ──────────────────────────────────────────────────────────────────
import io
import math
import os
import sys
import datetime

# ─── third-party ─────────────────────────────────────────────────────────────
import folium
import numpy as np
import pandas as pd
import matplotlib
matplotlib.rcParams["text.usetex"] = False
matplotlib.rcParams["mathtext.default"] = "regular"
matplotlib.use("Agg")          # non-interactive backend required in Streamlit
try:
    st.set_option("deprecation.showPyplotGlobalUse", False)
except Exception:
    pass  # option may not exist in newer Streamlit versions
import matplotlib.pyplot as plt
import requests
import streamlit as st

# ─── Make project modules importable regardless of launch directory ───────────
_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

# ── Biomass Transport (standalone, always available) ──────────────────────────
import Biomass_Transport as bt   # delivered_cost, cost_vs_distance, plot_*

# ── Bioenergy Economics: bioenergy_MAIN_economics_FINAL.py ───────────────────
# This is the final bioenergy script.  It imports predict_output from itself
# and equipment_costs / TCI_calculation / depreciation_schedule from
# Bioenergy_dependencies.bioenergy_costs_FINAL, build_cash_flow_analysis /
# get_lcoe from Bioenergy_dependencies.bioenergy_finance_FINAL, and
# plot_all from Bioenergy_dependencies.bioenergy_plots_FINAL.
# Importing the module gives us access to all of these via bem.*
try:
    import BioEnergy_Economics as bem
    BEE_AVAILABLE = True
except ImportError as _e:
    BEE_AVAILABLE = False
    BEE_ERROR = str(_e)

# ── SAF Economics: saf_MAIN_economics_FINAL.py ───────────────────────────────
# Final SAF script.  Uses PER-SOURCE throughputs (forest, pulpwood, sawmill).
# build_cash_flow_analysis and solve_mfsp come from SAF_dependencies.SAF_Finance_FINAL.
# sp.plot_all comes from SAF_dependencies.SAF_plots_FINAL (imported as sfm.sp).
try:
    import SAF_Economics as sfm
    SAF_AVAILABLE = True
except ImportError as _e:
    SAF_AVAILABLE = False
    SAF_ERROR = str(_e)

# ── Jobs Creation Model ────────────────────────────────────────────────────────
# jobs_from_biopower / jobs_from_biofuel / plot_job_breakdown
# plot_job_breakdown uses plt.figure() (global) and saves to Jobscreation_plots/
# so after calling it we display the saved PNG via st.image().
try:
    import Jobscreation as jm
    JOBS_AVAILABLE = True
except ImportError as _e:
    JOBS_AVAILABLE = False
    JOBS_ERROR = str(_e)

# ── Policy Modules ─────────────────────────────────────────────────────────────
try:
    import Bioenergy_Policy as bepol
    BEE_POL_AVAILABLE = True
except ImportError as _e:
    BEE_POL_AVAILABLE = False
    BEE_POL_ERROR = str(_e)

try:
    import SAF_Policy as safpol
    SAF_POL_AVAILABLE = True
except ImportError as _e:
    SAF_POL_AVAILABLE = False
    SAF_POL_ERROR = str(_e)

# ── Output directories used by all plot-saving functions ─────────────────────
os.makedirs(os.path.join(_DIR, "Bioenergy_plots"),    exist_ok=True)
os.makedirs(os.path.join(_DIR, "SAF_plots"),           exist_ok=True)
os.makedirs(os.path.join(_DIR, "Policy_plots"),        exist_ok=True)
os.makedirs(os.path.join(_DIR, "Jobscreation_plots"),  exist_ok=True)
os.makedirs(os.path.join(_DIR, "LCA_plots"),           exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG  (must be the first Streamlit call)
# ══════════════════════════════════════════════════════════════════════════════
# Suppress matplotlib global pyplot deprecation warning
import warnings
warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="GREEN TEA",
    layout="wide",
    initial_sidebar_state="collapsed",   # collapse sidebar to maximise content area
)


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
CACHE_DIR        = os.path.join(_DIR, "cache")
METERS_PER_MILE  = 1_609.34
KM_PER_MILE      = 1.60934
L_PER_GAL        = 3.78541    # litres per US gallon
OSRM_BASE        = "http://router.project-osrm.org"
METRIC_TON_TO_US_TON = 1.102311 # for conversion between metric ton to US ton

# Forest residue quality split (Sahoo et al. 2019)
# SAF uses ONLY the high-quality fraction (treetops)
HQ_FRACTION = 0.692   # 69.2 %  → SAF/Bioenergy Options 1.x
LQ_FRACTION = 0.308   # 30.8 %  → Bioenergy Options 2.x

# BioEnergy capacity factor (hardcoded per BioEnergy_Economics.main)
BE_CAPACITY_FACTOR = 81   # %

# Transport option groupings (mirrors Biomass_Transport _OPTIONS keys)
# Bioenergy: Forest→2.x, Mill→3.x
# SAF:       Forest HQ→1.x, Mill→3.x, Pulpwood→4.x
OPTIONS_HIGH  = ["1.1", "1.2", "1.3", "1.4"]   # chipping/log — HQ forest 
OPTIONS_LOW   = ["2.1", "2.2", "2.3"]           # grinding — LQ / all forest (bioenergy)
OPTIONS_MILL  = ["3.1"]                          # direct transport — mill residues
OPTIONS_PULPWOOD = ["4.1", "4.2", "4.3", "4.4"]           # chipping/logging — pulpwood (SAF)

# ══════════════════════════════════════════════════════════════════════════════
# DARK THEME CSS
# Injected once at load time.  Selectors cover both the main app and the
# dropdown popups that Streamlit renders at body level outside .stApp.
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Background ─────────────────────────────────────────────────────── */
.stApp, [data-testid="stAppViewContainer"],
[data-testid="stMain"], section.main { background:#0b0e14 !important; }

/* Remove ALL top padding — start content from very top */
[data-testid="stAppViewContainer"] > section > div:first-child
  { padding-top:0 !important; }
[data-testid="stAppViewContainer"] > section { padding-top:0 !important; }
.block-container { padding-top:0.3rem !important; padding-bottom:0 !important; }
header[data-testid="stHeader"] { display:none !important; }

/* ── Text ────────────────────────────────────────────────────────────── */
html, body, p, li, span, div, .stApp,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span { color:#c9d1e0 !important; }

/* ── Headings ────────────────────────────────────────────────────────── */
h2 { font-size:1.0rem !important; color:#4ade80 !important; font-weight:700 !important;
     border-bottom:1px solid #1a2d1a; padding-bottom:3px; margin:6px 0 6px !important;
     text-transform:uppercase; letter-spacing:.05em; }
h3 { font-size:0.9rem !important; color:#7a9090 !important; font-weight:700 !important;
     text-transform:uppercase; letter-spacing:.05em; margin:4px 0 !important; }

/* ── Mode selector radio ─────────────────────────────────────────────── */
[data-testid="stRadio"] > div { gap:6px !important; }
[data-testid="stRadio"] label { font-size:0.9rem !important;
  font-weight:700 !important; color:#4ade80 !important; }

/* ── Tabs ────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  background:#0d1120; border-bottom:1px solid #1e2a3a;
  padding-top:0 !important; margin-top:0 !important; }
.stTabs [data-baseweb="tab"] {
  background:transparent !important; color:#8a9eb0 !important;
  font-size:2.0rem !important; font-weight:600; letter-spacing:.04em;
  padding:6px 14px !important;
  border-radius:4px 4px 0 0 !important; border:none !important; }
.stTabs [aria-selected="true"] {
  background:#0b0e14 !important; color:#4ade80 !important;
  border-top:2px solid #4ade80 !important;
  border-left:none !important; border-right:none !important; border-bottom:none !important; }
.stTabs [data-baseweb="tab-highlight"] { display:none !important; }
.stTabs [data-baseweb="tab-border"]    { display:none !important; }
.stTabs [data-baseweb="tab-panel"] { background:#0b0e14; padding-top:6px !important; }

/* ── Buttons ─────────────────────────────────────────────────────────── */
.stButton > button[kind="primary"] {
  background:linear-gradient(135deg,#166534,#15803d) !important;
  color:#f0fdf4 !important; border:none !important; border-radius:5px !important;
  font-weight:700 !important; font-size:0.9rem !important; padding:5px 12px !important; }
.stButton > button:not([kind="primary"]) {
  background:#111828 !important; color:#7a8a9a !important;
  border:1px solid #223040 !important; border-radius:5px !important;
  font-size:1.00rem !important; }

/* ── Widget labels ───────────────────────────────────────────────────── */
label, [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] span,
.stSlider label, .stNumberInput label, .stSelectbox label,
.stMultiSelect label, .stCheckbox label {
  color:#7a8e9e !important; font-size:1.00rem !important; font-weight:600 !important; }

/* ── Number/text inputs ──────────────────────────────────────────────── */
input, textarea, [data-baseweb="input"] input,
.stNumberInput input, .stTextInput input {
  background:#0f1826 !important; color:#d0dae8 !important;
  border:1px solid #2a3a4a !important; border-radius:4px !important;
  font-size:1.00rem !important; }

/* ── Select/multiselect control box ─────────────────────────────────── */
[data-baseweb="select"] > div:first-child,
.stSelectbox > div > div, .stMultiSelect > div > div {
  background:#0f1826 !important; border:1px solid #2a3a4a !important;
  border-radius:4px !important; }
[data-baseweb="select"] div[class*="singleValue"],
[data-baseweb="select"] div[class*="placeholder"],
[data-baseweb="select"] input, [data-baseweb="select"] span
  { color:#d0dae8 !important; }

/* ── Dropdown popup (renders outside .stApp at body level) ──────────── */
body [data-baseweb="popover"], [data-baseweb="popover"] {
  background:#0f1826 !important; border:1px solid #2a3a4a !important;
  border-radius:5px !important; }
[data-baseweb="popover"] * { background:#0f1826 !important; color:#d0dae8 !important; }
[data-baseweb="menu"], ul[role="listbox"] {
  background:#0f1826 !important; border:1px solid #2a3a4a !important; }
li[role="option"], [role="option"] {
  background:#0f1826 !important; color:#d0dae8 !important; font-size:1.0rem !important; }
li[role="option"]:hover, [role="option"]:hover,
[role="option"][aria-selected="true"]
  { background:#162535 !important; color:#4ade80 !important; }

/* ── Multiselect tags ────────────────────────────────────────────────── */
[data-baseweb="tag"] { background:#162535 !important; border:1px solid #2a4050 !important; }
[data-baseweb="tag"] span { color:#90c8a0 !important; font-size:1.00rem !important; }
[data-baseweb="tag"] [role="button"] { color:#4a7060 !important; }

/* ── Slider ──────────────────────────────────────────────────────────── */
[data-baseweb="slider"] div[role="slider"] { background:#4ade80 !important; }

/* ── Expanders ───────────────────────────────────────────────────────── */
details {
  background:#0d1422 !important; border:1px solid #1e2a3a !important;
  border-radius:5px !important; margin:3px 0 !important; }
summary {
  color:#6a8090 !important; font-size1.00rem !important;
  font-weight:700; letter-spacing:.04em; padding:5px 10px !important; }
details > div { background:#0d1422 !important; }


/* ── Hide Streamlit footer & map tile credits ────────────────────────── */
footer, footer *, [data-testid="stFooter"],
.leaflet-control-attribution, .leaflet-control-attribution *,
.leaflet-bottom, .leaflet-bottom * { display:none !important; }
/* ── Caption / divider ───────────────────────────────────────────────── */
.stCaption, small { color:#354555 !important; font-size:1.00rem !important; }
hr { border-color:#182030 !important; margin:4px 0 !important; }

/* ── Alerts ──────────────────────────────────────────────────────────── */
.stAlert { background:#0d1525 !important; border-radius:5px !important; }
            
/* ── Tooltips ────────────────────────────────────────────────────────── */
/* Targets the container box that appears when hovering over the icon */
div[data-testid="stTooltipContent"] {
    background-color: #ffffff !important; /* Changes popup background to solid white */
    border: 1px solid #c9d1e0 !important;
}

/* Forces all paragraph, spans, and text inside the popup to be black */
div[data-testid="stTooltipContent"] *, 
div[data-testid="stTooltipContent"] p,
div[data-testid="stTooltipContent"] span {
    color: #000000 !important;            /* Force font color to deep black */
    font-weight: 500 !important;          /* Boost weight slightly for contrast */
}
# Force Tooltip Icon Wrapper to Change Color
/* This targets the interactive button layer holding the icon */
[data-testid="stWidgetLabel"] button[data-testid="stTooltipHoverTarget"],
[data-testid="stTooltipHoverTarget"] {
    color: #4ade80 !important;   /* Changes the outer outline/circle color */
}

/* This drills down to the raw SVG icon layers inside the button */
[data-testid="stTooltipHoverTarget"] svg,
[data-testid="stTooltipHoverTarget"] svg path,
[data-testid="stTooltipHoverTarget"] .stIcon svg {
    fill: #000000 !important;    /* Forces the core vector fill to be deep black */
    stroke: #4ade80 !important;  /* Ensures any line borders match */
}

/* Optional: Subtle pulse effect when hovering right on top of the icon */
[data-testid="stTooltipHoverTarget"]:hover svg,
[data-testid="stTooltipHoverTarget"]:hover svg path {
    fill: #000000 !important;    /* Darkens to a rich forest green on hover */
    stroke: #22c55e !important;
}

/* ═══════════════════════════════════════════════════════════════════════
   METRIC CARDS  (.mc)
   Usage: st.markdown(mc("Label","Value","sub"), unsafe_allow_html=True)
   Variants: .mc-warn (amber)  .mc-neg (red)  .mc-blue  .mc-amber
═══════════════════════════════════════════════════════════════════════ */
.mc { background:#0f1826; border:1px solid #1a2535; border-left:3px solid #166534;
  border-radius:5px; padding:6px 9px 5px; }
.mc-lbl { font-size:1.00rem; color:#4a7060; font-weight:700;
  text-transform:uppercase; letter-spacing:.08em; margin-bottom:1px; }
.mc-val { font-size:1.05rem; font-weight:700; color:#90d8a8; line-height:1.1;
  font-variant-numeric:tabular-nums; }
.mc-sub { font-size:1.00rem; color:#304840; margin-top:1px; }
.mc-warn { border-left-color:#b45309 !important; }
.mc-warn .mc-val { color:#fbbf24 !important; }
.mc-warn .mc-lbl { color:#604010 !important; }
.mc-neg  { border-left-color:#991b1b !important; }
.mc-neg  .mc-val { color:#f87171 !important; }
.mc-neg  .mc-lbl { color:#501010 !important; }
.mc-blue { border-left-color:#2563eb !important; }
.mc-blue .mc-val { color:#93c5fd !important; }
.mc-blue .mc-lbl { color:#1e3a6a !important; }
.mc-amber { border-left-color:#d97706 !important; }
.mc-amber .mc-val { color:#fcd34d !important; }
.mc-amber .mc-lbl { color:#5a3800 !important; }

/* ═══════════════════════════════════════════════════════════════════════
   INFO / WARNING BOXES
═══════════════════════════════════════════════════════════════════════ */
.ib { background:#0b1a10; border-left:3px solid #166534; border-radius:5px;
  padding:6px 10px; margin-bottom:6px; font-size:0.9rem; line-height:1.5; }
.ib, .ib p, .ib span { color:#6aaa88 !important; }
.ib b { color:#4ade80 !important; }
.wb { background:#150e00; border-left:3px solid #b45309; border-radius:5px;
  padding:6px 10px; margin-bottom:6px; font-size:0.9rem; }
.wb, .wb p, .wb span { color:#c09040 !important; }

/* ═══════════════════════════════════════════════════════════════════════
   SECTION / COL HEADERS
═══════════════════════════════════════════════════════════════════════ */
.step-hdr { font-size1.00rem; font-weight:700; letter-spacing:.10em;
  text-transform:uppercase; color:#2a4838; margin:6px 0 3px;
  border-top:1px solid #182820; padding-top:5px; }
.col-hdr  { font-size:1.00rem; font-weight:700; color:#2a4838;
  letter-spacing:.09em; text-transform:uppercase;
  border-bottom:1px solid #182820; padding-bottom:3px; margin-bottom:6px; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def mc(label: str, value: str, sub: str = "", variant: str = "") -> str:
    """Return HTML for a dark metric card."""
    cls = f"mc {variant}".strip()
    return (f'<div class="{cls}">'
            f'<div class="mc-lbl">{label}</div>'
            f'<div class="mc-val">{value}</div>'
            f'<div class="mc-sub">{sub}</div></div>')


def section(label: str) -> None:
    """Small all-caps section divider with top rule."""
    st.markdown(f'<div class="step-hdr">{label}</div>', unsafe_allow_html=True)


def col_header(label: str) -> None:
    """Column-level header with bottom border."""
    st.markdown(f'<div class="col-hdr">{label}</div>', unsafe_allow_html=True)


def info(html: str) -> None:
    """Green info box."""
    st.markdown(f'<div class="ib">{html}</div>', unsafe_allow_html=True)


def warn(html: str) -> None:
    """Amber warning box."""
    st.markdown(f'<div class="wb">{html}</div>', unsafe_allow_html=True)


def show_folium(fmap, height: int = 400) -> None:
    """Embed a Folium map via st.iframe"""
    map_html = fmap._repr_html_()
    no_scroll_html = f"<div style='overflow:hidden;'>{map_html}</div>"

    st.iframe(no_scroll_html, height=height)


@st.cache_data(show_spinner="Fetching road route...")
def get_route_geometry(mill_lat: float, mill_lon: float,
                       c_lat: float, c_lon: float):
    """
    OSRM Route API: returns list of [lat, lon] waypoints for the road path
    between the mill and a county centroid.
    Returns None on failure — caller draws a straight-line fallback.
    A browser-like User-Agent header is sent because the public OSRM server
    requires it (returns 403 without it).
    """
    url = (f"{OSRM_BASE}/route/v1/driving/"
           f"{mill_lon},{mill_lat};{c_lon},{c_lat}"
           "?overview=full&geometries=geojson")
    try:
        data = requests.get(
            url, timeout=15,
            # headers={"User-Agent": "Mozilla/5.0 (compatible; GA-Biomass-Dashboard/1.0)"}
        ).json()
        if data.get("code") != "Ok":
            return None
        # GeoJSON coords are [lon, lat]; flip to [lat, lon] for Folium
        return [[c[1], c[0]] for c in data["routes"][0]["geometry"]["coordinates"]]
    except Exception:
        return None


@st.cache_data
def load_cache():
    """
    Load the pre-computed cache file built by preload.py.
    Returns None if the file doesn't exist yet.
    Columns: county, lat, lon, forest_kdry_metric, mill_kdry_metric,
             pulpwood_kdry_metric, [mill label cols...]
    """
    path = os.path.join(CACHE_DIR, "mill_distances.csv")
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


@st.cache_data
def load_mills_df():
    """
    Load GA_Mills.xlsx, filter operating GA mills with valid coordinates.
    Searches: same folder as dashboard.py, then current working directory.
    Returns None if the file is not found in either location.
    """
    # Try script directory first, then cwd (in case user launches from elsewhere)
    for candidate in [os.path.join(_DIR, "Locations/GA_Mills.xlsx"),
                      os.path.join(os.getcwd(), "Locations/GA_Mills.xlsx")]:
        if os.path.exists(candidate):
            path = candidate
            break
    else:
        return None
    df = pd.read_excel(path)
    df.columns = [c.replace("\n", " ").strip() for c in df.columns]
    df = df[(df["Status"] == "Operating") & (df["State"] == "GA")].copy()
    df = df.rename(columns={"X Coord.": "longitude", "Y Coord.": "latitude"})
    df["mill_label"] = (df["Mill site"].str.strip()
                        + " -- " + df["Company name"].str.strip())
    valid = df["latitude"].between(30.3, 35.1) & df["longitude"].between(-85.7, -80.8)
    return df[valid].reset_index(drop=True)


def weighted_avg_distance(county_rows: pd.DataFrame,
                          residue_col: str,
                          dist_col: str):
    """
    Compute the residue-weighted average road distance for a set of counties.

    weighted_avg = sum(residue_i * dist_i) / sum(residue_i)

    If total residue is zero or DataFrame is empty, returns None.
    This is the one-way distance in miles that gets passed to Biomass_Transport.
    """
    total_res = county_rows[residue_col].sum()
    if total_res <= 0 or county_rows.empty:
        return None
    return float((county_rows[residue_col] * county_rows[dist_col]).sum() / total_res)


def render_pyplot_safe(fig) -> None:
    """
    Render a matplotlib Figure safely.  Always pass fig explicitly to
    st.pyplot(fig) — avoids the Streamlit deprecation warning about
    using the global pyplot figure object (not thread-safe).
    """
    if fig is None:
        return
    try:
        st.pyplot(fig)
    except Exception as e:
        st.error(f"Could not render plot: {e}")
    finally:
        plt.close("all")


def render_plot_all(figs_result) -> None:
    """
    Render figures from plot_all() in a 2-column grid.
    None entries act as empty placeholders, keeping their paired chart at half-width.
    An odd non-None final figure spans full width.
    """
    if figs_result is None:
        return
    if not isinstance(figs_result, dict):
        render_pyplot_safe(figs_result)
        return
    # Preserve None placeholders — they control column layout
    _figs = list(figs_result.values())
    _i = 0
    while _i < len(_figs):
        if _i + 1 < len(_figs):
            # Always render pairs in two columns
            _col1, _col2 = st.columns(2, gap="medium")
            with _col1:
                if _figs[_i] is not None:
                    render_pyplot_safe(_figs[_i])
            with _col2:
                if _figs[_i + 1] is not None:
                    render_pyplot_safe(_figs[_i + 1])
            _i += 2
        else:
            # Odd final entry — render right-aligned at half width using columns
            # Use st.columns but wrap in a container to suppress the empty col height
            _, _col2 = st.columns([1, 1], gap="medium")
            with _col2:
                if _figs[_i] is not None:
                    render_pyplot_safe(_figs[_i])
            _i += 1


def render_saved_png(rel_path: str) -> None:
    """
    Display a PNG that a module has already saved to disk.
    Used for plot_job_breakdown() which calls plt.figure() globally
    (not returning the figure) and saves to Jobscreation_plots/plot_jobs.png.
    """
    full = os.path.join(_DIR, rel_path)
    if os.path.exists(full):
        st.image(full, width="stretch")
    else:
        st.caption(f"Plot not yet saved: {rel_path}")

def _make_lca_stage_fig(stages, mode_str, total_odt):
    """
    Two side-by-side subplots under one shared heading.
    Left : Processing + Transport  (t CO₂e / yr)
    Right: Production (Bioenergy or SAF)  (t CO₂e / yr)
    """
    import matplotlib.pyplot as _plt
    import matplotlib.patches as _mp
    import numpy as _np

    _C_BIO  = "#2471A3"; _C_FOSS = "#A93226"
    _C_CH4  = "#E67E22"; _C_N2O  = "#1E8449"
    _BG = "#0e1621"; _AX_BG = "#131e2d"
    _TEXT = "#c8d8e8"; _SPINE = "#2a3a4a"; _GRID = "#1e2d3d"

    def _style(ax):
        ax.set_facecolor(_AX_BG)
        ax.spines[["top","right"]].set_visible(False)
        ax.spines[["left","bottom"]].set_color(_SPINE)
        ax.tick_params(colors=_TEXT, labelsize=11)
        ax.yaxis.set_major_formatter(_plt.FuncFormatter(lambda v,_: f"{v:,.0f}"))
        ax.grid(axis="y", color=_GRID, linewidth=0.7, zorder=0)

    def _draw(ax, subset, ylabel):
        xs = _np.arange(len(subset)); w = 0.50
        bv = [s[1]["bioCO2_t"]*METRIC_TON_TO_US_TON  for s in subset]
        fv = [s[1]["fossCO2_t"]*METRIC_TON_TO_US_TON for s in subset]
        cv = [s[1]["CH4_CO2e"]*METRIC_TON_TO_US_TON  for s in subset]
        nv = [s[1]["N2O_CO2e"]*METRIC_TON_TO_US_TON  for s in subset]
        b1 = [bv[i]+fv[i] for i in range(len(subset))]
        b2 = [b1[i]+cv[i] for i in range(len(subset))]
        tots = [b2[i]+nv[i] for i in range(len(subset))]
        ax.bar(xs, bv, w, color=_C_BIO,  edgecolor="none", zorder=3)
        ax.bar(xs, fv, w, bottom=bv, color=_C_FOSS, edgecolor="none", zorder=3)
        ax.bar(xs, cv, w, bottom=b1, color=_C_CH4,  edgecolor="none", zorder=3)
        ax.bar(xs, nv, w, bottom=b2, color=_C_N2O,  edgecolor="none", zorder=3)
        mx = max(tots) if tots else 1
        ax.set_ylim(0, mx * 1.32)
        for i, t in enumerate(tots):
            ax.text(xs[i], t + mx*0.025, f"{t:,.0f}",
                    ha="center", fontsize=11, fontweight="bold", color="#f0f4f8")
        ax.set_xticks(xs)
        ax.set_xticklabels([s[0] for s in subset], fontsize=11, color=_TEXT)
        ax.set_ylabel(ylabel, fontsize=12, color=_TEXT)

    # Split stages: supply chain (everything except last) vs production (last stage)
    supply  = [s for s in stages if "roduct" not in s[0] and "ombust" not in s[0]]
    prod    = [s for s in stages if "roduct" in s[0] or "ombust" in s[0]]

    fig, (ax_l, ax_r) = _plt.subplots(1, 2, figsize=(11.5, 9),
                                       gridspec_kw={"width_ratios": [2, 1]})
    fig.patch.set_facecolor(_BG)
    _style(ax_l); _style(ax_r)

    _draw(ax_l, supply, "GHG Emissions  (US ton CO\u2082e / yr)")
    ax_l.set_title("Supply Chain — Processing & Transport",
                   fontsize=12, color=_TEXT, pad=8)

    if prod:
        _draw(ax_r, prod, "GHG Emissions  (US ton CO\u2082e / yr)")
    else:
        ax_r.text(0.5, 0.5, "No production\ndata", ha="center", va="center",
                  transform=ax_r.transAxes, color=_TEXT, fontsize=12)
    ax_r.set_title(f"Production — {mode_str}",
                   fontsize=12, color=_TEXT, pad=8)

    lps = [_mp.Patch(color=c, label=l) for c, l in [
        (_C_BIO,  "Biogenic CO\u2082  (wood combustion)"),
        (_C_FOSS, "Fossil CO\u2082  (NG heat / diesel)"),
        (_C_CH4,  "CH\u2084 CO\u2082e"),
        (_C_N2O,  "N\u2082O CO\u2082e"),
    ]]
    fig.legend(handles=lps, fontsize=10, facecolor=_BG,
               edgecolor=_SPINE, labelcolor=_TEXT,
               loc="lower center", ncol=4, framealpha=0.85,
               bbox_to_anchor=(0.5, -0.04))

    fig.suptitle(
        f"LCA Emissions by Stage  \u2014  {mode_str} mode  |  "
        f"{total_odt*METRIC_TON_TO_US_TON/1e3:.0f}k dry US ton/yr  |  GWP100 IPCC AR6",
        fontsize=13, fontweight="bold", color="#e8f0f8"
    )
    _plt.subplots_adjust(top=0.88, bottom=0.14, left=0.08, right=0.97, wspace=0.30)
    return fig

# def _make_lca_stage_fig(stages, mode_str, total_odt):
#     """
#     Build and return a matplotlib figure showing LCA emissions by stage.
#     Used by both the Impact tab (saved to PNG) and the Comparison tab (rendered inline).

#     Parameters
#     ----------
#     stages    : list of (label, result_dict) where result_dict has
#                 bioCO2_t, fossCO2_t, CH4_CO2e, N2O_CO2e keys
#     mode_str  : "SAF" or "Bioenergy"
#     total_odt : total biomass odt/yr for suptitle
#     """
#     import matplotlib.pyplot as _plt
#     import matplotlib.patches as _mp
#     import numpy as _np

#     _C_BIO  = "#2471A3"; _C_FOSS = "#A93226"
#     _C_CH4  = "#E67E22"; _C_N2O  = "#1E8449"
#     _BG = "#0e1621"; _AX_BG = "#131e2d"
#     _TEXT = "#c8d8e8"; _SPINE = "#2a3a4a"; _GRID = "#1e2d3d"

#     fig, ax = _plt.subplots(1, 1, figsize=(9, 7))
#     fig.patch.set_facecolor(_BG)
#     ax.set_facecolor(_AX_BG)
#     ax.spines[["top","right"]].set_visible(False)
#     ax.spines[["left","bottom"]].set_color(_SPINE)
#     ax.tick_params(colors=_TEXT, labelsize=12)
#     ax.yaxis.set_major_formatter(_plt.FuncFormatter(lambda v,_: f"{v:,.0f}"))
#     ax.grid(axis="y", color=_GRID, linewidth=0.7, zorder=0)

#     xs = _np.arange(len(stages)); w = 0.50
#     bv = [s[1]["bioCO2_t"]  for s in stages]
#     fv = [s[1]["fossCO2_t"] for s in stages]
#     cv = [s[1]["CH4_CO2e"]  for s in stages]
#     nv = [s[1]["N2O_CO2e"]  for s in stages]
#     b1 = [bv[i]+fv[i] for i in range(len(stages))]
#     b2 = [b1[i]+cv[i] for i in range(len(stages))]
#     tots = [b2[i]+nv[i] for i in range(len(stages))]

#     ax.bar(xs, bv, w, color=_C_BIO,  edgecolor="none", zorder=3)
#     ax.bar(xs, fv, w, bottom=bv, color=_C_FOSS, edgecolor="none", zorder=3)
#     ax.bar(xs, cv, w, bottom=b1, color=_C_CH4,  edgecolor="none", zorder=3)
#     ax.bar(xs, nv, w, bottom=b2, color=_C_N2O,  edgecolor="none", zorder=3)

#     mx = max(tots) if tots else 1
#     ax.set_ylim(0, mx * 1.32)
#     for i, t in enumerate(tots):
#         ax.text(xs[i], t + mx*0.025, f"{t:,.0f}",
#                 ha="center", fontsize=12, fontweight="bold", color="#f0f4f8")

#     ax.set_xticks(xs)
#     ax.set_xticklabels([s[0] for s in stages], fontsize=13, color=_TEXT)
#     ax.set_ylabel("GHG Emissions  (t CO\u2082e / yr)", fontsize=13, color=_TEXT)
#     ax.set_title(
#         "Lifecycle GHG by Stage\n(all emission types including biogenic CO\u2082)",
#         fontsize=13, color=_TEXT, pad=10
#     )

#     lps = [_mp.Patch(color=c, label=l) for c, l in [
#         (_C_BIO,  "Biogenic CO\u2082  (wood combustion)"),
#         (_C_FOSS, "Fossil CO\u2082  (NG heat / diesel)"),
#         (_C_CH4,  "CH\u2084 CO\u2082e"),
#         (_C_N2O,  "N\u2082O CO\u2082e"),
#     ]]
#     ax.legend(handles=lps, fontsize=11, facecolor=_BG,
#               edgecolor=_SPINE, labelcolor=_TEXT,
#               loc="upper left", framealpha=0.85)

#     fig.suptitle(
#         f"LCA Emissions by Stage  \u2014  {mode_str} mode  |  "
#         f"{total_odt/1e3:.0f}k odt/yr  |  GWP100 IPCC AR6",
#         fontsize=13, fontweight="bold", color="#e8f0f8"
#     )
#     _plt.subplots_adjust(top=0.88, bottom=0.10, left=0.12, right=0.97)
#     return fig

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE  ─  initialise all keys with defaults so tabs can read
# safely on first run before any button has been clicked
# ══════════════════════════════════════════════════════════════════════════════

_SS_DEFAULTS = {
    # ── Shared cache ──────────────────────────────────────────────────────────
    "cache_df":         None,    # full mill_distances.csv DataFrame
    "mills_df":         None,    # GA operating mills

    # ── Supply Chain results ──────────────────────────────────────────────────
    "sc_in_range":      None,    # DataFrame of in-range counties with all 3 residue cols
    "sc_selected": {             # selected county labels per source
        "forest": [], "mill": [], "pulpwood": []
    },
    "sc_results":       None,    # dict: per-source weighted dist, total residue, etc.

    # ── Transport results ─────────────────────────────────────────────────────
    "tr_results":       None,    # dict: per-source option, cost_odt, speed

    # ── BioEnergy Economics ───────────────────────────────────────────────────
    "be_equip_done":    False,   # True after Run button clicked
    "be_EC":            0.0,     # total equipment cost
    "be_stoker":        0.0,     # stoker boiler cost
    "be_fuel_eq":       0.0,     # fuel handling cost
    "be_turbine":       0.0,     # steam turbine cost
    "be_EC_list":       [],      # equipment cost list
    "be_TCI":           0.0,
    "be_FCI":           0.0,
    "be_breakdown":     {},
    "be_annual_dep":    [],
    "be_annual_AC":     0.0,     # annual kWh output year 1
    "be_df":            None,    # cash flow DataFrame
    "be_metrics":       None,    # financial metrics dict
    "be_lcoe":          None,    # LCOE result dict
    "be_f_cost":        25.0,     # Bioenergy economics forestry cost (Baseline default value to prevent crash on first load)
    "be_m_cost":        20.0,     # Bioenergy economics mill cost (Baseline default value to prevent crash on first load)

    # ── SAF Economics (per-source throughputs) ───────────────────────────────
    "saf_df":           None,    # cash flow DataFrame
    "saf_metrics":      None,    # financial metrics dict
    "saf_mfsp":         None,    # MFSP result dict (solve_mfsp output)
    "saf_pdc_f":        60.0,     # SAF economics forestry cost (Baseline default value to prevent crash on first load)
    "saf_pdc_pw":       60.0,     # SAF economics Pulpwood cost (Baseline default value to prevent crash on first load)
    "saf_pdc_sw":       60.0,     # SAF economics sawmill cost (Baseline default value to prevent crash on first load)

    # ── Jobs results ──────────────────────────────────────────────────────────
    "jobs_result":      None,    # dict from jobs_from_biopower or jobs_from_biofuel
    "fhr_results":      None,    # avoided emissions analysis results

    # ── Policy results (Bioenergy) ────────────────────────────────────────────
    "be_pol_df_none":       None,
    "be_pol_df_ptc":        None,
    "be_pol_df_itc":        None,
    "be_pol_met_none":      None,
    "be_pol_met_ptc":       None,
    "be_pol_met_itc":       None,
    "be_pol_credit_solved": None,   # min PTC for breakeven ($/kWh)

    # ── Policy results (SAF) ──────────────────────────────────────────────────
    "saf_pol_df_none":      None,
    "saf_pol_df_credit":    None,
    "saf_pol_met_none":     None,
    "saf_pol_met_credit":   None,
    "saf_pol_credit_saf":   None,
    "saf_pol_credit_nonsaf":None,

    # ── LCA results ──────────────────────────────────────────────────────────
    "lca_results":      None,

    # ── Saved scenarios (comparison tab) ─────────────────────────────────────
    "saved_scenarios":  [],
}

for _k, _v in _SS_DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ══════════════════════════════════════════════════════════════════════════════
# LOAD DATA  (once per session, cached)
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state["cache_df"] is None:
    st.session_state["cache_df"] = load_cache()

if st.session_state["mills_df"] is None:
    st.session_state["mills_df"] = load_mills_df()

cache_df = st.session_state["cache_df"]
mills_df = st.session_state["mills_df"]

# Non-mill columns in the cache (used to identify mill distance columns)
_NON_MILL_COLS = {"county", "lat", "lon", "status",
                  "forest_kdry_metric", "mill_kdry_metric", "pulpwood_kdry_metric"}
mill_col_names = (
    [c for c in cache_df.columns if c not in _NON_MILL_COLS]
    if cache_df is not None else []
)


# ══════════════════════════════════════════════════════════════════════════════
# MODE SELECTOR  ─  shown at the very top, above all tabs
# ══════════════════════════════════════════════════════════════════════════════

# Load Barlow Condensed from Google Fonts to match ASDL logo typography
# Also inject a named CSS class for GREEN TEA so Streamlit's global color
# overrides cannot clobber the green — inline color alone gets beaten.
st.markdown(
    '<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800&display=swap" rel="stylesheet">'
    '<style>'
    '.greentea-title {'
        'font-family:"Barlow Condensed",sans-serif !important;'
        'font-size:2.4rem !important;'
        'font-weight:800 !important;'
        'color:#4ade80 !important;'
        'letter-spacing:.06em !important;'
        'text-transform:uppercase !important;'
        'line-height:1.1 !important;'
    '}'
    '.greentea-sub {'
        'font-family:"Barlow Condensed",sans-serif !important;'
        'font-size:1.2rem !important;'
        'font-weight:400 !important;'
        'color:#3a5a4a !important;'
        'letter-spacing:.03em !important;'
        'line-height:1.0 !important;'
    '}'
    '</style>',
    unsafe_allow_html=True,
)

# ── Top bar: mode selector left | title center | logos right ──────────────
_top_mode, _top_title, _top_logo_r = st.columns([2, 4, 3])

with _top_mode:
    st.markdown(
        '<div style="font-size:1.0rem;font-weight:700;color:#6b8cad !important;'
        'text-transform:uppercase;letter-spacing:.07em;margin-bottom:2px;text-align:left">'
        'Select Operating Mode</div>',
        unsafe_allow_html=True,
    )
    mode = st.radio(
        "operating_mode",
        ["Bioenergy", "SAF"],
        horizontal=False,
        key="mode_selector",
        label_visibility="collapsed",
    )

with _top_title:
    st.markdown(
        '<div style="display: flex; flex-direction: column; align-items: center; gap: 0px; text-align: center;">'
            '<span class="greentea-title">GREEN TEA</span>'
            '<span class="greentea-sub">'
            'Generalized Residue-to-Energy Evaluation Network &amp; Techno-Economic Analysis'
            '</span>'
        '</div>',
        unsafe_allow_html=True
    )

with _top_logo_r:
    import pathlib as _pl
    _ASDL_LOGO  = _pl.Path(_DIR) / "assets" / "asdl_logo.png"
    _ENDOW_LOGO = _pl.Path(_DIR) / "assets" / "usendowment_logo.png"
    _logo_cols = st.columns(2, gap="small")
    with _logo_cols[0]:
        if _ASDL_LOGO.exists():
            st.image(str(_ASDL_LOGO), width="stretch")
        else:
            st.markdown(
                '<div style="font-size:0.75rem;color:#2a3a4a;padding-top:4px">'
                'ASDL logo<br><span style="color:#1a2a3a">(assets/asdl_logo.png)</span></div>',
                unsafe_allow_html=True
            )
    with _logo_cols[1]:
        if _ENDOW_LOGO.exists():
            st.image(str(_ENDOW_LOGO), width="stretch")
        else:
            st.markdown(
                '<div style="font-size:0.75rem;color:#2a3a4a;padding-top:4px">'
                'US Endowment logo<br><span style="color:#1a2a3a">(assets/usendowment_logo.png)</span></div>',
                unsafe_allow_html=True
            )

IS_SAF = ("SAF" in mode)


# ══════════════════════════════════════════════════════════════════════════════
# TABS  ─  labels adapt to mode
# ══════════════════════════════════════════════════════════════════════════════
econ_label = "3. SAF Economics " if IS_SAF else "3. Bioenergy Economics"
mode_badge = "SAF" if IS_SAF else "Bioenergy"

(tab_sc, tab_tr, tab_econ,tab_impact, tab_policy, tab_compare) = st.tabs([
    "1. Supply Chain",
    "2. Biomass Transport",
    econ_label,
    "4. Impact",
    "5. Policy",
    "6. Comparison",
])

# ── Cache status — shown below the tab bar, not in the banner ─────────────
if cache_df is not None:
    st.caption(f"Cache ready: {len(cache_df)} counties · {len(mill_col_names)} mills")
else:
    st.caption("Error: No cache, run preload.py first")


# ══════════════════════════════════════════════════════════════════════════════
# ┌──────────────────────────────────────────────────────────────────────────┐
# │  TAB 1 — SUPPLY CHAIN                                                    │
# │                                                                          │
# │  Left  : mill selector, radius slider, per-source county multiselects    │
# │  Right : Folium map (mill marker, radius circle, source-coloured dots,   │
# │           route lines after selection), summary metric cards             │
# └──────────────────────────────────────────────────────────────────────────┘
# ══════════════════════════════════════════════════════════════════════════════
with tab_sc:

    if cache_df is None:
        st.error("No cache found.  Run  python preload.py  first.")
        st.stop()

    _sc_left, _sc_right = st.columns([1, 2], gap="medium")

    # ─────────────────────────────────────────────────────────────────────────
    # LEFT — inputs
    # ─────────────────────────────────────────────────────────────────────────
    with _sc_left:
        col_header("Inputs")

        # Mill selector: labels come from cache columns (already filtered to
        # operating GA mills with valid coords during preload)
        if not mill_col_names:
            st.error("No mill columns in cache.  Check preload output.")
            st.stop()

        sel_mill = st.selectbox("Processing Mill:", mill_col_names, key="sc_mill")

        # Radius slider: how far from the mill to search for residue counties
        radius_mi = st.slider(
            "Search radius (miles)", 10, 200, 70, 5, key="sc_radius",
            help="Road-distance radius around the selected mill"
        )

        # Reset downstream state whenever the mill changes
        if st.session_state.get("_sc_last_mill") != sel_mill:
            st.session_state["sc_in_range"]   = None
            st.session_state["sc_selected"]   = {"forest": [], "mill": [], "pulpwood": []}
            st.session_state["sc_results"]    = None
            st.session_state["_sc_last_mill"] = sel_mill

        # Look up this mill's lat/lon from the mills DataFrame
        mill_lat = mill_lon = None
        mill_site = mill_company = ""
        if mills_df is not None and not mills_df.empty:
            _mr = mills_df[mills_df["mill_label"] == sel_mill]
            if not _mr.empty:
                mill_lat     = float(_mr.iloc[0]["latitude"])
                mill_lon     = float(_mr.iloc[0]["longitude"])
                mill_site    = str(_mr.iloc[0].get("Mill site", sel_mill))
                mill_company = str(_mr.iloc[0].get("Company name", ""))

        if mills_df is None:
            warn(
                "<b>GA_Mills.xlsx not found.</b>  "
                "Place GA_Mills.xlsx in the same folder as dashboard.py so mill "
                "coordinates can be shown on the map.  The mill selector still works "
                "from cache column names, but the map marker and route lines need the file."
            )
        elif mill_lat:
            info(f"<b>{mill_site}</b>  |  {mill_company}<br>"
                 f"<span style='color:#3a5248'>{mill_lat:.4f} N, {mill_lon:.4f} W</span>")

        # ── FIND COUNTIES button ──────────────────────────────────────────────
        find_btn = st.button("Find Counties in Range", type="primary",
                             width="stretch", key="sc_find")

        if find_btn and sel_mill in cache_df.columns:
            # Pull distance column for selected mill + residue columns
            _cols = ["county", "lat", "lon",
                     "forest_kdry_metric", "mill_kdry_metric", "pulpwood_kdry_metric", sel_mill]
            _dw = (cache_df[_cols]
                   .copy()
                   .rename(columns={sel_mill: "road_miles"})
                   .dropna(subset=["lat", "lon", "road_miles"]))
            _dw["county_label"] = _dw["county"] + " County"

            # Counties within the requested radius
            in_range = _dw[_dw["road_miles"] <= radius_mi].copy().reset_index(drop=True)
            st.session_state["sc_in_range"]  = in_range
            st.session_state["sc_results"]   = None   # reset calculated results
            st.session_state["sc_selected"]  = {"forest": [], "mill": [], "pulpwood": []}
            st.session_state["tr_results"]   = None   # transport results now stale

        # ── County multiselects (only after Find Counties runs) ───────────────
        in_range = st.session_state.get("sc_in_range")

        if in_range is not None and not in_range.empty:
            section("Select Source Counties")

            # Forest counties — all in-range counties can have forest residue
            _f_opts = (in_range[in_range["forest_kdry_metric"] > 0]
                       .sort_values("road_miles")["county_label"].tolist())
            sel_forest = st.multiselect(
                f"Forest Residue counties ({len(_f_opts)} w/ supply, sorted by distance):",
                _f_opts,
                default=st.session_state["sc_selected"]["forest"] or _f_opts[:3],
                key="sc_sel_forest",
            )
            st.session_state["sc_selected"]["forest"] = sel_forest

            # Mill residue counties
            _m_opts = (in_range[in_range["mill_kdry_metric"] > 0]
                       .sort_values("road_miles")["county_label"].tolist())
            sel_mill_res = st.multiselect(
                f"Mill Residue counties ({len(_m_opts)} w/ supply):",
                _m_opts,
                default=st.session_state["sc_selected"]["mill"] or _m_opts[:2],
                key="sc_sel_mill",
            )
            st.session_state["sc_selected"]["mill"] = sel_mill_res

            # Pulpwood counties (SAF only)
            if IS_SAF:
                _p_opts = (in_range[in_range["pulpwood_kdry_metric"] > 0]
                           .sort_values("road_miles")["county_label"].tolist())
                sel_pulp = st.multiselect(
                    f"Pulpwood counties ({len(_p_opts)} w/ supply):",
                    _p_opts,
                    default=st.session_state["sc_selected"]["pulpwood"] or _p_opts[:3],
                    key="sc_sel_pulp",
                )
                st.session_state["sc_selected"]["pulpwood"] = sel_pulp
            else:
                sel_pulp = []
                st.session_state["sc_selected"]["pulpwood"] = []

            # ── CALCULATE ROUTES button ───────────────────────────────────────
            calc_btn = st.button("Calculate Distance", type="primary", #Took out the word weighted 
                                 width="stretch", key="sc_calc")

            if calc_btn:
                # For each source, compute residue-weighted average road distance
                # to the selected counties.  This is the one-way haul distance
                # that feeds into Biomass_Transport.delivered_cost().

                results = {}

                # ── Forest ───────────────────────────────────────────────────
                _f_rows = in_range[in_range["county_label"].isin(sel_forest)]
                f_dist  = weighted_avg_distance(_f_rows, "forest_kdry_metric", "road_miles")
                f_total = _f_rows["forest_kdry_metric"].sum()

                # SAF: only HQ fraction (69.2%) of forest is used
                f_hq_total = f_total * HQ_FRACTION   # k metric t/yr
                f_lq_total = f_total * LQ_FRACTION

                results["forest"] = {
                    "counties":    sel_forest,
                    "dist_mi":     f_dist,
                    "total_kdry":  f_total,          # all forest, k metric t/yr
                    "hq_kdry":     f_hq_total,       # high-quality fraction
                    "lq_kdry":     f_lq_total,
                    "residue_col": "forest_kdry_metric",
                }

                # ── Mill residues ─────────────────────────────────────────────
                _m_rows = in_range[in_range["county_label"].isin(sel_mill_res)]
                m_dist  = weighted_avg_distance(_m_rows, "mill_kdry_metric", "road_miles")
                m_total = _m_rows["mill_kdry_metric"].sum()

                results["mill"] = {
                    "counties":    sel_mill_res,
                    "dist_mi":     m_dist,
                    "total_kdry":  m_total,
                    "residue_col": "mill_kdry_metric",
                }

                # ── Pulpwood (SAF only) ───────────────────────────────────────
                if IS_SAF:
                    _p_rows = in_range[in_range["county_label"].isin(sel_pulp)]
                    p_dist  = weighted_avg_distance(_p_rows, "pulpwood_kdry_metric", "road_miles")
                    p_total = _p_rows["pulpwood_kdry_metric"].sum()
                    results["pulpwood"] = {
                        "counties":    sel_pulp,
                        "dist_mi":     p_dist,
                        "total_kdry":  p_total,
                        "residue_col": "pulpwood_kdry_metric",
                    }

                results["mill_name"] = sel_mill
                results["mill_lat"]  = mill_lat
                results["mill_lon"]  = mill_lon
                results["radius_mi"] = radius_mi
                results["in_range"]  = in_range   # full county df for map generation
                st.session_state["sc_results"]  = results
                st.session_state["tr_results"]  = None   # transport now stale

        elif in_range is not None and in_range.empty:
            warn(f"No counties with biomass within {radius_mi} road miles of this mill.")

    # ─────────────────────────────────────────────────────────────────────────
    # RIGHT — map + metric cards
    # ─────────────────────────────────────────────────────────────────────────
    with _sc_right:
        col_header("Results")

        in_range = st.session_state.get("sc_in_range")
        results  = st.session_state.get("sc_results")

        if mill_lat is None:
            info("Select a mill to view its location on the map.")   
        else:
            # ── Build Folium map ──────────────────────────────────────────────
            # Zoom calibration: Mercator tiles are 256px per tile.
            # At zoom z, one tile covers 360/2^z degrees longitude.
            # Map container is 480px tall (see show_folium call below).
            # Target: radius circle fills ~75% of the shorter dimension.
            import math as _math
            _MAP_H_PX  = 480                             # must match show_folium height
            _MAP_W_PX  = 900                             # approximate rendered width
            _SHORT_PX  = min(_MAP_H_PX, _MAP_W_PX) * 0.75   # 75% of short side
            _lat_r_deg = radius_mi / 69.0                # radius in degrees latitude
            # px per degree at zoom z: 256 * 2^z / 360
            # We need: _lat_r_deg * px_per_deg = _SHORT_PX / 2
            # → 2^z = (_SHORT_PX/2) * 360 / (256 * _lat_r_deg)
            _zoom_f = _math.log2((_SHORT_PX / 2.0) * 360.0 / (256.0 * _lat_r_deg))
            _zoom   = max(5.0, min(10.0, round(_zoom_f * 2) / 2))  # clamp, snap 0.5

            # Shift center slightly north so the mill sits at visual midpoint.
            # The zoom controls and map chrome push content down ~5% of map height.
            _center_lat = mill_lat - (_lat_r_deg * 0.10)

            fmap = folium.Map(
                location=[_center_lat, mill_lon],
                zoom_start=_zoom,
                zoom_delta=0.5,            # each scroll tick = half a zoom level
                zoom_snap=0.5,             # allow half-level resting positions
                wheel_debounce_time=150,   # ms between scroll events (less jumpy)
                tiles=None,                # tile added manually below
            )
           # Stadia Alidade Smooth Dark — dark basemap, crisp white labels,
            # much better contrast than CartoDB Dark Matter
            _stadia_key = os.environ.get("STADIA_API_KEY", "")
            _stadia_url = (
                f"https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{{z}}/{{x}}/{{y}}{{r}}.png"
                + (f"?api_key={_stadia_key}" if _stadia_key else "")
            )
            folium.TileLayer(
                tiles=_stadia_url,
                attr='&copy; <a href="https://stadiamaps.com/">Stadia Maps</a> &copy; OpenMapTiles &copy; OpenStreetMap',
                max_zoom=20,
                opacity=1.0,               # full opacity for maximum contrast
            ).add_to(fmap)

            # Radius search circle (dashed, very light fill)
            if in_range is not None:
                folium.Circle(
                    location=[mill_lat, mill_lon],
                    radius=radius_mi * METERS_PER_MILE,
                    color="#4ade80", fill=True, fill_opacity=0.07,
                    weight=2.5, dash_array="8 5",
                    tooltip=f"{radius_mi}-mile search radius",
                ).add_to(fmap)

            # ── County dots ───────────────────────
            # Forest = green (solid, innermost).
            # Mill = amber ring (hollow, +5px offset).
            # Pulpwood = blue ring (hollow, +10px offset).
            # All three are independently hoverable because rings have no fill.
            if in_range is not None:
                _src_layers = [
                    # (col, hex, label, ring_offset, solid_fill)
                    ("forest_kdry_metric",   "#22c55e", "Forest",   0,  True),
                    ("mill_kdry_metric",     "#f59e0b", "Mill",     5,  False),
                ]
                if IS_SAF:
                    _src_layers.append(("pulpwood_kdry_metric", "#60a5fa", "Pulpwood", 10, False))

                for _col, _hex, _lbl, _ring_offset, _solid in _src_layers:
                    _sub = in_range[in_range[_col] > 0]
                    _mx  = _sub[_col].max() or 1
                    for _, _r in _sub.iterrows():
                        _intensity   = _r[_col] / _mx
                        _sel         = st.session_state["sc_selected"].get(_lbl.lower(), [])
                        _is_selected = _r["county_label"] in _sel
                        _base   = (5 + _intensity * 6) if _is_selected else (3 + _intensity * 4)
                        _radius = _base + _ring_offset
                        folium.CircleMarker(
                            location=[_r["lat"], _r["lon"]],
                            radius=_radius,
                            color=_hex,
                            fill=_solid,
                            fill_color=_hex if _solid else None,
                            fill_opacity=0.85 if (_solid and _is_selected) else (0.70 if _solid else 0),
                            weight=4.0 if not _solid else (2.0 if _is_selected else 1.2),
                            tooltip=(f"<b>{_lbl}</b>: {_r['county_label']}<br>"
                                     f"Supply: {_r[_col] * METRIC_TON_TO_US_TON:.2f}k dry US ton/yr<br>"
                                     f"Distance: {_r['road_miles']:.0f} mi"),
                        ).add_to(fmap)

            # ── Route lines to selected counties (after Calculate) ────────────
            if results is not None:
                for src_key, _hex in [("forest","#22c55e"),
                                       ("mill","#f59e0b"),
                                       ("pulpwood","#60a5fa")]:
                    if src_key not in results:
                        continue
                    for _cname in results[src_key]["counties"]:
                        _crow = in_range[in_range["county_label"] == _cname]
                        if _crow.empty:
                            continue
                        _cl, _co = float(_crow.iloc[0]["lat"]), float(_crow.iloc[0]["lon"])
                        _rpts = get_route_geometry(mill_lat, mill_lon, _cl, _co)
                        if _rpts:
                            folium.PolyLine(_rpts, color=_hex, weight=3.5,
                                            opacity=0.85,
                                            tooltip=f"{_cname}").add_to(fmap)
                        else:
                            # Straight-line fallback if OSRM unavailable
                            folium.PolyLine([[_cl, _co], [mill_lat, mill_lon]],
                                            color=_hex, weight=2, opacity=0.6,
                                            dash_array="5 4").add_to(fmap)
                        folium.CircleMarker(
                            location=[_cl, _co], radius=8,
                            color=_hex, fill=True, fill_color=_hex,
                            fill_opacity=0.9, weight=1.5,
                            tooltip=_cname,
                        ).add_to(fmap)

            # Mill marker
            if mill_lat:
                folium.Marker(
                    location=[mill_lat, mill_lon],
                    tooltip=f"Mill: {sel_mill}",
                    icon=folium.Icon(color="red", icon="home"),
                ).add_to(fmap)

            st.caption(
                "Green dot = Forest residue  |  "
                "Amber ring = Sawmill residue  |  "
                "Blue ring = Pulpwood (SAF only)  |  "
                "Red marker = Mill site  |  "
                "Dot size = supply volume  |  Rings = additional feedstock in same county"
            )
            show_folium(fmap, height=480)
            # Save map HTML for PDF screenshot
            try:
                _map_html_path = os.path.join(_DIR, "sc_map.html")
                fmap.save(_map_html_path)
                st.session_state["_sc_map_html"] = _map_html_path
            except Exception: pass

            # ── Summary metric cards (after Calculate Weighted Distance) ───────
            if results is not None:
                # gap removed — metric cards follow map immediately

                # ── Forest row: Total | Dist | HQ fraction (SAF only) ──────────
                fr = results["forest"]
                _f_dist_str  = f"{fr['dist_mi']:.1f} mi" if fr["dist_mi"] else "—"
                _f_total_str = f"{fr['total_kdry']:.2f}" if fr["total_kdry"] else "—"
                _hq_str      = f"{fr['hq_kdry']:.2f}" if IS_SAF else None

                # 3 cols in SAF (adds HQ card), 2 in Bioenergy
                _f_cols = st.columns(3) if IS_SAF else st.columns(2)
                with _f_cols[0]:
                    _f_total_str_US_units = float(_f_total_str)*METRIC_TON_TO_US_TON
                    _f_total_str_US_units_str = f"{_f_total_str_US_units:.1f}" 
                    st.markdown(mc("Forest Total", _f_total_str_US_units_str, "k dry US ton/yr"),
                                unsafe_allow_html=True)
                with _f_cols[1]:
                    st.markdown(mc("Forest Dist", _f_dist_str, "weighted avg mi"),
                                unsafe_allow_html=True)
                if IS_SAF and len(_f_cols) > 2:
                    with _f_cols[2]:
                        # HQ card immediately next to forest total/dist
                        _hq_str_US_units = float(_hq_str)*METRIC_TON_TO_US_TON
                        _hq_str_US_units_str = f"{_hq_str_US_units:.1f}"
                        st.markdown(mc("Forest HQ (69.2%)", _hq_str_US_units_str,
                                       "k dry US ton/yr usable for SAF"),
                                    unsafe_allow_html=True)

                # ── Mill residue row ──────────────────────────────────────────
                mr = results["mill"]
                _mr_dist_str  = f"{mr['dist_mi']:.1f} mi" if mr["dist_mi"] else "—"
                _mr_total_str = f"{mr['total_kdry']:.2f}" if mr["total_kdry"] else "—"
                _m_cols = st.columns(2)
                with _m_cols[0]:
                    _mr_total_str_US_units = float(_mr_total_str)*METRIC_TON_TO_US_TON
                    _mr_total_str_US_units_str = f"{_mr_total_str_US_units:.1f}"
                    st.markdown(mc("Mill Total", _mr_total_str_US_units_str, "k dry US ton/yr",
                                   "mc-amber"), unsafe_allow_html=True)
                with _m_cols[1]:
                    st.markdown(mc("Mill Dist", _mr_dist_str, "weighted avg mi",
                                   "mc-amber"), unsafe_allow_html=True)

                # ── Pulpwood row (SAF only) ───────────────────────────────────
                if IS_SAF and "pulpwood" in results:
                    pr = results["pulpwood"]
                    _pr_dist_str  = f"{pr['dist_mi']:.1f} mi" if pr["dist_mi"] else "—"
                    _pr_total_str = f"{pr['total_kdry']:.2f}" if pr["total_kdry"] else "—"
                    _p_cols = st.columns(2)
                    with _p_cols[0]:
                        _pr_total_str_US_units = float(_pr_total_str)*METRIC_TON_TO_US_TON
                        _pr_total_str_US_units_str = f"{_pr_total_str_US_units:.1f}"
                        st.markdown(mc("Pulpwood Total", _pr_total_str_US_units_str, "k dry US ton/yr",
                                       "mc-blue"), unsafe_allow_html=True)
                    with _p_cols[1]:
                        st.markdown(mc("Pulpwood Dist", _pr_dist_str, "weighted avg mi",
                                       "mc-blue"), unsafe_allow_html=True)

                # st.markdown("<br>", unsafe_allow_html=True)
                info(
                    f"<b>Distances computed.</b>  "
                    f"These feed into Biomass Transport tab as one-way haul distances."
                )


# ══════════════════════════════════════════════════════════════════════════════
# ┌──────────────────────────────────────────────────────────────────────────┐
# │  TAB 2 — BIOMASS TRANSPORT                                               │
# │                                                                          │
# │  For each enabled biomass source:                                        │
# │    • Option selectbox (filtered by source/mode)                          │
# │    • Speed slider (shared, 10-50 mph, default 20)                       │
# │    • delivered_cost() → $/ODT breakdown cards                            │
# │    • plot_cost_vs_distance() stacked-area chart                          │
# │    • plot_compare_options() horizontal bar chart                         │
# │                                                                          │
# │  Option routing:                                                         │
# │    Bioenergy  Forest → 2.x   Mill → 3.x                                 │
# │    SAF        Forest HQ → 1.x   Mill → 3.x   Pulpwood → 1.x            │
# └──────────────────────────────────────────────────────────────────────────┘
# ══════════════════════════════════════════════════════════════════════════════
with tab_tr:

    sc_results = st.session_state.get("sc_results")

    if sc_results is None:
        info("Complete the <b>Supply Chain</b> tab first (click "
             "<b>Calculate Weighted Distance</b>).")
    else:
        # ── Shared speed slider ───────────────────────────────────────────────
        # Applies to ALL sources — matches Biomass_Transport.delivered_cost() API
        # which accepts speed_mph as a parameter.  Range 10-50 mph, default 20 mph
        # (20 mph is the typical forest-road average per Sahoo et al. 2019).
        section("Truck Speed (applies to all sources)")
        speed_mph = st.slider(
            "Average truck speed (mph)", 10, 50, 20, 1, key="tr_speed",
            help="Sahoo et al. 2019 default: 20 mph for forest haul roads"
        )

        # Helper: build a transport section for one source
        def render_transport_source(source_key, label, dist_mi,
                                    option_ids, hex_color, residue_kdry_base):
            """
            Render inputs, cost cards, and plots for one biomass source.

            Parameters
            ----------
            source_key      : "forest" | "mill" | "pulpwood"
            label           : display name shown in the UI header
            dist_mi         : weighted-average one-way haul distance (miles)
                              from the Supply Chain tab
            option_ids      : valid transport option IDs for this source
            hex_color       : theme hex for metric card variant selection
            residue_kdry_base : total supply from Supply Chain (k metric dry t/yr)
                              BEFORE the obtainability adjustment applied here
            """
            st.markdown(f"### {label}")

            if dist_mi is None or dist_mi <= 0:
                warn(f"No counties selected for {label} in Supply Chain tab.")
                return None

            _vc = "mc-amber" if hex_color == "#f59e0b" else (
                  "mc-blue"  if hex_color == "#60a5fa" else "")

            # ── Top row: inputs | cost cards (no plot here — plots go full-width below)
            _c_inp, _c_cards = st.columns([1, 1], gap="small")

            with _c_inp:
                # ── Obtainability slider ──────────────────────────────────────
                # Lets user specify what fraction of the available residue is
                # actually obtainable/accessible (e.g. terrain, ownership, etc.)
                # Range: 0–100 %, default 100 %.
                # For forest in SAF mode this is applied AFTER the 69.2% HQ split
                # so residue_kdry_base already reflects the HQ fraction.
                _obtain = st.slider(
                    f"{label} obtainability (%)",
                    min_value=0, max_value=100,
                    value=st.session_state.get(f"tr_obtain_{source_key}", 100),
                    step=1,
                    key=f"tr_obtain_{source_key}",
                    help="% of total supply that can actually be collected"
                )
                # Effective usable supply after obtainability — updates live with slider
                residue_kdry = residue_kdry_base * (_obtain / 100.0)
                st.markdown(
                    f'<div style="font-size:0.9rem;color:#4a5a6a;margin:2px 0 6px 0">'
                    f'Effective supply: '
                    f'<span style="color:#c9d1e0;font-weight:600">{residue_kdry*METRIC_TON_TO_US_TON:.2f}k US ton/yr</span>'
                    f' (of {residue_kdry_base*METRIC_TON_TO_US_TON:.2f}k base)</div>',
                    unsafe_allow_html=True
                )

                # Option selectbox (filtered to valid options for this source)
                _opt_labels = {oid: f"{oid} — {bt._OPTIONS[oid]['label']}"
                               for oid in option_ids}
                _sel_oid = st.selectbox(
                    "Processing option:",
                    list(_opt_labels.keys()),
                    format_func=lambda x: _opt_labels[x],
                    key=f"tr_opt_{source_key}",
                )

            with _c_cards:
                # Call delivered_cost exactly as Biomass_Transport.main() does
                result = bt.delivered_cost(
                    option_id      = _sel_oid,
                    distance_miles = dist_mi,
                    speed_mph      = speed_mph,
                    cost_year      = 2025,
                )

                # ── Find cheapest option for this source at this distance ──────
                # Run all valid options and identify the minimum total cost.
                # Report it as a recommendation to the user.
                _all_costs = {
                    oid: bt.delivered_cost(oid, dist_mi, speed_mph, 2025)["total"]
                    for oid in option_ids
                }
                _best_oid  = min(_all_costs, key=_all_costs.get)
                _best_cost = _all_costs[_best_oid]
                _curr_cost = result["total"]

                if _best_oid == _sel_oid:
                    info(f"<b>Best option selected</b><br>"
                         f"Option {_best_oid} is cheapest at ${_best_cost:.2f}/ODT")
                else:
                    warn(f"<b>Cheaper option available:</b> {_best_oid}<br>"
                         f"${_best_cost:.2f}/ODT vs ${_curr_cost:.2f}/ODT selected")

                # Distance + supply summary
                st.markdown(
                    f'<div class="ib" style="font-size:0.9rem">'
                    f'Distance: <b>{dist_mi:.1f} mi</b>  |  '
                    f'Supply: <b>{residue_kdry*METRIC_TON_TO_US_TON:.2f}k US ton/yr</b> '
                    f'(base {residue_kdry_base*METRIC_TON_TO_US_TON:.2f}k, {_obtain}%)</div>',
                    unsafe_allow_html=True
                )

                # $/ODT breakdown cards (2x2 grid)
                _cm1, _cm2 = st.columns(2)
                with _cm1:
                    st.markdown(mc("BSTP",       f"${result['bstp']:.2f}",
                                   "$/ODT", _vc), unsafe_allow_html=True)
                    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
                    st.markdown(mc("Processing", f"${result['processing']:.2f}",
                                   "$/ODT", _vc), unsafe_allow_html=True)
                with _cm2:
                    st.markdown(mc("Transport",  f"${result['transportation']:.2f}",
                                   "$/ODT", _vc), unsafe_allow_html=True)
                    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
                    st.markdown(mc("TOTAL",      f"${result['total']:.2f}",
                                   "$/ODT", _vc), unsafe_allow_html=True)

            # ── Plots: full-width row below inputs/cards ──────────────────────
            # Always show both plots side-by-side (even single-option sources
            # get the comparison chart — it just shows one bar, confirming cost).
            _n_opts = len(option_ids)
            _p1, _p2 = st.columns([1, 1], gap="medium")

            _PLOT_H = 3.8   # fixed height keeps both charts the same

            with _p1:
                _fig1 = bt.plot_cost_vs_distance(
                    option_id     = _sel_oid,
                    speed_mph     = speed_mph,
                    cost_year     = 2025,
                    mark_distance = dist_mi,
                )
                _fig1.set_size_inches(7, _PLOT_H)
                plt.tight_layout(pad=0.5)
                st.pyplot(_fig1, width="stretch")
                plt.close(_fig1)

            with _p2:
                _fig2 = bt.plot_compare_options(
                    distance_miles = dist_mi,
                    speed_mph      = speed_mph,
                    cost_year      = 2025,
                    option_ids     = option_ids,
                )
                _fig2.set_size_inches(7, _PLOT_H)
                plt.tight_layout(pad=0.5)
                st.pyplot(_fig2, width="stretch")
                plt.close(_fig2)

            # Return result with effective (post-obtainability) residue attached
            result["residue_kdry_effective"] = residue_kdry
            return result

        # ── Render one section per source ─────────────────────────────────────
        tr_results = {}

        # Forest
        _f = sc_results["forest"]
        _f_opts    = OPTIONS_LOW if not IS_SAF else OPTIONS_HIGH
        _f_dist    = _f.get("dist_mi")
        _f_residue = _f.get("hq_kdry" if IS_SAF else "total_kdry", 0)

        st.markdown("<hr style='border-color:#1e2a3a'>", unsafe_allow_html=True)
        res_forest = render_transport_source(
            "forest",
            "Forest Residue (HQ 69.2%)" if IS_SAF else "Forest Residue",
            _f_dist, _f_opts, "#22c55e", _f_residue
        )
        if res_forest:
            tr_results["forest"] = {
                "option":        res_forest["option_id"],
                "cost_odt":      res_forest["total"],
                "dist_mi":       _f_dist,
                "label":         res_forest["label"],
                "residue_kdry":  res_forest.get("residue_kdry_effective", _f_residue),
                "obtainability": st.session_state.get("tr_obtain_forest", 100),
            }

        # Mill residues (always available in both modes)
        _m = sc_results["mill"]
        st.markdown("<hr style='border-color:#1e2a3a'>", unsafe_allow_html=True)
        res_mill = render_transport_source(
            "mill", "Mill Residue",
            _m.get("dist_mi"), OPTIONS_MILL,
            "#f59e0b", _m.get("total_kdry", 0)
        )
        if res_mill:
            tr_results["mill"] = {
                "option":        res_mill["option_id"],
                "cost_odt":      res_mill["total"],
                "dist_mi":       _m.get("dist_mi"),
                "label":         res_mill["label"],
                "residue_kdry":  res_mill.get("residue_kdry_effective", _m.get("total_kdry", 0)),
                "obtainability": st.session_state.get("tr_obtain_mill", 100),
            }

        # Pulpwood (SAF only)
        if IS_SAF and "pulpwood" in sc_results:
            _p = sc_results["pulpwood"]
            st.markdown("<hr style='border-color:#1e2a3a'>", unsafe_allow_html=True)
            res_pulp = render_transport_source(
                "pulpwood", "Pulpwood",
                _p.get("dist_mi"), OPTIONS_PULPWOOD,
                "#60a5fa", _p.get("total_kdry", 0)
            )
            if res_pulp:
                tr_results["pulpwood"] = {
                    "option":        res_pulp["option_id"],
                    "cost_odt":      res_pulp["total"],
                    "dist_mi":       _p.get("dist_mi"),
                    "label":         res_pulp["label"],
                    "residue_kdry":  res_pulp.get("residue_kdry_effective", _p.get("total_kdry", 0)),
                    "obtainability": st.session_state.get("tr_obtain_pulpwood", 100),
                }

        tr_results["speed_mph"] = speed_mph
        st.session_state["tr_results"] = tr_results

        # ── Combined summary ──────────────────────────────────────────────────
        st.markdown("<hr style='border-color:#1e2a3a'>", unsafe_allow_html=True)
        section("Delivered Cost Summary")
        _sc1, _sc2, _sc3 = st.columns(3)
        with _sc1:
            if "forest" in tr_results:
                st.markdown(mc("Forest Delivered",
                               f"${tr_results['forest']['cost_odt']:.2f}",
                               f"$/ODT · {tr_results['forest']['option']}"),
                            unsafe_allow_html=True)
        with _sc2:
            if "mill" in tr_results:
                st.markdown(mc("Mill Delivered",
                               f"${tr_results['mill']['cost_odt']:.2f}",
                               f"$/ODT · {tr_results['mill']['option']}",
                               "mc-amber"), unsafe_allow_html=True)
        with _sc3:
            if IS_SAF and "pulpwood" in tr_results:
                st.markdown(mc("Pulpwood Delivered",
                               f"${tr_results['pulpwood']['cost_odt']:.2f}",
                               f"$/ODT · {tr_results['pulpwood']['option']}",
                               "mc-blue"), unsafe_allow_html=True)

        # ── Auto-send: write transport results downstream on every render ──────
        # No button needed — results are always available to Economics tab.
        st.session_state["tr_results"]      = tr_results
        st.session_state["tr_sent_to_econ"] = True
        if True:  # keep indentation

            # ── Write values directly into Economics widget keys ─────────────
            # Streamlit widgets ignore value= after first render; must write
            # to session_state keys directly to update widget display values.

            # Effective (post-obtainability) tons — for display only.
            # Raw base tons and obtainability are passed separately to the models.
            _f_eff  = tr_results.get("forest",   {}).get("residue_kdry", 0)
            _m_eff  = tr_results.get("mill",     {}).get("residue_kdry", 0)
            _pw_eff = tr_results.get("pulpwood", {}).get("residue_kdry", 0)
            _f_c    = tr_results.get("forest",   {}).get("cost_odt", 25.0)
            _m_c    = tr_results.get("mill",     {}).get("cost_odt", 20.0)
            _pw_c   = tr_results.get("pulpwood", {}).get("cost_odt", 60.0)

            # Raw (pre-obtainability) base tons — recover from effective / obtain fraction.
            # Prefer obtainability stored in tr_results (persists in saved scenarios);
            # fall back to session-state slider key for backward compatibility.
            _f_ob_frac  = float(tr_results.get("forest",   {}).get("obtainability", st.session_state.get("tr_obtain_forest",   100))) / 100.0
            _m_ob_frac  = float(tr_results.get("mill",     {}).get("obtainability", st.session_state.get("tr_obtain_mill",     100))) / 100.0
            _pw_ob_frac = float(tr_results.get("pulpwood", {}).get("obtainability", st.session_state.get("tr_obtain_pulpwood", 100))) / 100.0
            _f_raw  = (_f_eff  / _f_ob_frac)  if _f_ob_frac  > 0 else _f_eff
            _m_raw  = (_m_eff  / _m_ob_frac)  if _m_ob_frac  > 0 else _m_eff
            _pw_raw = (_pw_eff / _pw_ob_frac) if _pw_ob_frac > 0 else _pw_eff

            # ── Bioenergy widget keys ─────────────────────────────────────────
            # Push RAW tons — model receives raw tons + obtainability and applies
            # the reduction itself. Clamp to widget min_value=1.
            if _f_raw > 0:
                st.session_state["be_f_tons"]  = max(1, int(_f_raw * 1000))
            if _m_raw > 0:
                st.session_state["be_m_tons"]  = max(0, int(_m_raw * 1000))
            if _f_c > 0:
                st.session_state["be_f_cost"]  = float(round(_f_c, 2))
            if _m_c > 0:
                st.session_state["be_m_cost"]  = float(round(_m_c, 2))
            # obtainability: Economics tab reads tr_obtain_* directly from session_state

            # ── SAF widget keys ───────────────────────────────────────────────
            # Push RAW tons — SAF model receives raw tons + obtainability and applies
            # the reduction itself.
            if _f_raw > 0:
                st.session_state["saf_f_tons"]  = int(_f_raw * 1000)
            if _pw_raw > 0:
                st.session_state["saf_pw_tons"] = int(_pw_raw * 1000)
            if _m_raw > 0:
                st.session_state["saf_sw_tons"] = int(_m_raw * 1000)
            if _f_c > 0:
                st.session_state["saf_pdc_f"]   = float(round(_f_c, 2))
            if _pw_c > 0:
                st.session_state["saf_pdc_pw"]  = float(round(_pw_c, 2))
            if _m_c > 0:
                st.session_state["saf_pdc_sw"]  = float(round(_m_c, 2))
            # obtainability: Economics tab reads tr_obtain_* directly from session_state

            # Only clear stale economics cache when transport values have changed.
            # This prevents wiping LCOE/be_df every time you visit this tab.
            import json as _jj
            try:
                _tr_sig = str({k: (round(v.get("cost_odt",0),2), round(v.get("residue_kdry",0),2))
                               for k,v in tr_results.items() if isinstance(v,dict)})
            except Exception:
                _tr_sig = ""
            if _tr_sig != st.session_state.get("_tr_sig_last", ""):
                st.session_state["_tr_sig_last"] = _tr_sig
                for _k in ["be_df", "be_metrics", "be_lcoe", "be_equip_done",
                            "saf_df", "saf_metrics", "saf_mfsp"]:
                    st.session_state.pop(_k, None)

            st.success(
                f"✓ Sent — "
                f"Forest {_f_eff*METRIC_TON_TO_US_TON:.1f}k US ton/yr @ ${_f_c:.2f}/ODT  |  "
                f"Pulpwood {_pw_eff*METRIC_TON_TO_US_TON:.1f}k US ton/yr @ ${_pw_c:.2f}/ODT  |  "
                f"Mill {_m_eff*METRIC_TON_TO_US_TON:.1f}k US ton/yr @ ${_m_c:.2f}/ODT"
            )


# ══════════════════════════════════════════════════════════════════════════════
# ┌──────────────────────────────────────────────────────────────────────────┐
# │  TAB 3a — BIOENERGY ECONOMICS                                            │
# │                                                                          │
# │  Calls BioEnergy_Economics EXACTLY as main() does:                      │
# │    predict_output → equipment_costs → TCI_calculation →                 │
# │    depreciation_schedule → build_cash_flow_analysis → plot_all          │
# │    → get_lcoe                                                            │
# │                                                                          │
# │  "Heavy" computation (equipment_costs, TCI, depreciation) runs once     │
# │  when Run button is clicked and results are cached in session_state.     │
# │  Electricity-price slider and loan-term slider then re-run ONLY the     │
# │  fast build_cash_flow_analysis so plots update dynamically.             │
# └──────────────────────────────────────────────────────────────────────────┘
# ══════════════════════════════════════════════════════════════════════════════
with tab_econ:
    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — ECONOMICS
    # Bioenergy path calls bioenergy_MAIN_economics_FINAL exactly as main() does:
    #   predict_output → equipment_costs → TCI_calculation →
    #   depreciation_schedule → build_cash_flow_analysis → get_lcoe → plot_all
    # SAF path calls saf_MAIN_economics_FINAL exactly as main() does:
    #   build_cash_flow_analysis (per-source throughputs) → solve_mfsp → sp.plot_all
    # Jobs called via Jobscreation_model exactly as each main() does.
    # ══════════════════════════════════════════════════════════════════════════

    if IS_SAF:
        # ──────────────────────────────────────────────────────────────────────
        # SAF ECONOMICS  (saf_MAIN_economics_FINAL)
        # KEY CHANGE from old dashboard: separate forest / pulpwood / sawmill
        # throughputs and PDCs, matching the new main() call signature exactly.
        # obtainibility is a FRACTION (0.0–1.0), not a percentage.
        # ──────────────────────────────────────────────────────────────────────
        if not SAF_AVAILABLE:
            st.error(f"saf_MAIN_economics_FINAL.py could not be imported: **{SAF_ERROR}**")
        else:
            sc_res = st.session_state.get("sc_results")
            tr_res = st.session_state.get("tr_results")

            # ── Raw (pre-obtainability) throughputs from session_state ─────────
            # These were set by the Transport auto-send. The model applies
            # obtainability internally — raw tons + obtain fraction is the correct input.
            _f_tons_base   = int(st.session_state.get("saf_f_tons",  (int(sc_res["forest"].get("hq_kdry", 0) * 1000) if sc_res else 100_000)))
            _pw_tons_base  = int(st.session_state.get("saf_pw_tons", (int(sc_res.get("pulpwood", {}).get("total_kdry", 0) * 1000) if sc_res else 100_000)))
            _sw_tons_base  = int(st.session_state.get("saf_sw_tons", (int(sc_res["mill"].get("total_kdry", 0) * 1000) if sc_res else 100_000)))

            # ── Auto-fill PDCs from Transport tab ($/dry ton = $/ODT) ─────────
            _pdc_f  = tr_res["forest"]["cost_odt"]   if tr_res and "forest"   in tr_res else 60.0
            _pdc_pw = tr_res["pulpwood"]["cost_odt"] if tr_res and "pulpwood" in tr_res else 60.0
            _pdc_sw = tr_res["mill"]["cost_odt"]     if tr_res and "mill"     in tr_res else 60.0

            # Obtainability from Transport tab — prefer value stored in tr_results
            # (persists across sessions/saved scenarios); fall back to slider key.
            _f_ob_auto  = float((tr_res or {}).get("forest",   {}).get("obtainability", st.session_state.get("tr_obtain_forest",   100))) / 100.0
            _pw_ob_auto = float((tr_res or {}).get("pulpwood", {}).get("obtainability", st.session_state.get("tr_obtain_pulpwood", 100))) / 100.0
            _sw_ob_auto = float((tr_res or {}).get("mill",     {}).get("obtainability", st.session_state.get("tr_obtain_mill",     100))) / 100.0

            # Effective tonnage for display only
            _f_eff_disp  = _f_tons_base  * _f_ob_auto
            _pw_eff_disp = _pw_tons_base * _pw_ob_auto
            _sw_eff_disp = _sw_tons_base * _sw_ob_auto

            # Raw tons and obtainability are passive — set from Transport tab, not editable here
            saf_f_tons  = _f_tons_base
            saf_pw_tons = _pw_tons_base
            saf_sw_tons = _sw_tons_base
            saf_f_ob    = _f_ob_auto
            saf_pw_ob   = _pw_ob_auto
            saf_sw_ob   = _sw_ob_auto
            st.session_state["saf_f_tons"]  = saf_f_tons
            st.session_state["saf_pw_tons"] = saf_pw_tons
            st.session_state["saf_sw_tons"] = saf_sw_tons
            st.session_state["saf_f_ob"]    = saf_f_ob
            st.session_state["saf_pw_ob"]   = saf_pw_ob
            st.session_state["saf_sw_ob"]   = saf_sw_ob

            col_header("SAF Inputs")
            if sc_res and tr_res:
                info(
                    f"<b>Effective Throughput</b> (Obtainability Applied From Transport Tab — "
                    f"Forest {_f_ob_auto:.0%}  Pulpwood {_pw_ob_auto:.0%}  Sawmill {_sw_ob_auto:.0%}):<br>"
                    f"Forest <b>{_f_eff_disp*METRIC_TON_TO_US_TON:,.0f} US ton/yr</b>  |  "
                    f"Pulpwood <b>{_pw_eff_disp*METRIC_TON_TO_US_TON:,.0f} US ton/yr</b>  |  "
                    f"Sawmill <b>{_sw_eff_disp*METRIC_TON_TO_US_TON:,.0f} US ton/yr</b>"
                )

            # ── 4 input columns across the top ───────────────────────────────
            _sa, _sb, _sc, _sd = st.columns(4, gap="medium")

            with _sa:
                section("Feedstock")
                saf_year = st.number_input("Analysis Year", 2024, 2040, 2025, 1, key="saf_year")
                for _lbl, _eff, _raw, _ob, _pdc_key, _pdc_val, _cost_lbl in [
                    ("Effective Forest Residue",  _f_eff_disp*METRIC_TON_TO_US_TON,  _f_tons_base*METRIC_TON_TO_US_TON,  _f_ob_auto,  "saf_pdc_f",  _pdc_f,  "Forest Cost ($/US ton)"),
                    ("Effective Pulpwood",         _pw_eff_disp*METRIC_TON_TO_US_TON, _pw_tons_base*METRIC_TON_TO_US_TON, _pw_ob_auto, "saf_pdc_pw", _pdc_pw, "Pulpwood Cost ($/US ton)"),
                    ("Effective Sawmill Residue",  _sw_eff_disp*METRIC_TON_TO_US_TON, _sw_tons_base*METRIC_TON_TO_US_TON, _sw_ob_auto, "saf_pdc_sw", _pdc_sw, "Sawmill Cost ($/US ton)"),
                ]:
                    st.markdown(
                        f'<div style="margin-bottom:4px">'
                        f'<div style="font-size:0.9rem;color:#8a9ab0;margin-bottom:2px">{_lbl} (US ton/yr)</div>'
                        f'<div style="font-size:1.05rem;font-weight:700;color:#c9d1e0;'
                        f'background:#0e1621;border:1px solid #1e2d3d;border-radius:6px;'
                        f'padding:8px 12px;letter-spacing:0.02em">'
                        f'{int(_eff):,}'
                        f'<span style="font-size:0.9rem;font-weight:400;color:#4a6a8a;margin-left:8px">'
                        f'{int(_raw):,} raw × {_ob:.0%}</span></div></div>',
                        unsafe_allow_html=True
                    )
                    st.markdown(
                        f'<div style="margin-bottom:10px">'
                        f'<div style="font-size:0.9rem;color:#8a9ab0;margin-bottom:2px">{_cost_lbl}</div>'
                        f'<div style="font-size:1.05rem;font-weight:700;color:#c9d1e0;'
                        f'background:#0e1621;border:1px solid #1e2d3d;border-radius:6px;'
                        f'padding:8px 12px;letter-spacing:0.02em">'
                        f'{st.session_state[_pdc_key]:,}',
                        unsafe_allow_html=True
                    )
                saf_pdc_f  = st.session_state.get("saf_pdc_f",  float(round(_pdc_f,  2)))
                saf_pdc_pw = st.session_state.get("saf_pdc_pw", float(round(_pdc_pw, 2)))
                saf_pdc_sw = st.session_state.get("saf_pdc_sw", float(round(_pdc_sw, 2)))

            with _sb:
                section("Product Prices ($/gal)")
                saf_saf_p_gal = st.number_input("SAF Price ($/gal)",     1.0, 15.0, round(1.61*L_PER_GAL, 2), 0.01, format="%.2f", key="saf_safprice")
                saf_die_p_gal = st.number_input("Diesel Price ($/gal)",  0.5, 10.0, round(1.03*L_PER_GAL, 2), 0.01, format="%.2f", key="saf_dieprice")
                saf_nap_p_gal = st.number_input("Naphtha Price ($/gal)", 0.5, 10.0, round(0.75*L_PER_GAL, 2), 0.01, format="%.2f", key="saf_napprice")
                # Convert to $/L for model
                saf_saf_p = saf_saf_p_gal / L_PER_GAL
                saf_die_p = saf_die_p_gal / L_PER_GAL
                saf_nap_p = saf_nap_p_gal / L_PER_GAL
                section("Distillate")
                saf_distil = st.selectbox(
                    "Distillate Type",
                    ["distillate 1", "distillate 2"],
                    format_func=lambda x: {
                        "distillate 1": "SAF 50% / Diesel 30% / Naphtha 20%",
                        "distillate 2": "SAF 40% / Diesel 40% / Naphtha 20%",
                    }[x],
                    key="saf_distil"
                )

            with _sc:
                section("Finance")
                saf_life      = st.number_input("Plant Lifespan (yr)", 10, 50, 20, 1, key="saf_life")
                saf_disc      = st.number_input("Real Discount Rate (%)", 0.0, 30.0, 10.0, 0.5, format="%.1f", key="saf_disc") / 100
                saf_infl      = st.number_input("Inflation (%)", 0.0, 20.0, 2.5, 0.1, format="%.1f", key="saf_infl") / 100
                saf_debt      = st.number_input("Debt Fraction (%)", 0, 100, 70, 5, key="saf_debt") / 100
                saf_loan_r    = st.number_input("Loan Rate (%)", 0.0, 20.0, 8.0, 0.5, format="%.1f", key="saf_loan_r") / 100
                saf_loan_term = st.number_input("Loan Term (yr)", 5, 30, 15, 1, key="saf_loanterm")
                saf_cpi       = st.number_input("CPI", 200.0, 400.0, 321.05, 0.01, format="%.2f", key="saf_cpi")
                saf_degr      = st.number_input("Degradation (%/yr)", 0.0, 5.0, 0.0, 0.1, format="%.1f", key="saf_degr") / 100

            with _sd:
                section("Escalation")
                saf_pesc  = st.number_input("Price Escalation (%/yr)",    0.0, 10.0, 2.5, 0.1, format="%.1f", key="saf_pesc")  / 100
                saf_fesc  = st.number_input("Fuel Escalation (%/yr)",     0.0, 10.0, 2.5, 0.1, format="%.1f", key="saf_fesc")  / 100
                saf_cesc  = st.number_input("Cost Escalation (%/yr)",     0.0, 10.0, 2.5, 0.1, format="%.1f", key="saf_cesc")  / 100
                saf_kaesc = st.number_input("Catalyst Escalation (%/yr)", 0.0, 10.0, 2.5, 0.1, format="%.1f", key="saf_kaesc") / 100
                section("Tax")
                saf_fed_tax = st.number_input("Federal Tax (%)", 0, 50, 21, 1, key="saf_fedtax") / 100
                saf_st_tax  = st.number_input("State Tax (%)",   0, 20,  7, 1, key="saf_sttax")  / 100

            run_saf = st.button("Run SAF Economics", type="primary", width="stretch", key="run_saf_btn")
            st.markdown("<hr style='border-color:#1e2d3d;margin:4px 0'>", unsafe_allow_html=True)

            col_header("SAF Results")
            with st.container():
                if True:

                    def _run_saf_cashflow():
                        """
                        Call sfm.build_cash_flow_analysis exactly as saf_MAIN_economics_FINAL.main() does.
                        Positional args match the main() call order precisely.
                        verbose=False suppresses console output in the dashboard.
                        """
                        return sfm.build_cash_flow_analysis(
                            saf_year,
                            saf_f_tons,
                            saf_pw_tons,
                            saf_sw_tons,
                            saf_f_ob,
                            saf_pw_ob,
                            saf_sw_ob,
                            saf_distil,
                            saf_life,
                            saf_disc,
                            saf_infl,
                            saf_debt,
                            saf_loan_r,
                            saf_loan_term,
                            saf_cpi,
                            saf_pdc_f,
                            saf_pdc_pw,
                            saf_pdc_sw,
                            saf_degr,
                            saf_saf_p,
                            saf_die_p,
                            saf_nap_p,
                            saf_pesc,
                            saf_fesc,
                            saf_cesc,
                            saf_kaesc,
                            saf_fed_tax,
                            saf_st_tax,
                            verbose=False,
                        )

                    if run_saf:
                        _saf_total_tons = (saf_f_tons * saf_f_ob +
                                           saf_pw_tons * saf_pw_ob +
                                           saf_sw_tons * saf_sw_ob)
                        if _saf_total_tons <= 0:
                            st.error("Total effective throughput is zero — set obtainability and throughput in the Transport tab before running economics.")
                        else:
                          with st.spinner("Running SAF economics..."):
                            try:
                                _df, _mets = _run_saf_cashflow()
                                # solve_mfsp called exactly as saf_MAIN_economics_FINAL.main() does
                                _mfsp = sfm.solve_mfsp(
                                    saf_year,
                                    saf_f_tons,
                                    saf_pw_tons,
                                    saf_sw_tons,
                                    saf_f_ob,
                                    saf_pw_ob,
                                    saf_sw_ob,
                                    saf_distil,
                                    saf_life,
                                    saf_disc,
                                    saf_infl,
                                    saf_debt,
                                    saf_loan_r,
                                    saf_loan_term,
                                    saf_cpi,
                                    saf_pdc_f,
                                    saf_pdc_pw,
                                    saf_pdc_sw,
                                    saf_degr,
                                    saf_pesc,
                                    saf_fesc,
                                    saf_cesc,
                                    saf_kaesc,
                                    saf_fed_tax,
                                    saf_st_tax,
                                )
                                st.session_state.update({
                                    "saf_df": _df, "saf_metrics": _mets, "saf_mfsp": _mfsp
                                })
                                # Snapshot all SAF inputs for PDF report
                                st.session_state["_snap_saf_inputs"] = {
                                    "in_saf_year":     saf_year,
                                    "in_saf_distil":   saf_distil,
                                    "in_saf_life":     saf_life,
                                    "in_saf_disc":     saf_disc   * 100,
                                    "in_saf_infl":     saf_infl   * 100,
                                    "in_saf_debt":     saf_debt   * 100,
                                    "in_saf_loan_r":   saf_loan_r * 100,
                                    "in_saf_loanterm": saf_loan_term,
                                    "in_saf_cpi":      saf_cpi,
                                    "in_saf_degr":     saf_degr   * 100,
                                    "in_saf_fedtax":   saf_fed_tax* 100,
                                    "in_saf_sttax":    saf_st_tax * 100,
                                    "in_saf_safprice": st.session_state.get("saf_safprice"),
                                    "in_saf_dieprice": st.session_state.get("saf_dieprice"),
                                    "in_saf_napprice": st.session_state.get("saf_napprice"),
                                    "in_saf_pesc":     saf_pesc   * 100,
                                    "in_saf_fesc":     saf_fesc   * 100,
                                }
                                # Jobs — exactly as saf_MAIN_economics_FINAL.main() calls it
                                if JOBS_AVAILABLE:
                                    _jout = jm.jobs_from_biofuel("Biofuel Plant", _df["Revenue"][1])
                                    jm.plot_job_breakdown(_jout, title="Biofuel Plant Jobs Analysis")
                                    st.session_state["jobs_result"] = _jout
                            except Exception as _e:
                                st.error(f"SAF economics failed: {_e}")
                                import traceback; st.code(traceback.format_exc())

                    elif st.session_state.get("saf_df") is not None:
                        # Dynamic slider update: re-run only build_cash_flow_analysis
                        try:
                            _df, _mets = _run_saf_cashflow()
                            st.session_state["saf_df"]      = _df
                            st.session_state["saf_metrics"] = _mets
                        except Exception:
                            pass

                    _sdf  = st.session_state.get("saf_df")
                    _smts = st.session_state.get("saf_metrics")
                    _mfsp = st.session_state.get("saf_mfsp")

                    if _sdf is not None and _smts is not None:
                        _npv  = _smts.get("NPV (Equity, Nominal)", 0)
                        _irr  = _smts.get("Equity IRR", float("nan"))
                        _pb   = _smts.get("Payback Period (years)")
                        _irrs = f"{_irr*100:.2f}%" if not np.isnan(_irr) else "N/A"
                        _pbs  = f"{_pb:.2f} yr" if _pb else "Never"

                        _c1, _c2, _c3 = st.columns(3)
                        with _c1: st.markdown(mc("NPV", f"${_npv/1e6:.2f}M", "equity", "mc-neg" if _npv<0 else ""), unsafe_allow_html=True)
                        with _c2: st.markdown(mc("Equity IRR", _irrs), unsafe_allow_html=True)
                        with _c3: st.markdown(mc("Payback", _pbs, "", "mc-warn" if not _pb else ""), unsafe_allow_html=True)

                        if _mfsp:
                            _m1, _m2, _m3 = st.columns(3)
                            with _m1: st.markdown(mc("MFSP SAF",     f"${_mfsp['MFSP SAF ($/L)']*L_PER_GAL:.4f}",    "$/gal at NPV=0"), unsafe_allow_html=True)
                            with _m2: st.markdown(mc("MFSP Diesel",  f"${_mfsp['MFSP Diesel ($/L)']*L_PER_GAL:.4f}", "$/gal at NPV=0"), unsafe_allow_html=True)
                            with _m3: st.markdown(mc("MFSP Naphtha", f"${_mfsp['MFSP Naptha ($/L)']*L_PER_GAL:.4f}", "$/gal at NPV=0"), unsafe_allow_html=True)

                        _k1, _k2, _k3 = st.columns(3)
                        with _k1: st.markdown(mc("TCI", f"${_smts.get('Total Capital Investment (TCI)',0)/1e6:.2f}M"), unsafe_allow_html=True)
                        with _k2: st.markdown(mc("FCI", f"${_smts.get('Fixed Capital Investment (FCI)',0)/1e6:.2f}M"), unsafe_allow_html=True)
                        with _k3: st.markdown(mc("Year 1 Revenue", f"${_smts.get('Total Revenue ($/yr, Yr1)',0)/1e6:.2f}M"), unsafe_allow_html=True)

                        # Fuel production (Year 1) in gallons
                        _fp1, _fp2, _fp3 = st.columns(3)
                        _saf_gal = _smts.get("SAF (L/yr, Yr1)", 0) / L_PER_GAL
                        _die_gal = _smts.get("Diesel (L/yr, Yr1)", 0) / L_PER_GAL
                        _nap_gal = _smts.get("Naptha (L/yr, Yr1)", 0) / L_PER_GAL
                        with _fp1: st.markdown(mc("SAF Production", f"{_saf_gal/1e6:.2f}M gal/yr", "Year 1"), unsafe_allow_html=True)
                        with _fp2: st.markdown(mc("Diesel Production", f"{_die_gal/1e6:.2f}M gal/yr", "Year 1"), unsafe_allow_html=True)
                        with _fp3: st.markdown(mc("Naphtha Production", f"{_nap_gal/1e6:.2f}M gal/yr", "Year 1"), unsafe_allow_html=True)

                        st.markdown("<br>", unsafe_allow_html=True)

                        # Plots — called exactly as saf_MAIN_economics_FINAL.main() calls sfm.sp.plot_all
                        section("Cash Flow Plots")
                        try:
                            _figs = sfm.sp.plot_all(_sdf, _smts)
                            render_plot_all(_figs)
                        except Exception as _pe:
                            st.error(f"Plot error: {_pe}")

                        with st.expander("Cash Flow Table", expanded=False):
                            st.dataframe(_sdf, width="stretch", height=300)
                            st.download_button("Download CSV", _sdf.to_csv(index=False).encode(), "saf_cashflow.csv", "text/csv")
                    else:
                        info("Configure inputs and click <b>Run SAF Economics</b>.")

    else:
        # ──────────────────────────────────────────────────────────────────────
        # BIOENERGY ECONOMICS  (bioenergy_MAIN_economics_FINAL)
        # Step sequence exactly as main():
        #   predict_output → equipment_costs → TCI_calculation →
        #   depreciation_schedule → build_cash_flow_analysis → get_lcoe → plot_all
        # ──────────────────────────────────────────────────────────────────────
        if not BEE_AVAILABLE:
            st.error(f"bioenergy_MAIN_economics_FINAL.py could not be imported: **{BEE_ERROR}**")
        else:
            sc_res = st.session_state.get("sc_results")
            tr_res = st.session_state.get("tr_results")

            # Raw (pre-obtainability) tons — read from session_state (set by Transport auto-send).
            # Do NOT recalculate here; Transport auto-send is the single source of truth.
            # Fall back through tr_results → sc_results only if auto-send never ran.
            if st.session_state.get("be_f_tons"):
                _f_tons = st.session_state["be_f_tons"]
            elif tr_res and "forest" in tr_res:
                _f_ob_frac = float(tr_res["forest"].get("obtainability", st.session_state.get("tr_obtain_forest", 100))) / 100.0
                _f_tons = max(1, int(tr_res["forest"]["residue_kdry"] / _f_ob_frac * 1000)) if _f_ob_frac > 0 else max(1, int(tr_res["forest"]["residue_kdry"] * 1000))
            elif sc_res:
                _f_tons = max(1, int(sc_res["forest"].get("total_kdry", 0) * 1000))
            else:
                _f_tons = 100_000

            if st.session_state.get("be_m_tons") is not None:
                _m_tons = st.session_state["be_m_tons"]
            elif tr_res and "mill" in tr_res:
                _m_ob_frac = float(tr_res["mill"].get("obtainability", st.session_state.get("tr_obtain_mill", 100))) / 100.0
                _m_tons = int(tr_res["mill"]["residue_kdry"] / _m_ob_frac * 1000) if _m_ob_frac > 0 else int(tr_res["mill"]["residue_kdry"] * 1000)
            elif sc_res:
                _m_tons = int(sc_res["mill"].get("total_kdry", 0) * 1000)
            else:
                _m_tons = 80_000

            _f_cost = tr_res["forest"]["cost_odt"] if tr_res and "forest" in tr_res else 25.0
            _m_cost = tr_res["mill"]["cost_odt"]   if tr_res and "mill"   in tr_res else 20.0

            # Obtainability — prefer value stored in tr_results (persists in saved scenarios)
            _f_ob_auto = int(tr_res["forest"].get("obtainability", st.session_state.get("tr_obtain_forest", 100))) if tr_res and "forest" in tr_res else int(st.session_state.get("tr_obtain_forest", 100))
            _m_ob_auto = int(tr_res["mill"].get("obtainability",   st.session_state.get("tr_obtain_mill",   100))) if tr_res and "mill"   in tr_res else int(st.session_state.get("tr_obtain_mill",   100))

            # Effective tonnage for display only
            _f_eff_disp = int(_f_tons * _f_ob_auto / 100)
            _m_eff_disp = int(_m_tons * _m_ob_auto / 100)

            # ── Raw / obtain passthrough — not editable in this tab ──────────
            # be_f_tons / be_m_tons: Transport auto-send is the single source of truth;
            # only write here if they were derived from fallback (auto-send never ran).
            be_f_tons   = _f_tons
            be_m_tons   = _m_tons
            be_f_obtain = _f_ob_auto
            be_m_obtain = _m_ob_auto
            if not st.session_state.get("tr_sent_to_econ"):
                st.session_state["be_f_tons"] = be_f_tons
                st.session_state["be_m_tons"] = be_m_tons
            st.session_state["be_f_obtain"] = be_f_obtain
            st.session_state["be_m_obtain"] = be_m_obtain

            col_header("Bioenergy Inputs")
            if sc_res and tr_res:
                info(
                    f"<b>Effective Throughput</b> (Obtainability Applied From Transport Tab — "
                    f"Forest {_f_ob_auto}%  Mill {_m_ob_auto}%):<br>"
                    f"Forest <b>{round(_f_eff_disp*METRIC_TON_TO_US_TON,2):,} US ton/yr</b>  |  "
                    f"Mill <b>{round(_m_eff_disp*METRIC_TON_TO_US_TON,2):,} US ton/yr</b>"
                )

            # ── 4 input columns across the top ───────────────────────────────
            _bc1, _bc2, _bc3, _bc4 = st.columns(4, gap="medium")

            with _bc1:
                section("Feedstock")
                st.markdown(
                    f'<div style="margin-bottom:6px">'
                    f'<div style="font-size:0.9rem;color:#8a9ab0;margin-bottom:2px">Effective Forest Residue (US ton/yr)</div>'
                    f'<div style="font-size:1.05rem;font-weight:700;color:#c9d1e0;'
                    f'background:#0e1621;border:1px solid #1e2d3d;border-radius:6px;'
                    f'padding:8px 12px;letter-spacing:0.02em">'
                    f'{round(_f_eff_disp*METRIC_TON_TO_US_TON,2):,}'
                    f'<span style="font-size:0.9rem;font-weight:400;color:#4a6a8a;margin-left:8px">'
                    f'{round(_f_tons*METRIC_TON_TO_US_TON,2):,} raw × {_f_ob_auto}%</span></div></div>',
                    unsafe_allow_html=True
                )
                st.markdown(
                    f'<div style="margin-bottom:10px">'
                    f'<div style="font-size:0.9rem;color:#8a9ab0;margin-bottom:2px">Effective Mill Residue (US ton/yr)</div>'
                    f'<div style="font-size:1.05rem;font-weight:700;color:#c9d1e0;'
                    f'background:#0e1621;border:1px solid #1e2d3d;border-radius:6px;'
                    f'padding:8px 12px;letter-spacing:0.02em">'
                    f'{round(_m_eff_disp*METRIC_TON_TO_US_TON,2):,}'
                    f'<span style="font-size:0.9rem;font-weight:400;color:#4a6a8a;margin-left:8px">'
                    f'{round(_m_tons*METRIC_TON_TO_US_TON,2):,} raw × {_m_ob_auto}%</span></div></div>',
                    unsafe_allow_html=True
                )
                st.markdown(
                    f'<div style="margin-bottom:10px">'
                    f'<div style="font-size:0.9rem;color:#8a9ab0;margin-bottom:2px">Forest Cost ($/US ton)</div>'
                    f'<div style="font-size:1.05rem;font-weight:700;color:#c9d1e0;'
                    f'background:#0e1621;border:1px solid #1e2d3d;border-radius:6px;'
                    f'padding:8px 12px;letter-spacing:0.02em">'
                    f'{st.session_state["be_f_cost"]:,}',
                    unsafe_allow_html=True
                )
                st.markdown(
                    f'<div style="margin-bottom:10px">'
                    f'<div style="font-size:0.9rem;color:#8a9ab0;margin-bottom:2px">Mill Cost ($/US ton)</div>'
                    f'<div style="font-size:1.05rem;font-weight:700;color:#c9d1e0;'
                    f'background:#0e1621;border:1px solid #1e2d3d;border-radius:6px;'
                    f'padding:8px 12px;letter-spacing:0.02em">'
                    f'{st.session_state["be_m_cost"]:,}',
                    unsafe_allow_html=True
                )
                be_elec_price = st.slider("Electricity Price ($/MWh)", 50.0, 300.0, 166.0, 1.0, key="be_elec_price")

            with _bc2:
                section("Finance")
                be_cepci     = st.number_input("Analysis Year", 2006, 2030, 2030, 1, key="be_cepci")
                be_life      = st.number_input("Lifespan (yr)", 10, 50, 30, 1, key="be_life")
                be_degr      = st.number_input("Degradation (%/yr)", 0.0, 5.0, 0.5, 0.05, format="%.2f", key="be_degr") / 100
                be_disc      = st.number_input("Real Discount Rate (%)", 0.0, 30.0, 7.0, 0.5, format="%.1f", key="be_disc") / 100
                be_infl      = st.number_input("Inflation (%)", 0.0, 20.0, 2.5, 0.1, format="%.1f", key="be_infl") / 100
                be_debt      = st.number_input("Debt Fraction (%)", 0, 100, 60, 5, key="be_debt") / 100
                be_loan_r    = st.number_input("Loan Rate (%)", 0.0, 20.0, 6.5, 0.5, format="%.1f", key="be_loan_r") / 100
                be_loan_term = st.number_input("Loan Term (yr)", 5, 30, 15, 1, key="be_loan_term")

            with _bc3:
                section("Escalation")
                be_elec_esc = st.number_input("Electricity Escalation (%/yr)", 0.0, 10.0, 1.0, 0.1, format="%.1f", key="be_eesc") / 100
                be_fuel_esc = st.number_input("Fuel Escalation (%/yr)",        0.0, 10.0, 2.5, 0.1, format="%.1f", key="be_fesc") / 100
                be_fom_esc  = st.number_input("Fixed OM Escalation (%/yr)",    0.0, 10.0, 2.5, 0.1, format="%.1f", key="be_fomesc") / 100
                be_vom_esc  = st.number_input("Variable OM Escalation (%/yr)", 0.0, 10.0, 2.0, 0.1, format="%.1f", key="be_vomesc") / 100

            with _bc4:
                section("Tax")
                be_fed_tax = st.number_input("Federal Tax (%)", 0, 50, 21, 1, key="be_fed") / 100
                be_st_tax  = st.number_input("State Tax (%)",   0, 20,  7, 1, key="be_st")  / 100

            # Run button full-width below inputs
            run_be = st.button("Run Bioenergy Economics", type="primary",
                               width="stretch", key="run_be_btn")
            st.markdown("<hr style='border-color:#1e2d3d;margin:4px 0'>", unsafe_allow_html=True)

            col_header("Bioenergy Results")
            with st.container():
                if True:
                    # ── Electricity generation chart in results area ──────────
                    _be_elec_df = st.session_state.get("be_df")
                    if _be_elec_df is not None and "Annual Generation (GWh)" in _be_elec_df.columns:
                        try:
                            _eg_fig, _eg_ax = plt.subplots(figsize=(7, 3))
                            _eg_fig.patch.set_facecolor("#0e1621")
                            _eg_ax.set_facecolor("#131e2d")
                            _yrs = _be_elec_df["Year"].values
                            _gen = _be_elec_df["Annual Generation (GWh)"].values
                            _eg_ax.plot(_yrs, _gen, color="#1D9E75", linewidth=2, label="Annual Generation (GWh)")
                            if "Cumulative Output Loss (%)" in _be_elec_df.columns:
                                _eg2 = _eg_ax.twinx()
                                _eg2.plot(_yrs, _be_elec_df["Cumulative Output Loss (%)"].values,
                                          color="#e76f51", linewidth=1.5, linestyle="--",
                                          label="Output Loss (%)")
                                _eg2.set_ylabel("Cumulative Output Loss (%)", fontsize=8, color="#e76f51")
                                _eg2.tick_params(colors="#e76f51")
                                _eg2.spines[["top"]].set_visible(False)
                                _eg2.spines[["right"]].set_color("#e76f51")
                            _eg_ax.set_xlabel("Year", fontsize=9, color="#c8d8e8")
                            _eg_ax.set_ylabel("Annual Generation (GWh)", fontsize=9, color="#c8d8e8")
                            _eg_ax.set_title("Electricity Generation Over Time",
                                             fontsize=10, fontweight="bold", color="#e8f0f8")
                            _eg_ax.spines[["top","right"]].set_visible(False)
                            _eg_ax.spines[["left","bottom"]].set_color("#2a3a4a")
                            _eg_ax.tick_params(colors="#c8d8e8")
                            _eg_ax.grid(axis="y", color="#1e2d3d", linewidth=0.7)
                            lines1, labs1 = _eg_ax.get_legend_handles_labels()
                            if "Cumulative Output Loss (%)" in _be_elec_df.columns:
                                lines2, labs2 = _eg2.get_legend_handles_labels()
                                _eg_ax.legend(lines1+lines2, labs1+labs2,
                                              fontsize=8, facecolor="#0e1621",
                                              edgecolor="#2a3a4a", labelcolor="#c8d8e8",
                                              loc="upper right")
                            else:
                                _eg_ax.legend(fontsize=8, facecolor="#0e1621",
                                              edgecolor="#2a3a4a", labelcolor="#c8d8e8")
                            plt.tight_layout()
                            render_pyplot_safe(_eg_fig)
                        except Exception as _ege:
                            st.caption(f"Generation chart: {_ege}")
                    if True:  # keep subsequent results block indentation

                        def _run_be_cashflow():
                            """
                            Call bem.build_cash_flow_analysis exactly as
                            bioenergy_MAIN_economics_FINAL.main() does.
                            Uses cached TCI/FCI/dep/annual_AC from session_state.
                            """
                            return bem.build_cash_flow_analysis(
                                TCI                          = st.session_state["be_TCI"],
                                FCI                          = st.session_state["be_FCI"],
                                annual_depreciation_schedule = st.session_state["be_annual_dep"],
                                annual_AC_year1              = st.session_state["be_annual_AC"],
                                # Effective tons for fuel cost calculation (raw tons × obtainability)
                                forest_annual_tons           = be_f_tons * be_f_obtain / 100,
                                mill_annual_tons             = be_m_tons * be_m_obtain / 100,
                                degradation_factor           = be_degr,
                                capacity_factor              = BE_CAPACITY_FACTOR,
                                Plant_Lifespan               = be_life,
                                c_fuel_per_ton_forest        = st.session_state["be_f_cost"],
                                c_fuel_per_ton_mill          = st.session_state["be_m_cost"],
                                electricity_price            = be_elec_price,
                                real_discount_rate           = be_disc,
                                inflation_rate               = be_infl,
                                debt_fraction                = be_debt,
                                loan_rate                    = be_loan_r,
                                loan_term                    = be_loan_term,
                                electricity_escalation       = be_elec_esc,
                                fuel_escalation              = be_fuel_esc,
                                fixed_om_escalation          = be_fom_esc,
                                var_om_escalation            = be_vom_esc,
                                federal_tax_rate             = be_fed_tax,
                                state_tax_rate               = be_st_tax,
                                verbose                      = False,
                            )

                        if run_be:
                            with st.spinner("Running equipment sizing and bioenergy cash flow..."):
                                try:
                                    # Step 1: predict_output (from bem, calls bioenergyproduction_FINAL)
                                    # Raw tons + obtainability — model applies the reduction internally.
                                    _annual_AC = bem.predict_output(
                                        be_f_tons, be_m_tons, be_f_obtain, be_m_obtain)

                                    # Step 2: equipment_costs (from bioenergy_costs_FINAL via bem)
                                    # biomass_daily = (forest + mill) / 365, exactly as main()
                                    _biomass_daily = (be_f_tons + be_m_tons) / 365
                                    _EC, _stoker, _fuel_eq, _turbine, _EC_list = bem.equipment_costs(
                                        _biomass_daily, be_cepci)

                                    # Step 3: TCI_calculation
                                    _TCI, _FCI, _breakdown = bem.TCI_calculation(_EC, _EC_list)

                                    # Step 4: depreciation_schedule
                                    _dep = bem.depreciation_schedule(_breakdown, _EC_list, max_years=be_life)

                                    # Cache heavy results — slider changes only re-run step 5
                                    st.session_state.update({
                                        "be_equip_done": True,
                                        "be_annual_AC":  _annual_AC,
                                        "be_EC":  _EC, "be_stoker": _stoker,
                                        "be_fuel_eq": _fuel_eq, "be_turbine": _turbine,
                                        "be_EC_list": _EC_list,
                                        "be_TCI": _TCI, "be_FCI": _FCI,
                                        "be_breakdown": _breakdown,
                                        "be_annual_dep": _dep,
                                    })

                                    # Step 5: build_cash_flow_analysis
                                    _df, _mets = _run_be_cashflow()
                                    st.session_state["be_df"]      = _df
                                    st.session_state["be_metrics"] = _mets
                                    # Snapshot all BE inputs for PDF report
                                    st.session_state["_snap_be_inputs"] = {
                                        "in_be_cepci":      be_cepci,
                                        "in_be_life":       be_life,
                                        "in_be_disc":       be_disc    * 100,
                                        "in_be_infl":       be_infl    * 100,
                                        "in_be_debt":       be_debt    * 100,
                                        "in_be_loan_r":     be_loan_r  * 100,
                                        "in_be_loan_term":  be_loan_term,
                                        "in_be_degr":       be_degr    * 100,
                                        "in_be_elec_price": be_elec_price,
                                        "in_be_f_cost":     st.session_state["be_f_cost"],
                                        "in_be_m_cost":     st.session_state["be_m_cost"],
                                        "in_be_eesc":       be_elec_esc* 100,
                                        "in_be_fesc":       be_fuel_esc* 100,
                                        "in_be_fomesc":     be_fom_esc * 100,
                                        "in_be_vomesc":     be_vom_esc * 100,
                                        "in_be_fed":        be_fed_tax * 100,
                                        "in_be_st":         be_st_tax  * 100,
                                    }

                                    # Step 6: get_lcoe (exactly as main() does)
                                    try:
                                        _lcoe = bem.get_lcoe(
                                            TCI=_TCI, FCI=_FCI,
                                            annual_depreciation_schedule=_dep,
                                            annual_AC_year1=_annual_AC,
                                            # Effective tons for fuel cost calculation (raw tons × obtainability)
                                            forest_annual_tons=be_f_tons * be_f_obtain / 100,
                                            mill_annual_tons=be_m_tons * be_m_obtain / 100,
                                            degradation_factor=be_degr,
                                            capacity_factor=BE_CAPACITY_FACTOR,
                                            Plant_Lifespan=be_life,
                                            c_fuel_per_ton_forest=st.session_state["be_f_cost"],
                                            c_fuel_per_ton_mill=st.session_state["be_m_cost"],
                                            electricity_price=be_elec_price,
                                            real_discount_rate=be_disc,
                                            inflation_rate=be_infl,
                                            debt_fraction=be_debt,
                                            loan_rate=be_loan_r,
                                            loan_term=be_loan_term,
                                            electricity_escalation=be_elec_esc,
                                            fuel_escalation=be_fuel_esc,
                                            fixed_om_escalation=be_fom_esc,
                                            var_om_escalation=be_vom_esc,
                                            federal_tax_rate=be_fed_tax,
                                            state_tax_rate=be_st_tax,
                                            verbose=False,
                                        )
                                        st.session_state["be_lcoe"] = _lcoe
                                    except Exception:
                                        st.session_state["be_lcoe"] = None

                                    # Step 7: Jobs — exactly as bioenergy_MAIN_economics_FINAL.main() does:
                                    #   bio_out = Jobscreation_model.jobs_from_biopower("Bioenergy Plant", df['Revenue'][1])
                                    #   Jobscreation_model.plot_job_breakdown(bio_out, ...)
                                    if JOBS_AVAILABLE:
                                        _jout = jm.jobs_from_biopower("Bioenergy Plant", _df["Revenue"][1])
                                        jm.plot_job_breakdown(_jout, title="Bioenergy Plant Jobs Analysis")
                                        st.session_state["jobs_result"] = _jout

                                except Exception as _e:
                                    st.error(f"Bioenergy analysis failed: {_e}")
                                    import traceback; st.code(traceback.format_exc())

                        elif st.session_state.get("be_equip_done") and st.session_state.get("be_df") is None:
                            # Only re-run if results aren't already cached
                            try:
                                _df, _mets = _run_be_cashflow()
                                st.session_state["be_df"]      = _df
                                st.session_state["be_metrics"] = _mets
                            except Exception:
                                pass

                        _bdf  = st.session_state.get("be_df")
                        _bmts = st.session_state.get("be_metrics")
                        _blcoe = st.session_state.get("be_lcoe")

                        if _bdf is not None and _bmts is not None:
                            _npv  = _bmts.get("NPV (Equity, Nominal)", 0)
                            _irr  = _bmts.get("Equity IRR", float("nan"))
                            _pb   = _bmts.get("Payback Period (years)")
                            _irrs = f"{_irr*100:.2f}%" if not np.isnan(_irr) else "N/A"
                            _pbs  = f"{_pb:.2f} yr" if _pb else "Never"
                            _cap  = _bmts.get("Plant Capacity (MW)", 0)

                            _c1,_c2,_c3,_c4,_c5 = st.columns(5)
                            with _c1: st.markdown(mc("NPV", f"${_npv/1e6:.2f}M", "", "mc-neg" if _npv<0 else ""), unsafe_allow_html=True)
                            with _c2: st.markdown(mc("Equity IRR", _irrs), unsafe_allow_html=True)
                            with _c3: st.markdown(mc("Payback", _pbs, "", "mc-warn" if not _pb else ""), unsafe_allow_html=True)
                            with _c4: st.markdown(mc("Plant Capacity", f"{_cap:.2f} MW"), unsafe_allow_html=True)
                            with _c5:
                                if _blcoe:
                                    _lv = _blcoe if isinstance(_blcoe, (int,float)) else _blcoe.get("LCOE ($/MWh)", 0)
                                    st.markdown(mc("LCOE", f"${_lv:.2f}", "$/MWh"), unsafe_allow_html=True)

                            _k1,_k2,_k3,_k4 = st.columns(4)
                            with _k1: st.markdown(mc("TCI", f"${st.session_state['be_TCI']/1e6:.2f}M"), unsafe_allow_html=True)
                            with _k2: st.markdown(mc("FCI", f"${st.session_state['be_FCI']/1e6:.2f}M"), unsafe_allow_html=True)
                            with _k3: st.markdown(mc("Equipment", f"${st.session_state['be_EC']/1e6:.2f}M"), unsafe_allow_html=True)
                            with _k4: st.markdown(mc("Ann. AC Yr1", f"{st.session_state['be_annual_AC']/1e6:.2f} GWh"), unsafe_allow_html=True)

                            st.markdown("<br>", unsafe_allow_html=True)
                        else:
                            info("Configure inputs and click <b>Run Bioenergy Economics</b>.")

                # ── Full-width plots below the two-panel section ───────────────────
                # Rendered outside _be_left / _be_right so they span the full page.
                _bdf2  = st.session_state.get("be_df")
                _bmts2 = st.session_state.get("be_metrics")
                if _bdf2 is not None and _bmts2 is not None:
                    st.markdown("<hr style='border-color:#1e2d3d;margin:8px 0'>",
                                unsafe_allow_html=True)
                    section("Cash Flow Plots")
                    try:
                        _figs2 = bem.plot_all(_bdf2, _bmts2)
                        # Filter out the Net Income plot — not needed in dashboard
                        if isinstance(_figs2, dict):
                            _figs2 = {k: v for k, v in _figs2.items()
                                      if "net income" not in k.lower() and "income" not in k.lower()}
                        render_plot_all(_figs2)
                    except Exception as _pe2:
                        st.error(f"Plot error: {_pe2}")
                    with st.expander("Cash Flow Table", expanded=False):
                        st.dataframe(_bdf2, width="stretch", height=300)
                        st.download_button("Download CSV",
                                           _bdf2.to_csv(index=False).encode(),
                                           "bioenergy_cashflow.csv", "text/csv")

with tab_impact:
    col_header("Impact")
    os.makedirs(os.path.join(_DIR, "LCA_plots"), exist_ok=True)

    # ── Import LCA modules (graceful fail if LCA_dependencies/ not present) ───
    _lca_ok = True
    try:
        from LCA_dependencies.SAF_production_LCA        import calc as _saf_calc
        from LCA_dependencies.SAF_production_LCA        import INPUTS as _SAF_INPUTS
        from LCA_dependencies.Bioenergy_production_LCA  import calculate_one_option as _bio_calc
        from LCA_dependencies.Biomass_transport_LCA     import phase2_transport as _trans_calc
        from LCA_dependencies.Biomass_processing_LCA import calculate_one as _proc_calc
        # Avoided Emissions Analysis — dark dashboard theme
        def _fhr_plot(lc, baselines, outdir):
            os.makedirs(outdir, exist_ok=True)
            import matplotlib.patches as __fp  # moved here so it's always in scope
            # Colours matching dashboard palette
            _CB = "#e76f51"   # burnt orange — open burning
            _CF = "#378ADD"   # blue         — fossil fuel (all liquid co-products)

            # Baseline (a): avoided vs open pile burning — full lifecycle vs full burn
            _avb = baselines["open_burn"] - lc["combined"]
            _pb  = _avb / baselines["open_burn"] * 100 if baselines["open_burn"] else 0

            if IS_SAF:
                # Baseline (b): same MJ of SAF produced from petroleum instead.
                # Compare against full project lifecycle GHG (all sources, all phases).
                _avj = baselines["fossil_jf"] - lc["combined"]
                _pj  = _avj / baselines["fossil_jf"] * 100 if baselines["fossil_jf"] else 0
                _vals = [_avb, _avj]
                _cols = [_CB, _CF]
                _lbls = [
                    "Avoided vs\nOpen Burning\n(all residue, all pathways)",
                    "Avoided vs\nFossil Jet Fuel\n(same MJ SAF, production phase)",
                ]
                _pcts = [_pb, _pj]
                _leg_handles_extra = [
                    __fp.Patch(color=_CF, label="Avoided vs fossil JF  ({:.1f}% reduction)".format(_pj)),
                ]
                _footer = ("Open burning EF: 0.143 kg CO₂e/kg OD [Khatri 2025]  |  "
                           "Fossil JF CI: 15.93 g CO₂e/MJ cradle-to-gate [CA-GREET4.0]  |  "
                           "SAF LHV from SAF_production_LCA.INPUTS [GREET]")
                _footer = ("Open burning EF: 0.143 kg CO₂e/kg OD [Khatri 2025]  |  "
                           "Fossil fuel CI: 15.93 g CO₂e/MJ [CA-GREET4.0] × total liquid energy "
                           "(SAF + diesel + naphtha, all at 43.8 MJ/kg [SAF_production_LCA.INPUTS])")
            else:
                # Bioenergy: one bar — open burning comparison only
                # Fossil fuel displacement not applicable (electricity, not jet fuel)
                _vals = [_avb]
                _cols = [_CB]
                _lbls = ["Avoided vs\nOpen Burning\n(all residue, all pathways)"]
                _pcts = [_pb]
                _leg_handles_extra = []
                _footer = "Open burning EF: 0.143 kg CO₂e/kg OD [Khatri 2025]"

            # Figure — dark background matching dashboard
            fig, ax = plt.subplots(figsize=(11, 8))
            fig.patch.set_facecolor("#0e1621")
            ax.set_facecolor("#131e2d")
            _mx = max(_vals) if max(_vals) > 0 else 1
            # extend y-axis so value labels clear the bars
            ax.set_ylim(0, _mx * 1.35)
            _bar_x = list(range(len(_vals)))
            _bars = ax.bar(_bar_x, _vals, color=_cols, width=0.42,
                           edgecolor="#0e1621", linewidth=1.2, zorder=3)
            for b, v, p in zip(_bars, _vals, _pcts):
                ax.text(b.get_x() + b.get_width()/2, v + _mx*0.04,
                        "{:,.0f}\n({:.1f}% reduction)".format(v, p),
                        ha="center", va="bottom", fontsize=15, fontweight="bold",
                        color="#f0f4f8")
            ax.set_xticks(_bar_x)
            ax.set_xticklabels(_lbls, fontsize=15, color="#c8d8e8")
            ax.set_ylabel("Avoided GHG Emissions (t CO₂e / yr)", fontsize=16,
                          color="#c8d8e8")
            # Title on figure level to avoid overlapping the axes
            fig.suptitle("Avoided Emissions Analysis — Lifecycle GHG vs Baselines",
                fontsize=17, fontweight="bold", color="#e8f0f8", y=1.02)
            ax.set_title(
                "Non-biogenic GHG only  |  GWP100 IPCC AR6  |  [Khatri 2025; CA-GREET4.0]",
                fontsize=14, color="#a0b4c8", pad=10)
            ax.spines[["top","right"]].set_visible(False)
            ax.spines[["left","bottom"]].set_color("#2a3a4a")
            ax.tick_params(colors="#c8d8e8", labelsize=14)
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,_: "{:,.0f}".format(v)))
            ax.grid(axis="y", color="#1e2d3d", linewidth=0.8, zorder=0)
            # Legend
            _leg_handles = [
                __fp.Patch(color=_CB, label="Avoided vs open burning  ({:.1f}% reduction)".format(_pb)),
            ] + _leg_handles_extra
            ax.legend(handles=_leg_handles, fontsize=14, facecolor="#0e1621", edgecolor="#2a3a4a",
                      labelcolor="#c8d8e8", loc="upper right")
            # Annotation footer
            fig.text(0.5, -0.02, _footer,
                ha="center", fontsize=12, color="#6b8cad", style="italic")
            plt.tight_layout(rect=[0, 0.04, 1, 0.97])
            plt.savefig(os.path.join(outdir, "fhr_net_climate_impact.png"),
                        dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
            plt.close(fig)
        _fhr_ok = True
    except ImportError as _lca_err:
        _lca_ok = False
        _fhr_ok = False
        st.error(
            f"LCA modules could not be imported: **{_lca_err}**  \n\n"
            "Place all LCA scripts inside a **LCA_dependencies/** subfolder "
            "next to dashboard.py and add an empty `__init__.py`.  "
            "Place **forest_health_report.py** inside the **LCA_dependencies/** subfolder "
            "(alongside its sub-modules: LCA_Transport_Only.py, SAF_production_v2.py, etc.)."
        )

    # ══════════════════════════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════════════════════
    if _lca_ok:

        # ── Auto-fill biomass from Supply Chain + Transport ───────────────────
        _sc_res = st.session_state.get("sc_results")
        _tr_res = st.session_state.get("tr_results")

        # Total residue in odt/yr (k metric dry t → dry t; 1 metric t ≈ 1.10231 short t)
        # Use metric tonnes directly — all LCA modules use ODT as "odt" loosely
        _auto_total_odt = 0
        _auto_hq_odt    = 0
        # _auto_dist  = 161.0
        _auto_dist  = 100.0
        _f_kdry = _m_kdry = _pw_kdry = 0  # initialized here; overwritten below if data available

        if _tr_res:
            # Use post-obtainability residue from tr_results (same as economics tab L1384-1386)
            _f_kdry  = _tr_res.get("forest",   {}).get("residue_kdry", 0)
            _m_kdry  = _tr_res.get("mill",     {}).get("residue_kdry", 0)
            _pw_kdry = _tr_res.get("pulpwood", {}).get("residue_kdry", 0)
            _auto_total_odt = (_f_kdry + _m_kdry + _pw_kdry) * 1000   # k-odt → odt (post-obtainability)
            _auto_hq_odt    = _f_kdry * 1000  # HQ = forest residue after obtainability
        elif _sc_res:
            # Fallback to sc_results (pre-obtainability) if transport tab not yet run
            _f_kdry  = _sc_res["forest"].get("total_kdry", 0)
            _m_kdry  = _sc_res["mill"].get("total_kdry", 0)
            _pw_kdry = _sc_res.get("pulpwood", {}).get("total_kdry", 0)
            _auto_total_odt = (_f_kdry + _m_kdry + _pw_kdry) * 1000
            _auto_hq_odt    = _sc_res["forest"].get("hq_kdry", _f_kdry * HQ_FRACTION) * 1000

        if _tr_res:
            _f_d  = _tr_res.get("forest",   {}).get("dist_mi")
            _m_d  = _tr_res.get("mill",     {}).get("dist_mi")
            _pw_d = _tr_res.get("pulpwood", {}).get("dist_mi")
            if _f_d: _auto_dist_saf = round(_f_d * KM_PER_MILE, 1)   # forest → SAF plant (km)
            # Per-source distances for bioenergy transport (km); default to forest dist if missing
            _auto_dist_f  = round(_f_d  * KM_PER_MILE, 1) if _f_d  else _auto_dist
            _auto_dist_m  = round(_m_d  * KM_PER_MILE, 1) if _m_d  else _auto_dist
            _auto_dist_pw = round(_pw_d * KM_PER_MILE, 1) if _pw_d else _auto_dist
        else:
            _auto_dist_f  = _auto_dist
            _auto_dist_m  = _auto_dist
            _auto_dist_pw = _auto_dist
        # Display in miles
        # _auto_dist_saf_mi   = round(_auto_dist_saf / KM_PER_MILE, 1)
        _auto_dist_f_mi = round(_auto_dist_f  / KM_PER_MILE, 1)
        _auto_dist_m_mi = round(_auto_dist_m  / KM_PER_MILE, 1)
        _auto_dist_pw_mi= round(_auto_dist_pw / KM_PER_MILE, 1)

        # ── AUTO-FILLED VALUES (computed before layout) ─────────────────────
        _auto_tr = st.session_state.get("tr_results")
        _auto_sc = st.session_state.get("sc_results")
        _auto_saf_mfsp = st.session_state.get("saf_mfsp")

        _auto_total_odt_use  = max(int(_auto_total_odt), 1)
        _auto_hq_odt_use     = int(_auto_hq_odt) if _auto_hq_odt > 0 else int(_auto_total_odt_use * HQ_FRACTION)
        _auto_hq_frac_use    = _auto_hq_odt_use / _auto_total_odt_use if _auto_total_odt_use > 0 else HQ_FRACTION

        _auto_saf_L   = 12_000_000
        _auto_die_L   = 5_617_977
        _auto_nap_L   = 5_333_333
        _fuel_vol_source = None   # will be set to describe where volumes came from
        if IS_SAF:
            if _auto_saf_mfsp:
                _df_mfsp = _auto_saf_mfsp.get("df at MFSP")
                if _df_mfsp is not None and len(_df_mfsp) > 1:
                    _auto_saf_L = int(_df_mfsp["Annual SAF Generation (L/yr)"].iloc[1])
                    _auto_die_L = int(_df_mfsp["Annual Biodiesel Generation (L/yr)"].iloc[1])
                    _auto_nap_L = int(_df_mfsp["Annual Naptha Generation (L/yr)"].iloc[1])
                    _fuel_vol_source = "SAF Economics (MFSP solve)"
            if _fuel_vol_source is None and st.session_state.get("saf_metrics"):
                _sm = st.session_state["saf_metrics"]
                _v_saf = _sm.get("SAF (L/yr, Yr1)")
                _v_die = _sm.get("Diesel (L/yr, Yr1)")
                _v_nap = _sm.get("Naptha (L/yr, Yr1)")
                if _v_saf and _v_die and _v_nap:
                    _auto_saf_L = int(_v_saf)
                    _auto_die_L = int(_v_die)
                    _auto_nap_L = int(_v_nap)
                    _fuel_vol_source = "SAF Economics (cash flow)"
        _auto_tr_opt_saf = st.session_state.get("tr_opt_forest", "1.1") if IS_SAF else "1.1"
        _auto_tr_opt_bio = st.session_state.get("tr_opt_forest", "2.1") if not IS_SAF else "2.1"
        _auto_tr_opt_mill = st.session_state.get("tr_opt_mill", "3.1")
        _auto_tr_opt_pulpwood = st.session_state.get("tr_opt_pulpwood", "3.1")

        # Per-source truck payloads derived from the transport type of the selected option.
        # Each option defines a "transport" key (e.g. "chips", "logs", "hog_fuel") which maps
        # to a _FEEDSTOCK entry whose index [3] is the payload in ODMT → convert to OD kg.
        def _payload_for_option(option_id: str, default_odmt: float = 18.3) -> int:
            try:
                transport_key = bt._OPTIONS[option_id]["transport"]
                odmt = bt._FEEDSTOCK[transport_key][3]
            except Exception:
                odmt = default_odmt
            return int(odmt * 1000)

        _active_forest_opt   = st.session_state.get("tr_opt_forest",   "1.1")
        _active_mill_opt     = st.session_state.get("tr_opt_mill",     "3.1")
        _active_pulpwood_opt = st.session_state.get("tr_opt_pulpwood", "4.1")
        _bt_payload_forest   = _payload_for_option(_active_forest_opt)
        _bt_payload_mill     = _payload_for_option(_active_mill_opt,   default_odmt=14.5)
        _bt_payload_pulpwood = _payload_for_option(_active_pulpwood_opt)
        # Representative payload for the single-payload display widget:
        # SAF mode → forest (HQ) drives the majority of tonnage; bio mode → forest too.
        _bt_payload = _bt_payload_forest

        col_header("LCA Inputs")

        # ── Auto-fill info banner ─────────────────────────────────────────────
        _sc_lca = st.session_state.get("sc_results")
        _tr_lca = st.session_state.get("tr_results")
        if _sc_lca:
            # Show the post-obtainability values actually passed to the model (_auto_* variables),
            # not the SC base tons. Pull obtainability from tr_results for display.
            _f_ob_disp  = _tr_lca.get("forest",   {}).get("obtainability", 100) if _tr_lca else 100
            _m_ob_disp  = _tr_lca.get("mill",     {}).get("obtainability", 100) if _tr_lca else 100
            _pw_ob_disp = _tr_lca.get("pulpwood", {}).get("obtainability", 100) if _tr_lca else 100
            _f_opt  = _tr_lca.get("forest",   {}).get("option", "—") if _tr_lca else "—"
            _m_opt  = _tr_lca.get("mill",     {}).get("option", "—") if _tr_lca else "—"
            _pw_opt = _tr_lca.get("pulpwood", {}).get("option", "—") if _tr_lca else "—"
            # Effective (post-obtainability) odt values for display — same as what model receives
            _f_eff_disp  = _f_kdry  * 1000  # _f_kdry already post-obtainability from tr_results branch
            _m_eff_disp  = _m_kdry  * 1000
            _pw_eff_disp = _pw_kdry * 1000
            _source = "Transport tab (post-obtainability)" if _tr_lca else "Supply Chain (pre-obtainability fallback)"
            info(
                    f"<b>Auto-Filled from {_source}:</b>  "
                    f"Forest{'(HQ)' if IS_SAF else ''}: <b>{_f_eff_disp*METRIC_TON_TO_US_TON:,.0f} US ton/yr</b> "
                    f"({_f_ob_disp}% obtainability, Opt {_f_opt})  |  "
                    f"Mill: <b>{_m_eff_disp*METRIC_TON_TO_US_TON:,.0f} US ton/yr</b> "
                    f"({_m_ob_disp}% obtainability, Opt {_m_opt})"
                    + (f"  |  Pulpwood: <b>{_pw_eff_disp*METRIC_TON_TO_US_TON:,.0f} US ton/yr</b> "
                    f"({_pw_ob_disp}% obtainability, Opt {_pw_opt})" if IS_SAF else "")
                    + (
                        f"<br>SAF: <b>{_auto_saf_L/L_PER_GAL/1e6:.2f}M</b>  "
                        f"Diesel: <b>{_auto_die_L/L_PER_GAL/1e6:.2f}M</b>  "
                        f"Naphtha: <b>{_auto_nap_L/L_PER_GAL/1e6:.2f}M gal/yr</b>"
                        f"  <i>(from {_fuel_vol_source})</i>"
                        if IS_SAF else ""
                    )
                    + f"<br>Haul distances — "
                    f"Forest: <b>{_auto_dist_f_mi:.0f} mi</b>  "
                    f"Mill: <b>{_auto_dist_m_mi:.0f} mi</b>"
                    + (f"  |  Pulpwood: <b>{_auto_dist_pw_mi:.0f} mi</b>" if IS_SAF else "")
                )
            if IS_SAF and _fuel_vol_source is None:
                warn(
                    "<b>SAF Economics not yet run.</b> Fuel volumes are module defaults "
                    f"(SAF {_auto_saf_L/L_PER_GAL/1e6:.2f}M gal/yr, calibrated for ~100k ODT). "
                    "Run the <b>SAF Economics tab</b> first so LCA uses production volumes "
                    "matched to your actual biomass supply."
                )


        # ── Inputs: col 1 = Feedstock + Truck stacked; cols 2–5 = one section each
        _lc1, _lc2, _lc3, _lc4, _lc5 = st.columns(5, gap="medium")

        with _lc1:
            section("Feedstock")
            lca_moisture = st.slider(
                "Moisture Content (%)", 0, 80, 40, 1, key="lca_moisture",
                help="Wet-basis moisture entering the bioenergy boiler")
            section("Truck Parameters")
            # Payloads derived from selected transport option per source — not user inputs
            lca_payload_kg          = _bt_payload_forest
            lca_payload_kg_mill     = _bt_payload_mill
            lca_payload_kg_pulpwood = _bt_payload_pulpwood
            # st.caption(
            #     f"Truck Payload (OD kg/load) by source:  \n"
            #     f"**Forest** ({_active_forest_opt}): {lca_payload_kg:,}  \n"
            #     f"**Mill** ({_active_mill_opt}): {lca_payload_kg_mill:,}  \n"
            #     f"**Pulpwood** ({_active_pulpwood_opt}): {lca_payload_kg_pulpwood:,}"
            # )
            kg_to_metric_ton = 1/1000
            st.caption(
                f"Truck Payload (OD kg/load) by source:  \n"
                f"**Forest** ({_active_forest_opt}): {lca_payload_kg:,}  \n"
                f"**Mill** ({_active_mill_opt}): {lca_payload_kg_mill:,}"
                + (f"  \n**Pulpwood** ({_active_pulpwood_opt}): {lca_payload_kg_pulpwood:,}" if IS_SAF else "")
            )
            lca_truck_l_mi = st.number_input(
                "Truck Fuel Economy (L/mi)", 0.1, 3.0,
                round(0.35 * KM_PER_MILE, 3), 0.01,
                format="%.3f", key="lca_truck_l_mi",
                help="Sahoo 2019: 0.35 L/km ≈ 0.563 L/mi")
            lca_truck_l_km = lca_truck_l_mi / KM_PER_MILE

        with _lc2:
            section("Diesel EFs — GREET 2025")
            lca_ef_co2 = st.number_input("CO2 (kg/L)", 1.0, 5.0, 2.68, 0.01, format="%.3f", key="lca_ef_co2")
            lca_ef_ch4 = st.number_input("CH4 (kg/L, ×1e-5)", 0.1, 100.0, 2.7186, 0.01, format="%.4f", key="lca_ef_ch4",
                                          help="2.7186e-5 kg/L — GREET 2025 HDV Long-Haul")
            lca_ef_n2o = st.number_input("N2O (kg/L, ×1e-6)", 0.1, 100.0, 3.6488, 0.01, format="%.4f", key="lca_ef_n2o",
                                          help="3.6488e-6 kg/L — GREET 2025 HDV Long-Haul")

        with _lc3:
            section("Processing EFs — IPCC 2006")
            lca_proc_ef_co2 = st.number_input("Diesel CO2 (kg/L)", 1.0, 5.0, 2.68, 0.01, format="%.3f", key="lca_proc_ef_co2")
            lca_proc_ncv    = st.number_input("NCV Diesel (MJ/L)", 20.0, 50.0, 35.8, 0.1, format="%.1f", key="lca_proc_ncv")
            lca_proc_ch4_mj = st.number_input("CH4 EF (g/MJ Diesel)", 0.01, 1.0, 0.10, 0.01, format="%.3f", key="lca_proc_ch4_mj",
                                                help="IPCC 2006 Table 3.3.1: 0.10 g/MJ")
            lca_proc_n2o_mj = st.number_input("N2O EF (g/MJ Diesel)", 0.01, 1.0, 0.10, 0.01, format="%.3f", key="lca_proc_n2o_mj",
                                                help="IPCC 2006 Table 3.3.1: 0.10 g/MJ")

        with _lc4:
            # All bioenergy combustion constants — no user inputs needed
            lca_cf_wood   = 0.50    # carbon fraction woody biomass [IPCC]
            lca_cf_pulp   = 0.48    # carbon fraction pulp residues [IPCC]
            lca_gwp_ch4   = 27.9    # GWP CH4 AR6 [IPCC]
            lca_gwp_n2o   = 273.0   # GWP N2O AR6 [IPCC]
            lca_ef_ch4_gj = 30.0    # CH4 EF g/GJ [IPCC 2006 Table 2.5]
            lca_ef_n2o_gj = 4.0     # N2O EF g/GJ [IPCC 2006 Table 2.5]
            lca_rankine   = 21.651  # Rankine efficiency % [GREET Bio_electricity row 22]
            if not IS_SAF:
                section("Bioenergy Combustion Constants")
                st.caption(f"CF Wood: {lca_cf_wood}  |  CF Pulp: {lca_cf_pulp}  |  "
                           f"CH4 EF: {lca_ef_ch4_gj} g/GJ  |  N2O EF: {lca_ef_n2o_gj} g/GJ  |  ")

        with _lc5:
            # All SAF production constants — no user inputs, not displayed
            lca_cf_saf = _SAF_INPUTS["cf_forest"]; lca_c_liquid = 0.842  # cf_forest=0.44 per GREET [R2]
            lca_rho_saf = 0.75; lca_rho_diesel = 0.89; lca_rho_naphtha = 0.75

        # Hardcoded GREET internal values (not shown)
        lca_almena_pct    = _SAF_INPUTS["almena_pct"]     if _lca_ok else 60
        lca_greet_ng_btu  = _SAF_INPUTS["greet_ng_btu"]  if _lca_ok else 2304
        lca_greet_bio_btu = _SAF_INPUTS["greet_biomass_feed_loss_btu"] if _lca_ok else 1_000_000

        run_lca = st.button("Run Analysis", type="primary",
                            width="stretch", key="run_lca_btn")
        st.markdown("<hr style='border-color:#1e2d3d;margin:4px 0'>", unsafe_allow_html=True)

        col_header("Impact Results")
        _ir = st.container()

        # ── USE AUTO-FILLED VALUES for the run ────────────────────────────────
        lca_total_odt     = _auto_total_odt_use
        lca_hq_frac       = _auto_hq_frac_use
        lca_saf_L         = _auto_saf_L
        lca_diesel_L      = _auto_die_L
        lca_naphtha_L     = _auto_nap_L
        # lca_dist_saf      = _auto_dist_saf
        lca_dist_f    = _auto_dist_f
        lca_dist_m    = _auto_dist_m
        lca_dist_pw   = _auto_dist_pw
        # lca_dist_saf_mi   = _auto_dist_saf_mi
        lca_dist_f_mi = _auto_dist_f_mi
        lca_dist_m_mi = _auto_dist_m_mi
        lca_dist_pw_mi= _auto_dist_pw_mi
        # Processing options: mirror the options selected in Transport tab per source.
        # SAF feedstock (forest HQ) uses tr_opt_forest (1.x); bioenergy forest uses same.
        # Mill always uses tr_opt_mill (default 3.1); pulpwood uses tr_opt_pulpwood.
        lca_proc_code_saf = st.session_state.get("tr_opt_forest", "1.1")
        # Keep only valid 1.x for SAF
        if lca_proc_code_saf not in ["1.1","1.2","1.3","1.4"]:
            lca_proc_code_saf = "1.1"
        lca_proc_code_bio = st.session_state.get("tr_opt_forest", "2.1")
        if lca_proc_code_bio not in ["2.1","2.2","2.3","3.1"]:
            lca_proc_code_bio = "2.1"
        lca_proc_code_mill = st.session_state.get("tr_opt_mill", "3.1")
        if lca_proc_code_mill not in ["2.1","2.2","2.3","3.1"]:
            lca_proc_code_mill = "3.1"
        lca_proc_code_pulpwood = st.session_state.get("tr_opt_pulpwood", "4.1")
        # 4.x options use the same processing equipment as their 1.x equivalents
        # (same disc-chipper/micro-chipper steps, just without BSTP sorting cost).
        # Map to the corresponding 1.x code for _proc_calc, which only defines 1.x–3.1.
        _PULPWOOD_TO_PROC = {"4.1": "1.1", "4.2": "1.2", "4.3": "1.3", "4.4": "1.4"}
        lca_proc_code_pulpwood = _PULPWOOD_TO_PROC.get(lca_proc_code_pulpwood, lca_proc_code_pulpwood)
        if lca_proc_code_pulpwood not in ["1.1","1.2","1.3","1.4","2.1","2.2","2.3","3.1"]:
            lca_proc_code_pulpwood = "1.1"
        lca_bio_option    = lca_proc_code_bio if lca_proc_code_bio in ["1.1","1.2","1.3","1.4","2.1","2.2","2.3"] else "2.1"

        # Screener checkbox: shown when disc-chip option (1.1/1.2) is active for
        # the primary forest source, OR pulpwood uses an equivalent 4.1/4.2 option.
        _active_proc = lca_proc_code_saf if IS_SAF else lca_proc_code_bio
        _pulpwood_raw_opt = st.session_state.get("tr_opt_pulpwood", "4.1")
        _screener_eligible = _active_proc in ("1.1", "1.2") or (IS_SAF and _pulpwood_raw_opt in ("4.1", "4.2"))
        if _screener_eligible:
            lca_include_screener = st.checkbox(
                f"Include star screener emissions (disc-chip options)",
                value=True,
                key="lca_include_screener",
                help="Adds Sahoo 2019 star-screener fuel consumption on top of disc-chipper. "
                     "Applies to forest options 1.1/1.2 and pulpwood options 4.1/4.2. "
                     "Default ON."
            )
        else:
            lca_include_screener = False

        with _ir:
            col_header("LCA Results")

            if run_lca:
                with st.spinner("Running lifecycle emissions analysis..."):
                    try:
                        import contextlib, io as _io, importlib, types

                        # ── Patch module-level constants before calling functions ─
                        # Each module reads its own global constants at call time.
                        # We patch them temporarily so our dashboard inputs are used.

                        # --- Biomass_transport patches (EFs and fuel economy) ---
                        import LCA_dependencies.Biomass_transport_LCA as _bt_mod
                        # TRUCK_PAYLOAD_OD_KG is patched per-source call below
                        _bt_mod.TRUCK_L_PER_KM        = lca_truck_l_km
                        _bt_mod.DIESEL_CO2            = lca_ef_co2
                        _bt_mod.DIESEL_CH4_ONROAD     = lca_ef_ch4 * 1e-5
                        _bt_mod.DIESEL_N2O_ONROAD     = lca_ef_n2o * 1e-6
                        _bt_mod.GWP_CH4               = lca_gwp_ch4
                        _bt_mod.GWP_N2O               = lca_gwp_n2o

                        # --- Biomass_processing_v2 patches ---
                        import LCA_dependencies.Biomass_processing_LCA as _bp_mod
                        _bp_mod.EF_DIESEL_CO2_KG_PER_L = lca_proc_ef_co2
                        _bp_mod.NCV_DIESEL_MJ_PER_L    = lca_proc_ncv
                        _bp_mod.EF_CH4_G_PER_MJ        = lca_proc_ch4_mj
                        _bp_mod.EF_N2O_G_PER_MJ        = lca_proc_n2o_mj
                        _bp_mod.GWP_CH4                = lca_gwp_ch4
                        _bp_mod.GWP_N2O                = lca_gwp_n2o

                        # --- Bioenergy_production patches ---
                        import LCA_dependencies.Bioenergy_production_LCA as _be_mod
                        _be_mod.CF_WOOD         = lca_cf_wood
                        _be_mod.CF_PULP         = lca_cf_pulp
                        _be_mod.EF_CH4_G_PER_GJ = lca_ef_ch4_gj
                        _be_mod.EF_N2O_G_PER_GJ = lca_ef_n2o_gj
                        _be_mod.GWP_CH4         = lca_gwp_ch4
                        _be_mod.GWP_N2O         = lca_gwp_n2o
                        # RANKINE_EFF not patched — electricity comes from economics tab (be_annual_AC)

                        # ── Derived quantities ────────────────────────────────
                        hq_odt   = lca_total_odt * lca_hq_frac
                        total_kg = lca_total_odt * 1000   # odt → OD kg

                        # ── 1. Processing emissions ───────────────────────────
                        # Run calculate_one() for each residue source separately then sum.
                        # Screener is added on top of disc-chipper options when checkbox is ticked.
                        _tr_run = st.session_state.get("tr_results") or {}

                        def _pack_proc(r):
                            return {"bioCO2_t": 0, "fossCO2_t": r["CO2_t"],
                                    "CH4_CO2e": r["CH4_CO2e"], "N2O_CO2e": r["N2O_CO2e"]}

                        def _sum_proc(*dicts):
                            return {
                                "bioCO2_t":  0,
                                "fossCO2_t": sum(d["fossCO2_t"] for d in dicts),
                                "CH4_CO2e":  sum(d["CH4_CO2e"]  for d in dicts),
                                "N2O_CO2e":  sum(d["N2O_CO2e"]  for d in dicts),
                            }

                        # Forest odt (post-obtainability) for each mode
                        _f_odt  = _tr_run.get("forest",   {}).get("residue_kdry", hq_odt/1000) * 1000
                        _m_odt  = _tr_run.get("mill",     {}).get("residue_kdry", 0) * 1000
                        _pw_odt = _tr_run.get("pulpwood", {}).get("residue_kdry", 0) * 1000

                        if IS_SAF:
                            # SAF: HQ forest with selected forest option; mill/pulpwood with their own selected options
                            _ps_f = _pack_proc(_proc_calc(int(_f_odt),  lca_proc_code_saf,
                                                           include_screener=lca_include_screener)["mid"])
                            _ps_m = _pack_proc(_proc_calc(int(_m_odt),  lca_proc_code_mill)["mid"]) if _m_odt > 0 else None
                            # Pulpwood: screener applies when option maps to 1.1/1.2 (i.e. original 4.1/4.2)
                            _pw_screener = lca_include_screener and lca_proc_code_pulpwood in ("1.1", "1.2")
                            _ps_p = _pack_proc(_proc_calc(int(_pw_odt), lca_proc_code_pulpwood,
                                                           include_screener=_pw_screener)["mid"]) if _pw_odt > 0 else None
                            proc_saf = _sum_proc(_ps_f, *[x for x in [_ps_m, _ps_p] if x])
                            proc_bio = {"bioCO2_t": 0, "fossCO2_t": 0, "CH4_CO2e": 0, "N2O_CO2e": 0}
                        else:
                            # Bioenergy: forest with selected forest option; mill with its own selected option
                            _f_odt_bio = _tr_run.get("forest", {}).get("residue_kdry", lca_total_odt/1000) * 1000
                            _pb_f = _pack_proc(_proc_calc(int(_f_odt_bio), lca_proc_code_bio,
                                                           include_screener=lca_include_screener)["mid"])
                            _pb_m = _pack_proc(_proc_calc(int(_m_odt), lca_proc_code_mill)["mid"]) if _m_odt > 0 else None
                            proc_bio = _sum_proc(_pb_f, *([_pb_m] if _pb_m else []))
                            proc_saf = {"bioCO2_t": 0, "fossCO2_t": 0, "CH4_CO2e": 0, "N2O_CO2e": 0}

                        # Legacy single-source variables kept for chart labels
                        # ps_raw = _proc_calc(int(_f_odt), lca_proc_code_saf,
                        #                      include_screener=lca_include_screener)["mid"]
                        # pb_raw = _proc_calc(int(_f_odt_bio if not IS_SAF else _f_odt),
                        #                      lca_proc_code_bio,
                        #                      include_screener=lca_include_screener)["mid"]

                        # ── 2. Transport emissions — one call per source ──────
                        # phase2_transport uses a single global TRUCK_PAYLOAD_OD_KG, so we
                        # treats the supplied res_kg as the full load (saf==bio case).
                        def _call_trans(res_kg, dist_km, payload_kg):
                            _bt_mod.TRUCK_PAYLOAD_OD_KG = int(payload_kg)
                            with contextlib.redirect_stdout(_io.StringIO()):
                                _r = _trans_calc(res_kg, dist_km)
                            return _r["saf"]   # saf == bio when hq_frac=1.0

                        def _pack_trans(t):
                            ch4_t = t["CH4"] / 1000; n2o_t = t["N2O"] / 1000
                            return {"bioCO2_t": 0, "fossCO2_t": t["CO2"] / 1000,
                                    "CH4_CO2e": ch4_t * lca_gwp_ch4,
                                    "N2O_CO2e": n2o_t * lca_gwp_n2o}

                        def _add_trans(a, b):
                            return {"bioCO2_t":  0,
                                    "fossCO2_t": a["fossCO2_t"] + b["fossCO2_t"],
                                    "CH4_CO2e":  a["CH4_CO2e"]  + b["CH4_CO2e"],
                                    "N2O_CO2e":  a["N2O_CO2e"]  + b["N2O_CO2e"]}

                        _zero_trans = {"bioCO2_t": 0, "fossCO2_t": 0, "CH4_CO2e": 0, "N2O_CO2e": 0}

                        if IS_SAF:
                            # SAF mode: all sources → SAF plant, each with its own payload
                            trans_saf = _zero_trans
                            if _f_odt  > 0: trans_saf = _add_trans(trans_saf, _pack_trans(_call_trans(_f_odt  * 907.185, lca_dist_f, lca_payload_kg)))
                            if _m_odt  > 0: trans_saf = _add_trans(trans_saf, _pack_trans(_call_trans(_m_odt  * 907.185, lca_dist_m, lca_payload_kg_mill)))
                            if _pw_odt > 0: trans_saf = _add_trans(trans_saf, _pack_trans(_call_trans(_pw_odt * 907.185, lca_dist_pw, lca_payload_kg_pulpwood)))
                            trans_bio = _zero_trans
                        else:
                            # Bioenergy mode: each source → bioenergy plant at its own distance and payload
                            _f_odt_bio = _tr_run.get("forest", {}).get("residue_kdry", lca_total_odt/1000) * 1000
                            trans_bio = _zero_trans
                            if _f_odt_bio > 0: trans_bio = _add_trans(trans_bio, _pack_trans(_call_trans(_f_odt_bio * 907.185, lca_dist_f,  lca_payload_kg)))
                            if _m_odt    > 0: trans_bio = _add_trans(trans_bio, _pack_trans(_call_trans(_m_odt     * 907.185, lca_dist_m,  lca_payload_kg_mill)))
                            # if _pw_odt   > 0: trans_bio = _add_trans(trans_bio, _pack_trans(_call_trans(_pw_odt    * 907.185, lca_dist_bio_pw, lca_payload_kg_pulpwood)))
                            trans_saf = _zero_trans

                        # ── 3. Bioenergy production emissions (Bioenergy mode only) ──
                        if not IS_SAF:
                            # Use electricity from bioenergy economics tab (be_annual_AC kWh/yr → GWh/yr)
                            # Not recalculated here — economics tab is authoritative for power output
                            _be_ac_kwh = st.session_state.get("be_annual_AC", 0)
                            _elec_override = (_be_ac_kwh / 1e6) if _be_ac_kwh and _be_ac_kwh > 0 else None
                            with contextlib.redirect_stdout(_io.StringIO()):
                                # br = _bio_calc(int(lca_total_odt), "forest", lca_bio_option, lca_moisture,
                                #                elec_GWh_yr_override=_elec_override)
                                br = _bio_calc(int(lca_total_odt), "forest",
                                                moisture_pct_override=lca_moisture,
                                                elec_GWh_yr_override=_elec_override)
                            bio_prod = {
                                "bioCO2_t":  br["CO2_t_yr"],
                                "fossCO2_t": 0.0,
                                "CH4_CO2e":  br["CH4_CO2e_t_yr"],
                                "N2O_CO2e":  br["N2O_CO2e_t_yr"],
                                "elec_GWh":  br["elec_GWh_yr"],
                            }
                        else:
                            br = None
                            bio_prod = None

                        # ── 4. SAF production emissions (SAF mode only) ────────
                        _saf_shared = {
                            # Total biomass — all sources (forest + mill + pulpwood) —
                            # matching what the economics module feeds into biofuel_production().
                            "biomass_odt_yr":           int(lca_total_odt),
                            "c_liquid":                 lca_c_liquid,
                            "lhv_saf":                  _SAF_INPUTS["lhv_saf"],
                            "saf_L_yr":                 float(lca_saf_L),
                            "diesel_L_yr":              float(lca_diesel_L),
                            "naphtha_L_yr":             float(lca_naphtha_L),
                            "rho_saf":                  lca_rho_saf,
                            "rho_diesel":               lca_rho_diesel,
                            "rho_naphtha":              lca_rho_naphtha,
                            "almena_pct":               lca_almena_pct,
                            "greet_ng_btu":             lca_greet_ng_btu,
                            "greet_biomass_feed_loss_btu": lca_greet_bio_btu,
                            "ef_ng_co2":                _SAF_INPUTS["ef_ng_co2"],
                            "ef_ng_ch4":                _SAF_INPUTS["ef_ng_ch4"],
                            "ef_ng_n2o":                _SAF_INPUTS["ef_ng_n2o"],
                            "ef_fr_gasifier_ch4":        _SAF_INPUTS["ef_fr_gasifier_ch4"],
                            "ef_fr_gasifier_n2o":        _SAF_INPUTS["ef_fr_gasifier_n2o"],
                            "lhv_saf_btu_per_gal":      _SAF_INPUTS["lhv_saf_btu_per_gal"],
                            "gwp_ch4":                  lca_gwp_ch4,
                            "gwp_n2o":                  lca_gwp_n2o,
                        }
                        if IS_SAF:
                            sr = _saf_calc(cf=lca_cf_saf, **_saf_shared)
                            # Sanity check: bioCO2 should be positive (C released > C in liquid products).
                            # A negative value means fuel volumes from economics are inconsistent
                            # with the biomass input — re-run Economics before LCA.
                            if sr["bioCO2_kt"] < 0:
                                st.warning(
                                    f"⚠️ Carbon balance error: biogenic CO₂ = {sr['bioCO2_kt']:.1f} kt "
                                    f"(negative means liquid product carbon ({sr['C_in_kt']*sr['pct_liq']/100:.1f} kt-C) "
                                    f"exceeds biomass carbon input ({sr['C_in_kt']:.1f} kt-C from {int(lca_total_odt):,} ODT total). "
                                    f"Fuel volumes ({lca_saf_L/1e6:.1f}M L SAF/yr) are inconsistent with "
                                    f"total biomass supply. Re-run SAF Economics with the current supply chain before running LCA."
                                )
                            saf_prod = {
                                "bioCO2_t":  sr["bioCO2_kt"] * 1000,
                                "fossCO2_t": sr["fossCO2_t"],
                                "CH4_CO2e":  sr["CH4_CO2e_t"],
                                "N2O_CO2e":  sr["N2O_CO2e_t"],
                            }
                        else:
                            sr = None
                            saf_prod = None

                        # Save everything to session state
                        st.session_state["lca_results"] = {
                            "mode":      "SAF" if IS_SAF else "Bioenergy",
                            "proc_saf":  proc_saf,  "proc_bio":  proc_bio,
                            "trans_saf": trans_saf, "trans_bio": trans_bio,
                            "bio_prod":  bio_prod,  "saf_prod":  saf_prod,
                            "br": br, "sr": sr if IS_SAF else None,
                            "hq_odt": hq_odt, "total_odt": lca_total_odt,
                        }

                        # ── CHARTS: unified two-panel figure ─────────────────
                        import matplotlib.patches as _mpatch
                        import numpy as _np_lca
                        _C_BIO  = "#2471A3"; _C_FOSS = "#A93226"
                        _C_CH4  = "#E67E22"; _C_N2O  = "#1E8449"
                        _C_BURN = "#e76f51"; _C_FOSS_BL = "#378ADD"
                        _BG     = "#0e1621"; _AX_BG = "#131e2d"
                        _TEXT   = "#c8d8e8"; _SPINE = "#2a3a4a"; _GRID = "#1e2d3d"
                        os.makedirs(os.path.join(_DIR, "LCA_plots"), exist_ok=True)

                        def _ax_style(ax):
                            ax.set_facecolor(_AX_BG)
                            ax.spines[["top","right"]].set_visible(False)
                            ax.spines[["left","bottom"]].set_color(_SPINE)
                            ax.tick_params(colors=_TEXT, labelsize=12)
                            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,_: f"{v:,.0f}"))
                            ax.grid(axis="y", color=_GRID, linewidth=0.7, zorder=0)

                        try:
                            # ── Stage data ───────────────────────────────────
                            _zero = {"bioCO2_t":0,"fossCO2_t":0,"CH4_CO2e":0,"N2O_CO2e":0}
                            if IS_SAF:
                                _stages = [
                                    ("Processing",      proc_saf),
                                    ("Transport",       trans_saf),
                                    ("SAF\nProduction", saf_prod if saf_prod else _zero),
                                ]
                            else:
                                _stages = [
                                    ("Processing",           proc_bio),
                                    ("Transport",            trans_bio),
                                    ("Bioenergy\nProduction", bio_prod if bio_prod else _zero),
                                ]

                            def _nb(r):
                                return r["fossCO2_t"] + r["CH4_CO2e"] + r["N2O_CO2e"]

                            # Non-biogenic totals
                            if IS_SAF:
                                _proj_nb = _nb(proc_saf) + _nb(trans_saf) + (_nb(saf_prod) if saf_prod else 0)
                                _proj_nb_combined = (_nb(proc_saf)+_nb(trans_saf)+(_nb(saf_prod) if saf_prod else 0) 
                                    # + _nb(proc_bio)+_nb(trans_bio)
                                )
                            else:
                                _proj_nb = _nb(proc_bio) + _nb(trans_bio) + (_nb(bio_prod) if bio_prod else 0)
                                # _proj_nb_combined = _proj_nb
                                _proj_nb_combined = _nb(proc_bio) + _nb(trans_bio) + (_nb(bio_prod) if bio_prod else 0)

                            # ── Build figure ─────────────────────────────────
                            _fig, (_axL, _axR) = plt.subplots(
                                1, 2, figsize=(18, 7),
                                gridspec_kw={"width_ratios": [1.1, 1]}
                            )
                            _fig.patch.set_facecolor(_BG)

                            # ── LEFT: LCA breakdown by stage ─────────────────
                            _ax_style(_axL)
                            _xs = _np_lca.arange(len(_stages))
                            _w  = 0.50
                            _bv = [float(s[1]["bioCO2_t"])*METRIC_TON_TO_US_TON  for s in _stages]
                            _fv = [float(s[1]["fossCO2_t"])*METRIC_TON_TO_US_TON for s in _stages]
                            _cv = [float(s[1]["CH4_CO2e"])*METRIC_TON_TO_US_TON  for s in _stages]
                            _nv = [float(s[1]["N2O_CO2e"])*METRIC_TON_TO_US_TON  for s in _stages]
                            _b1 = [_bv[i]+_fv[i] for i in range(len(_stages))]
                            _b2 = [_b1[i]+_cv[i] for i in range(len(_stages))]
                            _tots = [_b2[i]+_nv[i] for i in range(len(_stages))]
                            _axL.bar(_xs, _bv, _w, color=_C_BIO,  edgecolor="none", zorder=3)
                            _axL.bar(_xs, _fv, _w, bottom=_bv, color=_C_FOSS, edgecolor="none", zorder=3)
                            _axL.bar(_xs, _cv, _w, bottom=_b1, color=_C_CH4,  edgecolor="none", zorder=3)
                            _axL.bar(_xs, _nv, _w, bottom=_b2, color=_C_N2O,  edgecolor="none", zorder=3)
                            _mx_L = max(_tots) if _tots else 1
                            _axL.set_ylim(0, _mx_L * 1.32)
                            for i, t in enumerate(_tots):
                                _axL.text(_xs[i], t + _mx_L*0.025, f"{t:,.0f}",
                                          ha="center", fontsize=12, fontweight="bold", color="#f0f4f8")
                            _axL.set_xticks(_xs)
                            _axL.set_xticklabels([s[0] for s in _stages], fontsize=13, color=_TEXT)
                            _axL.set_ylabel("GHG Emissions  (US ton CO\u2082e / yr)", fontsize=13, color=_TEXT)
                            _axL.set_title(
                                "Lifecycle GHG by Stage\n(all emission types including biogenic CO\u2082)",
                                fontsize=13, color=_TEXT, pad=10
                            )
                            _lps = [_mpatch.Patch(color=c, label=l) for c,l in [
                                (_C_BIO,  "Biogenic CO\u2082  (wood combustion)"),
                                (_C_FOSS, "Fossil CO\u2082  (NG heat / diesel)"),
                                (_C_CH4,  "CH\u2084 CO\u2082e"),
                                (_C_N2O,  "N\u2082O CO\u2082e"),
                            ]]
                            _axL.legend(handles=_lps, fontsize=11, facecolor=_BG,
                                        edgecolor=_SPINE, labelcolor=_TEXT,
                                        loc="upper left", framealpha=0.85)

                            # ── RIGHT: baseline vs project (non-biogenic) ─────
                            _ax_style(_axR)
                            _burn_bl = lca_total_odt * 1000 * 0.143 / 1000
                            if IS_SAF:
                                _BTU_MJ = 947.817; _L_gal = 3.78541
                                _lhv_MJ_L = (_SAF_INPUTS["lhv_saf_btu_per_gal"] / _L_gal) / _BTU_MJ
                                _fj_bl = 15.93 * float(lca_saf_L) * _lhv_MJ_L / 1e6
                                _saf_nb = _nb(proc_saf)+_nb(trans_saf)+(_nb(saf_prod) if saf_prod else 0)
                                _groups = [
                                    ("Open Burning\nvs This Project",
                                     _burn_bl, _proj_nb_combined, _C_BURN),
                                    ("Fossil Jet Fuel\nvs SAF Pathway",
                                     _fj_bl,   _saf_nb,           _C_FOSS_BL),
                                ]
                            else:
                                _groups = [
                                    ("Open Burning\nvs This Project",
                                     _burn_bl, _proj_nb_combined, _C_BURN),
                                ]

                            _gw  = 0.32
                            _gap = 0.10
                            _grp_w = 2*_gw + _gap + 0.45
                            _grp_xs = _np_lca.arange(len(_groups)) * _grp_w
                            _all_vals = [v for g in _groups for v in [g[1], g[2]]]
                            _mx_R = max(_all_vals) if _all_vals else 1
                            _axR.set_ylim(0, _mx_R * 1.42)

                            for gi, (lbl, bl_val, pj_val, col) in enumerate(_groups):
                                _cx = _grp_xs[gi]
                                _bx = _cx - (_gw/2 + _gap/2)
                                _px = _cx + (_gw/2 + _gap/2)
                                _axR.bar(_bx, bl_val, _gw, color=col, alpha=0.55,
                                         hatch="////", edgecolor=col, linewidth=0.8, zorder=3)
                                _axR.bar(_px, pj_val, _gw, color="#22c55e", alpha=0.9,
                                         edgecolor="none", zorder=3)
                                _axR.text(_bx, bl_val + _mx_R*0.02, f"{bl_val:,.0f}",
                                          ha="center", fontsize=11, fontweight="bold", color="#f0f4f8")
                                _axR.text(_px, pj_val + _mx_R*0.02, f"{pj_val:,.0f}",
                                          ha="center", fontsize=11, fontweight="bold", color="#f0f4f8")
                                _pct = (bl_val - pj_val) / bl_val * 100 if bl_val else 0
                                _axR.annotate(
                                    f"\u2193 {_pct:.1f}% reduction",
                                    xy=(_cx, max(bl_val, pj_val) + _mx_R*0.08),
                                    ha="center", fontsize=12, fontweight="bold", color="#a3e635"
                                )
                                _axR.text(_cx, -_mx_R*0.08, lbl,
                                          ha="center", va="top", fontsize=12, color=_TEXT,
                                          transform=_axR.transData)

                            _axR.set_xlim(-0.5, _grp_xs[-1] + 0.8 if _grp_xs.size > 0 else 1.5)
                            _axR.set_xticks([])
                            _axR.set_ylabel("GHG Emissions  (t CO\u2082e / yr)", fontsize=13, color=_TEXT)
                            _axR.set_title(
                                "Baseline vs This Project\n"
                                "(non-biogenic only: fossil CO\u2082 + CH\u2084 + N\u2082O CO\u2082e)",
                                fontsize=13, color=_TEXT, pad=10
                            )
                            _bl_patch = _mpatch.Patch(facecolor="grey", alpha=0.55,
                                                      hatch="////", edgecolor="grey", label="Baseline (counterfactual)")
                            _pj_patch = _mpatch.Patch(color="#22c55e", label="This project")
                            _axR.legend(handles=[_bl_patch, _pj_patch], fontsize=11,
                                        facecolor=_BG, edgecolor=_SPINE, labelcolor=_TEXT,
                                        loc="upper right", framealpha=0.85)

                            # ── Shared elements ───────────────────────────────
                            _mode_str = "SAF" if IS_SAF else "Bioenergy"
                            _fig.suptitle(
                                f"LCA Results  \u2014  {_mode_str} mode  |  "
                                f"{lca_total_odt*METRIC_TON_TO_US_TON/1e3:.0f}k dry US ton/yr total  |  GWP100 IPCC AR6",
                                fontsize=15, fontweight="bold", color="#e8f0f8", y=1.02
                            )
                            _fig.text(
                                0.5, -0.03,
                                "Left: includes biogenic CO\u2082 from wood combustion.  "
                                "Right (non-biogenic only): consistent with open-burning baseline "
                                "EF 0.143 kg CO\u2082e/kg OD [Khatri 2025] which likewise excludes combustion CO\u2082. "
                                "Both sides of the right panel use the same accounting boundary.",
                                ha="center", fontsize=10, color="#6b8cad", style="italic"
                            )
                            # Save Plot 1: LCA breakdown — use shared function
                            _mode_str1 = "SAF" if IS_SAF else "Bioenergy"
                            _fig1 = _make_lca_stage_fig(_stages, _mode_str1, lca_total_odt)
                            _fig1.savefig(
                                os.path.join(_DIR, "LCA_plots", "lca_integrated.png"),
                                dpi=150, facecolor=_fig1.get_facecolor()
                            )
                            plt.close(_fig1)

                            # Save Plot 2: Avoided emissions (right panel)
                            _fig2, _ax2_only = plt.subplots(1, 1, figsize=(9, 7))
                            _fig2.patch.set_facecolor(_BG)
                            _ax_style(_ax2_only)
                            _scaled_mx_R = _mx_R * METRIC_TON_TO_US_TON
                            _ax2_only.set_ylim(0, _scaled_mx_R * 1.42)
                            for gi, (lbl, bl_val, pj_val, col) in enumerate(_groups):
                                scaled_bl_val = bl_val * METRIC_TON_TO_US_TON
                                scaled_pj_val = pj_val * METRIC_TON_TO_US_TON
                                _cx2 = _grp_xs[gi]
                                _bx2 = _cx2 - (_gw/2 + _gap/2)
                                _px2 = _cx2 + (_gw/2 + _gap/2)
                                _ax2_only.bar(_bx2, scaled_bl_val, _gw, color=col, alpha=0.55,
                                              hatch="////", edgecolor=col, linewidth=0.8, zorder=3)
                                _ax2_only.bar(_px2, scaled_pj_val, _gw, color="#22c55e", alpha=0.9,
                                              edgecolor="none", zorder=3)
                                _ax2_only.text(_bx2, scaled_bl_val + _scaled_mx_R*0.02, f"{scaled_bl_val:,.0f}",
                                            ha="center", fontsize=11, fontweight="bold", color="#f0f4f8")
                                _ax2_only.text(_px2, scaled_pj_val + _scaled_mx_R*0.02, f"{scaled_pj_val:,.0f}",
                                            ha="center", fontsize=11, fontweight="bold", color="#f0f4f8")
                                _pct2 = (bl_val - pj_val) / bl_val * 100 if bl_val else 0
                                _ax2_only.annotate(
                                    f"\u2193 {_pct2:.1f}% reduction",
                                    xy=(_cx2, max(bl_val*METRIC_TON_TO_US_TON, pj_val*METRIC_TON_TO_US_TON) + _mx_R*METRIC_TON_TO_US_TON*0.08),
                                    ha="center", fontsize=12, fontweight="bold", color="#a3e635"
                                )
                                _ax2_only.text(_cx2, -_scaled_mx_R*0.08, lbl,
                                               ha="center", va="top", fontsize=12, color=_TEXT,
                                               transform=_ax2_only.transData)
                            _ax2_only.set_xlim(-0.5, _grp_xs[-1] + 0.8 if _grp_xs.size > 0 else 1.5)
                            _ax2_only.set_xticks([])
                            _ax2_only.set_ylabel("GHG Emissions  (US ton CO\u2082e / yr)", fontsize=13, color=_TEXT)
                            _ax2_only.set_title(
                                "Avoided Emissions Analysis\n"
                                "(non-biogenic only: fossil CO\u2082 + CH\u2084 + N\u2082O CO\u2082e)",
                                fontsize=13, color=_TEXT, pad=10
                            )
                            _ax2_only.legend(handles=[_bl_patch, _pj_patch], fontsize=11,
                                             facecolor=_BG, edgecolor=_SPINE, labelcolor=_TEXT,
                                             loc="upper right", framealpha=0.85)
                            _mode_str2 = "SAF" if IS_SAF else "Bioenergy"
                            _fig2.suptitle(
                                f"Avoided Emissions  \u2014  {_mode_str2} mode  |  GWP100 IPCC AR6",
                                fontsize=13, fontweight="bold", color="#e8f0f8"
                            )
                            _fig2.text(
                                0.5, -0.02,
                                "Baseline (hatched) vs this project (green).  "
                                "Non-biogenic only — consistent with open-burning EF 0.143 kg CO\u2082e/kg OD "
                                "[Khatri 2025] which likewise excludes combustion CO\u2082.",
                                ha="center", fontsize=10, color="#6b8cad", style="italic"
                            )
                            _fig2.subplots_adjust(top=0.88, bottom=0.10, left=0.12, right=0.97)
                            _fig2.savefig(
                                os.path.join(_DIR, "LCA_plots", "fhr_net_climate_impact.png"),
                                dpi=150, facecolor=_fig2.get_facecolor()
                            )
                            plt.close(_fig2)
                            plt.close(_fig)

                        except Exception as _ie:
                            st.warning(f"LCA chart failed: {_ie}")
                            import traceback; st.code(traceback.format_exc())

                        # ── Save avoided emissions baselines to session state ─
                        try:
                            def _nb2(r): return r["fossCO2_t"] + r["CH4_CO2e"] + r["N2O_CO2e"]
                            _fhr_saf_lc = _nb2(proc_saf)+_nb2(trans_saf)+(_nb2(saf_prod) if saf_prod else 0)
                            _fhr_bio_lc = _nb2(proc_bio)+_nb2(trans_bio)+(_nb2(bio_prod) if bio_prod else 0)
                            _fhr_lc = {"saf": _fhr_saf_lc, "bio": _fhr_bio_lc,
                                       "combined": _fhr_saf_lc + _fhr_bio_lc}
                            _fhr_open_burn = lca_total_odt * 1000 * 0.143 / 1000
                            _BTU_MJ2 = 947.817; _L_gal2 = 3.78541
                            _lhv2 = (_SAF_INPUTS["lhv_saf_btu_per_gal"] / _L_gal2) / _BTU_MJ2
                            _fhr_bl = {
                                "open_burn": _fhr_open_burn,
                                "fossil_jf": 15.93 * float(lca_saf_L) * _lhv2 / 1e6,
                                "saf_MJ":    float(lca_saf_L) * _lhv2,
                            }
                            st.session_state["fhr_results"] = {"lc": _fhr_lc, "baselines": _fhr_bl}
                        except Exception as _fe:
                            st.warning(f"Avoided Emissions Analysis failed: {_fe}")

                        st.success("LCA complete.")

                    except Exception as _lca_e:
                        st.error(f"LCA analysis failed: {_lca_e}")
                        import traceback; st.code(traceback.format_exc())

            # ── Display results from session state ────────────────────────────
            _lca_r = st.session_state.get("lca_results")

            if _lca_r:
                def _tot(r): return r["bioCO2_t"] + r["fossCO2_t"] + r["CH4_CO2e"] + r["N2O_CO2e"]
                _lca_mode = _lca_r.get("mode", "SAF" if IS_SAF else "Bioenergy")

                # ── Key metrics ───────────────────────────────────────────────
                _mc1, _mc2, _mc3 = st.columns(3)
                if _lca_mode == "SAF" and _lca_r.get("saf_prod"):
                    _s = _lca_r["saf_prod"]
                    with _mc1: st.markdown(mc("SAF Total CO2e", f"{_tot(_s)*METRIC_TON_TO_US_TON/1000:,.1f} k US ton/yr", "production"), unsafe_allow_html=True)
                    with _mc2: st.markdown(mc("Transport CO2e", f"{_tot(_lca_r['trans_saf'])*METRIC_TON_TO_US_TON:,.0f} US ton/yr", "SAF supply chain"), unsafe_allow_html=True)
                    with _mc3: st.markdown(mc("Processing CO2e", f"{_tot(_lca_r['proc_saf'])*METRIC_TON_TO_US_TON:,.0f} US ton/yr", "SAF feedstock"), unsafe_allow_html=True)
                elif _lca_r.get("bio_prod"):
                    _b = _lca_r["bio_prod"]
                    with _mc1: st.markdown(mc("Bioenergy Output", f"{_b.get('elec_GWh',0):,.1f} GWh/yr", "Rankine cycle"), unsafe_allow_html=True)
                    with _mc2: st.markdown(mc("Transport CO2e", f"{_tot(_lca_r['trans_bio'])*METRIC_TON_TO_US_TON:,.0f} US ton/yr", "bioenergy supply chain"), unsafe_allow_html=True)
                    with _mc3: st.markdown(mc("Processing CO2e", f"{_tot(_lca_r['proc_bio'])*METRIC_TON_TO_US_TON:,.0f} US ton/yr", "bioenergy feedstock"), unsafe_allow_html=True)

                # ── PLOTS 1 + 2 side by side ────────────────────────────────
                _plt_l, _plt_r = st.columns(2, gap="medium")
                with _plt_l:
                    section("Plot 1 — LCA Emissions by Stage")
                    render_saved_png("LCA_plots/lca_integrated.png")
                with _plt_r:
                    section("Plot 2 — Avoided Emissions Analysis")
                    _fhr_r = st.session_state.get("fhr_results")
                    if _fhr_r:
                        render_saved_png("LCA_plots/fhr_net_climate_impact.png")
                    else:
                        st.caption("Avoided Emissions Analysis not yet run — click Run Analysis above.")

            # ── PLOT 3: Jobs (only after LCA run) ──────────────────────────────
            if st.session_state.get("lca_results") is not None:
                if JOBS_AVAILABLE:
                    _jobs = st.session_state.get("jobs_result")
                    if _jobs is None:
                        info("<b>Run Economics tab first</b> to calculate jobs.")
                    else:
                        section("Plot 3 — Jobs Creation")
                        _j1, _j2, _j3, _j4 = st.columns(4)
                        with _j1: st.markdown(mc("Direct Jobs",   str(_jobs["direct_jobs"]),   "plant operations"),         unsafe_allow_html=True)
                        with _j2: st.markdown(mc("Indirect Jobs", str(_jobs["indirect_jobs"]), "supply chain", "mc-amber"), unsafe_allow_html=True)
                        with _j3: st.markdown(mc("Induced Jobs",  str(_jobs["induced_jobs"]),  "local economy", "mc-blue"), unsafe_allow_html=True)
                        with _j4: st.markdown(mc("Total Jobs",    str(_jobs["total_jobs"]),    "all categories"),            unsafe_allow_html=True)
                        # info(
                        #     "<b>EPI Employment Multipliers (2019$).</b> "
                        #     "Bioenergy: Electric Power sector. "
                        #     "SAF: Petroleum Manufacturing sector."
                        # )
                        render_saved_png("Jobscreation_plots/plot_jobs.png")

            if not st.session_state.get("lca_results"):
                info("Configure inputs above and click <b>Run Analysis</b>.")
# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — POLICY ANALYSIS
# Bioenergy: Bioenergy_Policy_FINAL.base_credit_cash_flow_analysis × 3 scenarios
#   + required_credit_for_breakeven + plot_policy_comparison(df1,df2,df3)
# SAF:       SAF_Policy_FINAL.credit_cash_flow_analysis
#   + required_credit_for_market + plot_policy_comparison(df1,df2)
# All called exactly as the respective main() functions call them.
# ══════════════════════════════════════════════════════════════════════════════
with tab_policy:
    col_header("Policy Analysis")

    if not IS_SAF:
        # ──────────────────────────────────────────────────────────────────────
        # BIOENERGY POLICY  (Bioenergy_Policy_FINAL)
        # Requires Economics tab (TCI, FCI, dep, annual_AC stored in session)
        # main() uses LCOE as the electricity selling price so the no-policy
        # scenario has NPV≈0, isolating the pure policy uplift.
        # ──────────────────────────────────────────────────────────────────────
        if not BEE_POL_AVAILABLE:
            st.error(f"Bioenergy_Policy_FINAL.py could not be imported: **{BEE_POL_ERROR}**")
        elif not st.session_state.get("be_equip_done") and not st.session_state.get("be_TCI"):
            warn("<b>Run Bioenergy Economics first.</b> Policy reuses TCI/FCI/depreciation from that tab.")
        else:
            _TCI = st.session_state["be_TCI"]
            _FCI = st.session_state["be_FCI"]
            _dep = st.session_state["be_annual_dep"]
            _AC  = st.session_state["be_annual_AC"]

            # LCOE from economics tab (electricity selling price for policy comparison)
            _lcoe_raw = st.session_state.get("be_lcoe")
            _lcoe_val = (_lcoe_raw if isinstance(_lcoe_raw,(int,float))
                         else _lcoe_raw.get("LCOE ($/MWh)") if _lcoe_raw else None)

            # Read economics widget values from session_state.
            # NOTE: Streamlit stores the raw displayed value in session_state, so
            # widgets defined as  st.number_input(..., key="be_disc") / 100  store
            # the percentage (e.g. 7.0), NOT the decimal (0.07).  We divide here
            # to match exactly what the Economics tab passes to build_cash_flow_analysis.
            _ss     = st.session_state
            _f_t    = _ss.get("be_f_tons",    100_000)
            _m_t    = _ss.get("be_m_tons",     80_000)
            _life   = _ss.get("be_life",           30)
            _fc     = _ss.get("be_f_cost",       25.0)
            _mc     = _ss.get("be_m_cost",       20.0)
            _lt     = _ss.get("be_loan_term",      15)
            # These are stored as display-scale percentages -> divide by 100
            _degr   = _ss.get("be_degr",   0.5) / 100
            _disc   = _ss.get("be_disc",   7.0) / 100
            _infl   = _ss.get("be_infl",   2.5) / 100
            _debt   = _ss.get("be_debt",    60) / 100
            _lr     = _ss.get("be_loan_r", 6.5) / 100
            _eesc   = _ss.get("be_eesc",   1.0) / 100
            _fesc   = _ss.get("be_fesc",   2.5) / 100
            _fomesc = _ss.get("be_fomesc", 2.5) / 100
            _vomesc = _ss.get("be_vomesc", 2.0) / 100
            _fed    = _ss.get("be_fed",     21)  / 100
            _st     = _ss.get("be_st",       7)  / 100

            _bpl, _bpr = st.columns([1, 2], gap="medium")

            with _bpl:
                col_header("Policy Inputs")

                if _lcoe_val:
                    info(f"<b>LCOE (from Economics):</b> ${_lcoe_val:.2f}/MWh — used as selling price for all scenarios")
                    _ep = st.number_input("Electricity price for policy scenarios ($/MWh)",
                                          10.0, 500.0, float(round(_lcoe_val,2)), 1.0,
                                          format="%.2f", key="bepol_elec_price")
                else:
                    warn("LCOE not available — run Economics tab first (or enter price manually).")
                    _ep = st.number_input("Electricity price ($/MWh)", 10.0, 500.0, 166.0, 1.0,
                                          format="%.2f", key="bepol_elec_price")

                section("IRA 45Y Credit Parameters")
                info("Finds minimum IRA 45Y PTC ($/kWh) for NPV=0 at a market price below LCOE.")
                _market_p = st.number_input("Market electricity price ($/MWh)", 10.0, 500.0,
                                             120.0, 1.0, format="%.2f", key="bepol_market_price")
                _run_solver = st.checkbox("Solve for minimum IRA 45Y PTC credit", False, key="bepol_run_solver")

                run_bepol = st.button("Run Policy Analysis", type="primary",
                                      width="stretch", key="run_bepol_btn")

            with _bpr:
                col_header("Policy Results")

                # Common kwargs for all three scenario calls — exactly as main() passes them
                _common = dict(
                    TCI=_TCI, FCI=_FCI,
                    annual_depreciation_schedule=list(_dep),
                    annual_AC_year1=_AC,
                    # Effective tons for fuel cost calculation (raw tons × obtainability)
                    forest_annual_tons=_f_t * _ss.get("be_f_obtain", 100) / 100,
                    mill_annual_tons=_m_t * _ss.get("be_m_obtain", 100) / 100,
                    degradation_factor=_degr,
                    capacity_factor=BE_CAPACITY_FACTOR,
                    Plant_Lifespan=_life,
                    c_fuel_per_ton_forest=_fc,
                    c_fuel_per_ton_mill=_mc,
                    electricity_price=_ep,
                    real_discount_rate=_disc,
                    inflation_rate=_infl,
                    debt_fraction=_debt,
                    loan_rate=_lr,
                    loan_term=_lt,
                    electricity_escalation=_eesc,
                    fuel_escalation=_fesc,
                    fixed_om_escalation=_fomesc,
                    var_om_escalation=_vomesc,
                    federal_tax_rate=_fed,
                    state_tax_rate=_st,
                    verbose=False,
                )

                if run_bepol:
                    with st.spinner("Running three-scenario policy analysis..."):
                        try:
                            # Exactly as Bioenergy_Policy_FINAL.main() calls base_credit_cash_flow_analysis
                            _df1, _m1 = bepol.base_credit_cash_flow_analysis('none',           **_common)
                            _df2, _m2 = bepol.base_credit_cash_flow_analysis('basecredit',     **_common)
                            _df3, _m3 = bepol.base_credit_cash_flow_analysis('investmentcredit', **_common)
                            st.session_state.update({
                                "be_pol_df_none":_df1, "be_pol_met_none":_m1,
                                "be_pol_df_ptc": _df2, "be_pol_met_ptc": _m2,
                                "be_pol_df_itc": _df3, "be_pol_met_itc": _m3,
                            })
                            if _run_solver:
                                with st.spinner("Solving for minimum PTC..."):
                                    try:
                                        # Exactly as main() calls required_credit_for_breakeven
                                        _cs = bepol.required_credit_for_breakeven(
                                            **{**_common, "electricity_price": _market_p})
                                        st.session_state["be_pol_credit_solved"] = _cs
                                    except Exception as _ce:
                                        st.error(f"Credit solver failed: {_ce}")
                        except Exception as _pe:
                            st.error(f"Policy analysis failed: {_pe}")
                            import traceback; st.code(traceback.format_exc())

                _df1 = st.session_state.get("be_pol_df_none")
                _m1  = st.session_state.get("be_pol_met_none")
                _df2 = st.session_state.get("be_pol_df_ptc")
                _m2  = st.session_state.get("be_pol_met_ptc")
                _df3 = st.session_state.get("be_pol_df_itc")
                _m3  = st.session_state.get("be_pol_met_itc")
                _cs  = st.session_state.get("be_pol_credit_solved")

                if _df1 is not None:
                    section("Scenario Comparison")
                    _pc1, _pc2, _pc3 = st.columns(3)

                    def _bepol_mc(col, label, m, hex_top="#4a5a6a"):
                        _irr = m.get("Equity IRR", float("nan"))
                        _pb  = m.get("Payback Period (years)")
                        _npv = m.get("NPV (Equity, Nominal)", 0)
                        with col:
                            st.markdown(
                                f'<div style="background:#0f1826;border:1px solid #2a3a4a;'
                                f'border-top:3px solid {hex_top};border-radius:5px;'
                                f'padding:7px 9px;margin-bottom:6px">'
                                f'<div style="font-size:1.00rem;font-weight:700;color:#4a5a6a;'
                                f'text-transform:uppercase">{label}</div></div>',
                                unsafe_allow_html=True)
                            st.markdown(mc("NPV", f"${_npv/1e6:.2f}M","","mc-neg" if _npv<0 else ""), unsafe_allow_html=True)
                            st.markdown(mc("IRR", f"{_irr*100:.2f}%" if not np.isnan(_irr) else "N/A"), unsafe_allow_html=True)
                            st.markdown(mc("Payback", f"{_pb:.2f} yr" if _pb else "Never","","mc-warn" if not _pb else ""), unsafe_allow_html=True)

                    _bepol_mc(_pc1, "No Policy",            _m1, "#4a5a6a")
                    _bepol_mc(_pc2, "IRA 45Y PTC — Production Tax Credit (0.3¢/kWh)",   _m2, "#1D9E75")
                    _bepol_mc(_pc3, "IRA 45Y ITC — Investment Tax Credit (6% of FCI)",       _m3, "#378ADD")

                    if _cs is not None:
                        st.markdown(mc("Min IRA 45Y PTC for NPV=0",
                                       f"${_cs*100:.4f} cents/kWh",
                                       f"at ${_market_p:.0f}/MWh market price", "mc-amber"),
                                    unsafe_allow_html=True)

                    # ── Policy comparison bar chart ────────────────────────────────────
                    # plot_policy_comparison saves to Policy_plots/policy_comparison.png
                    # and does NOT return the figure, so we display the saved PNG.
                    section("Annual FCF: No Policy vs IRA 45Y PTC vs IRA 45Y ITC")
                    try:
                        bepol.plot_policy_comparison(_df1, _df2, _df3)
                        render_saved_png("Policy_plots/policy_comparison.png")
                    except Exception as _pfe:
                        st.error(f"Plot failed: {_pfe}")

                    # ── Per-scenario cumulative CF plots ──────────────────────────────
                    section("Cumulative Cash Flow by Scenario")
                    _cp1, _cp2, _cp3 = st.columns(3, gap="medium")
                    for _col, _df_s, _m_s, _lbl in [
                        (_cp1, _df1, _m1, "No Policy"),
                        (_cp2, _df2, _m2, "IRA 45Y PTC"),
                        (_cp3, _df3, _m3, "IRA 45Y ITC"),
                    ]:
                        with _col:
                            st.markdown(f'<div style="font-size:1.00rem;font-weight:700;'
                                        f'color:#c9d1e0;text-transform:uppercase;'
                                        f'margin-bottom:6px">{_lbl}</div>',
                                        unsafe_allow_html=True)
                            try:
                                from Bioenergy_dependencies.bioenergy_plots_FINAL import plot_cumulative_cashflow as _plot_cum_cf
                                _cf_fig = _plot_cum_cf(_df_s, _m_s)
                                _cf_fig.set_size_inches(5, 6.5)
                                plt.tight_layout(pad=0.4)
                                render_pyplot_safe(_cf_fig)
                            except Exception as _pe:
                                st.caption(f"Plot error: {_pe}")

                    with st.expander("Data Tables", expanded=False):
                        _dt1, _dt2, _dt3 = st.tabs(["No Policy", "IRA 45Y PTC", "IRA 45Y ITC"])
                        with _dt1: st.dataframe(_df1, width="stretch", height=250)
                        with _dt2: st.dataframe(_df2, width="stretch", height=250)
                        with _dt3: st.dataframe(_df3, width="stretch", height=250)
                else:
                    info("Configure inputs and click <b>Run Policy Analysis</b>.")

    else:
        # ──────────────────────────────────────────────────────────────────────
        # SAF POLICY  (SAF_Policy_FINAL)
        # main() calls: sf.solve_mfsp → sf.build_cash_flow_analysis (no-policy at MFSP)
        #              → credit_cash_flow_analysis (with IRA 45Z)
        #              → plot_policy_comparison(df1,df2)
        #              → required_credit_for_market
        # All positional args match the new saf_MAIN_economics_FINAL signature.
        # ──────────────────────────────────────────────────────────────────────
        if not SAF_POL_AVAILABLE:
            st.error(f"SAF_Policy_FINAL.py could not be imported: **{SAF_POL_ERROR}**")
        else:
            sc_res = st.session_state.get("sc_results")
            tr_res = st.session_state.get("tr_results")
            _mfsp  = st.session_state.get("saf_mfsp")

            # Auto-fill throughputs and PDCs (same as economics tab).
            # Prefer session_state values set by Transport auto-send (post-send raw tons).
            # Fall back to sc_results (pre-obtainability) only as last resort — warn the user.
            _f_t_sc  = int(sc_res["forest"].get("hq_kdry",0)*1000) if sc_res else 100_000
            _pw_t_sc = int(sc_res.get("pulpwood",{}).get("total_kdry",0)*1000) if sc_res else 100_000
            _sw_t_sc = int(sc_res["mill"].get("total_kdry",0)*1000) if sc_res else 100_000
            _using_sc_fallback = not st.session_state.get("tr_sent_to_econ") and not st.session_state.get("saf_f_tons")
            _f_t  = st.session_state.get("saf_f_tons",  _f_t_sc)
            _pw_t = st.session_state.get("saf_pw_tons", _pw_t_sc)
            _sw_t = st.session_state.get("saf_sw_tons", _sw_t_sc)
            _pdc_f  = tr_res["forest"]["cost_odt"]   if tr_res and "forest"   in tr_res else 60.0
            _pdc_pw = tr_res["pulpwood"]["cost_odt"] if tr_res and "pulpwood" in tr_res else 60.0
            _pdc_sw = tr_res["mill"]["cost_odt"]     if tr_res and "mill"     in tr_res else 60.0

            if _using_sc_fallback:
                warn(
                    "<b>Transport tab not yet run.</b> Throughputs are pre-obtainability totals "
                    "from Supply Chain — run the Transport tab first for accurate policy inputs."
                )

            _spl, _spr = st.columns([1, 2], gap="medium")

            with _spl:
                col_header("SAF Policy Inputs")

                # ── Carry forward all inputs from Economics + Transport tabs ──────
                # These are read from session state — no re-entry required
                # Read SAF economics widget values from session state.
                # Widgets store display-scale values (e.g. 10.0 not 0.10) → divide % ones by 100.
                _ss = st.session_state
                _sp_f_t    = _ss.get("saf_f_tons",    _f_t)
                _sp_pw_t   = _ss.get("saf_pw_tons",   _pw_t)
                _sp_sw_t   = _ss.get("saf_sw_tons",   _sw_t)
                _sp_f_ob   = _ss.get("saf_f_ob",      1.0)
                _sp_pw_ob  = _ss.get("saf_pw_ob",     1.0)
                _sp_sw_ob  = _ss.get("saf_sw_ob",     1.0)
                _sp_pdc_f  = _ss.get("saf_pdc_f",     float(round(_pdc_f,2)))
                _sp_pdc_pw = _ss.get("saf_pdc_pw",    float(round(_pdc_pw,2)))
                _sp_pdc_sw = _ss.get("saf_pdc_sw",    float(round(_pdc_sw,2)))
                _sp_distil = _ss.get("saf_distil",    "distillate 1")
                _sp_life   = _ss.get("saf_life",      20)
                _sp_cpi    = _ss.get("saf_cpi",       321.05)
                _sp_year   = _ss.get("saf_year",      2025)
                _sp_lt     = _ss.get("saf_loanterm",  15)
                # These are stored as display-scale percentages → divide by 100
                _sp_disc   = _ss.get("saf_disc",   10.0) / 100
                _sp_infl   = _ss.get("saf_infl",    2.5) / 100
                _sp_debt   = _ss.get("saf_debt",   70.0) / 100
                _sp_lr     = _ss.get("saf_loan_r",  8.0) / 100
                _sp_degr   = _ss.get("saf_degr",    0.0) / 100
                _sp_fed    = _ss.get("saf_fedtax", 21.0) / 100
                _sp_st     = _ss.get("saf_sttax",   7.0) / 100
                _sp_pesc   = _ss.get("saf_pesc",    2.5) / 100
                _sp_fesc   = _ss.get("saf_fesc",    2.5) / 100
                _sp_cesc   = _ss.get("saf_cesc",    2.5) / 100
                _sp_kaesc  = _ss.get("saf_kaesc",   2.5) / 100

                info(
                    f"<b>Carried forward from SAF Economics tab:</b>  "
                    f"Forest {_sp_f_t*METRIC_TON_TO_US_TON:,.0f} US ton  |  Pulpwood {_sp_pw_t*METRIC_TON_TO_US_TON:,.0f} US ton  |  Sawmill {_sp_sw_t*METRIC_TON_TO_US_TON:,.0f} US ton<br>"
                    f"PDC ($/US ton): F ${_sp_pdc_f:.2f}  P ${_sp_pdc_pw:.2f}  S ${_sp_pdc_sw:.2f}  |  "
                    f"Obtain: F {_sp_f_ob:.0%}  P {_sp_pw_ob:.0%}  S {_sp_sw_ob:.0%}<br>"
                    f"Disc {_sp_disc:.1%}  Debt {_sp_debt:.0%}  Loan {_sp_lr:.1%} / {_sp_lt}yr"
                )

                # Selling prices — auto-fill from MFSP if available
                _msp_saf  = _mfsp["MFSP SAF ($/L)"]    if _mfsp else 1.61
                _msp_die  = _mfsp["MFSP Diesel ($/L)"] if _mfsp else 1.03
                _msp_nap  = _mfsp["MFSP Naptha ($/L)"] if _mfsp else 0.75
                # Push MFSP values into session_state so number_input widgets
                # always reflect the latest run (value= arg is only used on first render).
                if _mfsp:
                    st.session_state["sp_saf_p"] = float(round(_msp_saf * L_PER_GAL, 4))
                    st.session_state["sp_die_p"] = float(round(_msp_die * L_PER_GAL, 4))
                    st.session_state["sp_nap_p"] = float(round(_msp_nap * L_PER_GAL, 4))
                    info(f"<b>MFSP auto-fill:</b> SAF ${_msp_saf*L_PER_GAL:.4f} | Diesel ${_msp_die*L_PER_GAL:.4f} | Naphtha ${_msp_nap*L_PER_GAL:.4f} /gal")
                section("Minimum Fuel Selling Prices ($/gal)")
                _spp1, _spp2, _spp3 = st.columns(3)

                with _spp1:
                    st.markdown(
                        f'<div style="margin-bottom:10px">'
                        f'<div style="font-size:0.9rem;color:#8a9ab0;margin-bottom:2px">SAF</div>'
                        f'<div style="font-size:1.05rem;font-weight:700;color:#c9d1e0;'
                        f'background:#0e1621;border:1px solid #1e2d3d;border-radius:6px;'
                        f'padding:8px 12px;letter-spacing:0.02em">'
                        f'${float(_msp_saf * L_PER_GAL):.4f}</div></div>',
                        unsafe_allow_html=True
                    )

                with _spp2:
                    st.markdown(
                        f'<div style="margin-bottom:10px">'
                        f'<div style="font-size:0.9rem;color:#8a9ab0;margin-bottom:2px">Diesel</div>'
                        f'<div style="font-size:1.05rem;font-weight:700;color:#c9d1e0;'
                        f'background:#0e1621;border:1px solid #1e2d3d;border-radius:6px;'
                        f'padding:8px 12px;letter-spacing:0.02em">'
                        f'${float(_msp_die * L_PER_GAL):.4f}</div></div>',
                        unsafe_allow_html=True
                    )

                with _spp3:
                    st.markdown(
                        f'<div style="margin-bottom:10px">'
                        f'<div style="font-size:0.9rem;color:#8a9ab0;margin-bottom:2px">Naphtha</div>'
                        f'<div style="font-size:1.05rem;font-weight:700;color:#c9d1e0;'
                        f'background:#0e1621;border:1px solid #1e2d3d;border-radius:6px;'
                        f'padding:8px 12px;letter-spacing:0.02em">'
                        f'${float(_msp_nap * L_PER_GAL):.4f}</div></div>',
                        unsafe_allow_html=True
                    )

                # Convert back to $/L for model calls
                _sp_saf_p = _msp_saf
                _sp_die_p = _msp_die
                _sp_nap_p = _msp_nap

                section("IRA 45Z Credit Parameters")
                _scr1, _scr2 = st.columns(2)
                with _scr1:
                    _sp_cr_saf  = st.number_input("SAF credit ($/GGE)", 0.01,2.0,0.35,0.01,format="%.3f",key="sp_cr_saf")
                    _sp_cr_nons = st.number_input("Non-SAF credit ($/GGE)",0.01,2.0,0.20,0.01,format="%.3f",key="sp_cr_nons")
                    _sp_cr_dur  = st.number_input("Credit duration (yr)",1,20,10,1,key="sp_cr_dur")
                with _scr2:
                    _sp_jet_mkt_gal = st.number_input("Jet-A market ($/gal)", 0.1, 20.0, round(0.82*L_PER_GAL, 3), 0.01, format="%.3f", key="sp_jet_mkt")
                    _sp_die_mkt_gal = st.number_input("Diesel market ($/gal)",0.1, 20.0, round(1.34*L_PER_GAL, 3), 0.01, format="%.3f", key="sp_die_mkt")
                    _sp_nap_mkt_gal = st.number_input("Naphtha market ($/gal)",0.1,20.0, round(0.98*L_PER_GAL, 3), 0.01, format="%.3f", key="sp_nap_mkt")
                    _sp_jet_mkt = _sp_jet_mkt_gal / L_PER_GAL
                    _sp_die_mkt = _sp_die_mkt_gal / L_PER_GAL
                    _sp_nap_mkt = _sp_nap_mkt_gal / L_PER_GAL
                _run_saf_solver = st.checkbox("Solve for required SAF credit", False, key="sp_run_solver")

                run_safpol = st.button("Run SAF Policy Analysis", type="primary",
                                       width="stretch", key="run_safpol_btn")

            with _spr:
                col_header("SAF Policy Results")

                if run_safpol:
                    with st.spinner("Running SAF policy analysis..."):
                        try:
                            # Common positional args for all calls (matches saf_MAIN_economics_FINAL signature)
                            _base_args = (_sp_year, _sp_f_t, _sp_pw_t, _sp_sw_t,
                                          _sp_f_ob, _sp_pw_ob, _sp_sw_ob,
                                          _sp_distil, _sp_life,
                                          _sp_disc, _sp_infl, _sp_debt, _sp_lr, _sp_lt,
                                          _sp_cpi, _sp_pdc_f, _sp_pdc_pw, _sp_pdc_sw,
                                          _sp_degr)

                            # No-policy baseline at MFSP prices (exactly as main() calls sf.build_cash_flow_analysis)
                            _spdf1, _spm1 = sfm.build_cash_flow_analysis(
                                *_base_args,
                                _sp_saf_p, _sp_die_p, _sp_nap_p,
                                _sp_pesc, _sp_fesc, _sp_cesc, _sp_kaesc,
                                _sp_fed, _sp_st,
                                verbose=False,
                            )

                            # With-credit scenario (exactly as main() calls credit_cash_flow_analysis)
                            _spdf2, _spm2 = safpol.credit_cash_flow_analysis(
                                *_base_args,
                                _sp_saf_p, _sp_die_p, _sp_nap_p,
                                _sp_pesc, _sp_fesc, _sp_cesc, _sp_kaesc,
                                credit_SAF      = _sp_cr_saf,
                                credit_nonSAAF  = _sp_cr_nons,
                                credit_duration = _sp_cr_dur,
                                federal_tax_rate = _sp_fed,
                                state_tax_rate   = _sp_st,
                                verbose          = False,
                            )

                            st.session_state.update({
                                "saf_pol_df_none":   _spdf1, "saf_pol_met_none":   _spm1,
                                "saf_pol_df_credit": _spdf2, "saf_pol_met_credit": _spm2,
                            })

                            if _run_saf_solver:
                                with st.spinner("Solving for minimum SAF credit..."):
                                    try:
                                        # Exactly as SAF_Policy_FINAL.main() calls required_credit_for_market
                                        _cr_s, _cr_ns = safpol.required_credit_for_market(
                                            *_base_args,
                                            _sp_jet_mkt, _sp_die_mkt, _sp_nap_mkt,
                                            _sp_pesc, _sp_fesc, _sp_cesc, _sp_kaesc,
                                            federal_tax_rate=_sp_fed,
                                            state_tax_rate=_sp_st,
                                            verbose=False,
                                        )
                                        st.session_state["saf_pol_credit_saf"]    = _cr_s
                                        st.session_state["saf_pol_credit_nonsaf"] = _cr_ns
                                    except Exception as _sce:
                                        st.error(f"SAF credit solver failed: {_sce}")

                        except Exception as _spe:
                            st.error(f"SAF policy analysis failed: {_spe}")
                            import traceback; st.code(traceback.format_exc())

                _spdf1 = st.session_state.get("saf_pol_df_none")
                _spm1  = st.session_state.get("saf_pol_met_none")
                _spdf2 = st.session_state.get("saf_pol_df_credit")
                _spm2  = st.session_state.get("saf_pol_met_credit")
                _cr_s  = st.session_state.get("saf_pol_credit_saf")
                _cr_ns = st.session_state.get("saf_pol_credit_nonsaf")

                if _spdf1 is not None:
                    section("Scenario Comparison")
                    _spc1, _spc2 = st.columns(2)

                    def _safpol_mc(col, label, m, hex_top="#4a5a6a"):
                        _irr = m.get("Equity IRR", float("nan"))
                        _pb  = m.get("Payback Period (years)")
                        _npv = m.get("NPV (Equity, Nominal)", 0)
                        with col:
                            st.markdown(
                                f'<div style="background:#0f1826;border:1px solid #2a3a4a;'
                                f'border-top:3px solid {hex_top};border-radius:5px;'
                                f'padding:7px 9px;margin-bottom:6px">'
                                f'<div style="font-size:1.00rem;font-weight:700;color:#4a5a6a;'
                                f'text-transform:uppercase">{label}</div></div>',
                                unsafe_allow_html=True)
                            st.markdown(mc("NPV",f"${_npv/1e6:.2f}M","","mc-neg" if _npv<0 else ""), unsafe_allow_html=True)
                            st.markdown(mc("IRR",f"{_irr*100:.2f}%" if not np.isnan(_irr) else "N/A"), unsafe_allow_html=True)
                            st.markdown(mc("Payback",f"{_pb:.2f} yr" if _pb else "Never","","mc-warn" if not _pb else ""), unsafe_allow_html=True)

                    _safpol_mc(_spc1, "No Policy (MFSP Prices)", _spm1, "#4a5a6a")
                    _safpol_mc(_spc2, "IRA 45Z Clean Fuel Credit", _spm2, "#1D9E75")

                    if _cr_s is not None:
                        _rc1, _rc2 = st.columns(2)
                        with _rc1: st.markdown(mc("Min SAF Credit ($/GGE)",f"${_cr_s:.4f}","for NPV=0 at market prices","mc-amber"), unsafe_allow_html=True)
                        with _rc2: st.markdown(mc("Min Non-SAF Credit ($/GGE)",f"${_cr_ns:.4f}","diesel + naphtha","mc-amber"), unsafe_allow_html=True)

                    # ── Policy comparison bar chart ────────────────────────────────────
                    # plot_policy_comparison saves to Policy_plots/policy_comparison.png
                    # and does NOT return the figure, so we display the saved PNG.
                    section("Annual FCF: No Policy vs IRA 45Z Credit")
                    try:
                        safpol.plot_policy_comparison(_spdf1, _spdf2)
                        render_saved_png("Policy_plots/policy_comparison.png")
                    except Exception as _spfe:
                        st.error(f"SAF policy plot failed: {_spfe}")

                    # ── Per-scenario cumulative CF plots ──────────────────────────────
                    section("Cumulative Cash Flow by Scenario")
                    _scc1, _scc2 = st.columns(2, gap="medium")
                    for _col, _df_s, _m_s, _lbl in [
                        (_scc1, _spdf1, _spm1, "No Policy"),
                        (_scc2, _spdf2, _spm2, "IRA 45Z Credit"),
                    ]:
                        with _col:
                            st.markdown(f'<div style="font-size:1.00rem;font-weight:700;'
                                        f'color:#c9d1e0;text-transform:uppercase;'
                                        f'margin-bottom:6px">{_lbl}</div>',
                                        unsafe_allow_html=True)
                            try:
                                from SAF_dependencies.SAF_plots_FINAL import plot_cumulative_cashflow as _saf_plot_cum
                                _cf_fig = _saf_plot_cum(_df_s, _m_s)
                                _cf_fig.set_size_inches(6, 10)
                                plt.tight_layout(pad=0.4)
                                render_pyplot_safe(_cf_fig)
                            except Exception as _pe:
                                st.caption(f"Plot error: {_pe}")

                    with st.expander("Data Tables", expanded=False):
                        _st1, _st2 = st.tabs(["No Policy", "IRA 45Z Credit"])
                        with _st1: st.dataframe(_spdf1, width="stretch", height=250)
                        with _st2: st.dataframe(_spdf2, width="stretch", height=250)
                else:
                    info("Configure inputs and click <b>Run SAF Policy Analysis</b>.")



# ══════════════════════════════════════════════════════════════════════════════
# ┌──────────────────────────────────────────────────────────────────────────┐
# │  TAB 6 — COMPARISON                                                      │
# │                                                                          │
# │  Save the current scenario with a user-supplied name.                   │
# │  Saved scenarios displayed as expandable cards showing all key           │
# │  metrics and plots side-by-side for comparison.                          │
# └──────────────────────────────────────────────────────────────────────────┘
# ══════════════════════════════════════════════════════════════════════════════
with tab_compare:
    col_header("Scenario Comparison")

    # ── Save current scenario ─────────────────────────────────────────────────
    section("Save Current Scenario")
    _cmp_name = st.text_input("Scenario name:", placeholder="e.g. Baseline 70 mi radius",
                               key="cmp_name_input")
    _btn_col1, _btn_col2 = st.columns([1, 1], gap="small")
    with _btn_col1:
        save_btn = st.button("Save Scenario", type="primary", key="cmp_save_btn",
                             width="stretch")
    with _btn_col2:
        pdf_btn  = st.button("📄 Export PDF Report", key="cmp_pdf_btn",
                             width="stretch")

    if pdf_btn:
        _sc_pdf = st.session_state.get("sc_results")
        if _sc_pdf is None:
            warn("Nothing to export — run Supply Chain tab first.")
        else:
            _pdf_name = _cmp_name.strip() or "Current Scenario"
            _pdf_snap = {
                "name":         _pdf_name,
                "timestamp":    datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "mode":         "SAF" if IS_SAF else "Bioenergy",
                "sc":           _sc_pdf,
                "tr":           st.session_state.get("tr_results"),
                "be_df":        st.session_state.get("be_df"),
                "be_metrics":   st.session_state.get("be_metrics"),
                "be_lcoe":      st.session_state.get("be_lcoe"),
                "be_TCI":       st.session_state.get("be_TCI"),
                "be_FCI":       st.session_state.get("be_FCI"),
                "be_annual_AC": st.session_state.get("be_annual_AC"),
                "saf_df":       st.session_state.get("saf_df"),
                "saf_metrics":  st.session_state.get("saf_metrics"),
                "saf_mfsp":     st.session_state.get("saf_mfsp"),
                "lca_results":  st.session_state.get("lca_results"),
                "jobs_result":  st.session_state.get("jobs_result"),
                "be_pol_met1":  st.session_state.get("be_pol_met_none"),
                "be_pol_met2":  st.session_state.get("be_pol_met_ptc"),
                "be_pol_met3":  st.session_state.get("be_pol_met_itc"),
                "saf_pol_met1": st.session_state.get("saf_pol_met_none"),
                "saf_pol_met2": st.session_state.get("saf_pol_met_credit"),
                "_map_html":    st.session_state.get("_sc_map_html"),
                "_dir":         _DIR,
                # Transport slider values — needed by report Transport Inputs table
                "tr_obtain_forest":   st.session_state.get("tr_obtain_forest",   100),
                "tr_obtain_mill":     st.session_state.get("tr_obtain_mill",     100),
                "tr_obtain_pulpwood": st.session_state.get("tr_obtain_pulpwood", 100),
                "tr_speed":           st.session_state.get("tr_speed",            20),
                "tr_opt_forest":      st.session_state.get("tr_opt_forest",       "-"),
                "tr_opt_mill":        st.session_state.get("tr_opt_mill",         "-"),
                "tr_opt_pulpwood":    st.session_state.get("tr_opt_pulpwood",     "-"),
                # Total biomass from tr_results for summary card (fallback when LCA not run)
                "total_biomass_odt":  sum(
                    (st.session_state.get("tr_results") or {}).get(k, {}).get("residue_kdry", 0)
                    for k in ("forest", "mill", "pulpwood")
                ) * 1000,
            }
            with st.spinner("Generating PDF report..."):
                try:
                    import Generate_Report as _gr
                    _safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in _pdf_name)
                    _pdf_path  = os.path.join(_DIR, f"report_{_safe_name}.pdf")
                    _lca_png   = os.path.join(_DIR, "LCA_plots", "lca_integrated.png")
                    _avd_png   = os.path.join(_DIR, "LCA_plots", "fhr_net_climate_impact.png")
                    _gr.generate_scenario_pdf(
                        _pdf_snap, _pdf_path,
                        lca_plot_path     = _lca_png if os.path.exists(_lca_png) else None,
                        avoided_plot_path = _avd_png if os.path.exists(_avd_png) else None,
                        saf_plot_mod      = sfm.sp if SAF_AVAILABLE else None,
                        be_plot_mod       = bem    if BEE_AVAILABLE else None,
                    )
                    with open(_pdf_path, "rb") as _pf:
                        st.download_button(
                            "⬇ Download PDF",
                            data=_pf.read(),
                            file_name=f"{_safe_name}_report.pdf",
                            mime="application/pdf",
                            key="cmp_pdf_dl",
                        )
                    st.success(f"PDF ready: **{_pdf_name}**")
                except Exception as _pe:
                    st.error(f"PDF generation failed: {_pe}")
                    import traceback; st.code(traceback.format_exc())

    if save_btn:
        _sc = st.session_state.get("sc_results")
        if _sc is None:
            warn("Nothing to save — run Supply Chain tab first.")
        else:
            _name = _cmp_name.strip() or f"Scenario {len(st.session_state['saved_scenarios'])+1}"
            _snap = {
                "name":         _name,
                "timestamp":    datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "mode":         "SAF" if IS_SAF else "Bioenergy",
                "sc":           _sc,
                "tr":           st.session_state.get("tr_results"),
                # Economics
                "be_df":        st.session_state.get("be_df"),
                "be_metrics":   st.session_state.get("be_metrics"),
                "be_lcoe":      st.session_state.get("be_lcoe"),
                "be_TCI":       st.session_state.get("be_TCI"),
                "be_FCI":       st.session_state.get("be_FCI"),
                "be_annual_AC": st.session_state.get("be_annual_AC"),
                "saf_df":       st.session_state.get("saf_df"),
                "saf_metrics":  st.session_state.get("saf_metrics"),
                "saf_mfsp":     st.session_state.get("saf_mfsp"),
                # Economics inputs — widget keys store display values (pre-division)
                # SAF: percentages stored as e.g. 10.0 (not 0.10)
                "in_saf_year":     st.session_state.get("saf_year",     2025),
                "in_saf_distil":   st.session_state.get("saf_distil",   "distillate 1"),
                "in_saf_life":     st.session_state.get("saf_life",     20),
                "in_saf_disc":     st.session_state.get("saf_disc",     10.0),
                "in_saf_infl":     st.session_state.get("saf_infl",     2.5),
                "in_saf_debt":     st.session_state.get("saf_debt",     70),
                "in_saf_loan_r":   st.session_state.get("saf_loan_r",   8.0),
                "in_saf_loanterm": st.session_state.get("saf_loanterm", 15),
                "in_saf_degr":     st.session_state.get("saf_degr",     0.0),
                "in_saf_cpi":      st.session_state.get("saf_cpi",      321.05),
                "in_saf_safprice": st.session_state.get("saf_safprice", round(1.61*L_PER_GAL,2)),
                "in_saf_dieprice": st.session_state.get("saf_dieprice", round(1.03*L_PER_GAL,2)),
                "in_saf_napprice": st.session_state.get("saf_napprice", round(0.75*L_PER_GAL,2)),
                "in_saf_pesc":     st.session_state.get("saf_pesc",     2.5),
                "in_saf_fesc":     st.session_state.get("saf_fesc",     2.5),
                "in_saf_fedtax":   st.session_state.get("saf_fedtax",   21),
                "in_saf_sttax":    st.session_state.get("saf_sttax",    7),
                # BE: percentages stored as e.g. 7.0 (not 0.07)
                "in_be_cepci":      st.session_state.get("be_cepci",     2030),
                "in_be_life":       st.session_state.get("be_life",      30),
                "in_be_disc":       st.session_state.get("be_disc",      7.0),
                "in_be_infl":       st.session_state.get("be_infl",      2.5),
                "in_be_debt":       st.session_state.get("be_debt",      60),
                "in_be_loan_r":     st.session_state.get("be_loan_r",    6.5),
                "in_be_loan_term":  st.session_state.get("be_loan_term", 15),
                "in_be_degr":       st.session_state.get("be_degr",      0.5),
                "in_be_elec_price": st.session_state.get("be_elec_price",166.0),
                "in_be_f_cost":     st.session_state.get("be_f_cost",    0),
                "in_be_m_cost":     st.session_state.get("be_m_cost",    0),
                "in_be_eesc":       st.session_state.get("be_eesc",      1.0),
                "in_be_fesc":       st.session_state.get("be_fesc",      2.5),
                "in_be_fomesc":     st.session_state.get("be_fomesc",    2.5),
                "in_be_vomesc":     st.session_state.get("be_vomesc",    2.0),
                "in_be_fed":        st.session_state.get("be_fed",       21),
                "in_be_st":         st.session_state.get("be_st",        7),
                # LCA
                "lca_results":  st.session_state.get("lca_results"),
                # Jobs
                "jobs_result":  st.session_state.get("jobs_result"),
                # Policy
                "be_pol_df1":   st.session_state.get("be_pol_df_none"),
                "be_pol_met1":  st.session_state.get("be_pol_met_none"),
                "be_pol_df2":   st.session_state.get("be_pol_df_ptc"),
                "be_pol_met2":  st.session_state.get("be_pol_met_ptc"),
                "be_pol_df3":   st.session_state.get("be_pol_df_itc"),
                "be_pol_met3":  st.session_state.get("be_pol_met_itc"),
                "saf_pol_df1":  st.session_state.get("saf_pol_df_none"),
                "saf_pol_met1": st.session_state.get("saf_pol_met_none"),
                "saf_pol_df2":  st.session_state.get("saf_pol_df_credit"),
                "saf_pol_met2": st.session_state.get("saf_pol_met_credit"),
                # Saved plot paths
                "_plot_lca":     os.path.join(_DIR, "LCA_plots", "lca_integrated.png"),
                "_plot_avoided": os.path.join(_DIR, "LCA_plots", "fhr_net_climate_impact.png"),
                "_plot_jobs":    os.path.join(_DIR, "Jobscreation_plots", "plot_jobs.png"),
                "_plot_policy":  os.path.join(_DIR, "Policy_plots", "policy_comparison.png"),
                "_map_html":     st.session_state.get("_sc_map_html"),
                "_dir":          _DIR,
            }
            st.session_state["saved_scenarios"].append(_snap)
            st.success(f"Saved: **{_name}**  ({_snap['timestamp']})")

    # ── Load saved scenarios ──────────────────────────────────────────────────
    saved = st.session_state.get("saved_scenarios", [])

    if not saved:
        info("No scenarios saved yet. Run an analysis then click <b>Save Scenario</b>.")
    else:
        _sa1, _sa2 = st.columns([6, 1])
        with _sa1:
            st.markdown(f"**{len(saved)} saved scenario(s)**")
        with _sa2:
            if st.button("Clear All", key="cmp_clear"):
                st.session_state["saved_scenarios"] = []
                st.rerun()

        # ══════════════════════════════════════════════════════════════════════
        # SECTION 1 — METRICS TABLE (unlimited scenarios)
        # ══════════════════════════════════════════════════════════════════════
        section("All Scenarios — Metrics Table")

        def _safe(d, *keys, fmt=None, scale=1, default="—"):
            """Safely drill into nested dict and optionally format."""
            v = d
            for k in keys:
                if not isinstance(v, dict): return default
                v = v.get(k)
                if v is None: return default
            try:
                v = float(v) * scale
                return fmt.format(v) if fmt else v
            except Exception:
                return str(v) if v is not None else default

        _rows = []
        for _s in saved:
            _r = {"Name": _s["name"], "Mode": _s["mode"], "Saved": _s["timestamp"]}

            # Supply chain
            _r["Forest (k dry US ton/yr)"] = _safe(_s,"sc","forest","total_kdry", fmt="{:.1f}", scale=METRIC_TON_TO_US_TON)
            _r["Mill (k dry US ton/yr)"]   = _safe(_s,"sc","mill",  "total_kdry", fmt="{:.1f}", scale=METRIC_TON_TO_US_TON)
            if _s["mode"] == "SAF":
                _r["Pulpwood (k dry US ton/yr)"]   = _safe(_s,"sc","pulpwood",  "total_kdry", fmt="{:.1f}", scale=METRIC_TON_TO_US_TON)
            _r["Forest Dist (mi)"]  = _safe(_s,"sc","forest","dist_mi",    fmt="{:.0f}")

            # Transport
            _r["Forest $/ODT"]  = _safe(_s,"tr","forest",  "cost_odt", fmt="${:.2f}")
            _r["Mill $/ODT"]    = _safe(_s,"tr","mill",    "cost_odt", fmt="${:.2f}")
            if _s["mode"]=="SAF":
                _r["Pulpwood $/ODT"]    = _safe(_s,"tr","pulpwood",    "cost_odt", fmt="${:.2f}")

            # Economics
            if _s["mode"] == "Bioenergy" and _s.get("be_metrics"):
                _m  = _s["be_metrics"]
                _irr = _m.get("Equity IRR", float("nan"))
                _pb  = _m.get("Payback Period (years)")
                _r["NPV ($M)"]     = f"${_m.get('NPV (Equity, Nominal)',0)/1e6:.2f}M"
                _r["IRR"]          = f"{_irr*100:.1f}%" if not np.isnan(_irr) else "N/A"
                _r["Payback (yr)"] = f"{_pb:.1f}" if _pb else "Never"
                _r["TCI ($M)"]     = f"${_s.get('be_TCI',0)/1e6:.1f}M"
                _lv = _s.get("be_lcoe")
                if _lv:
                    _lv = _lv if isinstance(_lv, float) else _lv.get("LCOE ($/MWh)", 0)
                    _r["LCOE ($/MWh)"] = f"${_lv:.2f}"
            elif _s["mode"] == "SAF" and _s.get("saf_metrics"):
                _m  = _s["saf_metrics"]
                _irr = _m.get("Equity IRR", float("nan"))
                _pb  = _m.get("Payback Period (years)")
                _r["NPV ($M)"]     = f"${_m.get('NPV (Equity, Nominal)',0)/1e6:.2f}M"
                _r["IRR"]          = f"{_irr*100:.1f}%" if not np.isnan(_irr) else "N/A"
                _r["Payback (yr)"] = f"{_pb:.1f}" if _pb else "Never"
                _r["TCI ($M)"]     = f"${_m.get('Total Capital Investment (TCI)',0)/1e6:.1f}M"
                if _s.get("saf_mfsp"):
                    _r["MFSP SAF ($/gal)"] = f"${_s['saf_mfsp']['MFSP SAF ($/L)']*L_PER_GAL:.4f}"

            # LCA
            if _s.get("lca_results"):
                _lca = _s["lca_results"]
                def _tot_co2e(r):
                    if not r: return None
                    return r.get("bioCO2_t",0)+r.get("fossCO2_t",0)+r.get("CH4_CO2e",0)+r.get("N2O_CO2e",0)
                if _lca.get("mode") == "SAF":
                    _v = _tot_co2e(_lca.get("saf_prod"))
                    _r["SAF CO2e (US ton/yr)"] = f"{_v*METRIC_TON_TO_US_TON/1000:.1f}k" if _v else "—"
                else:
                    _v = _tot_co2e(_lca.get("bio_prod"))
                    _r["Bio CO2e (US ton/yr)"] = f"{_v*METRIC_TON_TO_US_TON/1000:.1f}k" if _v else "—"

            # Jobs
            if _s.get("jobs_result"):
                _j = _s["jobs_result"]
                _r["Total Jobs"] = _j.get("total_jobs", "—")

            # Policy
            if _s["mode"] == "Bioenergy":
                for _plbl, _pkey in [("No-Pol NPV","be_pol_met1"),("PTC NPV","be_pol_met2"),("ITC NPV","be_pol_met3")]:
                    _pm = _s.get(_pkey)
                    if _pm:
                        _pv = _pm.get("NPV (Equity, Nominal)",0)
                        _r[_plbl] = f"${_pv/1e6:.2f}M"
            elif _s["mode"] == "SAF":
                for _plbl, _pkey in [("No-Pol NPV","saf_pol_met1"),("45Z NPV","saf_pol_met2")]:
                    _pm = _s.get(_pkey)
                    if _pm:
                        _pv = _pm.get("NPV (Equity, Nominal)",0)
                        _r[_plbl] = f"${_pv/1e6:.2f}M"

            _rows.append(_r)

        _cmp_df = pd.DataFrame(_rows).set_index("Name")
        st.dataframe(_cmp_df, width="stretch",
                     height=min(600, 45 * len(_rows) + 45))
        st.download_button("⬇ Download CSV",
                           _cmp_df.reset_index().to_csv(index=False).encode(),
                           "scenario_comparison.csv", "text/csv", key="dl_csv")

        # ══════════════════════════════════════════════════════════════════════
        # SECTION 2 — PLOT COMPARISON (max 3 scenarios, user picks which)
        # ══════════════════════════════════════════════════════════════════════
        section("Visual Comparison — Select Up to 3 Scenarios")

        _scen_names = [_s["name"] for _s in saved]
        _sel_names  = st.multiselect(
            "Select up to 3 scenarios to compare visually:",
            _scen_names,
            default=_scen_names[:min(3, len(_scen_names))],
            max_selections=3,
            key="cmp_sel_scenarios",
        )
        _sel = [_s for _s in saved if _s["name"] in _sel_names]

        if not _sel:
            info("Select at least one scenario above to see plots.")
        else:
            _nc    = len(_sel)
            _accents = ["#4ade80","#60a5fa","#f59e0b"]

            # Helper: get a plot figure or None safely
            def _get_fig(fn, *args):
                try: return fn(*args)
                except Exception: return None

            # Pre-import plot functions once
            try:
                from Bioenergy_dependencies.bioenergy_plots_FINAL import (
                    plot_cumulative_cashflow as _be_cum,
                    plot_annual_cashflow     as _be_ann,
                    plot_opex_pie            as _be_pie,
                    plot_debt_service        as _be_dbt,
                )
            except Exception: _be_cum=_be_ann=_be_pie=_be_dbt=None
            try:
                from SAF_dependencies.SAF_plots_FINAL import (
                    plot_cumulative_cashflow as _saf_cum,
                    plot_annual_cashflow     as _saf_ann,
                    plot_opex_pie            as _saf_pie,
                    plot_debt_service        as _saf_dbt,
                    plot_generation          as _saf_gen,
                )
            except Exception: _saf_cum=_saf_ann=_saf_pie=_saf_dbt=_saf_gen=None
            try:
                import Jobscreation as _jm
            except Exception: _jm = None

            # ── ROW 0: Headers + metric cards ────────────────────────────────
            _hcols = st.columns(_nc, gap="medium")
            for _ci, (_col, _s) in enumerate(zip(_hcols, _sel)):
                _i = saved.index(_s)
                with _col:
                    _acc = _accents[_ci % 3]
                    st.markdown(
                        f'<div style="background:#0f1826;border:1px solid #2a3a4a;'
                        f'border-top:3px solid {_acc};border-radius:5px;'
                        f'padding:8px 10px;margin-bottom:6px">'
                        f'<div style="font-size:0.95rem;font-weight:700;color:{_acc}">'
                        f'{_s["name"]}</div>'
                        f'<div style="font-size:0.9rem;color:#4a5a6a">'
                        f'{_s["mode"]} · {_s["timestamp"]}</div></div>',
                        unsafe_allow_html=True
                    )
                    # Economics cards
                    if _s["mode"] == "Bioenergy" and _s.get("be_metrics"):
                        _m=_s["be_metrics"]; _irr=_m.get("Equity IRR",float("nan"))
                        _pb=_m.get("Payback Period (years)"); _npv=_m.get("NPV (Equity, Nominal)",0)
                        st.markdown(mc("NPV",f"${_npv/1e6:.2f}M","","mc-neg" if _npv<0 else ""),unsafe_allow_html=True)
                        st.markdown(mc("IRR",f"{_irr*100:.1f}%" if not np.isnan(_irr) else "N/A"),unsafe_allow_html=True)
                        st.markdown(mc("Payback",f"{_pb:.1f} yr" if _pb else "Never","","mc-warn" if not _pb else ""),unsafe_allow_html=True)
                        _lv=_s.get("be_lcoe")
                        if _lv:
                            _lv=_lv if isinstance(_lv,float) else _lv.get("LCOE ($/MWh)",0)
                            st.markdown(mc("LCOE",f"${_lv:.2f}","$/MWh"),unsafe_allow_html=True)
                    elif _s["mode"] == "SAF" and _s.get("saf_metrics"):
                        _m=_s["saf_metrics"]; _irr=_m.get("Equity IRR",float("nan"))
                        _pb=_m.get("Payback Period (years)"); _npv=_m.get("NPV (Equity, Nominal)",0)
                        st.markdown(mc("NPV",f"${_npv/1e6:.2f}M","","mc-neg" if _npv<0 else ""),unsafe_allow_html=True)
                        st.markdown(mc("IRR",f"{_irr*100:.1f}%" if not np.isnan(_irr) else "N/A"),unsafe_allow_html=True)
                        st.markdown(mc("Payback",f"{_pb:.1f} yr" if _pb else "Never","","mc-warn" if not _pb else ""),unsafe_allow_html=True)
                        if _s.get("saf_mfsp"):
                            st.markdown(mc("MFSP SAF",f"${_s['saf_mfsp']['MFSP SAF ($/L)']*L_PER_GAL:.4f}","$/gal"),unsafe_allow_html=True)
                    # LCA card
                    if _s.get("lca_results"):
                        _lca=_s["lca_results"]
                        def _co2e_tot(r):
                            return (r or {}).get("bioCO2_t",0)+(r or {}).get("fossCO2_t",0)+(r or {}).get("CH4_CO2e",0)+(r or {}).get("N2O_CO2e",0)
                        if _lca.get("mode")=="SAF" and _lca.get("saf_prod"):
                            st.markdown(mc("SAF CO₂e",f"{_co2e_tot(_lca['saf_prod'])*METRIC_TON_TO_US_TON/1000:.1f} k US ton/yr","production"),unsafe_allow_html=True)
                        elif _lca.get("bio_prod"):
                            st.markdown(mc("Bio CO₂e",f"{_co2e_tot(_lca['bio_prod'])*METRIC_TON_TO_US_TON/1000:.1f} k US ton/yr","combustion"),unsafe_allow_html=True)
                    # Jobs card
                    if _s.get("jobs_result"):
                        _j=_s["jobs_result"]
                        st.markdown(mc("Total Jobs",str(_j.get("total_jobs","—")),f"Direct {_j.get('direct_jobs','—')} | Indirect {_j.get('indirect_jobs','—')}"),unsafe_allow_html=True)
                    # Policy cards
                    if _s["mode"]=="Bioenergy":
                        for _pl,_pk in [("PTC NPV","be_pol_met2"),("ITC NPV","be_pol_met3")]:
                            _pm=_s.get(_pk)
                            if _pm: st.markdown(mc(_pl,f"${_pm.get('NPV (Equity, Nominal)',0)/1e6:.2f}M","","mc-neg" if _pm.get('NPV (Equity, Nominal)',0)<0 else ""),unsafe_allow_html=True)
                    elif _s["mode"]=="SAF":
                        _pm2=_s.get("saf_pol_met2")
                        if _pm2: st.markdown(mc("45Z NPV",f"${_pm2.get('NPV (Equity, Nominal)',0)/1e6:.2f}M","","mc-neg" if _pm2.get('NPV (Equity, Nominal)',0)<0 else ""),unsafe_allow_html=True)
                    # Delete
                    if st.button("🗑 Delete", key=f"del_{_i}_{_s['name']}"):
                        st.session_state["saved_scenarios"].pop(_i); st.rerun()

            # ── ROW 1: Cumulative Cash Flow ───────────────────────────────────
            section("Cumulative Cash Flow")
            _r1 = st.columns(_nc, gap="medium")
            for _col, _s in zip(_r1, _sel):
                with _col:
                    if _s["mode"]=="Bioenergy" and _s.get("be_df") is not None and _be_cum:
                        render_pyplot_safe(_get_fig(_be_cum, _s["be_df"], _s["be_metrics"]))
                    elif _s["mode"]=="SAF" and _s.get("saf_df") is not None and _saf_cum:
                        render_pyplot_safe(_get_fig(_saf_cum, _s["saf_df"], _s["saf_metrics"]))
                    else: st.caption("No data")

            # ── ROW 2: Annual Cash Flow ───────────────────────────────────────
            section("Annual Cash Flow")
            _r2 = st.columns(_nc, gap="medium")
            for _col, _s in zip(_r2, _sel):
                with _col:
                    if _s["mode"]=="Bioenergy" and _s.get("be_df") is not None and _be_ann:
                        render_pyplot_safe(_get_fig(_be_ann, _s["be_df"], _s["be_metrics"]))
                    elif _s["mode"]=="SAF" and _s.get("saf_df") is not None and _saf_ann:
                        render_pyplot_safe(_get_fig(_saf_ann, _s["saf_df"], _s["saf_metrics"]))
                    else: st.caption("No data")

            # ── ROW 3: OPEX Breakdown ─────────────────────────────────────────
            section("OPEX Breakdown")
            _r3 = st.columns(_nc, gap="medium")
            for _col, _s in zip(_r3, _sel):
                with _col:
                    if _s["mode"]=="Bioenergy" and _s.get("be_df") is not None and _be_pie:
                        render_pyplot_safe(_get_fig(_be_pie, _s["be_df"], _s["be_metrics"]))
                    elif _s["mode"]=="SAF" and _s.get("saf_df") is not None and _saf_pie:
                        render_pyplot_safe(_get_fig(_saf_pie, _s["saf_df"], _s["saf_metrics"]))
                    else: st.caption("No data")

            # ── ROW 4: Debt Service ───────────────────────────────────────────
            section("Debt Service")
            _r4 = st.columns(_nc, gap="medium")
            for _col, _s in zip(_r4, _sel):
                with _col:
                    if _s["mode"]=="Bioenergy" and _s.get("be_df") is not None and _be_dbt:
                        render_pyplot_safe(_get_fig(_be_dbt, _s["be_df"], _s["be_metrics"]))
                    elif _s["mode"]=="SAF" and _s.get("saf_df") is not None and _saf_dbt:
                        render_pyplot_safe(_get_fig(_saf_dbt, _s["saf_df"], _s["saf_metrics"]))
                    else: st.caption("No data")

            # ── ROW 5: Production (Fuel Generation / Electricity) ────────────
            section("Production Output")
            _r5 = st.columns(_nc, gap="medium")
            for _col, _s in zip(_r5, _sel):
                with _col:
                    if _s["mode"]=="SAF" and _s.get("saf_df") is not None and _saf_gen:
                        render_pyplot_safe(_get_fig(_saf_gen, _s["saf_df"], _s["saf_metrics"]))
                    elif _s["mode"]=="Bioenergy" and _s.get("be_df") is not None:
                        try:
                            from Bioenergy_dependencies.bioenergy_plots_FINAL import plot_generation as _be_gen
                            render_pyplot_safe(_get_fig(_be_gen, _s["be_df"], _s["be_metrics"]))
                        except Exception: st.caption("No generation plot")
                    else: st.caption("No data")

            # ── ROW 5b: LCA Emissions (if saved) ─────────────────────────────
            _has_lca = any(_s.get("lca_results") is not None for _s in _sel)
            if _has_lca:
                section("LCA Emissions by Stage")
                _r5b = st.columns(_nc, gap="medium")
                for _col, _s in zip(_r5b, _sel):
                    with _col:
                        if _s.get("lca_results"):
                            _lca_s = _s["lca_results"]
                            try:
                                _zero_r = {"bioCO2_t":0,"fossCO2_t":0,"CH4_CO2e":0,"N2O_CO2e":0}
                                if _lca_s.get("mode") == "SAF" and _lca_s.get("saf_prod"):
                                    _stg = [("Processing", _lca_s["proc_saf"]),
                                            ("Transport",  _lca_s["trans_saf"]),
                                            ("SAF\nProduction", _lca_s["saf_prod"])]
                                else:
                                    _stg = [("Processing",  _lca_s.get("proc_bio", _zero_r)),
                                            ("Transport",   _lca_s.get("trans_bio", _zero_r)),
                                            ("Bioenergy\nProduction", _lca_s.get("bio_prod", _zero_r) or _zero_r)]
                                _fig_cmp = _make_lca_stage_fig(
                                    _stg, _lca_s.get("mode",""), _lca_s.get("total_odt", 0)
                                )
                                render_pyplot_safe(_fig_cmp)
                                plt.close(_fig_cmp)
                            except Exception as _le2: st.caption("LCA plot: "+str(_le2))
                        else: st.caption("No LCA data")

            # ── ROW 5c: Avoided Emissions (if LCA saved) ─────────────────────
            if _has_lca:
                section("Avoided Emissions Analysis")
                _r5c = st.columns(_nc, gap="medium")
                for _col, _s in zip(_r5c, _sel):
                    with _col:
                        if _s.get("lca_results"):
                            _lca_s = _s["lca_results"]
                            try:
                                def _nb_cmp(r):
                                    return (r or {}).get("fossCO2_t",0)+(r or {}).get("CH4_CO2e",0)+(r or {}).get("N2O_CO2e",0)
                                _tot_odt = _lca_s.get("total_odt", 0)
                                _burn_bl_c = _tot_odt * 1000 * 0.143 / 1000
                                _is_saf_c = _lca_s.get("mode") == "SAF"
                                if _is_saf_c:
                                    _proj_nb_c = (_nb_cmp(_lca_s.get("proc_saf")) +
                                                  _nb_cmp(_lca_s.get("trans_saf")) +
                                                  _nb_cmp(_lca_s.get("saf_prod")))
                                    _groups_c = [
                                        ("Open\nBurning", _burn_bl_c, _proj_nb_c, "#e76f51"),
                                    ]
                                    # Add fossil JF if SAF_MJ available
                                    _sr = _lca_s.get("sr")
                                    if _sr and isinstance(_sr, dict) and "SAF_MJ_yr" in _sr:
                                        _fj_c = 15.93 * _sr["SAF_MJ_yr"] / 1e6
                                        _groups_c.append(("Fossil JF", _fj_c, _proj_nb_c, "#378ADD"))
                                else:
                                    _proj_nb_c = (_nb_cmp(_lca_s.get("proc_bio")) +
                                                  _nb_cmp(_lca_s.get("trans_bio")) +
                                                  _nb_cmp(_lca_s.get("bio_prod")))
                                    _groups_c = [
                                        ("Open\nBurning", _burn_bl_c, _proj_nb_c, "#e76f51"),
                                    ]

                                _ef3, _ea3 = plt.subplots(figsize=(5, 4))
                                _ef3.patch.set_facecolor("#0e1621"); _ea3.set_facecolor("#131e2d")
                                _gw_c = 0.28; _gap_c = 0.08; _grp_w_c = 2*_gw_c+_gap_c+0.3
                                _grp_xs_c = [i * _grp_w_c for i in range(len(_groups_c))]
                                _all_c = [v for g in _groups_c for v in [g[1], g[2]]]
                                _mx_c = max(_all_c) if _all_c else 1
                                _scaled_mx_c = _mx_c * METRIC_TON_TO_US_TON
                                _ea3.set_ylim(0, _scaled_mx_c * 1.45)
                                for gi_c, (lbl_c, bl_c, pj_c, col_c) in enumerate(_groups_c):
                                    scaled_bl_c = bl_c * METRIC_TON_TO_US_TON
                                    scaled_pj_c = pj_c * METRIC_TON_TO_US_TON

                                    _cx_c = _grp_xs_c[gi_c]
                                    _bx_c = _cx_c - (_gw_c/2 + _gap_c/2)
                                    _px_c = _cx_c + (_gw_c/2 + _gap_c/2)

                                    _ea3.bar(_bx_c, scaled_bl_c, _gw_c, color=col_c, alpha=0.55,
                                            hatch="////", edgecolor=col_c, linewidth=0.8)
                                    _ea3.bar(_px_c, scaled_pj_c, _gw_c, color="#22c55e", alpha=0.9, edgecolor="none")

                                    _ea3.text(_bx_c, scaled_bl_c + _scaled_mx_c*0.02, f"{scaled_bl_c:,.0f}",
                                            ha="center", fontsize=7, fontweight="bold", color="#f0f4f8")
                                    _ea3.text(_px_c, scaled_pj_c + _scaled_mx_c*0.02, f"{scaled_pj_c:,.0f}",
                                            ha="center", fontsize=7, fontweight="bold", color="#f0f4f8")
                                    _pct_c = (bl_c - pj_c) / bl_c * 100 if bl_c else 0

                                    _ea3.text(_cx_c, max(scaled_bl_c, scaled_pj_c) + _scaled_mx_c*0.12,
                                            f"\u2193{_pct_c:.1f}%", ha="center", fontsize=8,
                                            fontweight="bold", color="#a3e635")
                                    
                                    _ea3.text(_cx_c, -_scaled_mx_c*0.10, lbl_c, ha="center",
                                            va="top", fontsize=8, color="#c8d8e8")
                                _ea3.set_xlim(-0.5, _grp_xs_c[-1]+0.6)
                                _ea3.set_xticks([])

                                _ea3.set_ylabel("US ton CO\u2082e / yr", fontsize=8, color="#c8d8e8")
                                _ea3.set_title(f"Avoided Emissions — {_s['name']}\n(non-biogenic only)",
                                               fontsize=8, color="#e8f0f8")
                                _ea3.spines[["top","right"]].set_visible(False)
                                _ea3.spines[["left","bottom"]].set_color("#2a3a4a")
                                _ea3.tick_params(colors="#c8d8e8")
                                _ea3.grid(axis="y", color="#1e2d3d", linewidth=0.6)
                                from matplotlib.patches import Patch as _P
                                _ea3.legend(handles=[
                                    _P(facecolor="grey", alpha=0.55, hatch="////", edgecolor="grey", label="Baseline"),
                                    _P(color="#22c55e", label="This project"),
                                ], fontsize=7, facecolor="#0e1621", edgecolor="#2a3a4a", labelcolor="#c8d8e8")
                                plt.tight_layout(); render_pyplot_safe(_ef3)
                            except Exception as _le3: st.caption("Avoided plot: "+str(_le3))
                        else: st.caption("No LCA data")

            # ── ROW 6: Employment ─────────────────────────────────────────────
            # Inline per-scenario chart — avoids plot_job_breakdown overwriting
            # a shared PNG, which also caused the wrong scenario name to appear.
            section("Employment")
            _r6 = st.columns(_nc, gap="medium")
            for _col, _s in zip(_r6, _sel):
                with _col:
                    _jr = _s.get("jobs_result")
                    if _jr:
                        try:
                            _jf2, _ja2 = plt.subplots(figsize=(5, 4))
                            _jf2.patch.set_facecolor("#0e1621")
                            _ja2.set_facecolor("#131e2d")
                            _jv = [_jr.get("direct_jobs",0), _jr.get("indirect_jobs",0), _jr.get("induced_jobs",0)]
                            _jl = ["Direct","Indirect","Induced"]
                            _jc = ["#1D9E75","#378ADD","#e76f51"]
                            _jbr = _ja2.bar(_jl, _jv, color=_jc, width=0.5, edgecolor="#0e1621", linewidth=0.8)
                            _jmx = max(_jv) if max(_jv) > 0 else 1
                            for b, v in zip(_jbr, _jv):
                                _ja2.text(b.get_x()+b.get_width()/2, v+_jmx*0.02, str(v),
                                          ha="center", va="bottom", fontsize=9, fontweight="bold", color="#f0f4f8")
                            _ja2.set_title("Jobs — " + _s["name"], fontsize=9, color="#e8f0f8")
                            _ja2.set_ylabel("Jobs Created", fontsize=9, color="#c8d8e8")
                            _ja2.spines[["top","right"]].set_visible(False)
                            _ja2.spines[["left","bottom"]].set_color("#2a3a4a")
                            _ja2.tick_params(colors="#c8d8e8")
                            _ja2.grid(axis="y", color="#1e2d3d", linewidth=0.6)
                            plt.tight_layout()
                            render_pyplot_safe(_jf2)
                        except Exception as _je2:
                            st.caption("Jobs plot: " + str(_je2))
                    else: st.caption("No jobs data")

            # ── ROW 7: Policy — No Policy Cumulative CF ───────────────────────
            _has_pol = any(_s.get("be_pol_df1") is not None or _s.get("saf_pol_df1") is not None for _s in _sel)
            if _has_pol:
                section("Policy — Cumulative CF (No Policy Baseline)")
                _r7 = st.columns(_nc, gap="medium")
                for _col, _s in zip(_r7, _sel):
                    with _col:
                        if _s["mode"]=="Bioenergy" and _s.get("be_pol_df1") is not None and _be_cum:
                            render_pyplot_safe(_get_fig(_be_cum, _s["be_pol_df1"], _s["be_pol_met1"]))
                        elif _s["mode"]=="SAF" and _s.get("saf_pol_df1") is not None and _saf_cum:
                            render_pyplot_safe(_get_fig(_saf_cum, _s["saf_pol_df1"], _s["saf_pol_met1"]))
                        else: st.caption("No policy data")

            # ── ROW 8: Policy — With-Credit Cumulative CF ─────────────────────
            _has_pol2 = any(_s.get("be_pol_df2") is not None or _s.get("saf_pol_df2") is not None for _s in _sel)
            if _has_pol2:
                section("Policy — Cumulative CF (With Credit)")
                _r8 = st.columns(_nc, gap="medium")
                for _col, _s in zip(_r8, _sel):
                    with _col:
                        if _s["mode"]=="Bioenergy" and _s.get("be_pol_df2") is not None and _be_cum:
                            render_pyplot_safe(_get_fig(_be_cum, _s["be_pol_df2"], _s["be_pol_met2"]))
                        elif _s["mode"]=="SAF" and _s.get("saf_pol_df2") is not None and _saf_cum:
                            render_pyplot_safe(_get_fig(_saf_cum, _s["saf_pol_df2"], _s["saf_pol_met2"]))
                        else: st.caption("No policy data")
