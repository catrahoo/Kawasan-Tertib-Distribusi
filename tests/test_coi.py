"""COI TANAH AIR: KMZ Map Marker terbaca, pin duplikat digabung, warna pin jadi kode jenis."""
import pathlib

import pytest

pytest.importorskip("streamlit")
import coi  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_warna_pin_jadi_kode_jenis():
    assert coi.jenis_dari_warna("ff00b371") == "SNT"     # hijau
    assert coi.jenis_dari_warna("ff4ac38b") == "SNT"     # hijau muda
    assert coi.jenis_dari_warna("ff3643f4") == "PNT"     # merah
    assert coi.jenis_dari_warna("ff631ee9") == "PNT"     # pink
    assert coi.jenis_dari_warna("fff39621") == "SWK"     # biru
    assert coi.jenis_dari_warna("ff3bebff") == "OCS"     # kuning
    assert coi.jenis_dari_warna("ff9e9e9e") == "WARKOP"  # abu-abu


def test_nama_area():
    assert coi.area_dari_folder("Cluster uinsa") == "UINSA"
    assert coi.area_dari_folder("Sawahan girilaya") == "Girilaya"
    assert coi.area_dari_folder("Lontar ") == "Lontar"


def test_kmz_di_repo_terbaca_tanpa_duplikat():
    df, foto = coi.parse_kmz((ROOT / "data" / "coi_tanah_air.kmz").read_bytes())
    assert set(df["AREA"]) == {"Girilaya", "Lontar", "UINSA"}
    assert not df.duplicated(["AREA", "NAMA OUTLET", "LAT", "LON"]).any()
    assert df["JENIS OUTLET"].isin(["SNT", "PNT", "SWK"]).all()
    assert all(fn in foto for fns in df["FOTO"] for fn in fns)


def test_menu_coi_bisa_dibuka_tanpa_secrets():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.secrets["_CI"] = "1"
    at.session_state["menu"] = "🇮🇩 COI TANAH AIR"
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert any("COI TANAH AIR" in m.value for m in at.markdown)
    assert not any('class="spl"' in m.value for m in at.markdown), "layar loading harus hilang setelah data siap"
    assert any("kpi-card" in m.value for m in at.markdown)


def test_hapus_foto():
    raw = (ROOT / "data" / "coi_tanah_air.kmz").read_bytes()
    df, foto = coi.parse_kmz(raw)
    baris = df[df["JML FOTO"] > 0].iloc[0]
    fn = baris["FOTO"][0]
    df2, foto2 = coi.parse_kmz(coi.hapus_foto_kmz(raw, fn))
    assert len(df2) == len(df)
    assert len(foto2) == len(foto) - 1
    b2 = df2[(df2["NAMA OUTLET"] == baris["NAMA OUTLET"]) & (df2["AREA"] == baris["AREA"])].iloc[0]
    assert b2["JML FOTO"] == baris["JML FOTO"] - 1
