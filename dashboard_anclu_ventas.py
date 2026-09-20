import base64
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data_anclu")
LOGO_PATH = os.path.join(BASE_DIR, "assets", "logo_anclu.png")

# Fuentes de datos vivas (las mismas que alimenta el Power BI)
SIG_VENTAS = r"C:\Users\lubernu\Practicas\SIG\ventas_anclu.csv"
SIG_RP = r"C:\Users\lubernu\Practicas\SIG\ventas_anclu_rp.csv"
METAS_XLSX = r"C:\Users\lubernu\OneDrive\Anclu\Datos\MetasClaro.xlsx"

POSTPAGO_TIPOS = {"Migración", "Portabilidad", "Linea Nueva", "Power"}

with open(LOGO_PATH, "rb") as _fh:
    LOGO_B64 = base64.b64encode(_fh.read()).decode()

st.set_page_config(
    page_title="Anclu · Dashboard de Ventas",
    page_icon=LOGO_PATH,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Marca y utilidades
# ---------------------------------------------------------------------------
BRAND = "#E5212B"
BRAND_DARK = "#B71C1C"
INK = "#1C1E29"
MUTED = "#6B7280"
BG = "#F2F4F8"
GRID = "#E9EDF3"
GOLD = "#F59E0B"
PALETA = ["#E5212B", "#2563EB", "#F59E0B", "#10B981", "#8B5CF6", "#EC4899", "#0EA5E9"]
VERDE = "#10B981"
ROJO = "#E5212B"

MESES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}
FMT_NUM = lambda x: f"{int(x):,}".replace(",", ".")
FMT_DIN = lambda x: "$" + f"{x:,.0f}".replace(",", ".")
FMT_PCT = lambda x: f"{x:,.1f}".replace(",", ".") + " %"


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------
def _sig_fuentes():
    sigs = []
    for p in (SIG_VENTAS, SIG_RP, METAS_XLSX):
        if os.path.exists(p):
            sigs.append(pd.Timestamp(os.path.getmtime(p)).isoformat())
        else:
            sigs.append("no-local")
    return tuple(sigs)


def _url_supabase():
    try:
        s = st.secrets.get("supabase")
        if s and s.get("db_url"):
            return s["db_url"]
    except Exception:
        pass
    return os.environ.get("SUPABASE_DB_URL")


def _leer_supabase(url, tabla):
    import sqlalchemy as sa
    eng = sa.create_engine(url)
    with eng.connect() as c:
        df = pd.read_sql_query(f"select * from public.{tabla}", c)
    if "id" in df.columns:
        df = df.drop(columns=["id"])
    return df


def _leer_opcional(supa, tabla, fallback):
    if supa:
        try:
            return _leer_supabase(supa, tabla)
        except Exception:
            pass
    return fallback()


def _rp_local():
    try:
        return pd.read_csv(SIG_RP, sep=",", encoding="utf-8-sig", low_memory=False)
    except Exception:
        return pd.DataFrame(columns=["DISTRIBUIDOR", "PRODUCTO", "CO_ID", "ACTIVACION", "DESCRIPCION"])


def _metas_local():
    try:
        return pd.read_excel(METAS_XLSX, sheet_name="Hoja1")
    except Exception:
        return pd.DataFrame(columns=["CODIGO", "NOMBREPUNTO", "FECHA"])


@st.cache_data(ttl=600, max_entries=4)
def load_data(_sig_):
    supa = _url_supabase()
    if supa:
        try:
            fact = _leer_supabase(supa, "ventas_anclu")
        except Exception:
            fact = pd.read_csv(SIG_VENTAS, sep=",", encoding="utf-8-sig", low_memory=False)
    else:
        fact = pd.read_csv(SIG_VENTAS, sep=",", encoding="utf-8-sig", low_memory=False)
    fact["fec_registro"] = pd.to_datetime(fact["fec_registro"], errors="coerce")
    for c in ["valor_plan_", "iva_plan_", "valor_telefono_", "iva_telefono_",
              "vr_telefono", "vr_descuento", "costo"]:
        fact[c] = pd.to_numeric(fact[c], errors="coerce").fillna(0)
    fact["Producto"] = fact["TipoProducto"].map(
        lambda t: "Postpago" if t in POSTPAGO_TIPOS else "Equipos")
    fact["anio"] = fact["fec_registro"].dt.year
    fact["mes_num"] = fact["fec_registro"].dt.month
    fact["mes"] = fact["mes_num"].map(MESES)
    fact["anio_mes"] = fact["fec_registro"].dt.to_period("M").astype(str)
    fact["dia"] = fact["fec_registro"].dt.day

    rp = _leer_opcional(supa, "ventas_anclu_rp", _rp_local)
    rp["ACTIVACION"] = pd.to_datetime(rp["ACTIVACION"])
    rp["anio"] = rp["ACTIVACION"].dt.year
    rp["mes_num"] = rp["ACTIVACION"].dt.month
    rp["mes"] = rp["mes_num"].map(MESES)
    rp["anio_mes"] = rp["ACTIVACION"].dt.to_period("M").astype(str)
    rp["dia"] = rp["ACTIVACION"].dt.day

    meta_raw = None
    metas = None
    if supa:
        try:
            metas = _leer_supabase(supa, "metas_claro")
        except Exception:
            metas = None
        if metas is None:
            meta_raw = _metas_local()
    else:
        meta_raw = _metas_local()
    if metas is None:
        meta_cols = [c for c in meta_raw.columns if c not in ("CODIGO", "NOMBREPUNTO", "FECHA")]
        metas = meta_raw.melt(id_vars=["CODIGO", "FECHA"], value_vars=meta_cols,
                              var_name="META_DE", value_name="Valor")
    metas["FECHA"] = pd.to_datetime(metas["FECHA"], errors="coerce")
    metas["META_DE"] = metas["META_DE"].astype(str).str.strip()
    metas["Valor"] = pd.to_numeric(metas["Valor"], errors="coerce").fillna(0).astype("int64")
    metas["anio"] = metas["FECHA"].dt.year
    metas["mes_num"] = metas["FECHA"].dt.month

    if meta_raw is not None:
        codigos = meta_raw[["CODIGO", "NOMBREPUNTO"]].drop_duplicates().copy()
    else:
        codigos = _leer_opcional(supa, "puntos", lambda: None)
        if codigos is None:
            codigos = metas[["CODIGO"]].drop_duplicates().copy()
            codigos["NOMBREPUNTO"] = codigos["CODIGO"]
        else:
            codigos = codigos[["CODIGO", "NOMBREPUNTO"]].drop_duplicates().copy()
    codigos["NOMBREPUNTO"] = (
        codigos["NOMBREPUNTO"].astype(str)
        .str.replace("Anclu Sas -", "", regex=False)
        .str.replace("/Boyaca", "", regex=False)
        .str.strip()
    )

    cal = _leer_opcional(supa, "calendario",
                         lambda: pd.read_parquet(os.path.join(DATA_DIR, "Calendario.parquet")))
    cal["Date"] = pd.to_datetime(cal["Date"])
    cal["anio"] = cal["Date"].dt.year
    cal["mes_num"] = cal["Date"].dt.month

    return dict(fact=fact, rp=rp, metas=metas, cal=cal, codigos=codigos)


