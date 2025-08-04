import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import io
from pandas.api.types import is_datetime64tz_dtype
import pytz
from PIL import Image
import base64

# === Konfigurasi ===
DATA_URL = "https://script.google.com/macros/s/AKfycbyJgS_nkBZ05_0dv4uMiS1W3SStmkJr8GhL5S3xUdI9EBOlPGyhkj5T1tJkwRhmKM74TQ/exec"

# Menambahkan Logo
logo_path = "media/Electric.png"
logo = Image.open(logo_path)

# Convert ke base64 untuk HTML
with open(logo_path, "rb") as f:
    logo_base64 = base64.b64encode(f.read()).decode()

# Set page config sekali saja di awal
st.set_page_config(
    page_title="Monitoring Daya Listrik Solar Cell",
    layout="wide",
    page_icon=logo
)

# CSS + header logo
st.markdown(
    """
    <style>
        .top-logo {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .top-logo img {
            height: 40px;
        }
        .top-logo h1 {
            margin: 0;
            font-size: 1.4rem;
        }
    </style>
    """,
    unsafe_allow_html=True
)
st.markdown(
    f"""
    <div class="top-logo">
        <img src="data:image/png;base64,{logo_base64}" alt="logo" />
        <h1> Monitoring Daya Listrik Solar Cell</h1>
    </div>
    """,
    unsafe_allow_html=True
)

# === Ambil data dengan caching (auto-refresh tiap 60 detik) ===
@st.cache_data(ttl=60)
def fetch_data():
    try:
        res = requests.get(DATA_URL, timeout=60)
        if res.status_code != 200:
            st.error(f"❌ Gagal ambil data. HTTP {res.status_code}")
            return pd.DataFrame()
        data = res.json()
        df = pd.DataFrame(data)

        if "Waktu" not in df.columns:
            st.error("Kolom 'Waktu' tidak ditemukan dalam data.")
            return pd.DataFrame()

        # Parse Waktu; anggap sudah UTC (jika naive)
        df["Waktu"] = pd.to_datetime(df["Waktu"], utc=True, errors="coerce")
        df["Timestamp"] = df["Waktu"]  # konsistensi internal

        # Local_Date_Jakarta sekarang hanya tanggal dari UTC (kalau masih dipakai)
        if "Local_Date_Jakarta" in df.columns:
            df["Local_Date_Jakarta"] = df["Local_Date_Jakarta"].astype(str)
        else:
            df["Local_Date_Jakarta"] = df["Timestamp"].dt.date.astype(str)

        df = df.sort_values("Timestamp").reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"❌ Error ambil data: {e}")
        return pd.DataFrame()

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

with st.spinner("Mengambil data terbaru..."):
    df = fetch_data()

if df.empty:
    st.warning("⚠️ Tidak ada data yang bisa ditampilkan.")
    st.stop()

# Validasi struktur minimal
required_columns = [
    "Waktu", "Jenis", "Tegangan (V)", "Arus (A)", "Daya Aktif (W)",
    "Energi (kWh)", "Frekuensi (Hz)", "Faktor Daya",
    "Daya Reaktif (VAR)", "Daya Semu (VA)", "Local_Date_Jakarta"
]
missing = [c for c in required_columns if c not in df.columns]
if missing:
    st.error("⚠️ Struktur data tidak sesuai. Kolom hilang: " + ", ".join(missing))
    st.write("Kolom yang ada:", df.columns.tolist())
    st.stop()

# Rename untuk konsistensi internal
df = df.rename(columns={
    "Jenis": "Device_Type",
    "Tegangan (V)": "Voltage",
    "Arus (A)": "Current",
    "Daya Aktif (W)": "Active_Power",
    "Energi (kWh)": "Energy",
    "Frekuensi (Hz)": "Frequency",
    "Faktor Daya": "Power_Factor",
    "Daya Reaktif (VAR)": "Reactive_Power",
    "Daya Semu (VA)": "Apparent_Power"
})
df["Local_Date_Jakarta"] = df["Local_Date_Jakarta"].astype(str)

# Header utama
st.title("⚡ Monitoring Daya Listrik Solar Cell AC dan DC")
latest_ts = pd.to_datetime(df["Timestamp"].max())
# pastikan naive UTC (sudah UTC karena parse dengan utc=True)
st.caption(f"Terakhir diperbarui : {latest_ts.strftime('%Y-%m-%d %H:%M:%S')}")


# Sidebar: filter
with st.sidebar:
    # Logo di atas
    st.image(logo, width=50)

    st.header("Filter")
    jenis_filter = st.selectbox("Jenis Daya", ["Gabungan", "AC", "DC"])
    tanggal_range = st.date_input(
        "Rentang Tanggal (Riwayat)",
        value=(datetime.now().date(), datetime.now().date()),
        help="Hanya dipakai di tab Riwayat"
    )
    periode = st.selectbox("Periode Grafik", ["1 Jam", "24 Jam", "7 Hari"])

