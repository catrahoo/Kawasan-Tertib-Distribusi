# Dashboard Kunjungan Outlet (Kawasan Tertib Distribusi)

Dashboard Streamlit yang membaca data AppSheet **FORM_OUTLET_APPSHEET** (sheet `DATA OUTLET`). Isinya: peta titik outlet bernomor sesuai urutan input, garis rute ikut jalan (OSRM), ringkasan per area, ketersediaan WKSK/ALVA, program kompetitor, galeri foto, dan download CSV. Aplikasi ini hanya membaca data, tidak menulis ke sheet.

## Struktur
Semua kode ada di `app.py`, berurutan dari atas ke bawah:
- login (`password_ok`)
- koneksi Google (`sa_info`, `get_creds`, `get_drive`)
- pengambilan data (`load_data`, `prepare`)
- foto dari Drive (`get_photo`)
- rute OSRM (`osrm_route`)
- peta (`build_map`)
- tampilan

## Aturan
- Ubah hanya bagian yang perlu. Jangan menulis ulang `app.py` dari nol.
- Lihat dulu bagian kode yang akan diubah. Setelah mengubah, jalankan `pytest`.
- Data bisa diambil lewat service account (`gcp_json` + `sheet_id`) atau link CSV publik (`sheet_csv_url`). Keduanya harus tetap berfungsi.
- Kunci dan password hanya lewat `st.secrets` (contoh di `.streamlit/secrets.toml.example`). Jangan menulis kunci di kode, dan jangan commit `.streamlit/secrets.toml`.
- Nama kolom mengikuti sheet AppSheet apa adanya. Jangan mengganti nama kolom di sheet.
- Teks di tampilan memakai Bahasa Indonesia.

## Test
```
pip install -r requirements.txt pytest
pytest
```
GitHub Actions menjalankan test yang sama setiap ada push.
