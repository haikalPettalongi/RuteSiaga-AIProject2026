"""Reproducible batch of the web routing core for the 20-location test sheet."""
import copy
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEB = HERE.parent / "web"
CONFIG = json.loads((WEB / "config.json").read_text(encoding="utf-8"))
ENGINE = (WEB / CONFIG["engine_dir"]).resolve()
sys.path.insert(0, str(ENGINE))

from origin_access import OriginError, catalog_segments, prepare_origin, project_segment  # noqa: E402
from projection_diy import forward, inverse  # noqa: E402
from route_network import search_network, setup  # noqa: E402

SPECS = [
    ("Jalan Grafika", -7.766067024356544, 110.37390636072011),
    ("UGM — Jalan Pancasila", -7.773595801763427, 110.376947373952),
    ("Jalan Tentara Pelajar", -7.783391923119533, 110.36085404109025),
    ("Stasiun Tugu Yogyakarta", None, None),
    ("Malioboro Mall", None, None),
    ("Kantor Pos Kotagede", None, None),
    ("Terminal Giwangan", None, None),
    ("Terminal Jombor", None, None),
    ("Anggrek 212 Perumnas Condongcatur", None, None),
    ("Pasar Godean", None, None),
    ("Pasar Pakem", None, None),
    ("Pasar Bantul", None, None),
    ("Pasar Imogiri", None, None),
    ("Stasiun Wates", None, None),
    ("Sentolo", None, None),
    ("Pasar Argosari", None, None),
    ("Polsek Playen", None, None),
    ("Pasar Prambanan", None, None),
    ("SMP Negeri 2 Kalasan", None, None),
    ("Jalan Universitas Muhammadiyah Yogyakarta", None, None),
]
SCENARIOS = ("pagi", "siang", "sore", "malam")
PLACE_INDEX = json.loads((WEB / "places_osm.json").read_text(encoding="utf-8"))["items"]
GRAPH = json.loads((ENGINE / "network_diy" / "graph_diy_poi.json").read_text(encoding="utf-8"))
OUT = HERE.parent / "hasil/json_otomatis/hasil_batch_ulang.json"


def find_reference(name, lat, lon):
    if lat is not None:
        return lat, lon, "koordinat pengguna"
    matches = [p for p in PLACE_INDEX if p["name"] == name]
    if not matches:
        raise ValueError(f"Penanda OSM tidak ditemukan: {name}")
    if name == "Sentolo":
        matches.sort(key=lambda p: abs(p["lat"] + 7.834))
    p = matches[0]
    return p["lat"], p["lon"], f"OSM {p['osm_type']}/{p['osm_id']}"


def choose_origin(lat, lon, source):
    if source == "koordinat pengguna":
        return lat, lon, "koordinat pengguna; akses fisik belum diverifikasi", None
    xy = forward(lon, lat)
    candidates = []
    for seg in catalog_segments(xy, 350):
        gap, fraction, snap = project_segment(xy, seg["a"], seg["b"])
        if any(not e.get("blocked", False) for e in seg["edges"]):
            candidates.append((gap, fraction, snap, seg))
    if not candidates:
        return lat, lon, "penanda OSM; tidak ditemukan ruas dalam 350 m", None
    gap, fraction, snap, seg = min(candidates, key=lambda item: item[0])
    # Move slightly off junctions to avoid an ambiguous snap to crossing roads.
    if fraction < 0.01 or fraction > 0.99:
        fraction = 0.02 if fraction < 0.5 else 0.98
        a, b = seg["a"], seg["b"]
        snap = (a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction)
    use_lon, use_lat = inverse(*snap)
    road = seg["tags"].get("name", "jalan tanpa nama OSM")
    return use_lat, use_lon, f"titik jalan OSM otomatis dekat penanda; {road}; jarak penanda {gap:.1f} m; akses fisik belum diverifikasi", gap


def prepare_point(lat, lon):
    xy = forward(lon, lat)
    g = {
        **GRAPH,
        "nodes": dict(GRAPH["nodes"]),
        "edges": list(GRAPH["edges"]),
        "goals": list(GRAPH["goals"]),
        "goal_hospitals": copy.deepcopy(GRAPH["goal_hospitals"]),
        "turn_restrictions": list(GRAPH["turn_restrictions"]),
    }
    return prepare_origin(g, xy)


def run_one(prepared_origin, scenario):
    g, start, audit = prepared_origin
    prepared = setup(g, scenario)
    ucs = search_network(prepared, start, g["goals"], "ucs")
    astar = search_network(prepared, start, g["goals"], "astar")
    if (ucs["cost_s"] is None) != (astar["cost_s"] is None):
        raise RuntimeError("UCS/A* berbeda dalam keterjangkauan")
    if ucs["cost_s"] is None:
        return {"status": "Tidak ada rute", "message": "Tidak ditemukan rute sesuai aturan graf; belum membuktikan jalan fisik tidak dapat dilewati.", "road_name": audit["road_name"], "gap_m": audit["gap_m"], "ucs": ucs, "astar": astar}
    if not math.isclose(ucs["cost_s"], astar["cost_s"], abs_tol=1e-6):
        raise RuntimeError("Biaya UCS/A* tidak cocok")
    edges = prepared[2]
    return {
        "status": "Berhasil",
        "hospital": ", ".join(g["goal_hospitals"][ucs["goal"]]),
        "distance_m": sum(edges[e]["length_m"] for e in ucs["edges"]),
        "road_name": audit["road_name"],
        "gap_m": audit["gap_m"],
        "same_path": ucs["edges"] == astar["edges"],
        "ucs": {k: ucs[k] for k in ("algorithm", "goal", "cost_s", "expanded_states", "runtime_ms")},
        "astar": {k: astar[k] for k in ("algorithm", "goal", "cost_s", "expanded_states", "runtime_ms")},
    }


def main():
    results = []
    for i, (name, ref_lat, ref_lon) in enumerate(SPECS, 1):
        ref_lat, ref_lon, source = find_reference(name, ref_lat, ref_lon)
        use_lat, use_lon, selection, ref_gap = choose_origin(ref_lat, ref_lon, source)
        try:
            prepared_origin = prepare_point(use_lat, use_lon)
            origin_error = None
        except OriginError as exc:
            prepared_origin = None
            origin_error = str(exc)
        for scenario in SCENARIOS:
            started = time.perf_counter()
            row = {
                "id": f"U{len(results)+1:02d}", "location_id": f"L{i:02d}",
                "location": name, "scenario": scenario,
                "reference_lat": ref_lat, "reference_lon": ref_lon,
                "lat": use_lat, "lon": use_lon, "reference_source": source,
                "selection": selection, "reference_to_road_m": ref_gap,
                "tested_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            try:
                if origin_error:
                    row.update(status="Gagal memilih titik", message=origin_error)
                else:
                    row.update(run_one(prepared_origin, scenario))
            except OriginError as exc:
                row.update(status="Gagal memilih titik", message=str(exc))
            except Exception as exc:
                row.update(status="Galat aplikasi", message=f"{type(exc).__name__}: {exc}")
            row["elapsed_s"] = time.perf_counter() - started
            results.append(row)
            OUT.write_text(json.dumps({"source": "OSM 20 Sep 2026; core engine RuteSiaga", "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{row['id']} {name} {scenario}: {row['status']} ({row['elapsed_s']:.1f}s)", flush=True)
    print(f"Saved {len(results)} cases to {OUT}", flush=True)


if __name__ == "__main__":
    main()
