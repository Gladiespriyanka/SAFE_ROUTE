from typing import Any, Dict, List, Tuple


G = None


def _get_graph():
    """Load and cache the Delhi street network on first use."""
    global G
    if G is None:
        import osmnx as ox

        G = ox.graph_from_place("Delhi, India", network_type="drive")
    return G


def _nearest_node(lat: float, lon: float) -> int:
    import osmnx as ox

    graph = _get_graph()
    return ox.distance.nearest_nodes(graph, X=lon, Y=lat)


def _k_shortest_paths(graph, orig: int, dest: int, k: int, weight: str):
    try:
        import osmnx as ox

        return ox.k_shortest_paths(graph, orig, dest, k=k, weight=weight)
    except AttributeError:
        import networkx as nx

        return nx.shortest_simple_paths(graph, orig, dest, weight=weight)


def _path_length_m(graph, path_nodes: List[int]) -> float:
    total = 0.0
    for u, v in zip(path_nodes, path_nodes[1:]):
        edge_data = graph.get_edge_data(u, v, default={})
        if not edge_data:
            continue

        if "length" in edge_data:
            total += float(edge_data.get("length", 0.0))
            continue

        lengths = [
            float(data.get("length", 0.0))
            for data in edge_data.values()
            if isinstance(data, dict)
        ]
        if lengths:
            total += min(lengths)
    return total


def get_candidate_routes(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    k: int = 5,
) -> List[Dict[str, Any]]:
    from shapely.geometry import LineString

    graph = _get_graph()
    orig = _nearest_node(start_lat, start_lon)
    dest = _nearest_node(end_lat, end_lon)

    path_iter = _k_shortest_paths(graph, orig, dest, k=k, weight="length")

    routes: List[Dict[str, Any]] = []
    for path_nodes in path_iter:
        if len(routes) >= k:
            break

        path_nodes = list(path_nodes)
        coords: List[Tuple[float, float]] = []
        for node_id in path_nodes:
            node_data = graph.nodes[node_id]
            coords.append((node_data["y"], node_data["x"]))

        geom = LineString([(lon, lat) for lat, lon in coords])
        routes.append(
            {
                "node_ids": path_nodes,
                "coordinates": coords,
                "approx_length": _path_length_m(graph, path_nodes),
                "geometry_length_degrees": float(geom.length),
            }
        )

    return routes
