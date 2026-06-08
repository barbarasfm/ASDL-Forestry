"""
GREEN TEA LCA — Scenario PDF Report
Uses existing saved PNGs (LCA, avoided, jobs, policy).
Captures the Folium supply chain map via Playwright.
All economics inputs read from session state keys stored in snap.
"""
import os, io, datetime, warnings
warnings.filterwarnings("ignore")

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, PageBreak,
)
from reportlab.lib.utils import ImageReader

L_PER_GAL = 3.78541
PW  = letter[0] - 1.4 * inch   # 7.1 in
HW  = PW / 2 - 0.06 * inch

C_DARK  = colors.HexColor("#1a2a3a")
C_MID   = colors.HexColor("#2e4a6a")
C_LIGHT = colors.HexColor("#dde6ef")
C_PALE  = colors.HexColor("#f4f8fb")

def _mk_styles():
    b = getSampleStyleSheet()
    return {
        "title":   ParagraphStyle("T",  parent=b["Title"],   fontSize=22, textColor=C_DARK,
                                   alignment=TA_CENTER, spaceAfter=4),
        "sub":     ParagraphStyle("S",  parent=b["Normal"],  fontSize=10, textColor=C_MID,
                                   alignment=TA_CENTER, spaceAfter=3),
        "h1":      ParagraphStyle("H1", parent=b["Heading1"],fontSize=12, textColor=C_DARK,
                                   spaceBefore=12, spaceAfter=3, leading=15),
        "h2":      ParagraphStyle("H2", parent=b["Heading2"],fontSize=10, textColor=C_MID,
                                   spaceBefore=7, spaceAfter=2, leading=13),
        "cell":    ParagraphStyle("C",  parent=b["Normal"],  fontSize=8,  leading=10, alignment=TA_CENTER),
        "celll":   ParagraphStyle("CL", parent=b["Normal"],  fontSize=8,  leading=10),
        "note":    ParagraphStyle("N",  parent=b["Normal"],  fontSize=8,  textColor=C_MID,
                                   leading=11, leftIndent=8, spaceAfter=4),
        "caption": ParagraphStyle("CA", parent=b["Normal"],  fontSize=7.5, textColor=colors.grey,
                                   alignment=TA_CENTER, spaceAfter=6),
        "footer":  ParagraphStyle("F",  parent=b["Normal"],  fontSize=7,  textColor=colors.grey,
                                   alignment=TA_CENTER),
    }

S = _mk_styles()

def _hr(st): st.append(HRFlowable(width="100%", thickness=0.6, color=C_LIGHT, spaceAfter=3, spaceBefore=1))
def _sp(st, h=0.08): st.append(Spacer(1, h * inch))
def _pb(st): st.append(PageBreak())
def _sh(st, text, n): st.append(Paragraph(f"{n}. {text}", S["h1"])); _hr(st)
def _v(d, k, default=0): return (d or {}).get(k, default)
def _ss_read(snap, key, default):
    """Read widget value: direct key -> _ss sub-dict -> default."""
    if key in snap: return snap[key]
    ss = snap.get("_ss") or {}
    return ss.get(key, default)
def _nb(r): return (r or {}).get("fossCO2_t",0)+(r or {}).get("CH4_CO2e",0)+(r or {}).get("N2O_CO2e",0)
def _bio(r): return (r or {}).get("bioCO2_t",0)
def _tot(r): return _bio(r)+_nb(r)

def _tbl(rows, cw=None, hrows=1, bold_last=False):
    t = Table(rows, colWidths=cw, repeatRows=hrows)
    cmds = [
        ("FONTNAME",     (0,0),(-1,hrows-1), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0),(-1,-1), 8.5), ("LEADING",(0,0),(-1,-1), 11),
        ("BACKGROUND",   (0,0),(-1,hrows-1), C_LIGHT), ("TEXTCOLOR",(0,0),(-1,hrows-1), C_DARK),
        ("GRID",         (0,0),(-1,-1), 0.35, colors.HexColor("#b8c8d8")),
        ("ROWBACKGROUNDS",(0,hrows),(-1,-1), [colors.white, C_PALE]),
        ("ALIGN",        (0,0),(-1,-1), "CENTER"), ("ALIGN",(0,0),(0,-1), "LEFT"),
        ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
        ("LEFTPADDING",  (0,0),(-1,-1), 5), ("RIGHTPADDING",(0,0),(-1,-1), 5),
        ("TOPPADDING",   (0,0),(-1,-1), 3), ("BOTTOMPADDING",(0,0),(-1,-1), 3),
    ]
    if bold_last:
        cmds += [("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
                 ("BACKGROUND",(0,-1),(-1,-1),C_LIGHT)]
    t.setStyle(TableStyle(cmds))
    return t

def _two_col(left, right):
    t = Table([[left, right]], colWidths=[HW+0.06*inch, HW+0.06*inch])
    t.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                            ("LEFTPADDING",(0,0),(-1,-1),0),
                            ("RIGHTPADDING",(0,0),(-1,-1),0)]))
    return t

def _png(path, width=None):
    """Load PNG to ReportLab Image, maintaining aspect ratio."""
    if not path or not os.path.exists(path): return None
    w = width or PW
    try:
        from PIL import Image as PI
        with PI.open(path) as im: iw, ih = im.size
        return Image(path, width=w, height=w*ih/iw)
    except Exception:
        return Image(path, width=w, height=w*7/9)

