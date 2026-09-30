"""Streamlit entry point for the final RuteSiaga routing package."""
import json
import math
import sys
import unicodedata
from pathlib import Path

import folium
import streamlit as st
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "web"))
import server as routing

st.set_page_config(page_title="RuteSiaga DIY", page_icon="🚑", layout="wide")

st.markdown(
    """
<style>
.block-container { padding-top: 1.2rem; max-width: 1500px; }
header[data-testid="stHeader"] { background: transparent; }
.rs-hero { display: flex; align-items: center; gap: 14px; padding: 16px 22px; margin-bottom: 18px; color: #fff;
  background: linear-gradient(100deg, #0a1c2b, #0d2233 55%, #113a44); border-radius: 14px; box-shadow: 0 6px 20px rgba(13,34,51,.2); }
.rs-hero .logo { width: 44px; height: 44px; display: grid; place-items: center; border-radius: 11px; font-size: 24px;
  background: linear-gradient(145deg, #14a89c, #0f766e); }
.rs-hero h1 { margin: 0; padding: 0; font-size: 1.55rem; line-height: 1.1; color: #fff; }
.rs-hero h1 span { font-weight: 300; color: #9fe6dc; }
.rs-hero p { margin: 3px 0 0; color: #a9bfcc; font-size: .85rem; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; }
div[data-testid="stMetric"] { background: linear-gradient(135deg, #e6f4f1, #f1faf8); border: 1px solid #bfe0da; border-radius: 10px; padding: 12px 16px; }
div[data-testid="stMetricValue"] { color: #0b5a54; }
.stButton > button[kind="primary"], .stFormSubmitButton > button { border-radius: 10px; font-weight: 700; }
</style>
<div class="rs-hero"><div class="logo">✚</div>
<div><h1>Rute<span>Siaga</span> DIY</h1>
<p>Estimasi rute ambulans ke titik jalan rumah sakit tercepat · graf jalan OSM/Geofabrik 20 September 2026</p></div></div>
""",
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Memuat graf jalan (pertama kali sekitar 10–30 detik)...")
def warm_up():
    routing.base_graph()
    return True


warm_up()


def normalize(value):
    value = unicodedata.normalize("NFKD", str(value)).casefold()
    return " ".join("".join(c if c.isalnum() else " " for c in value).split())


@st.cache_data(show_spinner=False)
def places():
    rows = []
    for filename in ("locations_index.json", "places_osm.json"):
        payload = json.loads((ROOT / "web" / filename).read_text(encoding="utf-8"))
        rows.extend(payload["items"])
    seen = set()
    output = []
    for item in rows:
        try:
            lat, lon = float(item["lat"]), float(item["lon"])
            name = str(item["name"]).strip()
        except (KeyError, ValueError, TypeError):
            continue
        if not name or not (-8.5 < lat < -7.0 and 109.5 < lon < 111.0):
            continue
        key = (normalize(name), round(lat, 5), round(lon, 5))
        if key in seen:
            continue
        seen.add(key)
        item = dict(item)
        item["search_key"] = normalize(" ".join(str(item.get(k, "")) for k in ("name", "aliases", "address")))
        output.append(item)
    return output


def find_places(query):
    key = normalize(query)
    if len(key) < 2:
        return []
    words = key.split()
    found = [p for p in places() if all(word in p["search_key"] for word in words)]
    found.sort(key=lambda p: (not p["search_key"].startswith(key), len(p["name"]), p["name"]))
    return found[:15]


def base_map(lat, lon, result=None):
    center = [lat, lon]
    if result:
        center = list(reversed(routing.inverse(*result["snap_xy"])))
    m = folium.Map(location=center, zoom_start=14 if result else 13, tiles="OpenStreetMap", control_scale=True)
    if result:
        path = [list(reversed(routing.inverse(*xy))) for xy in result["path"]]
        folium.PolyLine(path, color="#2456b8", weight=6, opacity=0.9, tooltip="Rute tercepat menurut model").add_to(m)
        goal = list(reversed(routing.inverse(*result["goal_xy"])))
        folium.Marker(goal, tooltip=result["hospital"], icon=folium.Icon(color="green", icon="plus-sign")).add_to(m)
        if result["gap_m"] > 1:
            folium.PolyLine([[lat, lon], path[0]], color="#ef8732", weight=3, dash_array="6,6", tooltip="Penghubung titik awal; tidak masuk estimasi waktu").add_to(m)
        bounds = path + [[lat, lon], goal]
        m.fit_bounds(bounds, padding=(25, 25))
    folium.Marker([lat, lon], tooltip="Titik awal", icon=folium.Icon(color="orange", icon="flag")).add_to(m)
    return m


if "origin" not in st.session_state:
    st.session_state.origin = (-7.79334345, 110.3666525377634)
if "origin_name" not in st.session_state:
    st.session_state.origin_name = ""

left, right = st.columns([1, 1.6], gap="large")
with left:
    with st.container(border=True):
        st.subheader("1 · Titik keberangkatan")
        query = st.text_input("Cari nama tempat atau jalan", placeholder="Contoh: Malioboro, UGM, Jalan Grafika")
        matches = find_places(query)
        if matches:
            labels = [f"{p['name']} · {p.get('kind', 'Tempat')} · {p['lat']:.5f}, {p['lon']:.5f}" for p in matches]
            selected = st.selectbox("Hasil pencarian", range(len(matches)), format_func=lambda i: labels[i])
            if st.button("Pakai lokasi ini", width="stretch"):
                p = matches[selected]
                st.session_state.origin = (float(p["lat"]), float(p["lon"]))
                st.session_state.origin_name = p["name"]
                st.session_state.pop("result", None)
                st.rerun()
        elif query.strip():
            st.info("Nama belum ada di indeks OSM lokal. Masukkan koordinat atau klik titik di peta.")

        with st.expander("Masukkan koordinat manual"):
            with st.form("manual_origin", border=False):
                lat = st.number_input("Lintang", value=float(st.session_state.origin[0]), format="%.9f")
                lon = st.number_input("Bujur", value=float(st.session_state.origin[1]), format="%.9f")
                set_manual = st.form_submit_button("Pakai koordinat", width="stretch")
            if set_manual:
                st.session_state.origin = (lat, lon)
                st.session_state.origin_name = ""
                st.session_state.pop("result", None)
                st.rerun()
        origin = st.session_state.origin
        st.success(f"**Lokasi awal:** {st.session_state.origin_name or 'titik pilihan'}\n\n{origin[0]:.6f}, {origin[1]:.6f}", icon="📍")

    with st.container(border=True):
        st.subheader("2 · Skenario & hitung")
        scenario = st.selectbox("Skenario waktu", ("pagi", "siang", "sore", "malam"), help="Memengaruhi asumsi kemacetan dan waktu tunggu.")
        if st.session_state.get("result") and st.session_state.result["scenario"] != scenario:
            st.session_state.pop("result", None)
        if st.button("Cari RS terdekat", type="primary", width="stretch"):
            try:
                with st.spinner("Menghitung UCS dan A* pada jaringan jalan..."):
                    st.session_state.result = routing.calculate(
                        {"lat": st.session_state.origin[0], "lon": st.session_state.origin[1], "scenario": scenario},
                        include_trace=False, include_map=False,
                    )
            except Exception as exc:
                st.session_state.pop("result", None)
                st.error(f"Rute belum dapat dihitung: {exc}")
    st.caption("Estimasi skenario, bukan lalu lintas langsung. Tujuan berada di titik jalan dekat RS; jarak titik awal ke jalan tidak dihitung dalam waktu.")

with right:
    result = st.session_state.get("result")
    if result:
        with st.container(border=True):
            st.caption("TUJUAN TERCEPAT DALAM MODEL")
            st.markdown(f"### {result['hospital']}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Estimasi perjalanan", f"{result['cost_s'] / 60:.1f} menit")
            c2.metric("Jarak rute", f"{result['distance_m'] / 1000:.2f} km")
            c3.metric("Selisih titik ke jalan", f"{result['gap_m']:.1f} m")
            if result["gap_m"] > 50:
                st.warning("Titik awal jauh dari jalan terpilih. Periksa apakah penghubung oranye dapat dilalui kendaraan. Jarak penghubung belum dihitung dalam waktu.")
            with st.expander("Perbandingan algoritma & rincian"):
                st.dataframe([{"Algoritma": x["algorithm"].upper().replace("ASTAR", "A*"), "Biaya (detik)": round(x["cost_s"], 2), "Komputasi (ms)": round(x["runtime_ms"], 2), "State diperiksa": x["expanded_states"]} for x in result["algorithms"]], hide_index=True, width="stretch")
                if not result["same_path"]:
                    st.info("UCS dan A* memperoleh biaya minimum yang sama, meskipun pilihan jalurnya berbeda.")
                st.caption(result["scope"])
            st.download_button("Unduh hasil JSON", json.dumps(result, ensure_ascii=False, indent=2), file_name=f"rute-{result['scenario']}.json", mime="application/json")
    else:
        st.info("Klik peta atau cari tempat untuk menentukan titik awal, lalu tekan **Cari RS terdekat**.", icon="🚑")
    st.caption("Peta dasar memerlukan internet; data rute berasal dari paket lokal. Klik peta untuk memindahkan titik awal.")
    current = st.session_state.origin
    map_state = st_folium(base_map(*current, result=result), height=560, use_container_width=True, returned_objects=["last_clicked"], key="route_map")
    clicked = map_state.get("last_clicked") if map_state else None
    if clicked:
        point = (float(clicked["lat"]), float(clicked["lng"]))
        if all(math.isfinite(x) for x in point) and point != st.session_state.get("last_map_click"):
            st.session_state.last_map_click = point
            st.session_state.origin = point
            st.session_state.origin_name = ""
            st.session_state.pop("result", None)
            st.rerun()

st.caption("Prototipe penelitian. Waktu merupakan estimasi skenario, bukan informasi lalu lintas langsung atau panduan operasional ambulans.")
