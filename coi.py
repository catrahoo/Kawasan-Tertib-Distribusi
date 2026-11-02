"""Dashboard COI TANAH AIR — data dari export KMZ aplikasi Map Marker (pin + foto outlet)."""
import base64
import colorsys
import hashlib
import io
import pathlib
import re
import xml.etree.ElementTree as ET
import zipfile

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
import ui
from PIL import Image, ImageOps
from streamlit_folium import st_folium

KMZ_DEFAULT = pathlib.Path(__file__).resolve().parent / "data" / "coi_tanah_air.kmz"
AREA_ORDER = ["Girilaya", "Lontar", "UINSA"]
JENIS_COLORS = {"SNT": "#2E7D32", "PNT": "#D32F2F", "SWK": "#1E6FE0", "OCS": "#F2C200", "WARKOP": "#757575"}
JENIS_DEFAULT = "#9E9E9E"
_K = "{http://www.opengis.net/kml/2.2}"
_WARKOP = re.compile(r"warkop|wakrop|warung kopi|kopi|coffe|caffe|cafe|giras", re.I)


# ---------------------------------------------------------------- parse KMZ
def area_dari_folder(nama: str) -> str:
    n = re.sub(r"(?i)\bcluster\b", "", nama or "").strip()
    low = n.lower()
    if "girilaya" in low:
        return "Girilaya"
    if "uinsa" in low:
        return "UINSA"
    if "lontar" in low:
        return "Lontar"
    return n.title() or "Lainnya"


def jenis_dari_warna(kml_color: str) -> str:
    """Warna pin Map Marker (aabbggrr) → kode: hijau SNT, merah/pink PNT, biru SWK, kuning OCS, abu WARKOP."""
    c = (kml_color or "").strip().lower()
    if len(c) != 8:
        return ""
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (6, 4, 2))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < 0.2:
        return "WARKOP"
    h *= 360
    if h < 25 or h >= 290:
        return "PNT"
    if h < 70:
        return "OCS"
    if h < 170:
        return "SNT"
    return "SWK"


def type_dari_nama(nama: str) -> str:
    return "Warkop" if _WARKOP.search(nama or "") else "Kelontong"


@st.cache_data(show_spinner="Membaca KMZ…", max_entries=4)
def parse_kmz(raw: bytes):
    """Return (DataFrame outlet, dict nama_file → bytes foto). Pin duplikat (nama+titik sama) digabung."""
    z = zipfile.ZipFile(io.BytesIO(raw))
    kml_name = next(n for n in z.namelist() if n.lower().endswith(".kml"))
    root = ET.fromstring(z.read(kml_name))
    styles = {}
    for s in root.iter(_K + "Style"):
        col = s.find(f"{_K}IconStyle/{_K}color")
        if s.get("id") and col is not None:
            styles[s.get("id")] = col.text
    names = set(z.namelist())
    rows, seen, foto, foto_hash = [], {}, {}, {}

    def placemarks():
        folders = list(root.iter(_K + "Folder"))
        if not folders:
            for p in root.iter(_K + "Placemark"):
                yield "", p
        for f in folders:
            nm = f.find(_K + "name")
            for p in f.findall(_K + "Placemark"):
                yield (nm.text if nm is not None else ""), p

    for folder, p in placemarks():
        co = p.find(f".//{_K}coordinates")
        if co is None or not co.text:
            continue
        lon, lat = (float(x) for x in co.text.strip().split(",")[:2])
        nama = (p.findtext(_K + "name") or "").strip()
        desc = p.findtext(_K + "description") or ""
        imgs = re.findall(r'src="([^"]+)"', desc)
        note = re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", "\n", desc)).strip()
        style = (p.findtext(_K + "styleUrl") or "").lstrip("#")
        area = area_dari_folder(folder)
        key = (area, nama.lower(), round(lat, 6), round(lon, 6))
        if key not in seen:
            seen[key] = len(rows)
            rows.append({"AREA": area, "NAMA OUTLET": nama, "JENIS OUTLET": jenis_dari_warna(styles.get(style, "")),
                         "TYPE OUTLET": type_dari_nama(nama), "CATATAN": note, "LAT": lat, "LON": lon, "FOTO": []})
        r = rows[seen[key]]
        for path in imgs:
            if path not in names:
                continue
            b = z.read(path)
            h = hashlib.md5(b).hexdigest()
            fname = foto_hash.setdefault(h, path)
            foto[fname] = b
            if fname not in r["FOTO"]:
                r["FOTO"].append(fname)
    df = pd.DataFrame(rows, columns=["AREA", "NAMA OUTLET", "JENIS OUTLET", "TYPE OUTLET", "CATATAN",
                                     "LAT", "LON", "FOTO"])
    df["JML FOTO"] = df["FOTO"].apply(len)
    df["GOOGLE MAPS"] = [f"https://www.google.com/maps/search/?api=1&query={a},{b}" for a, b in zip(df["LAT"], df["LON"])]
    order = {a: i for i, a in enumerate(AREA_ORDER)}
    df = df.sort_values(["AREA", "NAMA OUTLET"], key=lambda s: s.map(order).fillna(99) if s.name == "AREA"
                        else s.str.lower()).reset_index(drop=True)
    return df, foto


