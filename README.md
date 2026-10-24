# Dashboard Kunjungan Outlet

Dashboard Streamlit untuk data AppSheet **FORM_OUTLET_APPSHEET** (sheet `DATA OUTLET`):
peta titik outlet bernomor sesuai urutan input + garis rute ikut jalan, ringkasan per area,
ketersediaan WKSK/ALVA, program kompetitor, galeri foto display & sunblind, dan download CSV.

## 1. Bikin service account (sekali saja)
1. Buka https://console.cloud.google.com → buat project baru (mis. `dashboard-outlet`).
2. Menu **APIs & Services → Library** → aktifkan **Google Sheets API** dan **Google Drive API**.
3. Menu **IAM & Admin → Service Accounts → Create service account** → beri nama → Done.
4. Klik service account-nya → tab **Keys → Add key → Create new key → JSON** → file .json terunduh.
5. Catat email service account (`...@....iam.gserviceaccount.com`).

## 2. Kasih akses ke data
- Google Sheet **FORM_OUTLET_APPSHEET** → Bagikan → tempel email service account → **Viewer**.
- Google Drive → folder **appsheet → data → (folder app kamu)** → klik kanan → Bagikan →
  email service account → **Viewer**. (Biar foto bisa tampil.)

## 3. Upload ke GitHub
Repo baru (boleh Private) → upload semua file ini: `app.py`, `requirements.txt`,
`README.md`, `.gitignore`, folder `.streamlit` (isi `config.toml` & `secrets.toml.example`).

## 4. Deploy di Streamlit
1. https://share.streamlit.io → **Create app** → pilih repo, branch `main`, file `app.py`.
2. **Advanced settings → Secrets** → isi sesuai `.streamlit/secrets.toml.example`:
   - `sheet_id` = ID dari link sheet (`https://docs.google.com/spreadsheets/d/`**ID_INI**`/edit`)
   - `[gcp_service_account]` = isi dari file .json (tiap baris `kunci = "nilai"`)
   - `app_password` = password untuk buka dashboard (opsional)
3. Deploy.

## Catatan
- Data refresh otomatis tiap 5 menit, atau klik **Refresh data** di sidebar.
- Nomor di peta = urutan input di sheet, dimulai dari 1 tiap tanggal. Beberapa tanggal = beda warna rute.
- Garis rute pakai server OSRM publik (mode mobil). Kalau lambat, matikan "Garis ikut jalan".
  Bisa diganti server sendiri lewat secret `osrm_url`.
