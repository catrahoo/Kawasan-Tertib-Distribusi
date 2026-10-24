"""Dashboard Form Outlet — data dari Google Sheet (AppSheet FORM_OUTLET_APPSHEET)."""
import io
import re

import folium
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from PIL import Image, ImageOps
from streamlit_folium import st_folium

st.set_page_config(page_title="Dashboard Outlet", page_icon="📍", layout="wide")

AREA_ORDER = ["SBY BRT", "SBY TIMUR", "SDA BRT", "SDA TIMUR"]
ROUTE_COLORS = ["#1E6FE0", "#E8590C", "#2F9E44", "#AE3EC9", "#C2255C", "#0C8599", "#F08C00", "#5C7CFA"]
YN_COLS = ["WKSK", "ALVA", "PROGRAM KOMPETITOR"]
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.6rem; padding-bottom: 2rem;}
    div[data-testid="stMetric"] {background: rgba(46,125,50,.07); border: 1px solid rgba(46,125,50,.25);
        border-radius: 10px; padding: 10px 14px;}
    div[data-testid="stMetricLabel"] p {font-size: .82rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- login
def password_ok() -> bool:
    pw = st.secrets.get("app_password")
    if not pw or st.session_state.get("login_ok"):
        return True
    st.title("📍 Dashboard Outlet")
    with st.form("login"):
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Masuk"):
            if p == pw:
                st.session_state.login_ok = True
                st.rerun()
            st.error("Password salah")
    return False


if not password_ok():
    st.stop()


# ---------------------------------------------------------------- data
def has_service_account() -> bool:
    return ("gcp_json" in st.secrets or "gcp_service_account" in st.secrets) and "sheet_id" in st.secrets


def sa_info() -> dict:
    """Kunci service account: isi file .json ditempel utuh di gcp_json (atau format [gcp_service_account])."""
    import json

    if "gcp_json" in st.secrets:
        return json.loads(st.secrets["gcp_json"], strict=False)
    return dict(st.secrets["gcp_service_account"])


def sheet_key() -> str:
    """Terima ID sheet atau link lengkap Google Sheet."""
    raw = str(st.secrets["sheet_id"]).strip()
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", raw)
    return m.group(1) if m else raw


@st.cache_resource
def get_creds():
    from google.oauth2.service_account import Credentials

    return Credentials.from_service_account_info(sa_info(), scopes=SCOPES)


@st.cache_resource
def get_drive():
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=get_creds(), cache_discovery=False)


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().upper() for c in df.columns]
    df = df[df["UNIQUE ID"].astype(str).str.strip().ne("") & df["UNIQUE ID"].notna()].copy()
    df["_URUT_INPUT"] = range(len(df))
    df["TANGGAL"] = pd.to_datetime(df["TANGGAL"], dayfirst=True, errors="coerce").dt.date
    ll = df["LOKASI"].astype(str).str.extract(r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)")
    df["LAT"] = pd.to_numeric(ll[0], errors="coerce")
    df["LON"] = pd.to_numeric(ll[1], errors="coerce")
    df.loc[(df["LAT"] == 0) & (df["LON"] == 0), ["LAT", "LON"]] = None
    for c in YN_COLS + ["AREA", "JENIS OUTLET"]:
        if c in df:
            df[c] = df[c].fillna("").astype(str).str.strip().str.upper()
    if "TYPE OUTLET" in df:
        df["TYPE OUTLET"] = df["TYPE OUTLET"].fillna("").astype(str).str.strip().str.title()
    for c in ["NAMA OUTLET", "ALAMAT", "KETERANGAN TAMBAHAN", "FOTO DISPLAY ROKOK", "FOTO SUNBLIND"]:
        if c not in df:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str).str.strip()
    return df.sort_values(["TANGGAL", "_URUT_INPUT"], na_position="last").reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner="Ambil data dari Google Sheet…")