# Terapkan filter jenis
df_filtered = df.copy()
if jenis_filter == "AC":
    df_filtered = df_filtered[df_filtered["Device_Type"].str.contains("AC", case=False, na=False)]
elif jenis_filter == "DC":
    df_filtered = df_filtered[df_filtered["Device_Type"].str.contains("DC", case=False, na=False)]
    if df_filtered.empty:
        st.warning("⚠️ Tidak ada data untuk Daya DC.")

# Tabs utama
tab_beranda, tab_terkini, tab_riwayat = st.tabs(["Beranda", "Data Terkini", "Riwayat"])

# === BERANDA ===
with tab_beranda:
    st.subheader("Ringkasan Terbaru")
    
    def fmt_number(val, decimals=2):
        try:
            num = float(val)
            return f"{num:.{decimals}f}"
        except (ValueError, TypeError):
            return "-"
        
    if df_filtered.empty:
        st.warning("Tidak ada data setelah filter jenis.")
    else:
        latest = df_filtered.iloc[-1]
        prev = df_filtered.iloc[-2] if len(df_filtered) > 1 else latest

        cols = st.columns([1, 1, 1, 1, 1], gap="medium")
        cols[0].metric("Tegangan (V)", fmt_number(latest['Voltage'], 1), delta=fmt_number(latest['Voltage'] - prev['Voltage'], 1))
        cols[1].metric("Arus (A)", fmt_number(latest['Current'], 2), delta=fmt_number(latest['Current'] - prev['Current'], 2))
        cols[2].metric("Daya Aktif (W)", fmt_number(latest['Active_Power'], 1), delta=fmt_number(latest['Active_Power'] - prev['Active_Power'], 1))
        cols[3].metric("Energi (kWh)", fmt_number(latest['Energy'], 3), delta=fmt_number(latest['Energy'] - prev['Energy'], 3))
        cols[4].metric("Faktor Daya", fmt_number(latest['Power_Factor'], 2))

        st.divider()
        # === 5 Daya Tertinggi Harian ===
        st.subheader("🔝 5 Daya Aktif Tertinggi")

        # Pastikan Timestamp dalam timezone Jakarta
        df_daily_max = df_filtered.copy()
        df_daily_max["Timestamp"] = pd.to_datetime(df_daily_max["Timestamp"], utc=True)
        df_daily_max["Timestamp"] = df_daily_max["Timestamp"].dt.tz_convert(JAKARTA_TZ)

        # Ambil tanggal (Jakarta) dan max per hari
        df_daily_max["Tanggal"] = df_daily_max["Timestamp"].dt.date
        df_daily_max = (
            df_daily_max.groupby("Tanggal", as_index=False)["Active_Power"]
            .max()
            .sort_values("Active_Power", ascending=False)
            .head(5)
        )

        # Format tanggal untuk tampilan
        df_daily_max["Tanggal"] = df_daily_max["Tanggal"].astype(str)

        # Tampilkan tabel
        st.table(df_daily_max.rename(columns={"Active_Power": "Daya Aktif Maks (W)"}))

        # Bagian Detail Tambahan
        st.subheader("Detail Tambahan")
        c6, c7, c8 = st.columns(3)
        c6.metric("Frekuensi (Hz)", fmt_number(latest['Frequency'], 2))
        c7.metric("Daya Reaktif (VAR)", fmt_number(latest['Reactive_Power'], 1))
        c8.metric("Daya Semu (VA)", fmt_number(latest['Apparent_Power'], 1))

        st.markdown(f"**Jenis Perangkat:** {latest['Device_Type']}")
        st.markdown(f"**Waktu Data Terakhir:** {latest['Timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")

