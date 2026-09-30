import math
import random
import unittest

from ambulance_router import demo, edge_cost, prepare, search


class RouterTests(unittest.TestCase):
    def test_farther_hospital_wins(self):
        graph = prepare(demo(), "pagi")
        for algo in ("ucs", "astar"):
            result = search(graph, "S", ["A", "B"], algo)
            self.assertEqual(result["goal"], "B")
            self.assertAlmostEqual(result["cost_s"], 27)

    def test_direction_and_start_goal(self):
        graph = prepare(demo(), "pagi")
        self.assertEqual(search(graph, "A", ["S"])["status"], "unreachable")
        self.assertEqual(search(graph, "S", ["S"])["cost_s"], 0)

    def test_parallel_and_closed(self):
        data = demo()
        data["edges"].append({"id": "SA_fast", "u": "S", "v": "A",
                              "length_m": 100, "highway": "primary"})
        self.assertEqual(search(prepare(data, "pagi"), "S", ["A", "B"])["edges"], ["SA_fast"])
        data["edges"][-1]["closed"] = True
        self.assertEqual(search(prepare(data, "pagi"), "S", ["A", "B"])["goal"], "B")

    def test_exposure_is_additive(self):
        whole = {"length_m": 200, "highway": "primary", "exposure_m": {"school": 100}}
        part = {"length_m": 100, "highway": "primary", "exposure_m": {"school": 50}}
        self.assertAlmostEqual(sum(edge_cost(whole, "pagi").values()),
                               2 * sum(edge_cost(part, "pagi").values()))

    def test_invalid_heuristic_geometry_rejected(self):
        data = demo()
        data["edges"][0]["length_m"] = 1
        with self.assertRaises(ValueError):
            prepare(data, "pagi")

    def test_random_graphs_against_independent_relaxation(self):
        rng = random.Random(20260921)
        for _ in range(40):
            nodes = {str(n): [rng.random() * 1000, rng.random() * 1000] for n in range(16)}
            edges = []
            for u in nodes:
                for v in nodes:
                    if u != v and rng.random() < .15:
                        edges.append({"id": f"{u}_{v}", "u": u, "v": v,
                                      "length_m": math.dist(nodes[u], nodes[v]) * 1.2,
                                      "highway": "primary", "rail_at_end": rng.random() < .2})
            data = {"nodes": nodes, "edges": edges}
            for scenario in ("pagi", "siang", "sore", "malam"):
                dist = dict.fromkeys(nodes, math.inf)
                dist["0"] = 0
                for _ in range(len(nodes) - 1):
                    for edge in edges:
                        dist[edge["v"]] = min(dist[edge["v"]], dist[edge["u"]] + sum(edge_cost(edge, scenario).values()))
                expected = min(dist["14"], dist["15"])
                graph = prepare(data, scenario)
                for algo in ("ucs", "astar"):
                    result = search(graph, "0", ["14", "15"], algo)
                    if math.isinf(expected):
                        self.assertIsNone(result["cost_s"])
                    else:
                        self.assertAlmostEqual(result["cost_s"], expected)


if __name__ == "__main__":
    unittest.main()
