## 3. Data & System Design

### 3.1 Data / Knowledge Source

RuteSiaga uses the Java OpenStreetMap (OSM) extract provided by Geofabrik, specifically the local snapshot java-260920.osm.pbf dated 20 September 2026. The source file is 896,987,462 bytes. Processing is performed locally, so subsequent online map updates do not change the experimental results. The model covers the Special Region of Yogyakarta (DIY) with a 10 km buffer beyond its boundary to avoid cutting off roads that briefly cross the regional border. The raw PBF is not included in the application package because of its size; the processed data required to run the application is included.

The input data comprises road geometry and classes (highway tags), direction and motor-vehicle access restrictions, width or vehicle-dimension tags where available, turn-restriction relations, traffic signals, at-grade railway crossings, schools, markets, malls, and hospitals. Geometry is projected to EPSG:32749 (UTM zone 49S), allowing lengths and distances to be measured in metres. These OSM attributes support a directed, time-weighted road graph, but their completeness and accuracy in the field have not been established.

The base graph contains 169,944 nodes and 330,774 directed edges. Of 138 candidate hospital objects extracted within DIY, name and facility-type filtering yielded 50 candidate general hospitals. Forty-four candidates met the model's criteria for a road-node proxy in the largest network component; six require further review. The active system adds one road-approach goal for RSUP Dr. Sardjito following an audit of local OSM data. Consequently, it has 45 road goal nodes representing 44 unique hospital names, not 45 distinct hospitals. These goals are road-network proxies near hospitals, not emergency-department entrances, and the list has not been verified as a complete register of DIY hospitals.

For location-based penalties, the processed dataset contains 1,871 schools, 376 markets, and 20 malls. These are objects extracted from the OSM snapshot, not a census of all such facilities in DIY. Their influence radii are 100 m, 150 m, and 200 m, respectively. The extraction counts are recorded in mesin/data_offline/inventory_report.json, mesin/network_diy/network_report.json, and mesin/network_diy/poi/penalty_report.json.

### 3.2 Data Preparation

Data preparation has four stages. First, OSM objects are read from the local PBF and clipped to DIY plus the 10 km buffer. Second, roads are filtered by highway class and access, width, surface, vehicle-dimension, and direction tags. Major classes such as motorway, trunk, primary, secondary, and tertiary, including their links, may enter the main graph if they pass the rules. Residential and unclassified roads enter the main graph only when an explicit width meets the assumed 3 m threshold. Service roads do not automatically enter the main graph; access from the departure point is handled separately. Pedestrian and bicycle facilities, roads represented by disallowed classes or insufficient recorded width, and roads with known access prohibitions are excluded. The class and width rules are proxies for ambulance suitability, not measurements of every road's physical clearance.

Third, eligible road segments become directed edges. One-way tags are retained, while two-way roads receive an edge in each direction. Supported turn-restriction relations constrain transitions from an incoming edge to an outgoing edge. Segment lengths are measured in metres in EPSG:32749. Schools, markets, and malls are then mapped to edges: exposure is the length of an edge intersecting each type's influence zone. Overlapping zones of the same type are merged so that exposure is not counted twice. Edges tagged as bridges or tunnels receive no point-of-interest (POI) exposure in this preparation stage. A railway-crossing penalty applies only when the data identifies an at-grade crossing on a road without a grade-separation tag. These rules depend on the accuracy of OSM tagging.

Fourth, candidate hospitals are filtered and mapped to road nodes that satisfy the model criteria. The system does not invent a straight-line road connection from a road node to a hospital entrance. When a user selects a departure point, the system searches the access catalog for a nearby road segment and places a direction-aware starting point on that segment. The initial access search is limited to a 1 km radius. Local or service roads that satisfy access rules may be used only for the initial connection; after the route reaches the goal-connected main network, the main graph rules apply. The lateral distance from the location marker to the selected road is displayed but excluded from travel-time cost. Selecting the nearest mapped road does not establish that the road is physically accessible from a building or property.

Each edge cost is expressed in seconds as the sum of base travel time, POI exposure, traffic-signal delay, railway-crossing delay, and a gate delay where applicable. Base time is edge length divided by the model speed for its road class. All cost components are non-negative. The morning, midday, evening, and night parameters are research assumptions held fixed during a search, not live traffic measurements. The processed graph, access catalog, location indexes, and supporting rules are included in the final application package.