def _map_screenshot(html_path, out_png, width=1100, height=520):
    """
    Render the supply-chain map from a Folium HTML file using matplotlib.

    Playwright/screenshot cannot work here: every CDN request (Leaflet, jQuery,
    Bootstrap) fails with ERR_NAME_NOT_RESOLVED because the environment has no
    network egress, leaving the map div transparent and the PNG blank (2830 B).
    Instead we parse the embedded JavaScript to extract L.circleMarker,
    L.polyline, and L.circle data and re-draw with matplotlib.
    """
    if not html_path or not os.path.exists(html_path):
        return None
    try:
        import re, math
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        html = open(html_path, encoding="utf-8", errors="replace").read()

        # County supply markers
        markers = []
        for lat, lon, opts in re.findall(
                r'L\.circleMarker\(\s*\[([0-9.\-]+),\s*([0-9.\-]+)\],\s*(\{[^}]+\})',
                html, re.DOTALL):
            color  = re.search(r'"color":\s*"([^"]+)"', opts)
            radius = re.search(r'"radius":\s*([0-9.]+)', opts)
            markers.append(dict(lat=float(lat), lon=float(lon),
                                color=color.group(1) if color else '#ffffff',
                                radius=float(radius.group(1)) if radius else 5.0))

        # Transport routes
        polylines = []
        for pts_str, opts in re.findall(
                r'L\.polyline\(\s*(\[\[.*?\]\]),\s*(\{[^}]*\})', html, re.DOTALL):
            color  = re.search(r'"color":\s*"([^"]+)"', opts)
            coords = re.findall(r'\[([0-9.\-]+),\s*([0-9.\-]+)\]', pts_str)
            polylines.append(dict(color=color.group(1) if color else '#ffffff',
                                  coords=[(float(a), float(b)) for a, b in coords]))

        # Search-radius boundary circle
        clat, clon, crad = 31.6, -81.9, 112654.0
        cm = re.search(r'L\.circle\(\s*\[([0-9.\-]+),\s*([0-9.\-]+)\],\s*\{([^}]*)\}', html)
        if cm:
            clat, clon = float(cm.group(1)), float(cm.group(2))
            rm = re.search(r'"radius":\s*([0-9.]+)', cm.group(3))
            if rm: crad = float(rm.group(1))

        # Mill marker
        mm = re.search(r'L\.marker\(\s*\[([0-9.\-]+),\s*([0-9.\-]+)\]', html)
        mill_lat = float(mm.group(1)) if mm else clat
        mill_lon = float(mm.group(2)) if mm else clon

        if not markers:
            return None

        fig, ax = plt.subplots(figsize=(9.5, 5.4), facecolor='#0e1117')
        ax.set_facecolor('#1a2535')

        for pl in polylines:
            lats = [c[0] for c in pl['coords']]
            lons = [c[1] for c in pl['coords']]
            ax.plot(lons, lats, color=pl['color'], linewidth=1.4, alpha=0.75, zorder=3)

        deg_lat = crad / 111320.0
        deg_lon = crad / (111320.0 * math.cos(math.radians(clat)))
        theta   = np.linspace(0, 2 * math.pi, 360)
        ax.plot(clon + deg_lon * np.cos(theta),
                clat + deg_lat * np.sin(theta),
                color='#4ade80', linewidth=1.2, linestyle='--', alpha=0.65, zorder=4)

        # Draw markers: green = solid fill, amber/blue = hollow rings
        _SOLID_COLORS  = {'#22c55e'}          # forest residue
        _RING_COLORS   = {'#f59e0b', '#60a5fa'}  # sawmill, pulpwood
        for m in markers:
            sz = max(25, m['radius'] ** 2 * 4.5)
            if m['color'] in _SOLID_COLORS:
                ax.scatter(m['lon'], m['lat'], s=sz, c=m['color'],
                           edgecolors='white', linewidths=0.5, alpha=0.88, zorder=5)
            else:
                # Hollow ring: facecolor='none', thick coloured edge
                ax.scatter(m['lon'], m['lat'], s=sz, facecolors='none',
                           edgecolors=m['color'], linewidths=2.5, alpha=0.90, zorder=5)

        # Extract mill name from Folium marker tooltip.
        # Folium writes: var marker_xxx = L.marker(...) then marker_xxx.bindTooltip(`<div>Mill: name</div>`)
        mill_label = 'Mill / Plant'
        _mm = re.search(r'var (marker_\w+)\s*=\s*L\.marker\(', html)
        if _mm:
            _mvar = _mm.group(1)
            _tt = re.search(rf'{re.escape(_mvar)}\.bindTooltip\(\s*`<div>\s*(.*?)\s*</div>`',
                            html, re.DOTALL)
            if _tt:
                _raw = _tt.group(1).strip()
                mill_label = _raw[6:] if _raw.startswith('Mill: ') else _raw

        ax.scatter(mill_lon, mill_lat, s=200, c='#ef4444', marker='^',
                   edgecolors='white', linewidths=1.2, zorder=10)
        ax.annotate(f'  {mill_label}', (mill_lon, mill_lat),
                    color='white', fontsize=7.5, va='center', fontweight='bold', zorder=11)

        ax.set_xlabel('Longitude', color='#8899aa', fontsize=8)
        ax.set_ylabel('Latitude',  color='#8899aa', fontsize=8)
        ax.tick_params(colors='#8899aa', labelsize=7)
        for spine in ax.spines.values(): spine.set_edgecolor('#334455')
        ax.grid(True, color='#223344', linewidth=0.4, alpha=0.55)

        all_lons = [m['lon'] for m in markers]
        all_lats = [m['lat'] for m in markers]
        px = (max(all_lons) - min(all_lons)) * 0.07
        py = (max(all_lats) - min(all_lats)) * 0.07
        # Zoom out so the full search-radius circle fits
        cx = (min(all_lons) + max(all_lons)) / 2
        cy = (min(all_lats) + max(all_lats)) / 2
        x0 = min(cx - deg_lon * 1.15, min(all_lons) - px)
        x1 = max(cx + deg_lon * 1.15, max(all_lons) + px)
        y0 = min(cy - deg_lat * 1.15, min(all_lats) - py)
        y1 = max(cy + deg_lat * 1.15, max(all_lats) + py)
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        # Correct aspect ratio: 1 deg lon = cos(lat) * 1 deg lat in metres
        ax.set_aspect(1.0 / math.cos(math.radians(clat)))

        legend_els = [
            mpatches.Patch(color='#22c55e', label='Forest Residue (solid dot)'),
            plt.Line2D([0],[0], marker='o', color='#f59e0b', markerfacecolor='none',
                       markersize=10, markeredgewidth=2.5, linewidth=0,
                       label='Sawmill Residue (ring)'),
            plt.Line2D([0],[0], marker='o', color='#60a5fa', markerfacecolor='none',
                       markersize=13, markeredgewidth=2.5, linewidth=0,
                       label='Pulpwood (outer ring, SAF only)'),
            plt.Line2D([0],[0], marker='^', color='w',
                       markerfacecolor='#ef4444', markersize=8, label='Mill / Plant'),
            plt.Line2D([0],[0], linestyle='--', color='#4ade80',
                       linewidth=1.2, label='Search radius boundary'),
        ]
        ax.legend(handles=legend_els, loc='lower left', fontsize=7,
                  facecolor='#1a2535', edgecolor='#334455',
                  labelcolor='white', framealpha=0.88)
        ax.set_title('Supply Chain Catchment Map', color='white', fontsize=9, pad=6)

        fig.tight_layout(pad=0.4)
        fig.savefig(out_png, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
        plt.close(fig)
        return out_png if os.path.exists(out_png) and os.path.getsize(out_png) > 10000 else None

    except Exception as e:
        print(f"Map render failed: {e}")
        return None

def _kv_grid(pairs, col_w=1.7*inch):
    """Two-column key/value table for inputs."""
    data = [[Paragraph(f"<b>{k}</b>", S["celll"]), Paragraph(str(v), S["celll"])]
            for k, v in pairs if v not in (None, "None", "—", "")]
    if not data: return None
    t = Table(data, colWidths=[col_w, PW/2-col_w])
    t.setStyle(TableStyle([
        ("FONTSIZE",(0,0),(-1,-1),8.5), ("LEADING",(0,0),(-1,-1),11),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#ccd8e4")),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.white,C_PALE]),
        ("LEFTPADDING",(0,0),(-1,-1),5), ("TOPPADDING",(0,0),(-1,-1),3),
        ("BOTTOMPADDING",(0,0),(-1,-1),3), ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]))
    return t

def _fmt_pct(v):
    """Format a percentage — session state stores display value (e.g. 7.0 not 0.07)."""
    if v is None: return "—"
    try: return f"{float(v):.1f}%"
    except: return str(v)

def _fmt_val(v, suffix=""):
    if v is None: return "—"
    return f"{v}{suffix}"

# ═════════════════════════════════════════════════════════════════════════════
def generate_scenario_pdf(snap, out_path,
                          lca_plot_path=None, avoided_plot_path=None,
                          saf_plot_mod=None, be_plot_mod=None):

    mode = snap.get("mode","SAF")
    name = snap.get("name","Scenario")
    ts   = snap.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    sc   = snap.get("sc") or {}
    tr   = snap.get("tr") or {}

    # Resolve saved plot paths — try snap keys first, then scan known locations
    def _find_plot(*candidates):
        for c in candidates:
            if c and os.path.exists(str(c)) and os.path.getsize(str(c)) > 500:
                return str(c)
        return ""

    # _DIR is where dashboard.py lives — derive from snap or use common locations
    _snap_dir = snap.get("_dir","") or snap.get("_plot_lca","").replace("/LCA_plots/lca_integrated.png","") or ""
    _search_dirs = [d for d in [_snap_dir, os.path.dirname(out_path),
                                os.path.expanduser("~"), "/tmp"] if d]

    p_lca     = _find_plot(lca_plot_path, snap.get("_plot_lca"),
                           *[os.path.join(d,"LCA_plots","lca_integrated.png") for d in _search_dirs])
    p_avoided = _find_plot(avoided_plot_path, snap.get("_plot_avoided"),
                           *[os.path.join(d,"LCA_plots","fhr_net_climate_impact.png") for d in _search_dirs])
    p_jobs    = _find_plot(snap.get("_plot_jobs"),
                           *[os.path.join(d,"Jobscreation_plots","plot_jobs.png") for d in _search_dirs])
    p_policy  = _find_plot(snap.get("_plot_policy"),
                           *[os.path.join(d,"Policy_plots","policy_comparison.png") for d in _search_dirs])
    # Resolve sc_map.html: try snap key first, then search all known dirs.
    # The PDF is always saved next to dashboard.py (_DIR), so that is the
    # most reliable fallback when _map_html is missing from the snap.
    p_map_html = snap.get("_map_html", "")
    if not p_map_html or not os.path.exists(str(p_map_html)):
        for d in _search_dirs:
            c = os.path.join(d, "sc_map.html")
            if os.path.exists(c): p_map_html = c; break

    # Screenshot the Folium map
    p_map_png = ""
    if p_map_html and os.path.exists(p_map_html):
        _map_out = os.path.join(os.path.dirname(out_path), "_sc_map_screenshot.png")
        p_map_png = _map_screenshot(p_map_html, _map_out) or ""

    doc = SimpleDocTemplate(
        out_path, pagesize=letter,
        leftMargin=0.7*inch, rightMargin=0.7*inch,
        topMargin=0.7*inch, bottomMargin=0.7*inch,
        title=f"GREEN TEA — {name}", author="GREEN TEA LCA Dashboard"
    )
    st = []

    # ══════════════════════════════════════════════════════════════════════════
    # COVER
    # ══════════════════════════════════════════════════════════════════════════
    _sp(st, 0.5)
    st.append(Paragraph("GREEN TEA LCA", S["title"]))
    st.append(Paragraph("Forest Residue Bioenergy &amp; SAF Techno-Economic Analysis", S["sub"]))
    _sp(st, 0.1)
    st.append(HRFlowable(width="100%", thickness=2, color=C_MID, spaceAfter=8))
    ct = Table([["Scenario", name],["Mode", mode],["Generated", ts]],
               colWidths=[1.3*inch, PW-1.3*inch])
    ct.setStyle(TableStyle([
        ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),10),
        ("LEADING",(0,0),(-1,-1),15),("TEXTCOLOR",(0,0),(0,-1),C_MID),
        ("TEXTCOLOR",(1,0),(1,-1),C_DARK),("LEFTPADDING",(0,0),(-1,-1),5),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LINEBELOW",(0,0),(-1,-2),0.3,C_LIGHT),
    ]))
    st.append(ct)
    st.append(HRFlowable(width="100%", thickness=2, color=C_MID, spaceAfter=10))
    _sp(st, 0.15)

    # KPIs
    lca = snap.get("lca_results") or {}
    if mode == "SAF":
        sm=snap.get("saf_metrics") or {}; mfsp=snap.get("saf_mfsp") or {}
        irr=_v(sm,"Equity IRR",float("nan"))
        _total_odt = lca.get("total_odt") or snap.get("total_biomass_odt", 0)
        kpis=[("NPV (Equity)",f"${_v(sm,'NPV (Equity, Nominal)')/1e6:.2f}M"),
              ("Equity IRR",f"{irr*100:.2f}%" if irr==irr else "N/A"),
              ("MFSP — SAF",f"${_v(mfsp,'MFSP SAF ($/L)')*L_PER_GAL:.4f}/gal"),
              ("TCI",f"${_v(sm,'Total Capital Investment (TCI)')/1e6:.2f}M"),
              ("SAF Output (Yr1)",f"{_v(sm,'SAF (L/yr, Yr1)')/L_PER_GAL/1e6:.2f}M gal/yr"),
              ("Total Biomass",f"{_total_odt/1e3:.1f}k odt/yr")]
    else:
        bm=snap.get("be_metrics") or {}
        lcoe=snap.get("be_lcoe"); lv=(lcoe if isinstance(lcoe,(int,float)) else (lcoe or {}).get("LCOE ($/MWh)"))
        irr=_v(bm,"Equity IRR",float("nan"))
        _total_odt = lca.get("total_odt") or snap.get("total_biomass_odt", 0)
        kpis=[("NPV (Equity)",f"${_v(bm,'NPV (Equity, Nominal)')/1e6:.2f}M"),
              ("Equity IRR",f"{irr*100:.2f}%" if irr==irr else "N/A"),
              ("LCOE",f"${lv:.2f}/MWh" if lv else "—"),
              ("TCI",f"${(snap.get('be_TCI') or 0)/1e6:.2f}M"),
              ("Annual Output",f"{(snap.get('be_annual_AC') or 0)/1e6:.2f} GWh/yr"),
              ("Total Biomass",f"{_total_odt/1e3:.1f}k odt/yr")]

    import math
    half = math.ceil(len(kpis)/2)
    def _kvt(rows):
        data=[[Paragraph(f"<b>{k}</b>",S["celll"]),Paragraph(v,S["celll"])] for k,v in rows]
        t=Table(data,colWidths=[1.6*inch,PW/2-1.7*inch])
        t.setStyle(TableStyle([("FONTSIZE",(0,0),(-1,-1),8.5),("LEADING",(0,0),(-1,-1),11),
            ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#ccd8e4")),
            ("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.white,C_PALE]),
            ("LEFTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),3),
            ("BOTTOMPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
        return t
    kg=Table([[_kvt(kpis[:half]),_kvt(kpis[half:])]],colWidths=[PW/2,PW/2])
    kg.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),0)]))
    st.append(kg)
    _pb(st)

    # ══════════════════════════════════════════════════════════════════════════
    # 1. SUPPLY CHAIN
    # ══════════════════════════════════════════════════════════════════════════
    _sh(st, "Supply Chain &amp; Transport", 1)

    # Summary table
    srcs=[("forest","Forest Residue"),("mill","Sawmill Residue"),("pulpwood","Pulpwood")]
    sc_hdr=["Source","Counties","Base Supply\n(k odt/yr)","Obtainability",
            "Effective\n(k odt/yr)","Haul Dist\n(mi)","Transport Opt.","Delivered\n($/ODT)"]
    sc_rows=[sc_hdr]
    for key, label in srcs:
        sc_s=sc.get(key,{}); tr_s=tr.get(key,{})
        base=sc_s.get("total_kdry",sc_s.get("hq_kdry",0))
        ob=tr_s.get("obtainability",100)
        eff=tr_s.get("residue_kdry",base*ob/100 if base else 0)
        dist=tr_s.get("dist_mi"); opt=tr_s.get("option","—"); cost=tr_s.get("cost_odt")
        counties=sc_s.get("counties",[])
        sc_rows.append([label,
            str(len(counties)) if counties else "—",
            f"{base:.1f}k" if base else "—",
            f"{ob:.0f}%",
            f"{eff:.1f}k" if eff else "—",
            f"{dist:.0f}" if dist else "—",
            str(opt),
            f"${cost:.2f}" if cost else "—"])
    cw=[1.15*inch,0.6*inch,0.78*inch,0.75*inch,0.75*inch,0.65*inch,0.85*inch,0.77*inch]
    st.append(_tbl(sc_rows, cw=cw))
    _sp(st, 0.06)

    # Mill metadata
    mill_name=sc.get("mill_name","—"); radius=sc.get("radius_mi","—")
    lat=sc.get("mill_lat"); lon=sc.get("mill_lon")
    meta=[["Mill / Plant",mill_name],["Search Radius",f"{radius} mi"],
          ["Coordinates",f"{lat:.4f}°N, {lon:.4f}°W" if lat and lon else "—"]]
    mt=Table(meta,colWidths=[1.3*inch,PW-1.3*inch])
    mt.setStyle(TableStyle([("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8.5),
        ("LEADING",(0,0),(-1,-1),11),("TEXTCOLOR",(0,0),(0,-1),C_MID),
        ("LINEBELOW",(0,0),(-1,-2),0.3,C_LIGHT),("LEFTPADDING",(0,0),(-1,-1),5),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    st.append(mt)
    _sp(st, 0.06)

    # Transport inputs
    _tr_speed  = _ss_read(snap, "tr_speed",           20)
    _tr_opt_f  = _ss_read(snap, "tr_opt_forest",      "-")
    _tr_opt_m  = _ss_read(snap, "tr_opt_mill",        "-")
    _tr_opt_p  = _ss_read(snap, "tr_opt_pulpwood",    "-")
    _tr_ob_f   = _ss_read(snap, "tr_obtain_forest",   100)
    _tr_ob_m   = _ss_read(snap, "tr_obtain_mill",     100)
    _tr_ob_p   = _ss_read(snap, "tr_obtain_pulpwood", 100)
    _tr_inp = [
        [Paragraph("<b>Parameter</b>", S["cell"]), Paragraph("<b>Value</b>", S["cell"])],
        [Paragraph("Avg. Truck Speed",          S["celll"]), Paragraph(f"{_tr_speed} mph",   S["cell"])],
        [Paragraph("Forest Transport Option",   S["celll"]), Paragraph(str(_tr_opt_f),       S["cell"])],
        [Paragraph("Sawmill Transport Option",  S["celll"]), Paragraph(str(_tr_opt_m),       S["cell"])],
        [Paragraph("Pulpwood Transport Option", S["celll"]), Paragraph(str(_tr_opt_p),       S["cell"])],
        [Paragraph("Forest Obtainability",      S["celll"]), Paragraph(f"{_tr_ob_f:.0f}%",  S["cell"])],
        [Paragraph("Sawmill Obtainability",     S["celll"]), Paragraph(f"{_tr_ob_m:.0f}%",  S["cell"])],
        [Paragraph("Pulpwood Obtainability",    S["celll"]), Paragraph(f"{_tr_ob_p:.0f}%",  S["cell"])],
    ]
    _half = len(_tr_inp) // 2 + 1
    def _half_tbl(rows):
        t = Table(rows, colWidths=[1.9*inch, PW/2-2.0*inch])
        t.setStyle(TableStyle([
            ("FONTSIZE",(0,0),(-1,-1),8.5),("LEADING",(0,0),(-1,-1),11),
            ("BACKGROUND",(0,0),(-1,0),C_LIGHT),
            ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#ccd8e4")),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,C_PALE]),
            ("LEFTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),3),
            ("BOTTOMPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("ALIGN",(1,0),(1,-1),"CENTER"),
        ]))
        return t
    st.append(Paragraph("Transport Inputs", S["h2"]))
    st.append(_two_col(_half_tbl(_tr_inp[:_half]), _half_tbl(_tr_inp[_half:])))
    _sp(st, 0.1)

    # Map
    if p_map_png:
        st.append(_png(p_map_png, PW))
        st.append(Paragraph(
            f"Supply catchment map — {mill_name}, {radius}-mile radius. "
            "Green: forest residue, amber: sawmill residue, blue: pulpwood. "
            "Dot size ∝ supply volume. Dashed circle = search boundary.",
            S["caption"]))
    _pb(st)

    # ══════════════════════════════════════════════════════════════════════════
    # 2. ECONOMICS
    # ══════════════════════════════════════════════════════════════════════════
    _sh(st, "Economic Performance", 2)

    if mode == "SAF":
        sm=snap.get("saf_metrics") or {}; mfsp=snap.get("saf_mfsp") or {}
        npv=_v(sm,"NPV (Equity, Nominal)"); irr=_v(sm,"Equity IRR",float("nan"))
        pb=sm.get("Payback Period (years)"); tci=_v(sm,"Total Capital Investment (TCI)")
        fci=_v(sm,"Fixed Capital Investment (FCI)"); rev=_v(sm,"Total Revenue ($/yr, Yr1)")
        saf_L=_v(sm,"SAF (L/yr, Yr1)"); die_L=_v(sm,"Diesel (L/yr, Yr1)"); nap_L=_v(sm,"Naptha (L/yr, Yr1)")

        # SAF Inputs
        st.append(Paragraph("Inputs", S["h2"]))
        _saf_year     = _ss_read(snap, "saf_year",     2025)
        _saf_distil   = _ss_read(snap, "saf_distil",   "distillate 1")
        _saf_safprice = _ss_read(snap, "saf_safprice",  round(1.61*3.78541, 2))
        _saf_dieprice = _ss_read(snap, "saf_dieprice",  round(1.03*3.78541, 2))
        _saf_napprice = _ss_read(snap, "saf_napprice",  round(0.75*3.78541, 2))
        _saf_life     = _ss_read(snap, "saf_life",      20)
        _saf_cpi      = _ss_read(snap, "saf_cpi",       321.05)
        _saf_degr     = _ss_read(snap, "saf_degr",      0.0)
        _saf_disc     = _ss_read(snap, "saf_disc",      10.0)
        _saf_infl     = _ss_read(snap, "saf_infl",       2.5)
        _saf_debt     = _ss_read(snap, "saf_debt",      70.0)
        _saf_loan_r   = _ss_read(snap, "saf_loan_r",     8.0)
        _saf_loanterm = _ss_read(snap, "saf_loanterm",   15)
        _saf_fedtax   = _ss_read(snap, "saf_fedtax",    21.0)
        _saf_sttax    = _ss_read(snap, "saf_sttax",      7.0)
        _saf_pesc     = _ss_read(snap, "saf_pesc",       2.5)
        _saf_fesc     = _ss_read(snap, "saf_fesc",       2.5)
        _saf_cesc     = _ss_read(snap, "saf_cesc",       2.5)
        _saf_kaesc    = _ss_read(snap, "saf_kaesc",      2.5)
        left_in=[
            ("Analysis Year",    str(_saf_year)),
            ("Distillate",       str(_saf_distil)),
            ("SAF Price",        f"${_saf_safprice:.2f}/gal"),
            ("Diesel Price",     f"${_saf_dieprice:.2f}/gal"),
            ("Naphtha Price",    f"${_saf_napprice:.2f}/gal"),
            ("Plant Life",       f"{_saf_life} yr"),
            ("CPI",              f"{_saf_cpi:.2f}"),
            ("Degradation",      f"{_saf_degr:.1f}%/yr"),
        ]
        right_in=[
            ("Discount Rate",    f"{_saf_disc:.1f}%"),
            ("Inflation",        f"{_saf_infl:.1f}%"),
            ("Debt Fraction",    f"{_saf_debt:.0f}%"),
            ("Loan Rate",        f"{_saf_loan_r:.1f}%"),
            ("Loan Term",        f"{_saf_loanterm} yr"),
            ("Federal Tax",      f"{_saf_fedtax:.0f}%"),
            ("State Tax",        f"{_saf_sttax:.0f}%"),
            ("Price Escalation", f"{_saf_pesc:.1f}%/yr"),
            ("Fuel Escalation",  f"{_saf_fesc:.1f}%/yr"),
            ("Cost Escalation",  f"{_saf_cesc:.1f}%/yr"),
        ]
        lt=_kv_grid(left_in); rt=_kv_grid(right_in)
        if lt and rt: st.append(_two_col(lt, rt))
        elif lt: st.append(lt)
        _sp(st, 0.08)

        # Outputs
        st.append(Paragraph("Outputs", S["h2"]))
        out_rows=[["Metric","Value","Notes"],
                  ["TCI",f"${tci/1e6:.2f}M","Total Capital Investment"],
                  ["FCI",f"${fci/1e6:.2f}M","Fixed Capital Investment"],
                  ["Year 1 Revenue",f"${rev/1e6:.2f}M/yr",""],
                  ["NPV (Equity)",f"${npv/1e6:.2f}M","Negative = below hurdle rate"],
                  ["Equity IRR",f"{irr*100:.2f}%" if irr==irr else "N/A",""],
                  ["Payback Period",f"{pb:.1f} yr" if pb else "Never",""],
                  ["MFSP — SAF",f"${_v(mfsp,'MFSP SAF ($/L)')*L_PER_GAL:.4f}/gal","At NPV=0"],
                  ["MFSP — Diesel",f"${_v(mfsp,'MFSP Diesel ($/L)')*L_PER_GAL:.4f}/gal","At NPV=0"],
                  ["MFSP — Naphtha",f"${_v(mfsp,'MFSP Naptha ($/L)')*L_PER_GAL:.4f}/gal","At NPV=0"],
                  ["SAF Production",f"{saf_L/L_PER_GAL/1e6:.2f}M gal/yr","Year 1"],
                  ["Diesel Production",f"{die_L/L_PER_GAL/1e6:.2f}M gal/yr","Year 1"],
                  ["Naphtha Production",f"{nap_L/L_PER_GAL/1e6:.2f}M gal/yr","Year 1"]]
        st.append(_tbl(out_rows,cw=[1.8*inch,1.5*inch,PW-3.3*inch]))

        # Cash flow plots — regenerated from stored df
        if saf_plot_mod and snap.get("saf_df") is not None:
            _sp(st,0.08); st.append(Paragraph("Cash Flow Plots", S["h2"]))
            try:
                import io as _io
                import matplotlib; matplotlib.use("Agg")
                import matplotlib.pyplot as plt
                figs=[f for f in saf_plot_mod.plot_all(snap["saf_df"],sm).values() if f is not None]
                for i in range(0,len(figs),2):
                    pair=figs[i:i+2]
                    imgs=[]
                    for fig in pair:
                        buf=_io.BytesIO(); fig.savefig(buf,format="png",dpi=150,bbox_inches="tight",facecolor=fig.get_facecolor()); buf.seek(0)
                        iw,ih=ImageReader(buf).getSize(); buf.seek(0)
                        img=Image(buf,width=HW,height=HW*ih/iw); img._buf=buf; imgs.append(img)
                        plt.close(fig)
                    if len(imgs)==2: st.append(_two_col(imgs[0],imgs[1]))
                    elif imgs: st.append(imgs[0])
            except Exception as e:
                st.append(Paragraph(f"Cash flow plots unavailable: {e}", S["note"]))

    else:  # Bioenergy
        bm=snap.get("be_metrics") or {}
        lcoe=snap.get("be_lcoe"); lv=(lcoe if isinstance(lcoe,(int,float)) else (lcoe or {}).get("LCOE ($/MWh)"))
        npv=_v(bm,"NPV (Equity, Nominal)"); irr=_v(bm,"Equity IRR",float("nan"))
        pb=bm.get("Payback Period (years)"); tci=snap.get("be_TCI") or 0
        fci=snap.get("be_FCI") or 0; ac=snap.get("be_annual_AC") or 0

        # BE Inputs
        st.append(Paragraph("Inputs", S["h2"]))
        _be_cepci      = _ss_read(snap, "be_cepci",      2030)
        _be_life       = _ss_read(snap, "be_life",        30)
        _be_elec_price = _ss_read(snap, "be_elec_price",  166.0)
        _be_f_cost     = _ss_read(snap, "be_f_cost",      0.0)
        _be_m_cost     = _ss_read(snap, "be_m_cost",      0.0)
        _be_degr       = _ss_read(snap, "be_degr",        0.5)
        _be_disc       = _ss_read(snap, "be_disc",        7.0)
        _be_infl       = _ss_read(snap, "be_infl",        2.5)
        _be_debt       = _ss_read(snap, "be_debt",        60.0)
        _be_loan_r     = _ss_read(snap, "be_loan_r",      6.5)
        _be_loan_term  = _ss_read(snap, "be_loan_term",   15)
        _be_eesc       = _ss_read(snap, "be_eesc",        1.0)
        _be_fesc       = _ss_read(snap, "be_fesc",        2.5)
        _be_fomesc     = _ss_read(snap, "be_fomesc",      2.5)
        _be_vomesc     = _ss_read(snap, "be_vomesc",      2.0)
        _be_fed        = _ss_read(snap, "be_fed",         21.0)
        _be_st         = _ss_read(snap, "be_st",          7.0)
        left_in=[
            ("Analysis Year",     str(_be_cepci)),
            ("Plant Life",        f"{_be_life} yr"),
            ("Electricity Price", f"${_be_elec_price:.1f}/MWh"),
            ("Forest Fuel Cost",  f"${_be_f_cost:.2f}/t"),
            ("Mill Fuel Cost",    f"${_be_m_cost:.2f}/t"),
            ("Degradation",       f"{_be_degr:.2f}%/yr"),
            ("Elec. Escalation",  f"{_be_eesc:.1f}%/yr"),
            ("Fuel Escalation",   f"{_be_fesc:.1f}%/yr"),
        ]
        right_in=[
            ("Discount Rate",   f"{_be_disc:.1f}%"),
            ("Inflation",       f"{_be_infl:.1f}%"),
            ("Debt Fraction",   f"{_be_debt:.0f}%"),
            ("Loan Rate",       f"{_be_loan_r:.1f}%"),
            ("Loan Term",       f"{_be_loan_term} yr"),
            ("Federal Tax",     f"{_be_fed:.0f}%"),
            ("State Tax",       f"{_be_st:.0f}%"),
            ("Fixed OM Esc.",   f"{_be_fomesc:.1f}%/yr"),
            ("Var. OM Esc.",    f"{_be_vomesc:.1f}%/yr"),
        ]
        lt=_kv_grid(left_in); rt=_kv_grid(right_in)
        if lt and rt: st.append(_two_col(lt, rt))
        elif lt: st.append(lt)
        _sp(st, 0.08)

        # Outputs
        st.append(Paragraph("Outputs", S["h2"]))
        out_rows=[["Metric","Value","Notes"],
                  ["TCI",f"${tci/1e6:.2f}M","Total Capital Investment"],
                  ["FCI",f"${fci/1e6:.2f}M","Fixed Capital Investment"],
                  ["Annual Output",f"{ac/1e6:.2f} GWh/yr","Year 1"],
                  ["LCOE",f"${lv:.2f}/MWh" if lv else "—","Levelised cost"],
                  ["NPV (Equity)",f"${npv/1e6:.2f}M","Negative = below hurdle rate"],
                  ["Equity IRR",f"{irr*100:.2f}%" if irr==irr else "N/A",""],
                  ["Payback Period",f"{pb:.1f} yr" if pb else "Never",""]]
        st.append(_tbl(out_rows,cw=[1.8*inch,1.5*inch,PW-3.3*inch]))

        if be_plot_mod and snap.get("be_df") is not None:
            _sp(st,0.08); st.append(Paragraph("Cash Flow Plots", S["h2"]))
            try:
                import io as _io
                import matplotlib; matplotlib.use("Agg")
                import matplotlib.pyplot as plt
                figs=[f for f in be_plot_mod.plot_all(snap["be_df"],bm).values() if f is not None]
                for i in range(0,len(figs),2):
                    pair=figs[i:i+2]; imgs=[]
                    for fig in pair:
                        buf=_io.BytesIO(); fig.savefig(buf,format="png",dpi=150,bbox_inches="tight",facecolor=fig.get_facecolor()); buf.seek(0)
                        iw,ih=ImageReader(buf).getSize(); buf.seek(0)
                        img=Image(buf,width=HW,height=HW*ih/iw); img._buf=buf; imgs.append(img)
                        plt.close(fig)
                    if len(imgs)==2: st.append(_two_col(imgs[0],imgs[1]))
                    elif imgs: st.append(imgs[0])
            except Exception as e:
                st.append(Paragraph(f"Cash flow plots unavailable: {e}", S["note"]))
    _pb(st)

    # ══════════════════════════════════════════════════════════════════════════
    # 3. LIFECYCLE GHG
    # ══════════════════════════════════════════════════════════════════════════
    _sh(st,"Lifecycle GHG Emissions",3)
    lca=snap.get("lca_results") or {}
    _lca_moisture    = _ss_read(snap, "lca_moisture",     40)
    _lca_truck_l_mi  = _ss_read(snap, "lca_truck_l_mi",   0.000094)
    _lca_ef_co2      = _ss_read(snap, "lca_ef_co2",       2.68)
    _lca_ef_ch4      = _ss_read(snap, "lca_ef_ch4",       2.7186)
    _lca_ef_n2o      = _ss_read(snap, "lca_ef_n2o",       3.6488)
    _lca_proc_ef_co2 = _ss_read(snap, "lca_proc_ef_co2",  2.68)
    _lca_proc_ncv    = _ss_read(snap, "lca_proc_ncv",     35.8)
    _lca_proc_ch4_mj = _ss_read(snap, "lca_proc_ch4_mj",  0.10)
    _lca_proc_n2o_mj = _ss_read(snap, "lca_proc_n2o_mj",  0.10)
    lca_inp_rows = [
        [Paragraph("<b>Parameter</b>", S["cell"]), Paragraph("<b>Value</b>", S["cell"]), Paragraph("<b>Notes</b>", S["cell"])],
        [Paragraph("Moisture Content",              S["celll"]), Paragraph(f"{_lca_moisture:.0f}%",                         S["cell"]), Paragraph("Feedstock",          S["celll"])],
        [Paragraph("Truck Fuel (L/t-mi)",           S["celll"]), Paragraph(f"{_lca_truck_l_mi:.6f}",                        S["cell"]), Paragraph("Transport EF",       S["celll"])],
        [Paragraph("Transport CO<sub>2</sub> EF",   S["celll"]), Paragraph(f"{_lca_ef_co2:.3f} kg/L",                      S["cell"]), Paragraph("Diesel combustion",  S["celll"])],
        [Paragraph("Transport CH<sub>4</sub> EF",   S["celll"]), Paragraph(f"{_lca_ef_ch4:.4f}x10<super>-5</super> kg/L",  S["cell"]), Paragraph("",                   S["cell"])],
        [Paragraph("Transport N<sub>2</sub>O EF",   S["celll"]), Paragraph(f"{_lca_ef_n2o:.4f}x10<super>-6</super> kg/L",  S["cell"]), Paragraph("",                   S["cell"])],
        [Paragraph("Processing CO<sub>2</sub> EF",  S["celll"]), Paragraph(f"{_lca_proc_ef_co2:.3f} kg/L",                 S["cell"]), Paragraph("Diesel",             S["celll"])],
        [Paragraph("Processing NCV",                S["celll"]), Paragraph(f"{_lca_proc_ncv:.1f} MJ/L",                    S["cell"]), Paragraph("Diesel",             S["celll"])],
        [Paragraph("Processing CH<sub>4</sub> EF",  S["celll"]), Paragraph(f"{_lca_proc_ch4_mj:.3f} g/MJ",                 S["cell"]), Paragraph("",                   S["cell"])],
        [Paragraph("Processing N<sub>2</sub>O EF",  S["celll"]), Paragraph(f"{_lca_proc_n2o_mj:.3f} g/MJ",                 S["cell"]), Paragraph("",                   S["cell"])],
    ]
    st.append(Paragraph("Emission Factor Inputs", S["h2"]))
    st.append(_tbl(lca_inp_rows, cw=[2.3*inch, 2.0*inch, PW-4.3*inch], hrows=1))
    _sp(st, 0.1)
    if lca:
        p_r=lca.get("proc_saf" if mode=="SAF" else "proc_bio")
        t_r=lca.get("trans_saf" if mode=="SAF" else "trans_bio")
        pr_r=lca.get("saf_prod" if mode=="SAF" else "bio_prod")
        pl="SAF Production" if mode=="SAF" else "Bioenergy Production"

        def _lrow(lbl,r):
            return[lbl,f"{_bio(r):,.0f}",f"{(r or {}).get('fossCO2_t',0):,.0f}",
                   f"{(r or {}).get('CH4_CO2e',0):,.0f}",f"{(r or {}).get('N2O_CO2e',0):,.0f}",f"{_tot(r):,.0f}"]

        lhdr=["Stage","Biogenic CO<sub>2</sub>\n(t/yr)","Fossil CO<sub>2</sub>\n(t/yr)",
              "CH<sub>4</sub> CO<sub>2</sub>e\n(t/yr)","N<sub>2</sub>O CO<sub>2</sub>e\n(t/yr)","Total\n(t CO<sub>2</sub>e/yr)"]
        lrows=[lhdr,_lrow("Processing",p_r),_lrow("Transport",t_r),_lrow(pl,pr_r),
               ["TOTAL",f"{_bio(p_r)+_bio(t_r)+_bio(pr_r):,.0f}",
                f"{sum((r or {}).get('fossCO2_t',0) for r in [p_r,t_r,pr_r]):,.0f}",
                f"{sum((r or {}).get('CH4_CO2e',0) for r in [p_r,t_r,pr_r]):,.0f}",
                f"{sum((r or {}).get('N2O_CO2e',0) for r in [p_r,t_r,pr_r]):,.0f}",
                f"{_tot(p_r)+_tot(t_r)+_tot(pr_r):,.0f}"]]
        safe=[[Paragraph(str(c),S["cell"]) for c in row] for row in lrows]
        st.append(_tbl(safe,cw=[1.3*inch]+[(PW-1.3*inch)/5]*5,bold_last=True))
        st.append(Paragraph(
            "Biogenic CO<sub>2</sub> excluded per IPCC (2006) / RED II. "
            "Section 4 uses non-biogenic totals only — consistent with the open-burning "
            "baseline EF (0.143 kg CO<sub>2</sub>e/kg OD) which likewise excludes combustion CO<sub>2</sub>.",
            S["note"]))
        _sp(st,0.08)
        img=_png(p_lca, PW)
        if img: st.append(img); 
    else:
        st.append(Paragraph("LCA not run for this scenario.", S["h2"]))
    _pb(st)

    # ══════════════════════════════════════════════════════════════════════════
    # 4. AVOIDED EMISSIONS
    # ══════════════════════════════════════════════════════════════════════════
    _sh(st,"Avoided Emissions Analysis",4)
    if lca:
        tot_odt=lca.get("total_odt",0); burn_bl=tot_odt*1000*0.143/1000
        proj_nb=_nb(p_r)+_nb(t_r)+_nb(pr_r)
        avd_burn=burn_bl-proj_nb; pct_burn=avd_burn/burn_bl*100 if burn_bl else 0
        ahdr=["Baseline","Baseline GHG\n(t CO<sub>2</sub>e/yr)","This Project\n(non-biogenic,\nt CO<sub>2</sub>e/yr)",
              "Avoided\n(t CO<sub>2</sub>e/yr)","Reduction"]
        arows=[ahdr,["Open Pile Burning",f"{burn_bl:,.0f}",f"{proj_nb:,.0f}",
                     f"{avd_burn:,.0f}",f"{pct_burn:.1f}%"]]
        if mode=="SAF":
            sr=lca.get("sr")
            if sr and isinstance(sr,dict) and "SAF_MJ_yr" in sr:
                fj=15.93*sr["SAF_MJ_yr"]/1e6; avd_jf=fj-proj_nb; pct_jf=avd_jf/fj*100 if fj else 0
                arows.append(["Fossil Jet Fuel",f"{fj:,.0f}",f"{proj_nb:,.0f}",
                               f"{avd_jf:,.0f}",f"{pct_jf:.1f}%"])
        safe_a=[[Paragraph(str(c),S["cell"]) for c in row] for row in arows]
        st.append(_tbl(safe_a,cw=[1.6*inch]+[(PW-1.6*inch)/4]*4))
        _sp(st,0.08)
        img=_png(p_avoided, PW)
        if img: st.append(img)
    else:
        st.append(Paragraph("LCA not run for this scenario.", S["h2"]))
    _pb(st)

    # ══════════════════════════════════════════════════════════════════════════
    # 5. POLICY ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    _sh(st,"Policy Analysis",5)
    if mode=="SAF":
        _sp_saf_p   = _ss_read(snap, "sp_saf_p",   round(1.61*3.78541,4))
        _sp_die_p   = _ss_read(snap, "sp_die_p",   round(1.03*3.78541,4))
        _sp_nap_p   = _ss_read(snap, "sp_nap_p",   round(0.75*3.78541,4))
        _sp_cr_saf  = _ss_read(snap, "sp_cr_saf",  0.35)
        _sp_cr_nons = _ss_read(snap, "sp_cr_nons", 0.20)
        _sp_cr_dur  = _ss_read(snap, "sp_cr_dur",  10)
        _sp_jet_mkt = _ss_read(snap, "sp_jet_mkt", round(0.82*3.78541,3))
        _sp_die_mkt = _ss_read(snap, "sp_die_mkt", round(1.34*3.78541,3))
        _sp_nap_mkt = _ss_read(snap, "sp_nap_mkt", round(0.98*3.78541,3))
        _sp_solver  = _ss_read(snap, "sp_run_solver", False)
        _sp_solved  = snap.get("saf_pol_credit_solved")
        pol_inp = [
            [Paragraph("<b>Parameter</b>", S["cell"]), Paragraph("<b>Value</b>", S["cell"])],
            [Paragraph("SAF Sale Price",          S["celll"]), Paragraph(f"${_sp_saf_p:.4f}/gal",   S["cell"])],
            [Paragraph("Diesel Sale Price",       S["celll"]), Paragraph(f"${_sp_die_p:.4f}/gal",   S["cell"])],
            [Paragraph("Naphtha Sale Price",      S["celll"]), Paragraph(f"${_sp_nap_p:.4f}/gal",   S["cell"])],
            [Paragraph("45Z SAF Credit",          S["celll"]), Paragraph(f"${_sp_cr_saf:.3f}/GGE",  S["cell"])],
            [Paragraph("45Z Non-SAF Credit",      S["celll"]), Paragraph(f"${_sp_cr_nons:.3f}/GGE", S["cell"])],
            [Paragraph("Credit Duration",         S["celll"]), Paragraph(f"{_sp_cr_dur} yr",        S["cell"])],
            [Paragraph("Jet-A Market Price",      S["celll"]), Paragraph(f"${_sp_jet_mkt:.3f}/gal", S["cell"])],
            [Paragraph("Diesel Market Price",     S["celll"]), Paragraph(f"${_sp_die_mkt:.3f}/gal", S["cell"])],
            [Paragraph("Naphtha Market Price",    S["celll"]), Paragraph(f"${_sp_nap_mkt:.3f}/gal", S["cell"])],
            [Paragraph("Solve Required Credit",   S["celll"]), Paragraph("Yes" if _sp_solver else "No", S["cell"])],
        ]
        if _sp_solved is not None:
            pol_inp.append([Paragraph("<b>Required SAF Credit (solved)</b>", S["celll"]),
                            Paragraph(f"${_sp_solved:.4f}/GGE", S["cell"])])
        _phalf = len(pol_inp) // 2 + 1
        st.append(Paragraph("Policy Inputs (IRA 45Z)", S["h2"]))
        st.append(_two_col(_half_tbl(pol_inp[:_phalf]), _half_tbl(pol_inp[_phalf:])))
        _sp(st, 0.08)
        pm1=snap.get("saf_pol_met1") or {}; pm2=snap.get("saf_pol_met2") or {}
        if pm1 or pm2:
            phdr=["Metric","No Policy","With 45Z Credit"]
            pkeys=[("NPV (Equity, Nominal)","NPV (Equity)",lambda v:f"${v/1e6:.2f}M"),
                   ("Equity IRR","Equity IRR",lambda v:f"{v*100:.2f}%"),
                   ("Payback Period (years)","Payback",lambda v:f"{v:.1f} yr" if v else "Never"),
                   ("Total Revenue ($/yr, Yr1)","Revenue Yr1",lambda v:f"${v/1e6:.2f}M/yr")]
            prows=[phdr]+[[lbl,fmt(pm1.get(k)) if pm1.get(k) is not None else "—",
                           fmt(pm2.get(k)) if pm2.get(k) is not None else "—"] for k,lbl,fmt in pkeys]
            st.append(_tbl(prows,cw=[2.0*inch,(PW-2.0*inch)/2,(PW-2.0*inch)/2]))
        else:
            st.append(Paragraph("Policy analysis not run for this scenario.", S["h2"]))
    else:
        _bepol_ep     = _ss_read(snap, "bepol_elec_price",   166.0)
        _bepol_mkt    = _ss_read(snap, "bepol_market_price", 120.0)
        _bepol_solver = _ss_read(snap, "bepol_run_solver",   False)
        _bepol_solved = snap.get("be_pol_credit_solved")
        bepol_inp = [
            [Paragraph("<b>Parameter</b>", S["cell"]), Paragraph("<b>Value</b>", S["cell"])],
            [Paragraph("Electricity Price (policy)",  S["celll"]), Paragraph(f"${_bepol_ep:.2f}/MWh",  S["cell"])],
            [Paragraph("Market Electricity Price",    S["celll"]), Paragraph(f"${_bepol_mkt:.2f}/MWh", S["cell"])],
            [Paragraph("Solve for Min. PTC Credit",   S["celll"]), Paragraph("Yes" if _bepol_solver else "No", S["cell"])],
        ]
        if _bepol_solved is not None:
            bepol_inp.append([Paragraph("<b>Min. IRA 45Y PTC (solved)</b>", S["celll"]),
                              Paragraph(f"${_bepol_solved*100:.4f} cents/kWh", S["cell"])])
        st.append(Paragraph("Policy Inputs (IRA 45Y)", S["h2"]))
        st.append(_tbl(bepol_inp, cw=[2.6*inch, PW-2.6*inch], hrows=1))
        _sp(st, 0.08)
        pm1=snap.get("be_pol_met1") or {}; pm2=snap.get("be_pol_met2") or {}; pm3=snap.get("be_pol_met3") or {}
        if pm1 or pm2 or pm3:
            phdr=["Metric","No Policy","PTC","ITC"]
            pkeys=[("NPV (Equity, Nominal)","NPV",lambda v:f"${v/1e6:.2f}M"),
                   ("Equity IRR","IRR",lambda v:f"{v*100:.2f}%"),
                   ("Payback Period (years)","Payback",lambda v:f"{v:.1f} yr" if v else "Never")]
            w3=(PW-2.0*inch)/3
            prows=[phdr]+[[lbl]+[fmt(p.get(k)) if p.get(k) is not None else "—"
                          for p in [pm1,pm2,pm3]] for k,lbl,fmt in pkeys]
            st.append(_tbl(prows,cw=[2.0*inch,w3,w3,w3]))
        else:
            st.append(Paragraph("Policy analysis not run for this scenario.", S["h2"]))

    img=_png(p_policy, PW)
    if img:
        _sp(st,0.08)
        st.append(img)

    _sp(st,0.12)

    # ══════════════════════════════════════════════════════════════════════════
    # 6. EMPLOYMENT
    # ══════════════════════════════════════════════════════════════════════════
    _sh(st,"Employment Impact",6)
    jr=snap.get("jobs_result")
    if jr:
        jrows=[["Category","Jobs","Description"],
               ["Direct",  str(jr.get("direct_jobs","—")), "Conversion facility operations"],
               ["Indirect",str(jr.get("indirect_jobs","—")),"Supply chain and services"],
               ["Induced", str(jr.get("induced_jobs","—")), "Local economic spillover"],
               ["TOTAL",   str(jr.get("total_jobs","—")),   ""]]
        st.append(_tbl(jrows,cw=[1.4*inch,1.0*inch,PW-2.4*inch],bold_last=True))
        img=_png(p_jobs, PW*0.6)
        if img:
            _sp(st,0.08)
            st.append(img)

    else:
        st.append(Paragraph("Employment not calculated — run the Economics tab first.", S["h2"]))

    _sp(st,0.25); _hr(st)
    st.append(Paragraph(
        f"GREEN TEA LCA Dashboard — Generated {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} "
        "— Research purposes only.",
        S["footer"]))

    doc.build(st)
    return out_path