# === DATA TERKINI ===
with tab_terkini:
    st.subheader("Data Terkini & Grafik")
    st.markdown(f"**Filter Jenis:** {jenis_filter}")
    if df_filtered.empty:
        st.warning("Tidak ada data setelah filter jenis.")
    else:
        latest = df_filtered.iloc[-1]
        st.markdown(f"**Tanggal (UTC):** {latest['Timestamp'].strftime('%Y-%m-%d')}")

        metric_cols = st.columns(4)
        metric_cols[0].metric("Tegangan (V)", f"{latest['Voltage']:.1f}")
        metric_cols[1].metric("Arus (A)", f"{latest['Current']:.2f}")
        metric_cols[2].metric("Daya Aktif (W)", f"{latest['Active_Power']:.1f}")
        metric_cols[3].metric("Energi (kWh)", f"{latest['Energy']:.3f}")

        # Tentukan periode untuk grafik
        now = pd.to_datetime(df_filtered["Timestamp"].max())
        if periode == "1 Jam":
            since = now - pd.Timedelta(hours=1)
        elif periode == "24 Jam":
            since = now - pd.Timedelta(hours=24)
        else:
            since = now - pd.Timedelta(days=7)
        df_period = df_filtered[df_filtered["Timestamp"] >= since]

        st.markdown(f"### Periode: {periode}")
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=["Tegangan (V)", "Arus (A)", "Daya Aktif (W)", "Energi (kWh)"],
            vertical_spacing=0.1,
            horizontal_spacing=0.1
        )
        fig.add_trace(go.Scatter(
            x=df_period["Timestamp"], y=df_period["Voltage"], name="Tegangan", mode="lines+markers",
            hovertemplate="Tegangan: %{y:.2f} V<br>%{x}<extra></extra>"
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df_period["Timestamp"], y=df_period["Current"], name="Arus", mode="lines+markers",
            hovertemplate="Arus: %{y:.2f} A<br>%{x}<extra></extra>"
        ), row=1, col=2)
        fig.add_trace(go.Scatter(
            x=df_period["Timestamp"], y=df_period["Active_Power"], name="Daya Aktif", mode="lines+markers",
            hovertemplate="Daya Aktif: %{y:.2f} W<br>%{x}<extra></extra>"
        ), row=2, col=1)
        fig.add_trace(go.Scatter(
            x=df_period["Timestamp"], y=df_period["Energy"], name="Energi", mode="lines+markers",
            hovertemplate="Energi: %{y:.3f} kWh<br>%{x}<extra></extra>"
        ), row=2, col=2)

        fig.update_layout(height=600, showlegend=False, margin=dict(t=40))
        st.plotly_chart(fig, use_container_width=True)

# === RIWAYAT ===
with tab_riwayat:
    st.subheader("Riwayat & Statistik Harian")
    st.markdown(f"**Filter Jenis:** {jenis_filter}")

    # proses tanggal range
    if isinstance(tanggal_range, (list, tuple)):
        start_date, end_date = tanggal_range
    else:
        start_date = end_date = tanggal_range
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    mask = (pd.to_datetime(df_filtered["Local_Date_Jakarta"]) >= pd.to_datetime(start_str)) & \
           (pd.to_datetime(df_filtered["Local_Date_Jakarta"]) <= pd.to_datetime(end_str))
    filtered = df_filtered[mask].copy()

    if filtered.empty:
        st.warning("⚠️ Tidak ada data untuk rentang tanggal tersebut.")
    else:
        st.markdown("### Tabel Data")
        st.dataframe(filtered.reset_index(drop=True), use_container_width=True)

        st.markdown("### Statistik Harian (Rata-rata)")
        filtered["Timestamp"] = pd.to_datetime(filtered["Timestamp"], errors="coerce")
        numeric_cols = ["Voltage", "Current", "Active_Power", "Energy"]
        for col in numeric_cols:
            filtered[col] = pd.to_numeric(filtered[col], errors="coerce")

        daily_stats = None
        if not filtered[numeric_cols].dropna(how="all").empty:
            daily_stats = (
                filtered.set_index("Timestamp")
                .resample("D")[numeric_cols]
                .mean()
                .reset_index()
            )
            display = daily_stats.rename(columns={
                "Timestamp": "Tanggal",
                "Voltage": "Rata-rata Tegangan (V)",
                "Current": "Rata-rata Arus (A)",
                "Active_Power": "Rata-rata Daya Aktif (W)",
                "Energy": "Rata-rata Energi (kWh)"
            })
            st.dataframe(display, use_container_width=True)

        st.markdown("### Ekspor Data")
        csv_bytes = filtered.to_csv(index=False).encode("utf-8")

        # === Fungsi untuk hilangkan timezone, ubah ke waktu Jakarta ===
        def make_naive_jakarta(df_in, time_col="Timestamp"):
            df_copy = df_in.copy()
            if time_col in df_copy.columns:
                df_copy[time_col] = pd.to_datetime(df_copy[time_col], errors="coerce")
                if pd.api.types.is_datetime64tz_dtype(df_copy[time_col]):
                    df_copy[time_col] = df_copy[time_col].dt.tz_convert(JAKARTA_TZ).dt.tz_localize(None)
                else:
                    df_copy[time_col] = df_copy[time_col].dt.tz_localize("UTC").dt.tz_convert(JAKARTA_TZ).dt.tz_localize(None)
            return df_copy

        # === Ekspor Excel di menu Riwayat ===
        st.markdown("### 📤 Ekspor Data")
        # Download CSV
        csv_bytes = filtered.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Unduh CSV",
            data=csv_bytes,
            file_name="riwayat_ac_power.csv",
            mime="text/csv"
        )