@st.cache_data(show_spinner=False, max_entries=600)
def thumb(raw: bytes, size: int) -> bytes:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    img.thumbnail((size, size))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=78)
    return buf.getvalue()


# ---------------------------------------------------------------- tampilan
BENDERA = ("<span style='display:inline-flex;flex-direction:column;width:1.45em;height:.97em;"
           "border:1px solid rgba(0,0,0,.25);border-radius:3px;overflow:hidden;flex:none'>"
           "<span style='flex:1;background:#E70011'></span><span style='flex:1;background:#FFFFFF'></span></span>")


def judul():
    """Judul dengan bendera merah putih (CSS, supaya sama di Windows/Android/iPhone)."""
    st.markdown(f"<h1 style='display:flex;align-items:center;gap:.55em'>{BENDERA}COI TANAH AIR</h1>",
                unsafe_allow_html=True)


def _esc(x) -> str:
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_map(d: pd.DataFrame, foto: dict) -> folium.Map:
    m = folium.Map(location=[d["LAT"].mean(), d["LON"].mean()], zoom_start=15, control_scale=True,
                   tiles="OpenStreetMap")
    for _, r in d.iterrows():
        img = ""
        if r["FOTO"]:
            b64 = base64.b64encode(thumb(foto[r["FOTO"][0]], 320)).decode()
            img = f"<img src='data:image/jpeg;base64,{b64}' style='width:240px;border-radius:6px;margin-top:6px'><br>"
        note = _esc(r["CATATAN"]).replace("\n", "<br>")
        popup = (
            f"<div style='font-family:Arial;font-size:12px;min-width:200px'>"
            f"<b>{_esc(r['NAMA OUTLET'])}</b><br>{r['AREA']} · {r['JENIS OUTLET'] or '–'} · {r['TYPE OUTLET']}"
            + (f"<br><i>{note}</i>" if note else "") + "<br>" + img
            + (f"<span style='color:#666'>{r['JML FOTO']} foto — lihat tab Foto</span><br>" if r["JML FOTO"] > 1 else "")
            + f"<a href='{r['GOOGLE MAPS']}' target='_blank'>Buka di Google Maps ↗</a></div>"
        )
        color = JENIS_COLORS.get(r["JENIS OUTLET"], JENIS_DEFAULT)
        folium.CircleMarker([r["LAT"], r["LON"]], radius=9, color="#FFFFFF", weight=2, fill=True,
                            fill_color=color, fill_opacity=0.95, tooltip=r["NAMA OUTLET"],
                            popup=folium.Popup(popup, max_width=280)).add_to(m)
    m.fit_bounds([[d["LAT"].min(), d["LON"].min()], [d["LAT"].max(), d["LON"].max()]], padding=(20, 20))
    return m


