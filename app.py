import streamlit as st
import pydeck as pdk
import query_engine
from shapely import wkb

# 1. Page Configuration
st.set_page_config(page_title="SystemEarth MVP", layout="wide")
st.title("SystemEarth: Geospatial Data Optimization")

# 2. Sidebar Control Panel
st.sidebar.header("Navigation")
plot_ids = query_engine.get_all_plot_ids()
selected_plot = st.sidebar.selectbox("Select Plot ID to Analyze", plot_ids)

# 3. Execute Queries
with st.spinner("Querying multi-layer architecture..."):
    raw_results = query_engine.run_raw_baseline_query(selected_plot)
    opt_results = query_engine.run_optimized_query(selected_plot)

# 4. Map Visualization using PyDeck
st.subheader(f"Plot Geometry: {selected_plot}")
geom_raw = opt_results["geometry"]
geom = wkb.loads(bytes(geom_raw))
centroid = geom.centroid

# Convert Shapely polygon exterior coordinates for PyDeck
polygon_data = [{"geometry": [[list(coord) for coord in geom.exterior.coords]]}]

# Set color based on compliance status (Red for Non-Compliant, Green for Compliant)
fill_color = [200, 30, 0, 150] if "Non" in opt_results['compliance']['status'] else [0, 200, 50, 150]

view_state = pdk.ViewState(latitude=centroid.y, longitude=centroid.x, zoom=14, pitch=0)
polygon_layer = pdk.Layer(
    "PolygonLayer",
    data=polygon_data,
    get_polygon="geometry",
    get_fill_color=fill_color,
    get_line_color=[255, 255, 255],
    line_width_min_pixels=2,
)
st.pydeck_chart(pdk.Deck(layers=[polygon_layer], initial_view_state=view_state))

st.divider()

# 5. Side-by-Side Performance Comparison
st.subheader("Performance & Fidelity Comparison")
col1, col2 = st.columns(2)

with col1:
    st.header("Raw Layers (Baseline)")
    st.metric("Query Latency", f"{raw_results['query_time_ms']} ms")
    st.metric("Storage Required", raw_results['storage_size_display'])
    st.write("**Compliance Decision:**")
    st.json(raw_results['compliance'])

with col2:
    st.header("Optimized Architecture")
    
    # Calculate latency difference cleanly
    latency_diff = round(opt_results['query_time_ms'] - raw_results['query_time_ms'], 2)
    latency_label = f"{latency_diff} ms (Faster)" if latency_diff < 0 else f"+{latency_diff} ms (Slower)"
    
    # Calculate exact storage percentage reduction
    storage_saved_kb = round(raw_results['storage_kb'] - opt_results['storage_kb'], 2)
    storage_saved_pct = round((storage_saved_kb / raw_results['storage_kb']) * 100, 1)
    
    st.metric(
        "Query Latency", 
        f"{opt_results['query_time_ms']} ms", 
        delta=latency_label, 
        delta_color="inverse"
    )
    st.metric(
        "Storage Required", 
        opt_results['storage_size_display'], 
        delta=f"-{storage_saved_pct}% (-{storage_saved_kb} KB)", 
        delta_color="inverse"
    )
    st.write("**Compliance Decision:**")
    st.json(opt_results['compliance'])

# 6. Fidelity Validation
st.divider()
if raw_results['compliance'] == opt_results['compliance']:
    st.success("✅ **100% Decision Fidelity:** The optimized architecture produced the exact same compliance outcome as the raw multi-layer baseline.")
else:
    st.error("❌ **Fidelity Mismatch:** The compliance outcomes differ. Check your encoding strategy.")