def load_data() -> pd.DataFrame:
    if has_service_account():
        import gspread

        gc = gspread.authorize(get_creds())
        ws = gc.open_by_key(sheet_key()).worksheet(st.secrets.get("sheet_name", "DATA OUTLET"))
        rows = ws.get_all_values()
        df = pd.DataFrame(rows[1:], columns=rows[0])
    else:
        df = pd.read_csv(st.secrets["sheet_csv_url"], dtype=str)
    return prepare(df)


@st.cache_data(ttl=86400, show_spinner=False)
def get_photo(path: str):
    """Ambil foto dari folder AppSheet di Google Drive (perlu service account)."""
    name = str(path).split("/")[-1].strip()
    if not name or not has_service_account():
        return None
    try:
        drive = get_drive()
        q = "name = '%s' and trashed = false" % name.replace("\\", "\\\\").replace("'", "\\'")
        res = drive.files().list(
            q=q, fields="files(id)", pageSize=1, supportsAllDrives=True, includeItemsFromAllDrives=True
        ).execute()
        files = res.get("files", [])
        if not files:
            return None
        raw = drive.files().get_media(fileId=files[0]["id"], supportsAllDrives=True).execute()
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
        img.thumbnail((900, 900))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=82)
        return buf.getvalue()
    except Exception:
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def osrm_route(points: tuple) -> list:
    """Garis rute mengikuti jalan (OSRM). Kalau gagal, pakai garis lurus."""
    if len(points) < 2:
        return [list(p) for p in points]
    base = st.secrets.get("osrm_url", "https://router.project-osrm.org")
    path, step = [], 80
    for s in range(0, len(points) - 1, step - 1):
        chunk = points[s : s + step]
        if len(chunk) < 2:
            break
        coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in chunk)
        try:
            r = requests.get(
                f"{base}/route/v1/driving/{coords}",
                params={"overview": "full", "geometries": "geojson"},
                timeout=20,
            )
            r.raise_for_status()
            geo = r.json()["routes"][0]["geometry"]["coordinates"]
            path += [[lat, lon] for lon, lat in geo]
        except Exception:
            path += [list(p) for p in chunk]
    return path


# ---------------------------------------------------------------- helpers
def pct_y(s: pd.Series) -> str:
    s = s[s.isin(["Y", "N"])]
    return "–" if s.empty else f"{(s.eq('Y').mean() * 100):.0f}%"


