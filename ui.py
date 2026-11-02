"""Komponen tampilan bersama: kartu KPI gaya glass dan layar loading awal."""
import html

import streamlit as st

# ikon garis sederhana (gaya lucide), warna ikut currentColor
_SVG = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">{}</svg>')
IKON = {
    "toko": '<path d="M3 9l1.5-5h15L21 9"/><path d="M4 9v11h16V9"/><path d="M9 20v-6h6v6"/><path d="M3 9h18"/>',
    "cek": '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>',
    "silang": '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
    "kotak": '<path d="M21 8l-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/>',
    "persen": '<path d="M19 5L5 19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "bendera": '<path d="M5 21V4"/><path d="M5 4h12l-2 4 2 4H5"/>',
    "foto": '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-8 8"/>',
}
WARNA = {"hijau": "#4ADE80", "merah": "#F87171", "biru": "#60A5FA", "kuning": "#FACC15", "ungu": "#C084FC",
         "oranye": "#FB923C", "abu": "#CBD5E1"}

CSS = """
<style>
.kpi-grid {display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin: 6px 0 18px;}
.kpi-card {background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.12); border-radius: 16px;
    padding: 16px 18px; display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;
    backdrop-filter: blur(8px); transition: transform .25s ease, border-color .25s ease, background .25s ease;}
.kpi-card:hover {transform: translateY(-5px); border-color: rgba(255,255,255,.28); background: rgba(255,255,255,.08);}
.kpi-card .lbl {margin: 0; font-size: .82rem; color: rgba(255,255,255,.62); line-height: 1.3;}
.kpi-card .val {margin: 4px 0 0; font-size: 1.75rem; font-weight: 700; color: #fff; line-height: 1.15;}
.kpi-card .ico {width: 38px; height: 38px; border-radius: 11px; display: flex; align-items: center;
    justify-content: center; flex: none;}
@media (prefers-reduced-motion: reduce) {.kpi-card {transition: none;} .kpi-card:hover {transform: none;}}
</style>
"""


def kpi(items):
    """items: list of (label, nilai, ikon, warna). Tampil sebagai kartu glass dengan ikon."""
    cards = []
    for label, nilai, ikon, warna in items:
        c = WARNA.get(warna, warna)
        cards.append(
            f"<div class='kpi-card'><div><p class='lbl'>{html.escape(str(label))}</p>"
            f"<p class='val'>{html.escape(str(nilai))}</p></div>"
            f"<div class='ico' style='color:{c};background:{c}26'>{_SVG.format(IKON.get(ikon, ''))}</div></div>"
        )
    st.markdown(CSS + "<div class='kpi-grid'>" + "".join(cards) + "</div>", unsafe_allow_html=True)


SPLASH = """
<style>
@keyframes spl-pin {0%,100% {transform: translateY(0)} 50% {transform: translateY(-16px)}}
@keyframes spl-sh {0%,100% {transform: scaleX(1); opacity: .45} 50% {transform: scaleX(.55); opacity: .2}}
@keyframes spl-bar {0% {left: -40%} 100% {left: 100%}}
.spl {position: fixed; inset: 0; z-index: 1000000; background: #0f1a14; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 14px; font-family: "Source Sans Pro", sans-serif;}
.spl .pin {animation: spl-pin 1.1s ease-in-out infinite; color: #EF5350;}
.spl .sh {width: 34px; height: 7px; border-radius: 50%; background: #000; margin-top: -10px;
    animation: spl-sh 1.1s ease-in-out infinite;}
.spl .ttl {margin: 0; color: #fff; font-size: 1.35rem; font-weight: 700; text-align: center; padding: 0 16px;}
.spl .trk {width: 200px; height: 4px; border-radius: 4px; background: rgba(255,255,255,.12); position: relative;
    overflow: hidden;}
.spl .trk span {position: absolute; top: 0; height: 100%; width: 40%; border-radius: 4px; background: #43A047;
    animation: spl-bar 1.2s linear infinite;}
.spl .sub {margin: 0; color: rgba(255,255,255,.55); font-size: .85rem;}
.spl .cr {position: absolute; bottom: 18px; margin: 0; color: rgba(255,255,255,.35); font-size: .75rem;
    letter-spacing: .3px;}
@media (prefers-reduced-motion: reduce) {.spl .pin, .spl .sh, .spl .trk span {animation: none;}}
</style>
<div class="spl">
  <div class="pin"><svg width="54" height="54" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a7 7 0 0 0-7 7c0
  5.2 7 13 7 13s7-7.8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z"/></svg></div>
  <div class="sh"></div>
  <p class="ttl">{judul}</p>
  <div class="trk"><span></span></div>
  <p class="sub">{teks}</p>
  <p class="cr">Develop Program By Nurman Catra</p>
</div>
"""


def splash_mulai(judul: str, teks: str):
    """Tampilkan layar loading sekali per sesi. Return placeholder (atau None kalau sudah pernah tampil)."""
    if st.session_state.get("splash_selesai"):
        return None
    ph = st.empty()
    ph.markdown(SPLASH.replace("{judul}", html.escape(judul)).replace("{teks}", html.escape(teks)),
                unsafe_allow_html=True)
    return ph


def splash_selesai(ph):
    if ph is not None:
        ph.empty()
    st.session_state["splash_selesai"] = True
