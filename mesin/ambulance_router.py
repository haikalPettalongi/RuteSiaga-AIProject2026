"""Pencarian multitujuan; Python standard library, semua biaya dalam detik."""
import argparse
import heapq
import itertools
import json
import math
import time

SPEED_KMH = {
    "motorway": 60, "trunk": 50, "primary": 40, "secondary": 35,
    "tertiary": 30, "unclassified": 25, "residential": 20,
    "motorway_link": 30, "trunk_link": 30, "primary_link": 25,
    "secondary_link": 25, "tertiary_link": 20, "service": 10,
}
SCENARIOS = ("pagi", "siang", "sore", "malam")
# Detik per 100 meter jalan di dalam gabungan zona jenis POI tersebut.
POI_SECONDS = {"school": (20, 15, 5, 0), "market": (30, 20, 15, 5),
               "mall": (5, 15, 25, 10)}
SIGNAL_SECONDS = (35, 25, 40, 15)
RAIL_SECONDS = (45, 30, 45, 20)
VMAX = 60 / 3.6


def edge_cost(edge, scenario):
    i = SCENARIOS.index(scenario)
    speed = edge.get("speed_kmh", SPEED_KMH[edge["highway"]])
    if not math.isfinite(speed) or not 0 < speed <= 60:
        raise ValueError("Kecepatan harus >0 dan <=60 km/jam")
    length = float(edge["length_m"])
    if not math.isfinite(length) or length < 0:
        raise ValueError("Panjang tidak valid")
    base = length / (speed / 3.6)
    poi = 0.0
    for kind, values in POI_SECONDS.items():
        exposure = float(edge.get("exposure_m", {}).get(kind, 0))
        if not math.isfinite(exposure) or not 0 <= exposure <= length + 1e-6:
            raise ValueError("Panjang paparan harus berada dalam panjang ruas")
        poi += exposure / 100 * values[i]
    signal = SIGNAL_SECONDS[i] if edge.get("signal_at_end", False) else 0
    rail = RAIL_SECONDS[i] if edge.get("rail_at_end", False) else 0
    result={"base_s": base, "poi_s": poi, "signal_s": signal, "rail_s": rail}
    gate=float(edge.get("gate_wait_s",0))
    if not math.isfinite(gate) or gate<0:raise ValueError("Penalti gerbang harus finite dan tidak negatif")
    if gate:result["gate_s"]=gate
    return result


def prepare(data, scenario):
    if data.get("turn_restrictions"):
        raise ValueError("Gunakan route_network.py untuk graf dengan larangan belok")
    nodes = data["nodes"]
    adjacency = {n: [] for n in nodes}
    for xy in nodes.values():
        if len(xy) != 2 or not all(math.isfinite(c) for c in xy):
            raise ValueError("Koordinat harus pasangan x,y meter yang terbatas")
    ids = set()
    for edge in data["edges"]:
        u, v = edge["u"], edge["v"]
        if edge["id"] in ids:
            raise ValueError("ID ruas harus unik, termasuk parallel edges")
        ids.add(edge["id"])
        chord = math.dist(nodes[u], nodes[v])
        if edge["length_m"] + 1e-8 < chord:
            raise ValueError("Panjang ruas lebih kecil daripada jarak lurus; heuristik tidak sah")
        if edge.get("closed", False):
            continue
        components = edge_cost(edge, scenario)
        adjacency[u].append((edge, sum(components.values()), components))
    return nodes, adjacency


def search(prepared, start, goals, algorithm="astar"):
    """Berhenti saat goal dikeluarkan dari heap, bukan saat ditemukan."""
    if algorithm not in ("astar", "ucs"):
        raise ValueError("Algoritma harus astar atau ucs")
    nodes, adjacency = prepared
    goals = set(goals)
    if not goals or start not in nodes or not goals <= nodes.keys():
        raise ValueError("Start/goal kosong atau tidak ada pada graf")
    begin = time.perf_counter()
    cache = {}

    def h(n):
        if algorithm == "ucs":
            return 0.0
        if n not in cache:
            cache[n] = min(math.dist(nodes[n], nodes[t]) for t in goals) / VMAX
        return cache[n]

    serial = itertools.count()
    heap = [(h(start), next(serial), 0.0, start)]
    dist, parent = {start: 0.0}, {}
    expanded = 0
    peak = 1
    while heap:
        _, _, g, u = heapq.heappop(heap)
        if g != dist[u]:
            continue
        expanded += 1  # Termasuk goal yang di-pop secara valid.
        if u in goals:
            path, edge_ids = [u], []
            components = dict.fromkeys(("base_s", "poi_s", "signal_s", "rail_s"), 0.0)
            while path[-1] != start:
                p, edge_id, parts = parent[path[-1]]
                path.append(p)
                edge_ids.append(edge_id)
                for k, val in parts.items():
                    components[k] = components.get(k,0) + val
            return {"algorithm": algorithm, "goal": u, "cost_s": g,
                    "nodes": path[::-1], "edges": edge_ids[::-1], **components,
                    "expanded": expanded, "peak_heap_entries": peak,
                    "runtime_ms": (time.perf_counter() - begin) * 1000}
        for edge, weight, parts in adjacency[u]:
            v, trial = edge["v"], g + weight
            if trial < dist.get(v, math.inf):
                dist[v] = trial
                parent[v] = (u, edge["id"], parts)
                heapq.heappush(heap, (trial + h(v), next(serial), trial, v))
        peak = max(peak, len(heap))
    return {"algorithm": algorithm, "goal": None, "cost_s": None,
            "status": "unreachable", "expanded": expanded,
            "peak_heap_entries": peak,
            "runtime_ms": (time.perf_counter() - begin) * 1000}


def demo():
    # RS A lebih dekat, tetapi lampu dan perlintasan membuat RS B lebih cepat.
    return {"nodes": {"S": [0, 0], "A": [100, 0], "B": [0, 300]},
            "edges": [
                {"id": "SA", "u": "S", "v": "A", "length_m": 100,
                 "highway": "primary", "signal_at_end": True, "rail_at_end": True},
                {"id": "SB", "u": "S", "v": "B", "length_m": 300,
                 "highway": "primary"}], "start": "S", "goals": ["A", "B"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", help="JSON hasil build_osm.py atau graf terverifikasi")
    parser.add_argument("--start", help="ID node titik keberangkatan di jalan")
    parser.add_argument("--goals", nargs="+", help="ID node pintu IGD yang telah diverifikasi")
    parser.add_argument("--scenario", choices=SCENARIOS, default="pagi")
    args = parser.parse_args()
    if args.graph:
        with open(args.graph, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = demo()
    start = args.start or data.get("start")
    goals = args.goals or data.get("goals", [])
    graph = prepare(data, args.scenario)
    results = [search(graph, start, goals, algo) for algo in ("ucs", "astar")]
    print(json.dumps({"data_kind": "OSM/input" if args.graph else "SYNTHETIC DEMO",
                      "scenario": args.scenario, "results": results}, indent=2))