def render():
    # ---- sumber data
    with st.sidebar:
        st.header("Filter")
        up = st.file_uploader("Upload KMZ baru (Map Marker)", type=["kmz"],
                              help="Hanya untuk dilihat sementara. Data tetap di repo kembali dipakai saat app restart.")
    if up is not None:
        raw, sumber = up.getvalue(), f"upload: {up.name}"
    elif KMZ_DEFAULT.exists():
        raw, sumber = KMZ_DEFAULT.read_bytes(), "data tersimpan di repo"
    else:
        judul()
        st.info("Belum ada data. Upload file KMZ dari aplikasi Map Marker di sidebar.")
        return
    try:
        df, foto = parse_kmz(raw)
    except Exception as e:
        judul()
        st.error(f"File KMZ tidak bisa dibaca: {e}")
        return
    if df.empty:
        judul()
        st.warning("KMZ tidak berisi pin outlet.")
        return

    areas = [a for a in AREA_ORDER if a in df["AREA"].unique()] + sorted(
        a for a in df["AREA"].unique() if a not in AREA_ORDER)
    jenis_all = [j for j in JENIS_COLORS if j in df["JENIS OUTLET"].unique()]
    tipe_all = sorted(df["TYPE OUTLET"].unique())
    with st.sidebar:
        f_area = st.multiselect("Area", areas, default=areas, key="coi_area")
        f_jenis = st.multiselect("Jenis Outlet", jenis_all, default=jenis_all, key="coi_jenis")
        f_tipe = st.multiselect("Type Outlet", tipe_all, default=tipe_all, key="coi_tipe",
                                help="Ditebak dari nama outlet (warkop/kopi/giras = Warkop).")
        cari = st.text_input("Cari nama outlet", key="coi_cari")
        hanya_foto = st.toggle("Hanya yang ada foto", key="coi_foto")
        st.caption(f"Sumber: {sumber}")

    f = df[df["AREA"].isin(f_area) & (df["JENIS OUTLET"].isin(f_jenis) | df["JENIS OUTLET"].eq(""))
           & df["TYPE OUTLET"].isin(f_tipe)]
    if cari:
        f = f[f["NAMA OUTLET"].str.contains(re.escape(cari), case=False, na=False)]
    if hanya_foto:
        f = f[f["JML FOTO"] > 0]

    judul()
    st.caption(f"{len(f)} outlet · {int(f['JML FOTO'].sum())} foto · area {', '.join(f_area) or '–'}")
    ui.kpi([
        ("Total Outlet", f"{len(f):,}", "toko", "hijau"),
        ("SNT", f"{f['JENIS OUTLET'].eq('SNT').sum():,}", "bendera", "hijau"),
        ("PNT", f"{f['JENIS OUTLET'].eq('PNT').sum():,}", "bendera", "merah"),
        ("SWK", f"{f['JENIS OUTLET'].eq('SWK').sum():,}", "bendera", "biru"),
        ("Ada Foto", "–" if f.empty else f"{(f['JML FOTO'] > 0).mean() * 100:.0f}%", "foto", "kuning"),
    ])

    tab_map, tab_sum, tab_foto, tab_data = st.tabs(["🗺️ Peta", "📊 Ringkasan", "🖼️ Foto", "📋 Data"])

    with tab_map:
        if f.empty:
            st.info("Tidak ada data untuk filter ini.")
        else:
            st.markdown(" &nbsp; ".join(
                f"<span style='display:inline-block;width:12px;height:12px;border-radius:50%;"
                f"background:{JENIS_COLORS[j]};margin-right:4px;vertical-align:middle'></span>{j}"
                for j in jenis_all), unsafe_allow_html=True)
            st.caption("Klik titik untuk lihat nama, catatan, dan foto outlet.")
            with st.spinner("Menyusun peta…"):
                st_folium(build_map(f, foto), height=620, use_container_width=True, returned_objects=[],
                          key="coi_map")

    with tab_sum:
        if f.empty:
            st.info("Tidak ada data untuk filter ini.")
        else:
            c1, c2 = st.columns(2)
            pa = f.groupby(["AREA", "JENIS OUTLET"]).size().reset_index(name="Outlet")
            fig = px.bar(pa, x="AREA", y="Outlet", color="JENIS OUTLET", text_auto=True, title="Outlet per Area",
                         category_orders={"AREA": areas, "JENIS OUTLET": jenis_all},
                         color_discrete_map=JENIS_COLORS)
            fig.update_layout(legend_title=None, xaxis_title=None, margin=dict(t=50, b=10))
            c1.plotly_chart(fig, key="coi_fig_area")
            pt = f.groupby(["TYPE OUTLET", "JENIS OUTLET"]).size().reset_index(name="Outlet")
            fig = px.bar(pt, x="TYPE OUTLET", y="Outlet", color="JENIS OUTLET", text_auto=True,
                         title="Jenis per Type Outlet", category_orders={"JENIS OUTLET": jenis_all},
                         color_discrete_map=JENIS_COLORS)
            fig.update_layout(legend_title=None, xaxis_title=None, margin=dict(t=50, b=10))
            c2.plotly_chart(fig, key="coi_fig_type")

            st.subheader("Rekap per Area")
            agg = {"Outlet": ("NAMA OUTLET", "count")}
            for j in jenis_all:
                agg[j] = ("JENIS OUTLET", lambda s, j=j: s.eq(j).sum())
            agg["Kelontong"] = ("TYPE OUTLET", lambda s: s.eq("Kelontong").sum())
            agg["Warkop"] = ("TYPE OUTLET", lambda s: s.eq("Warkop").sum())
            agg["Ada_Foto"] = ("JML FOTO", lambda s: (s > 0).sum())
            rk = f.groupby("AREA").agg(**agg).reindex([a for a in areas if a in f["AREA"].unique()])
            rk.loc["TOTAL"] = rk.sum()
            st.dataframe(rk.rename(columns=lambda c: c.replace("_", " ")))

    with tab_foto:
        if f.empty:
            st.info("Tidak ada data untuk filter ini.")
        else:
            per_page = 6
            pages = max(1, -(-len(f) // per_page))
            cpg, cinfo = st.columns([1, 3])
            page = cpg.number_input("Halaman", 1, pages, 1, key="coi_page")
            cinfo.caption(f"\n\n{len(f)} outlet · {pages} halaman")
            sub = f.iloc[(page - 1) * per_page: page * per_page]
            cols = st.columns(3)
            for i, (_, r) in enumerate(sub.iterrows()):
                with cols[i % 3].container(border=True):
                    st.markdown(f"**{r['NAMA OUTLET']}**")
                    st.caption(f"{r['AREA']} · {r['JENIS OUTLET'] or '–'} · {r['TYPE OUTLET']}"
                               + (f" · {r['CATATAN']}" if r["CATATAN"] else ""))
                    if r["FOTO"]:
                        pcols = st.columns(min(len(r["FOTO"]), 2))
                        for j, fn in enumerate(r["FOTO"]):
                            pcols[j % len(pcols)].image(thumb(foto[fn], 900))
                    else:
                        st.caption("Belum ada foto.")
                    st.markdown(f"[Buka di Google Maps ↗]({r['GOOGLE MAPS']})")

    with tab_data:
        show = f.drop(columns=["FOTO"]).copy()
        st.dataframe(show, hide_index=True, height=520,
                     column_config={"GOOGLE MAPS": st.column_config.LinkColumn("GOOGLE MAPS", display_text="Buka ↗")})
        st.download_button("⬇️ Download CSV", show.to_csv(index=False).encode("utf-8-sig"),
                           file_name="coi_tanah_air.csv", mime="text/csv")