DATA = load_data(_sig_fuentes())
fact, rp, metas, cal = DATA["fact"], DATA["rp"], DATA["metas"], DATA["cal"]
codigos = DATA["codigos"]
FECHA_CORTE = fact["fec_registro"].max().date()

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
    :root {
        --brand:#E5212B; --brand-dark:#B71C1C; --ink:#1C1E29; --muted:#6B7280;
        --bg:#F2F4F8; --card:#FFFFFF; --grid:#E9EDF3;
    }
    html, body, [class*="css"] { font-family: 'Segoe UI', 'Roboto', sans-serif; }

    /* Fondo de la app */
    .stApp { background: var(--bg); }

    /* Header */
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    .banner {
        display:flex; align-items:center; gap:22px; background:var(--card);
        border-radius:16px; padding:16px 26px; margin-bottom:22px;
        box-shadow:0 1px 4px rgba(23,25,35,.07); border-top:4px solid var(--brand);
    }
    .banner img { height:58px; width:auto; border-radius:6px; }
    .banner-title { font-size:1.5rem; font-weight:800; color:var(--ink); line-height:1.15; }
    .banner-sub { font-size:.82rem; color:var(--muted); margin-top:2px; }
    .banner-right { margin-left:auto; text-align:right; }
    .badge {
        display:inline-block; background:#FDECEE; color:var(--brand-dark);
        font-weight:700; font-size:.78rem; padding:7px 14px; border-radius:999px;
    }
    .badge small { display:block; font-weight:600; color:var(--muted); font-size:.66rem;
                  letter-spacing:.05em; text-transform:uppercase; margin-bottom:2px; }

    /* Titulos de seccion */
    .sec-title {
        font-size:1.05rem; font-weight:700; color:var(--ink); margin:6px 0 10px;
        padding-left:10px; border-left:4px solid var(--brand); line-height:1.25;
    }
    .sec-title small { font-weight:600; color:var(--muted); font-size:.78rem; }

    /* Tarjetas KPI */
    .kpi-card {
        position:relative; background:var(--card); border:1px solid #E9EDF3;
        border-radius:14px; padding:15px 18px 14px 20px; height:100%;
        box-shadow:0 1px 3px rgba(23,25,35,.05); overflow:hidden;
    }
    .kpi-card::before { content:""; position:absolute; left:0; top:0; bottom:0; width:5px;
        background:var(--acc, var(--brand)); border-radius:0 3px 3px 0; }
    .kpi-lab { font-size:.68rem; font-weight:700; letter-spacing:.07em; text-transform:uppercase;
        color:var(--muted); margin-bottom:5px; }
    .kpi-val { font-size:1.4rem; font-weight:800; color:var(--ink); line-height:1.15;
        font-variant-numeric:tabular-nums; }
    .kpi-val.xs { font-size:1.12rem; }
    @media (max-width: 980px) {
        .kpi-val { font-size:1.2rem; }
        .kpi-val.xs { font-size:1rem; }
        .kpi-card { padding:11px 13px 11px 16px; }
    }
    .kpi-sub { font-size:.76rem; color:var(--muted); margin-top:4px; font-weight:600; }
    .kpi-delta { display:inline-block; font-size:.74rem; font-weight:700; margin-left:6px; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap:8px; background:transparent; border-bottom:1px solid var(--grid); }
    .stTabs [data-baseweb="tab"] {
        height:auto; border-radius:10px 10px 0 0; padding:9px 20px; font-weight:700;
        font-size:.9rem; color:var(--muted); background:transparent;
    }
    .stTabs [data-baseweb="tab"]:hover { color:var(--brand); }
    .stTabs [aria-selected="true"] { color:var(--brand) !important; }
    .stTabs [aria-selected="true"]::after {
        content:""; display:block; height:3px; background:var(--brand);
        border-radius:3px 3px 0 0; margin-top:6px;
    }

    /* Sidebar */
    [data-testid="stSidebar"] { background:var(--card); border-right:1px solid var(--grid); }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stMultiSelect label { font-weight:700; color:var(--ink); font-size:.78rem; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
        font-size:.8rem; letter-spacing:.08em; text-transform:uppercase; color:var(--brand);
        border-bottom:2px solid var(--grid); padding-bottom:6px; margin-top:14px;
    }
    .sidebar-logo { display:flex; align-items:center; gap:10px; padding:4px 0 10px; }
    .sidebar-logo img { height:40px; }

    /* Tablas */
    .stDataFrame { border-radius:12px; overflow:hidden; border:1px solid var(--grid);
        box-shadow:0 1px 3px rgba(23,25,35,.05); }
    [data-testid="stDataFrameResizable"] { background:var(--card); }

    /* Captions y footer */
    .foot { text-align:center; color:var(--muted); font-size:.74rem; margin-top:26px; }

    hr.sep { border:none; border-top:1px solid var(--grid); margin:6px 0 14px; }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="banner">
        <img src="data:image/png;base64,{LOGO_B64}" alt="Anclu">
        <div>
            <div class="banner-title">Dashboard de Ventas &amp; Metas</div>
            <div class="banner-sub">Reporte Anclu · ventas, metas Claro y proyecciones</div>
        </div>
        <div class="banner-right">
            <span class="badge">
                <small>Corte de datos</small>{FECHA_CORTE.strftime("%d/%m/%Y")}
            </span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Filtros globales
