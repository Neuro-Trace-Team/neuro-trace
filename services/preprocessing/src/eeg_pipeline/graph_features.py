from __future__ import annotations
import numpy as np

def graph_metrics(matrix, density=0.2):
    a=np.asarray(matrix, dtype=float).copy(); np.fill_diagonal(a, 0); n=a.shape[0]
    finite=a[np.isfinite(a) & (a>0)]; threshold=np.quantile(finite, 1-density) if len(finite) else np.inf
    adj=np.where(a>=threshold, a, 0); degree=(adj>0).sum(axis=1); strength=np.nansum(adj, axis=1)
    out={"node_degree": degree, "node_strength": strength, "clustering_coefficient": np.full(n, np.nan), "betweenness_centrality": np.full(n, np.nan), "characteristic_path_length": np.nan, "global_efficiency": np.nan, "local_efficiency": np.nan}
    try:
        import networkx as nx
        g=nx.Graph(); g.add_nodes_from(range(n))
        for i in range(n):
            for j in range(i):
                if adj[i,j]>0: g.add_edge(i,j, weight=float(adj[i,j]), distance=1/max(float(adj[i,j]),1e-12))
        out["clustering_coefficient"]=np.array(list(nx.clustering(g, weight="weight").values()))
        out["betweenness_centrality"]=np.array(list(nx.betweenness_centrality(g, weight="distance", normalized=True).values()))
        out["characteristic_path_length"]=nx.average_shortest_path_length(g, weight="distance") if nx.is_connected(g) else np.nan
        out["global_efficiency"]=nx.global_efficiency(g)
        out["local_efficiency"]=nx.local_efficiency(g)
    except ImportError: pass
    return out