def marker_icon(n: int, color: str) -> folium.DivIcon:
    size = 28 if n < 100 else 34
    html = (
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;background:{color};'
        f"border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.45);color:#fff;"
        f"font:700 12px/{size - 4}px Arial,sans-serif;text-align:center;\">{n}</div>"
    )
    return folium.DivIcon(html=html, icon_size=(size, size), icon_anchor=(size // 2, size // 2))


def esc(x) -> str:
    return (str(x) if pd.notna(x) else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_map(d: pd.DataFrame, show_route: bool, follow_road: bool) -> folium.Map:
    pts = d.dropna(subset=["LAT", "LON"])
    center = [pts["LAT"].mean(), pts["LON"].mean()] if len(pts) else [-7.29, 112.73]
    m = folium.Map(location=center, zoom_start=15, control_scale=True, tiles="OpenStreetMap")
    if pts.empty:
        return m
    for i, (tgl, g) in enumerate(pts.groupby("TANGGAL", sort=True)):
        color = ROUTE_COLORS[i % len(ROUTE_COLORS)]
        coords = tuple((float(a), float(b)) for a, b in zip(g["LAT"], g["LON"]))
        if show_route and len(coords) > 1:
            line = osrm_route(coords) if follow_road else [list(c) for c in coords]
            folium.PolyLine(line, color="#FFFFFF", weight=8, opacity=0.9).add_to(m)
            folium.PolyLine(line, color=color, weight=5, opacity=0.9, dash_array="12 8",
                            tooltip=f"Rute {tgl:%d/%m/%Y}").add_to(m)
        for _, r in g.iterrows():
            popup = (
                f"<div style='font-family:Arial;font-size:12px;min-width:190px'>"
                f"<b>#{int(r['NO'])} {esc(r['NAMA OUTLET'])}</b><br>"
                f"{esc(r['ALAMAT'])}<br><br>"
                f"Tanggal: {r['TANGGAL']:%d/%m/%Y}<br>Area: {esc(r['AREA'])}<br>"
                f"Jenis/Type: {esc(r['JENIS OUTLET'])} · {esc(r['TYPE OUTLET'])}<br>"
                f"WKSK: <b>{esc(r['WKSK'])}</b> · ALVA: <b>{esc(r['ALVA'])}</b><br>"
                f"Program Kompetitor: <b>{esc(r['PROGRAM KOMPETITOR'])}</b>"
                + (f"<br><i>{esc(r['KETERANGAN TAMBAHAN'])}</i>" if r["KETERANGAN TAMBAHAN"] else "")
                + "</div>"
            )
            folium.Marker(
                [r["LAT"], r["LON"]],
                icon=marker_icon(int(r["NO"]), color),
                tooltip=f"#{int(r['NO'])} {r['NAMA OUTLET']}",
                popup=folium.Popup(popup, max_width=280),
            ).add_to(m)
    m.fit_bounds([[pts["LAT"].min(), pts["LON"].min()], [pts["LAT"].max(), pts["LON"].max()]], padding=(20, 20))
    return m


# ---------------------------------------------------------------- load
if not has_service_account() and "sheet_csv_url" not in st.secrets:
    st.title("📍 Dashboard Outlet")
    st.error("Secrets belum diisi. Lihat README bagian **Isi Secrets di Streamlit**.")
    st.stop()

try:
    df = load_data()
except Exception as e:
    st.error(f"Gagal ambil data dari Google Sheet: {e}")
    st.stop()

if df.empty:
    st.warning("Belum ada data di sheet DATA OUTLET.")
    st.stop()

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Filter")
    tgl_valid = df["TANGGAL"].dropna()
    tmin, tmax = tgl_valid.min(), tgl_valid.max()
    rng = st.date_input("Tanggal", value=(tmax, tmax), min_value=tmin, max_value=tmax, format="DD/MM/YYYY")
    d_from, d_to = (rng[0], rng[-1]) if isinstance(rng, (list, tuple)) and rng else (tmax, tmax)

    areas = [a for a in AREA_ORDER if a in df["AREA"].unique()] + sorted(
        a for a in df["AREA"].unique() if a and a not in AREA_ORDER
    )
    f_area = st.multiselect("Area", areas, default=areas)
    jenis = sorted(x for x in df["JENIS OUTLET"].unique() if x)
    f_jenis = st.multiselect("Jenis Outlet", jenis, default=jenis)
    tipe = sorted(x for x in df["TYPE OUTLET"].unique() if x)
    f_tipe = st.multiselect("Type Outlet", tipe, default=tipe)
    cari = st.text_input("Cari nama outlet")

    st.divider()
    show_route = st.toggle("Tampilkan garis rute", value=True)
    follow_road = st.toggle("Garis ikut jalan", value=True, help="Pakai OSRM. Matikan kalau peta lambat.")
    if st.button("🔄 Refresh data"):
        load_data.clear()
        st.rerun()
    st.caption("Data otomatis diperbarui tiap 5 menit.")

f = df[
    df["TANGGAL"].between(d_from, d_to)
    & df["AREA"].isin(f_area)
    & (df["JENIS OUTLET"].isin(f_jenis) | df["JENIS OUTLET"].eq(""))
    & (df["TYPE OUTLET"].isin(f_tipe) | df["TYPE OUTLET"].eq(""))
].copy()
if cari:
    f = f[f["NAMA OUTLET"].str.contains(re.escape(cari), case=False, na=False)]
f["NO"] = f.groupby("TANGGAL").cumcount() + 1

# ---------------------------------------------------------------- header + KPI
st.title("📍 Dashboard Kunjungan Outlet")
periode = f"{d_from:%d/%m/%Y}" if d_from == d_to else f"{d_from:%d/%m/%Y} – {d_to:%d/%m/%Y}"
st.caption(f"Periode {periode} · {len(f)} outlet · data terakhir {tmax:%d/%m/%Y}")

k = st.columns(6)
k[0].metric("Total Outlet", f"{len(f):,}")
k[1].metric("OCS", f"{f['JENIS OUTLET'].eq('OCS').sum():,}")
k[2].metric("NON OCS", f"{f['JENIS OUTLET'].eq('NON OCS').sum():,}")
k[3].metric("WKSK tersedia (Y)", pct_y(f["WKSK"]))
k[4].metric("ALVA tersedia (Y)", pct_y(f["ALVA"]))
k[5].metric("Ada Program Kompetitor", pct_y(f["PROGRAM KOMPETITOR"]))

tab_map, tab_sum, tab_foto, tab_data = st.tabs(["🗺️ Peta Rute", "📊 Ringkasan", "🖼️ Foto", "📋 Data"])

# ---------------------------------------------------------------- map
with tab_map:
    if f.empty:
        st.info("Tidak ada data untuk filter ini.")
    else:
        no_loc = f["LAT"].isna().sum()
        hari = f["TANGGAL"].nunique()
        if hari > 1:
            st.caption(f"{hari} hari dipilih — tiap hari punya warna rute sendiri dan nomor urut mulai dari 1.")
        with st.spinner("Menyusun peta…"):
            st_folium(build_map(f, show_route, follow_road), height=620, use_container_width=True,
                      returned_objects=[])
        if no_loc:
            st.warning(f"{no_loc} outlet tidak punya titik lokasi, jadi tidak tampil di peta.")
        urut = f[["TANGGAL", "NO", "NAMA OUTLET", "ALAMAT", "AREA", "WKSK", "ALVA"]].copy()
        urut["TANGGAL"] = pd.to_datetime(urut["TANGGAL"]).dt.strftime("%d/%m/%Y")
        with st.expander("Urutan kunjungan"):
            st.dataframe(urut, hide_index=True)

# ---------------------------------------------------------------- summary
with tab_sum:
    if f.empty:
        st.info("Tidak ada data untuk filter ini.")
    else:
        c1, c2 = st.columns(2)
        per_area = f.groupby(["AREA", "JENIS OUTLET"]).size().reset_index(name="Outlet")
        fig = px.bar(per_area, x="AREA", y="Outlet", color="JENIS OUTLET", text_auto=True,
                     category_orders={"AREA": areas}, title="Outlet per Area",
                     color_discrete_sequence=["#2E7D32", "#81C784", "#FFB74D", "#90A4AE"])
        fig.update_layout(legend_title=None, xaxis_title=None, margin=dict(t=50, b=10))
        c1.plotly_chart(fig)

        av = []
        for col in ["WKSK", "ALVA"]:
            g = f[f[col].isin(["Y", "N"])].groupby("AREA")[col].apply(lambda s: s.eq("Y").mean() * 100)
            av += [{"AREA": a, "Produk": col, "% Tersedia": round(v, 1)} for a, v in g.items()]
        if av:
            fig = px.bar(pd.DataFrame(av), x="AREA", y="% Tersedia", color="Produk", barmode="group",
                         text_auto=".0f", category_orders={"AREA": areas}, title="Ketersediaan WKSK & ALVA (%)",
                         color_discrete_sequence=["#1E6FE0", "#E8590C"])
            fig.update_layout(legend_title=None, xaxis_title=None, yaxis_range=[0, 105], margin=dict(t=50, b=10))
            c2.plotly_chart(fig)

        c3, c4 = st.columns(2)
        per_hari = f.groupby(["TANGGAL", "AREA"]).size().reset_index(name="Outlet")
        per_hari["TANGGAL"] = pd.to_datetime(per_hari["TANGGAL"])
        fig = px.bar(per_hari, x="TANGGAL", y="Outlet", color="AREA", title="Outlet Dikunjungi per Hari",
                     category_orders={"AREA": areas})
        fig.update_layout(legend_title=None, xaxis_title=None, margin=dict(t=50, b=10))
        fig.update_xaxes(tickformat="%d/%m")
        c3.plotly_chart(fig)

        tp = f.groupby(["TYPE OUTLET", "PROGRAM KOMPETITOR"]).size().reset_index(name="Outlet")
        fig = px.bar(tp, x="TYPE OUTLET", y="Outlet", color="PROGRAM KOMPETITOR", text_auto=True,
                     title="Program Kompetitor per Type Outlet",
                     color_discrete_map={"Y": "#C62828", "N": "#B0BEC5"})
        fig.update_layout(legend_title="Kompetitor", xaxis_title=None, margin=dict(t=50, b=10))
        c4.plotly_chart(fig)

        st.subheader("Rekap per Area")
        rk = f.groupby("AREA").agg(
            Outlet=("UNIQUE ID", "count"),
            OCS=("JENIS OUTLET", lambda s: s.eq("OCS").sum()),
            NON_OCS=("JENIS OUTLET", lambda s: s.eq("NON OCS").sum()),
            Kelontong=("TYPE OUTLET", lambda s: s.eq("Kelontong").sum()),
            Warkop=("TYPE OUTLET", lambda s: s.eq("Warkop").sum()),
            WKSK_Y=("WKSK", lambda s: s.eq("Y").sum()),
            ALVA_Y=("ALVA", lambda s: s.eq("Y").sum()),
            Kompetitor_Y=("PROGRAM KOMPETITOR", lambda s: s.eq("Y").sum()),
        ).reindex([a for a in areas if a in f["AREA"].unique()])
        rk.loc["TOTAL"] = rk.sum()
        st.dataframe(rk.rename(columns=lambda c: c.replace("_", " ")))

        odd = f[~f["JENIS OUTLET"].isin(["OCS", "NON OCS", ""])]
        if len(odd):
            st.warning(f"{len(odd)} outlet isi JENIS OUTLET-nya di luar OCS/NON OCS "
                       f"({', '.join(sorted(odd['JENIS OUTLET'].unique()))}). Cek ke yang input.")

# ---------------------------------------------------------------- photos
with tab_foto:
    if f.empty:
        st.info("Tidak ada data untuk filter ini.")
    elif not has_service_account():
        st.info("Foto hanya bisa tampil kalau dashboard tersambung pakai service account (lihat README).")
    else:
        per_page = 6
        pages = max(1, -(-len(f) // per_page))
        cpg, cinfo = st.columns([1, 3])
        page = cpg.number_input("Halaman", 1, pages, 1)
        cinfo.caption(f"\n\n{len(f)} outlet · {pages} halaman · urut sesuai nomor di peta")
        sub = f.iloc[(page - 1) * per_page : page * per_page]
        cols = st.columns(3)
        for i, (_, r) in enumerate(sub.iterrows()):
            with cols[i % 3].container(border=True):
                st.markdown(f"**#{int(r['NO'])} {r['NAMA OUTLET']}**")
                st.caption(f"{r['TANGGAL']:%d/%m/%Y} · {r['AREA']} · {r['JENIS OUTLET']} · {r['TYPE OUTLET']} · "
                           f"WKSK {r['WKSK']} · ALVA {r['ALVA']}")
                a, b = st.columns(2)
                for colx, key, label in [(a, "FOTO DISPLAY ROKOK", "Display"), (b, "FOTO SUNBLIND", "Sunblind")]:
                    img = get_photo(r[key])
                    if img:
                        colx.image(img, caption=label)
                    else:
                        colx.caption(f"{label}: foto tidak ada")

# ---------------------------------------------------------------- table
with tab_data:
    show = f.drop(columns=["_URUT_INPUT", "LAT", "LON"], errors="ignore")
    show = show[["NO"] + [c for c in show.columns if c != "NO"]]
    show["TANGGAL"] = pd.to_datetime(show["TANGGAL"]).dt.strftime("%d/%m/%Y")
    st.dataframe(show, hide_index=True, height=520)
    st.download_button("⬇️ Download CSV", show.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"rekap_outlet_{d_from:%Y%m%d}_{d_to:%Y%m%d}.csv", mime="text/csv")