### 3.3 System Architecture

The system flow is as follows: the user enters a place name or coordinates, or selects a point on the map; the interface obtains coordinates; the origin-access module projects the point onto a road segment; the routing engine applies costs for the selected time scenario; UCS and A* search the same set of hospital goals; the server checks that their optimal costs agree; and the interface displays the route, hospital, estimated travel time, cost breakdown, and search statistics. Place-name lookup uses a local OSM index. If a place is absent from that index, the user can enter coordinates or select a map point.

The main components are (1) the road graph and access catalog; (2) mesin/origin_access.py for departure-point mapping; (3) mesin/ambulance_router.py for cost parameters; (4) mesin/route_network.py for UCS, A*, and turn restrictions; (5) web/server.py connecting the engine to the interface; and (6) the single-page HTML, CSS, and JavaScript interface. The terminal and web application use the same core search module. If UCS and A* return different optimal costs, the server raises an error instead of silently presenting a route. The web search animation visualizes expanded states; it does not represent a live ambulance trip.

The web map draws a simplified view of local OSM road segments. At wide zoom levels it displays major road classes to keep the interface responsive. This visual simplification does not change the routing graph used by the engine.

### 3.4 Technology

The application is implemented in Python 3.14. Its priority queue uses the standard-library heapq module, and the local server uses http.server. NumPy and Shapely support origin-to-road projection and geometric operations; NetworkX is used during network preparation or validation. The access catalog is stored in SQLite. The single-page interface uses HTML, CSS, JavaScript, and SVG without an online map-tile service. The application runs locally at http://127.0.0.1:8765/. Python package requirements are listed in requirements.txt. Repeating the extraction from scratch requires the raw OSM PBF, whereas running the supplied processed graph does not.

## 4. Implementation & Results

### 4.1 Algorithm Implementation

A search state is a pair (current node, incoming edge ID), because the legality of a turn can depend on the preceding edge. UCS and A* share a min-heap, a best-known cost for each state, and parent pointers for path reconstruction. UCS orders the queue by accumulated cost g(s). A* orders it by g(s) + h(s), where h(s) is the straight-line distance from the current node to the nearest hospital goal divided by the model's maximum speed of 60 km/h (approximately 16.67 m/s). Road-path length cannot be shorter than straight-line distance, model speeds do not exceed that maximum, and penalties are non-negative. Therefore, h(s) is a lower bound on the remaining cost in this model. The search stops when a valid goal state is removed from the queue, not when a goal is first discovered.

The main workflow is:

~~~text
prepare the graph and hospital goal set for the chosen scenario
insert the initial state with g = 0 into the min-heap
while the heap is not empty:
    remove the state with the lowest priority
    skip a stale entry if its g differs from the best-known cost
    if its node is a goal: reconstruct and return the route
    for each outgoing edge allowed by direction, access, and turn rules:
        calculate new_g = g + edge cost in seconds
        if new_g improves the next state's best-known cost:
            save its parent and new_g
            insert it with priority new_g (UCS)
            or new_g + h(next node) (A*)
if the heap becomes empty: report no route under the model
~~~

All hospital goals are included in one search. The result is therefore the goal with the lowest modelled travel-time cost in the available graph; the system does not run a separate search for each hospital. For example, the Jalan Grafika departure coordinate maps to a point 7.08 m from the selected road segment. In the morning scenario, both algorithms reach the road proxy for RSUP Dr. Sardjito with a cost of 44.89 seconds over 249.41 m. This is a model cost to a road point, not a measured time to an emergency-department entrance.

### 4.2 System Implementation

Users can search a place name in the local OSM index, enter latitude and longitude, or select a map point. Once a time scenario is selected, the interface sends a request to the local server. The server resolves initial road access, prepares edge costs for the scenario, and runs UCS and A*. Its response includes the road starting point, marker-to-road gap, selected hospital, route distance, total seconds, base/POI/signal/rail/gate cost breakdown, expanded-state counts, search runtimes, and route geometry. Users can download the result as JSON.

If the departure point cannot be mapped or no route satisfies the graph constraints, the system reports the problem instead of inventing a road connection. The interface shows the origin, hospital goal, route, and animated search trace. Algorithm runtimes in the experiment below measure only the search itself; data loading, access preparation, and web rendering are excluded.