# ---------------------------------------------------------------------------
anios_venta = sorted(fact["anio"].dropna().unique().tolist())
anio_default = anios_venta[-1]
meses_disponibles_anio = sorted(fact.loc[fact["anio"] == anio_default, "mes_num"].unique().tolist())
mes_default = meses_disponibles_anio[-1] if meses_disponibles_anio else 1

anios_rp = sorted(rp["anio"].dropna().unique().tolist())
anio_rp_default = anios_rp[-1]
meses_rp = sorted(rp.loc[rp["anio"] == anio_rp_default, "mes_num"].unique().tolist())
mes_rp_default = meses_rp[-1] if meses_rp else 1

OPCIONES_META = ["META POSPAGO", "META MIGRACIÓN", "POSPAGO_PORTADO", "TOTAL META POSPAGO",
                 "KIT PREPAGO CONTADO", "META CHIP", "META IN PREPAGO", "TOTAL META PREPAGO",
                 "META PROPAGO", "META HOGARES", "POSPAGO"]

OPCION_TODOS = "Todos"
def _indice_opcion(lista, sel):
    if not sel or len(lista) == len(sel):
        return 0
    return lista.index(sel[0]) + 1

with st.sidebar:
    st.markdown(
        f'<div class="sidebar-logo"><img src="data:image/png;base64,{LOGO_B64}">'
        '<span style="font-weight:800;color:#1C1E29;">Anclu</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown("### Filtros de ventas")
    sel_anio = st.selectbox("Año (ventas)", anios_venta,
                            index=anios_venta.index(anio_default), key="filtro_anio")
    sel_mes = st.selectbox(
        "Mes (ventas)", list(MESES.keys()),
        format_func=lambda m: MESES[m].capitalize(),
        index=list(MESES.keys()).index(mes_default),
        key="filtro_mes",
    )
    productos = sorted(fact["Producto"].dropna().unique().tolist())
    prod_opc = st.selectbox("Tipo de producto", [OPCION_TODOS] + productos,
                            index=0, key="filtro_producto")
    sel_productos = productos if prod_opc == OPCION_TODOS else [prod_opc]
    pdvs = sorted(fact["centro_costo"].dropna().unique().tolist())
    pdv_opc = st.selectbox("Oficina / PDV", [OPCION_TODOS] + pdvs,
                           index=0, key="filtro_pdv")
    sel_pdvs = pdvs if pdv_opc == OPCION_TODOS else [pdv_opc]

    if st.button("Restablecer filtros", width="stretch", key="btn_reset"):
        for _k in ("filtro_anio", "filtro_mes", "filtro_producto", "filtro_pdv",
                   "claro_anio", "claro_mes", "claro_meta", "pdv_oficinas"):
            st.session_state.pop(_k, None)
        st.rerun()

# ---------------------------------------------------------------------------
# Helpers de visualizacion
# ---------------------------------------------------------------------------
def render_kpis(items):
    """items: lista de (accent_color, label, valor, sub, clase_opt)"""
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        acc, label, valor, sub = item[0], item[1], item[2], item[3]
        cls = item[4] if len(item) > 4 else ""
        with col:
            st.markdown(
                f'<div class="kpi-card" style="--acc:{acc}">'
                f'<div class="kpi-lab">{label}</div>'
                f'<div class="kpi-val {cls}">{valor}</div>'
                f'<div class="kpi-sub">{sub or ""}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )


def sec_title(texto, nota=""):
    st.markdown(
        f'<div class="sec-title">{texto} <small>{nota}</small></div>',
        unsafe_allow_html=True,
    )


def estilizar(fig, h=320, title=None):
    fig.update_layout(
        template="plotly_white",
        height=h,
        margin=dict(l=8, r=8, t=40 if title else 8, b=8),
        font=dict(family="Segoe UI, Roboto, sans-serif", size=13, color=INK),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        title=dict(text=title or "", font=dict(size=15, color=INK), x=0.02),
        hoverlabel=dict(bgcolor=INK, bordercolor=INK, font=dict(color="#FFFFFF", size=12)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    if title:
        fig.update_layout(margin=dict(l=8, r=8, t=40, b=8))
    fig.update_xaxes(gridcolor=GRID, zeroline=False, showline=False, automargin=True, title="")
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickformat=",.0f", automargin=True, title="")
    try:
        fig.update_traces(marker_line_width=0)
    except Exception:
        pass
    return fig


def corneado(fig, r=5):
    try:
        fig.update_traces(marker=dict(cornerradius=r))
    except Exception:
        pass
    return fig


def tabla(df, **kw):
    st.dataframe(df, width="stretch", hide_index=True, **kw)

# ---------------------------------------------------------------------------
# Logica (medidas replicadas del reporte Power BI)
# ---------------------------------------------------------------------------
def filtra_ventas():
    m = fact["anio"] == sel_anio
    m &= fact["mes_num"] == sel_mes
    m &= fact["Producto"].isin(sel_productos)
    m &= fact["centro_costo"].isin(sel_pdvs)
    return fact[m].copy()


def conteos_por(grupo, f):
    return f.groupby(grupo, as_index=False).size().rename(columns={"size": "Cant. Ventas"})


def _base_ventas():
    return fact[(fact["Producto"].isin(sel_productos)) & (fact["centro_costo"].isin(sel_pdvs))]


def comparativos_por(grupo):
    base = _base_ventas()
    pv_anio, pv_mes = (sel_anio - 1, 12) if sel_mes == 1 else (sel_anio, sel_mes - 1)
    ay_anio = sel_anio - 1

    def cnt(an, me):
        d = base[(base["anio"] == an) & (base["mes_num"] == me)]
        if d.empty:
            return pd.DataFrame({grupo: pd.Series(dtype=object), "n": pd.Series(dtype="Int64")})
        return d.groupby(grupo, as_index=False).size().rename(columns={"size": "n"})

    out = cnt(sel_anio, sel_mes).rename(columns={"n": "Cant. Ventas"})
    out = out.merge(cnt(pv_anio, pv_mes).rename(columns={"n": "Mes Anterior"}), on=grupo, how="outer")
    out = out.merge(cnt(ay_anio, sel_mes).rename(columns={"n": "Año Anterior"}), on=grupo, how="outer")
    return out.sort_values("Cant. Ventas", ascending=False).fillna(0)


def dias_laborales_mes():
    return int(cal[(cal["anio"] == sel_anio) & (cal["mes_num"] == sel_mes)]["Día Laboral"].sum())


def dias_laborales_transcurridos(f):
    if f.empty:
        return 0
    fechamax = f["fec_registro"].max()
    cal_mes = cal[(cal["anio"] == sel_anio) & (cal["mes_num"] == sel_mes)]
    return int(cal_mes[cal_mes["Date"] <= fechamax]["Día Laboral"].sum())


def proyeccion(f):
    t = dias_laborales_transcurridos(f)
    dl = dias_laborales_mes()
    return (len(f) / t * dl) if t and dl else 0


def mes_anterior_total():
    pv_anio, pv_mes = (sel_anio - 1, 12) if sel_mes == 1 else (sel_anio, sel_mes - 1)
    b = _base_ventas()
    return len(b[(b["anio"] == pv_anio) & (b["mes_num"] == pv_mes)])


def anio_anterior_total():
    b = _base_ventas()
    return len(b[(b["anio"] == sel_anio - 1) & (b["mes_num"] == sel_mes)])


# ---------------------------------------------------------------------------
# Paginas
# ---------------------------------------------------------------------------
tab_inicio, tab_claro, tab_proy, tab_oficinas, tab_hist, tab_refs, tab_historial = st.tabs(
    ["📊 Inicio", "🎯 Claro", "🚀 Proy.", "🏢 Oficinas", "🕘 Histórico",
     "📱 Ventas x Ref.", "📈 Historial"]
)

periodo = f"{MESES[sel_mes].capitalize()} {sel_anio}"

# =============================== INICIO ======================================
with tab_inicio:
    f = filtra_ventas()
    if f.empty:
        st.warning("Sin ventas con los filtros seleccionados.")
    else:
        cant = len(f)
        ingresos = float(f["valor_telefono_"].fillna(0).sum() + f["valor_plan_"].fillna(0).sum())
        pm = mes_anterior_total()
        pa = anio_anterior_total()
        proy = proyeccion(f)
        var_m = cant - pm
        var_a = cant - pa

        render_kpis([
            (BRAND, "Ventas", FMT_NUM(cant), f"En {periodo} · {FMT_PCT(100 * cant / max(cant + pm, 1))} del mes anterior"),
            (GOLD, "Ingreso total", FMT_DIN(ingresos), "Planes + equipos", "xs"),
            ("#2563EB", "Mes anterior", FMT_NUM(pm), f"{FMT_NUM(abs(var_m))} respecto al actual"),
            (VERDE, "Año anterior", FMT_NUM(pa), f"{FMT_NUM(abs(var_a))} respecto al actual"),
            ("#8B5CF6", "Proyección del mes", FMT_NUM(proy), "Sobre días laborales"),
            (INK, "Corte", str(f["fec_registro"].max().date()), "Último registro cargado"),
        ])

        st.markdown('<hr class="sep">', unsafe_allow_html=True)

        c1, c2 = st.columns([1, 1.35], gap="medium")
        with c1:
            sec_title("Proyección vs. real", nota=periodo)
            pct = (cant / proy * 100) if proy else 0
            gauge = go.Figure(go.Indicator(
                mode="number", value=cant,
                number={"font": {"size": 46, "color": INK}},
                domain={"x": [0, 1], "y": [0.1, 1]},
                gauge={
                    "axis": {"range": [0, max(cant * 1.08, proy * 1.08)], "tickformat": ",.0f"},
                    "bar": {"color": BRAND},
                    "bgcolor": GRID,
                    "borderwidth": 0,
                    "steps": [{"range": [0, cant], "color": "#FDECEE"}],
                    "threshold": {"line": {"color": GOLD, "width": 4},
                                  "thickness": 0.9, "value": proy},
                },
            ))
            estilizar(gauge, h=250)
            gauge.add_annotation(
                x=0.5, y=0.02, showarrow=False,
                text=f"Meta del mes (línea dorada): <b>{FMT_NUM(proy)}</b> · cumplimiento "
                     f"<b>{FMT_PCT(pct)}</b>",
                xref="paper", yref="paper", font=dict(size=13, color=MUTED),
            )
            st.plotly_chart(gauge, width="stretch")

            sec_title("Ventas por tipo de producto")
            tp = conteos_por("TipoProducto", f).sort_values("Cant. Ventas", ascending=False)
            fig = px.bar(tp, x="TipoProducto", y="Cant. Ventas", text="Cant. Ventas",
                         color_discrete_sequence=[BRAND])
            fig.update_traces(textposition="outside", textfont_size=12,
                             texttemplate="%{y:,.0f}")
            estilizar(fig, h=290)
            corneado(fig)
            st.plotly_chart(fig, width="stretch")

        with c2:
            sec_title("Ventas por oficina · vs. mes y año anterior")
            comp = comparativos_por("centro_costo")
            figb = go.Figure()
            figb.add_bar(x=comp["centro_costo"], y=comp["Cant. Ventas"],
                         name="Actual", marker_color=BRAND)
            figb.add_bar(x=comp["centro_costo"], y=comp["Mes Anterior"],
                         name="Mes Anterior", marker_color="#CBD5E1")
            figb.add_bar(x=comp["centro_costo"], y=comp["Año Anterior"],
                         name="Año Anterior", marker_color="#93C5FD")
            figb.update_layout(barmode="group")
            estilizar(figb, h=380)
            corneado(figb, r=4)
            figb.update_xaxes(tickangle=-30)
            st.plotly_chart(figb, width="stretch")

            sec_title("Ventas diarias del mes")
            diaria = f.groupby("dia", as_index=False).size().rename(columns={"size": "Ventas"})
            figl = px.line(diaria, x="dia", y="Ventas", markers=True, color_discrete_sequence=[BRAND])
            figl.update_traces(line_width=3, marker_size=7, fill="tozeroy",
                               fillcolor="rgba(229,33,43,0.08)")
            figl.update_layout(xaxis_title="", yaxis_title="Ventas", xaxis=dict(dtick=1))
            estilizar(figl, h=260)
            st.plotly_chart(figl, width="stretch")

        c3, c4 = st.columns(2, gap="medium")
        with c3:
            sec_title("Top vendedores", nota=periodo)
            vend = f.groupby("vendedor", as_index=False).size().rename(columns={"size": "Cant. Ventas"})
            vend = vend.sort_values("Cant. Ventas", ascending=False).head(15)
            disp_v = pd.DataFrame({
                "Vendedor": vend["vendedor"],
                "Ventas": [FMT_NUM(v) for v in vend["Cant. Ventas"]],
            })
            tabla(disp_v, height=360)
        with c4:
            sec_title("Ventas por marca · vs. año anterior")
            mar = f.groupby("Marca", as_index=False).size().rename(columns={"size": "Cant. Ventas"})
            mar_ant = _base_ventas()
            mar_ant = mar_ant[(mar_ant["anio"] == sel_anio - 1) & (mar_ant["mes_num"] == sel_mes)]
            mar_ant = mar_ant.groupby("Marca", as_index=False).size().rename(columns={"size": "Año Anterior"})
            mar = mar.merge(mar_ant, on="Marca", how="outer").fillna(0)
            mar["Cant. Ventas"] = mar["Cant. Ventas"].astype(int)
            mar["Año Anterior"] = mar["Año Anterior"].astype(int)
            mar = mar.sort_values("Cant. Ventas", ascending=False).head(12)
            g = go.Figure()
            g.add_bar(x=mar["Marca"], y=mar["Cant. Ventas"], name="Actual", marker_color=BRAND)
            g.add_bar(x=mar["Marca"], y=mar["Año Anterior"], name="Año Anterior", marker_color="#93C5FD")
            g.update_layout(barmode="group")
            estilizar(g, h=360)
            corneado(g, r=4)
            g.update_xaxes(tickangle=-30)
            st.plotly_chart(g, width="stretch")

# =============================== CLARO =======================================
with tab_claro:
    c_anio, c_mes, c_meta = st.columns(3)
    with c_anio:
        anio_rp_sel = st.selectbox("Año (actividades)", anios_rp,
                                   index=anios_rp.index(anio_rp_default), key="claro_anio")
        mes_rp_opts = sorted(rp.loc[rp["anio"] == anio_rp_sel, "mes_num"].unique().tolist())
    with c_mes:
        mes_rp_sel = st.selectbox("Mes (actividades)", mes_rp_opts,
                                  format_func=lambda m: MESES[m].capitalize(),
                                  index=len(mes_rp_opts) - 1 if mes_rp_opts else 0, key="claro_mes")
    with c_meta:
        sel_meta = st.selectbox("Categoría de meta", OPCIONES_META, index=0, key="claro_meta")
    frp = rp[(rp["anio"] == anio_rp_sel) & (rp["mes_num"] == mes_rp_sel)].copy()
    fmet = metas[(metas["anio"] == anio_rp_sel) & (metas["mes_num"] == mes_rp_sel)].copy()
    fmet = fmet[fmet["META_DE"] == sel_meta]
    periodo_rp = f"{MESES[mes_rp_sel].capitalize()} {anio_rp_sel}"

    if frp.empty and fmet.empty:
        st.warning("Sin registros para este periodo.")
    else:
        diasm = pd.Timestamp(anio_rp_sel, mes_rp_sel, 1).days_in_month
        dia_act = int(frp["ACTIVACION"].max().day) if not frp.empty else 1
        proy_rp = round(len(frp) / dia_act * diasm) if not frp.empty and dia_act else 0
        cumpl_g = len(frp[frp["PRODUCTO"] == sel_meta]) if not frp.empty else 0
        meta_g = int(fmet["Valor"].sum())

        render_kpis([
            (BRAND, "Ventas Rp", FMT_NUM(len(frp)), f"Actividades en {periodo_rp}"),
            ("#8B5CF6", "Proyectado Rp", FMT_NUM(proy_rp), "Extrapolación al cierre del mes"),
            (INK, "Corte de activaciones", str(frp["ACTIVACION"].max().date()) if not frp.empty else "—",
             "Última fecha cargada"),
            (VERDE, f"Cumplimiento · {sel_meta}", FMT_NUM(cumpl_g),
             f"Meta {FMT_NUM(meta_g)} · {FMT_PCT(cumpl_g / meta_g * 100) if meta_g else '—'}"),
        ])

        st.markdown('<hr class="sep">', unsafe_allow_html=True)

        c1, c2 = st.columns([1, 1.35], gap="medium")
        with c1:
            sec_title("Ventas y proyección por producto", nota=periodo_rp)
            p1 = frp.groupby("PRODUCTO", as_index=False).agg(
                Ventas=("CO_ID", "count"),
                Corte=("ACTIVACION", "max"),
            )
            p1["Proyectado"] = (p1["Ventas"] / p1["Corte"].dt.day * diasm).round().astype(int)
            p1["Corte"] = p1["Corte"].dt.strftime("%d/%m/%Y")
            p1["Ventas"] = p1["Ventas"].map(FMT_NUM)
            p1["Proyectado"] = p1["Proyectado"].map(FMT_NUM)
            tabla(p1.rename(columns={"PRODUCTO": "Producto", "Corte": "Corte", 
                                     "Ventas": "Ventas Rp", "Proyectado": "Proyectado"}),
                  height=330)

            sec_title("Cumplimiento por punto")
            meta_p = fmet.groupby("CODIGO", as_index=False)["Valor"].sum().rename(
                columns={"Valor": "Meta Claro"})
            exig = frp[frp["PRODUCTO"] == sel_meta].groupby("DISTRIBUIDOR", as_index=False).size() \
                .rename(columns={"size": "Cumplimiento rp"})
            t2 = meta_p.merge(exig, left_on="CODIGO", right_on="DISTRIBUIDOR", how="left")
            t2 = t2.merge(codigos[["CODIGO", "NOMBREPUNTO"]], on="CODIGO", how="left")
            t2["Cumplimiento rp"] = t2["Cumplimiento rp"].fillna(0).astype(int)
            t2["% Cumplimiento"] = (
                t2["Cumplimiento rp"] / t2["Meta Claro"].replace(0, pd.NA) * 100
            ).round(1)
            t2 = t2.sort_values("% Cumplimiento", ascending=False, na_position="last")
            t2["Meta Claro"] = t2["Meta Claro"].map(FMT_NUM)
            t2["Cumplimiento rp"] = t2["Cumplimiento rp"].map(FMT_NUM)
            t2["% Cumplimiento"] = t2["% Cumplimiento"].map(lambda v: "" if pd.isna(v)
                                                             else FMT_PCT(v))
            tabla(t2[["NOMBREPUNTO", "Cumplimiento rp", "Meta Claro", "% Cumplimiento"]]
                  .rename(columns={"NOMBREPUNTO": "Punto"}),
                  height=360)

        with c2:
            sec_title("Evolución mensual por producto", nota=f"Año {anio_rp_sel}")
            evo = rp[(rp["anio"] == anio_rp_sel)].groupby("mes", as_index=False).size() \
                .rename(columns={"size": "Ventas"})
            figE = go.Figure()
            orden = [MESES[m] for m in range(1, 13) if MESES[m] in evo["mes"].tolist()]
            evo["mes"] = pd.Categorical(evo["mes"], categories=orden, ordered=True)
            evo = evo.sort_values("mes")
            for i, prod in enumerate(rp[rp["anio"] == anio_rp_sel].PRODUCTO.unique()):
                e2 = rp[(rp["anio"] == anio_rp_sel) & (rp["PRODUCTO"] == prod)] \
                    .groupby("mes").size().reindex(orden, fill_value=0)
                figE.add_bar(x=e2.index, y=e2.values, name=prod,
                             marker_color=PALETA[i % len(PALETA)])
            figE.update_layout(barmode="stack")
            estilizar(figE, h=380)
            corneado(figE, r=3)
            st.plotly_chart(figE, width="stretch")

            sec_title("Matriz producto × mes", nota=f"Ventas Rp del año {anio_rp_sel}")
            piv = rp[rp["anio"] == anio_rp_sel].groupby(
                ["PRODUCTO", "mes"], as_index=False).size().rename(columns={"size": "Ventas"})
            piv_t = piv.pivot_table(index="PRODUCTO", columns="mes", values="Ventas",
                                    aggfunc="sum", fill_value=0)
            piv_t = piv_t.reindex(columns=[c for c in orden if c in piv_t.columns])
            tab_piv = piv_t.copy()
            for c in tab_piv.columns:
                tab_piv[c] = tab_piv[c].map(FMT_NUM)
            tabla(tab_piv, height=330)

# =============================== PROYECCION ==================================
with tab_proy:
    f = filtra_ventas()
    dl = dias_laborales_mes()
    dlt = dias_laborales_transcurridos(f)
    proy = proyeccion(f)

    if f.empty:
        st.warning("Sin ventas con los filtros seleccionados.")
    else:
        render_kpis([
            (BRAND, "Cant. ventas", FMT_NUM(len(f)), f"Registros en {periodo}"),
            ("#2563EB", "Días laborales del mes", FMT_NUM(dl), "Según calendario"),
            (GOLD, "Días laborales transcurridos", FMT_NUM(dlt),
             "Hasta el último registro"),
            ("#8B5CF6", "Proyección", FMT_NUM(proy),
             f"{FMT_PCT(len(f) / proy * 100) if proy else '—'} de cumplimiento"),
        ])

        st.markdown('<hr class="sep">', unsafe_allow_html=True)

        c1, c2 = st.columns([1, 1.35], gap="medium")
        with c1:
            sec_title("Ventas y proyección por producto", nota=periodo)
            tp = f.groupby("TipoProducto", as_index=False).size().rename(
                columns={"size": "Cant. Ventas"})
            tp["Proyeccion"] = (tp["Cant. Ventas"] / dlt * dl).round().astype(int) if dlt else tp["Cant. Ventas"]
            tp["Cant. Ventas"] = tp["Cant. Ventas"].map(FMT_NUM)
            tp["Proyeccion"] = tp["Proyeccion"].map(FMT_NUM)
            tabla(tp.rename(columns={"TipoProducto": "Tipo", "Proyeccion": "Proyección"}),
                  height=300)

            sec_title("Proyección por oficina", nota=f"Tope: {FMT_NUM(proy)}")
            comp_p = f.groupby("centro_costo", as_index=False).size().rename(
                columns={"size": "Cant. Ventas"})
            comp_p["Proyeccion"] = (comp_p["Cant. Ventas"] / dlt * dl).round().astype(int) if dlt else 0
            comp_p = comp_p.sort_values("Proyeccion", ascending=False).head(12)
            figp = go.Figure()
            figp.add_bar(x=comp_p["centro_costo"], y=comp_p["Proyeccion"],
                         name="Proyección", marker_color=GOLD)
            figp.add_bar(x=comp_p["centro_costo"], y=comp_p["Cant. Ventas"],
                         name="Actual", marker_color="rgba(229,33,43,0.45)")
            figp.update_layout(barmode="group")
            estilizar(figp, h=320)
            corneado(figp, r=4)
            figp.update_xaxes(tickangle=-30)
            st.plotly_chart(figp, width="stretch")

        with c2:
            sec_title("Proyección por marca", nota="Barras: real · Línea: proyectado")
            mcomp = f.groupby("Marca", as_index=False).size().rename(columns={"size": "Cant. Ventas"})
            mcomp["Proyeccion"] = (mcomp["Cant. Ventas"] / dlt * dl).round().astype(int) if dlt else 0
            mcomp = mcomp.sort_values("Cant. Ventas", ascending=False).head(14)
            mc = go.Figure()
            mc.add_bar(x=mcomp["Marca"], y=mcomp["Cant. Ventas"], name="Cant. Ventas",
                       marker_color=BRAND)
            mc.add_trace(go.Scatter(x=mcomp["Marca"], y=mcomp["Proyeccion"],
                                    name="Proyección", mode="lines+markers",
                                    line=dict(color=GOLD, width=4),
                                    marker=dict(size=9, color=GOLD)))
            estilizar(mc, h=520)
            corneado(mc, r=4)
            mc.update_xaxes(tickangle=-30)
            st.plotly_chart(mc, width="stretch")

# =============================== OFICINAS ====================================
with tab_oficinas:
    f = filtra_ventas()
    ofi_opc = st.selectbox("Oficina / PDV", [OPCION_TODOS] + pdvs,
                           index=_indice_opcion(pdvs, sel_pdvs), key="pdv_oficinas")
    if ofi_opc != OPCION_TODOS:
        f = f[f["centro_costo"] == ofi_opc]
    if f.empty:
        st.warning("Sin datos con los filtros.")
    else:
        c1, c2 = st.columns([1, 1.35], gap="medium")
        with c1:
            sec_title("Ventas por tipo de producto", nota=periodo)
            tp = conteos_por("TipoProducto", f).sort_values("Cant. Ventas", ascending=False)
            tp["Cant. Ventas"] = tp["Cant. Ventas"].map(FMT_NUM)
            tabla(tp.rename(columns={"TipoProducto": "Tipo"}),
                  height=320)

            sec_title("Evolución por tipo de producto", nota="Serie mensual")
            evo = f.groupby(["anio_mes", "TipoProducto"], as_index=False).size() \
                .rename(columns={"size": "Ventas"})
            figE = px.bar(evo, x="anio_mes", y="Ventas", color="TipoProducto",
                          color_discrete_sequence=PALETA)
            figE.update_layout(barmode="group")
            estilizar(figE, h=340)
            corneado(figE, r=3)
            st.plotly_chart(figE, width="stretch")

        with c2:
            sec_title("Ventas por marca", nota=f"{len(f)} registros")
            mar = conteos_por("Marca", f).sort_values("Cant. Ventas", ascending=False).head(15)
            figm = px.bar(mar, x="Marca", y="Cant. Ventas", color_discrete_sequence=[BRAND])
            estilizar(figm, h=420)
            corneado(figm)
            figm.update_xaxes(tickangle=-35)
            st.plotly_chart(figm, width="stretch")

# =============================== HISTORICO ===================================
with tab_hist:
    f = filtra_ventas()
    if f.empty:
        st.warning("Sin datos con los filtros.")
    else:
        sec_title(f"Composición de ventas · {periodo}",
                  nota=f"{FMT_NUM(len(f))} registros · {FMT_DIN(float(f['valor_telefono_'].fillna(0).sum() + f['valor_plan_'].fillna(0).sum()))} ingreso")
        c1, c2, c3 = st.columns([1, 1.2, 1.35], gap="medium")
        with c1:
            sec_title("Por tipo de producto")
            tp = conteos_por("TipoProducto", f).sort_values("Cant. Ventas", ascending=False)
            tp["Cant. Ventas"] = tp["Cant. Ventas"].map(FMT_NUM)
            tabla(tp.rename(columns={"TipoProducto": "Tipo"}))
        with c2:
            sec_title("Por oficina")
            comp = conteos_por("centro_costo", f).sort_values("Cant. Ventas", ascending=False)
            figc = px.bar(comp, x="centro_costo", y="Cant. Ventas",
                          color_discrete_sequence=[BRAND])
            estilizar(figc, h=420)
            corneado(figc)
            figc.update_xaxes(tickangle=-35)
            st.plotly_chart(figc, width="stretch")
        with c3:
            sec_title("Por marca", nota="Top 12")
            mar = conteos_por("Marca", f).sort_values("Cant. Ventas", ascending=False).head(12)
            figm = px.bar(mar, y="Marca", x="Cant. Ventas", orientation="h",
                          color_discrete_sequence=[BRAND], text="Cant. Ventas")
            figm.update_traces(textposition="outside")
            estilizar(figm, h=420)
            corneado(figm)
            st.plotly_chart(figm, width="stretch")

# =============================== REFERENCIAS =================================
with tab_refs:
    f = filtra_ventas()
    if f.empty:
        st.warning("Sin datos con los filtros.")
    else:
        c1, c2 = st.columns([1, 1.5], gap="medium")
        with c1:
            sec_title("Ventas por tipo de producto", nota=periodo)
            tp = conteos_por("TipoProducto", f).sort_values("Cant. Ventas", ascending=False)
            fig = px.bar(tp, x="TipoProducto", y="Cant. Ventas", text="Cant. Ventas",
                         color_discrete_sequence=[BRAND])
            fig.update_traces(textposition="outside", textfont_size=13,
                             texttemplate="%{y:,.0f}")
            estilizar(fig, h=420)
            corneado(fig)
            st.plotly_chart(fig, width="stretch")
        with c2:
            sec_title("Ventas por referencia (modelo)", nota="Top 50")
            ref = f.groupby("Marca", as_index=False).size().rename(columns={"size": "Cant. Ventas"})
            ref = ref.sort_values("Cant. Ventas", ascending=False).head(50)
            ref["Cant. Ventas"] = ref["Cant. Ventas"].map(FMT_NUM)
            tabla(ref.rename(columns={"Marca": "Referencia", "Cant. Ventas": "Ventas"}),
                  height=460)

# =============================== HISTORIAL ===================================
with tab_historial:
    base = _base_ventas()
    piv = base.groupby(["anio_mes", "TipoProducto"], as_index=False).size().rename(
        columns={"size": "Cant. Ventas"})
    piv_t = piv.pivot_table(index="anio_mes", columns="TipoProducto",
                            values="Cant. Ventas", aggfunc="sum", fill_value=0)
    piv_t = piv_t.reindex(sorted(piv_t.index))
    totales = piv_t.sum(axis=1)
    piv_t.insert(0, "Total", totales)

    sec_title("Historial mensual por tipo de producto",
              nota=f"{FMT_NUM(int(totales.sum()))} ventas · {base['anio_mes'].min()} → {base['anio_mes'].max()}")

    figH = go.Figure()
    for i, col in enumerate(piv_t.columns[1:]):
        figH.add_scatter(x=piv_t.index, y=piv_t[col], name=col,
                         mode="lines+markers", line=dict(width=3, color=PALETA[i % len(PALETA)]),
                         marker=dict(size=6))
    estilizar(figH, h=420)
    st.plotly_chart(figH, width="stretch")

    tabP = piv_t.copy()
    for c in tabP.columns:
        tabP[c] = tabP[c].map(FMT_NUM)
    tabla(tabP.rename_axis("Mes / Año").reset_index(), height=360)

# ---------------------------------------------------------------------------
st.markdown(
    f'<div class="foot">Anclu · Dashboard portado de Power BI a Streamlit · '
    f'Datos con corte al {FECHA_CORTE.strftime("%d/%m/%Y")}</div>',
    unsafe_allow_html=True,
)