### 4.3 Results

The main test used 20 departure locations and four time scenarios, yielding 80 cases. Three locations used coordinates supplied by the user. For the other 17, the test script automatically selected an OSM road point near each place marker; physical access from the marker to that road has not been verified. All 80 cases found a route. UCS and A* returned equal optimal costs within 10^-6 seconds, and their final sequences of route edges were also identical in all 80 cases.

| Metric across 80 cases | UCS | A* |
|---|---:|---:|
| Total expanded states | 264,494 | 153,311 |
| Mean expanded states per case | 3,306.18 | 1,916.39 |
| Mean search runtime per case | 32.82 ms | 36.80 ms |
| Cases with lower search runtime | 66 | 14 |

A* expanded fewer states in every case, reducing the aggregate count by approximately 42.04% relative to UCS. Nevertheless, its mean search runtime was higher in this batch. Computing the heuristic against multiple goals adds work per state. Millisecond runtimes depend on hardware, caches, and execution conditions; these values describe one batch and are not a general performance guarantee. Agreement in model cost and final path supports implementation consistency on the tested inputs, but does not validate travel-time estimates against real ambulance journeys.

For the same 20 departure locations, mean modelled route costs were 592.55 seconds in the morning, 529.67 seconds at midday, 510.60 seconds in the evening, and 404.10 seconds at night. These differences arise from the model's scenario penalties. They are not empirical evidence that every night trip in DIY is faster. A location may select a different route or hospital under a different scenario.

| Batch example | Selected hospital | Route distance | UCS = A* cost | UCS / A* expanded states |
|---|---|---:|---:|---:|
| Jalan Grafika, morning | RSUP Dr. Sardjito | 249.41 m | 44.89 s | 43 / 36 |
| Jalan Tentara Pelajar, morning | Rumah Sakit Dr Soetarto | 2.75 km | 547.82 s | 922 / 847 |
| Malioboro Mall, morning | Rumah Sakit Ludira Husada Tama | 2.21 km | 563.58 s | 346 / 305 |

For the Malioboro Mall batch case, the test script first moved the OSM place marker to a road point approximately 100.28 m away. The 563.58-second cost excludes that lateral movement. Entering the original marker directly can produce a slightly different result.

An additional validation of the base graph compared the search implementation with a NetworkX Dijkstra oracle over 56 query pairs and 112 UCS/A* searches. The validation report records eight unreachable queries and matching costs for reachable queries. This supports correctness relative to the tested graph and cost function; it does not verify road conditions, gates, congestion, or real travel times. The principal evidence files are hasil/json_otomatis/hasil_batch.json, hasil/excel/Hasil_Uji_RuteSiaga_20_Lokasi.xlsx, and mesin/network_diy/validation_poi_report.json.

### 4.4 Working System

To reproduce one example, launch Jalankan-Web.cmd, open http://127.0.0.1:8765/, enter the Jalan Grafika coordinates (-7.766067024356544, 110.37390636072011), and select the morning scenario. Under the model, the system selects RSUP Dr. Sardjito, displays the route and an estimated cost of 44.89 seconds, and reports 43 expanded UCS states versus 36 A* states. The user can play the search animation or download the JSON details.

To satisfy the screenshot requirement in the report outline, insert a screenshot only after the example route has actually appeared in the running application. Suggested caption: **Figure 4.1. RuteSiaga showing the Jalan Grafika departure point in the morning scenario; the route and time are model estimates to a hospital road point.** No unverified screenshot is included in this file.

### Sources for Sections 3–4

- Geofabrik GmbH. (2026). *OpenStreetMap data extracts — Java*. https://download.geofabrik.de/asia/indonesia/java.html (local snapshot java-260920.osm.pbf, 20 September 2026).
- OpenStreetMap contributors. (2026). *OpenStreetMap* [database], licensed under the ODbL. https://www.openstreetmap.org/copyright
- RuteSiaga_FINAL/mesin/network_diy/network_report.json; RuteSiaga_FINAL/mesin/network_diy/poi/penalty_report.json; RuteSiaga_FINAL/hasil/json_otomatis/hasil_batch.json; RuteSiaga_FINAL/mesin/network_diy/validation_poi_report.json (project data and results, accessed 30 September 2026).
