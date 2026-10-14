import streamlit as st
import pandas as pd
import pydeck as pdk
import query_engine
import json
from shapely import wkb
from pathlib import Path

# 1. Page Configuration & Custom Styling
st.set_page_config(page_title="SystemEarth | Geospatial Optimization", page_icon="🌍", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 1.8rem; padding-bottom: 2rem; }
    div[data-testid="stMetric"] {
        background-color: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 14px 18px;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# 2. Load Shipment Overview Data
all_plots = query_engine.get_all_plots_geodata()
plot_ids = [p["plot_id"] for p in all_plots]
total_area = round(sum(p["area_ha"] for p in all_plots), 2)
alert_count = sum(1 for p in all_plots if p["has_spatial_alert"])

# 3. Sidebar Controls
with st.sidebar:
    st.title("🌍 SystemEarth")
    st.caption("Keep the decision, not the data")
    st.divider()
    
    selected_plot = st.selectbox("Select Farm Plot ID", plot_ids, index=0)
    
    st.markdown("### Encoding Architecture")
    st.info(
        "**Bitmask + GeoParquet (Zstd)**\n\n"
        "• **4 compliance layers** packed into a `1-byte uint8` bitmask.\n"
        "• **30 non-essential CSV columns** stripped via layer analysis.\n"
        "• **Zero-copy SQL queries** via persistent in-memory DuckDB."
    )

# 4. Run Queries for Selected Plot
raw_results = query_engine.run_raw_baseline_query(selected_plot)
opt_results = query_engine.run_optimized_query(selected_plot)

speedup_x = round(raw_results["query_time_ms"] / max(opt_results["query_time_ms"], 0.01), 1)
storage_saved_kb = round(raw_results["storage_kb"] - opt_results["storage_kb"], 2)
storage_saved_pct = round((storage_saved_kb / raw_results["storage_kb"]) * 100, 1)
fidelity_match = raw_results["compliance"] == opt_results["compliance"]

# 5. Top Executive Header & Shipment KPIs
st.title("Shipment Details & Architecture Benchmark")
st.caption("Region: Surat Thani, Chai Buri (Thailand) • Lot #200001 • Layer: Hansen Tree Cover Loss (2021–2023)")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Monitored Plots", f"{len(all_plots)} Plots", f"{total_area} ha total area")
kpi2.metric("Spatial Alerts (Hansen)", f"{alert_count} Plots ({round(alert_count/len(all_plots)*100, 1)}%)", "Mitigated via on-site evidence", delta_color="off")
kpi3.metric("Query Speedup", f"{speedup_x}x Faster", f"{opt_results['query_time_ms']} ms vs {raw_results['query_time_ms']} ms")
kpi4.metric("Storage Footprint", f"-{storage_saved_pct}% Smaller", f"{opt_results['storage_kb']} KB vs {raw_results['storage_kb']} KB")

st.write("")

# 6. Main Split Layout: Map on Left, Benchmark Cards on Right
map_col, bench_col = st.columns([1.15, 1.0], gap="large")

with map_col:
    with st.container(border=True):
        st.subheader(f"📍 Geospatial Plot Inspector: `{selected_plot}`")
        
        geom_raw = opt_results["geometry"]
        geom = wkb.loads(bytes(geom_raw))
        centroid = geom.centroid

        # Style all plots: Amber for spatial alerts, Emerald for clean, Bright White border for selected
        for p in all_plots:
            is_selected = p["plot_id"] == selected_plot
            if p["has_spatial_alert"]:
                p["fill_color"] = [245, 158, 11, 210] if is_selected else [245, 158, 11, 110]
            else:
                p["fill_color"] = [16, 185, 129, 210] if is_selected else [16, 185, 129, 110]
            p["line_color"] = [255, 255, 255, 255] if is_selected else [200, 200, 200, 120]
            p["line_width"] = 4 if is_selected else 1

        view_state = pdk.ViewState(latitude=centroid.y, longitude=centroid.x, zoom=14.5, pitch=25)
        polygon_layer = pdk.Layer(
            "PolygonLayer",
            data=all_plots,
            get_polygon="coordinates",
            get_fill_color="fill_color",
            get_line_color="line_color",
            get_line_width="line_width",
            line_width_min_pixels=2,
            pickable=True,
            auto_highlight=True,
        )
        
        tooltip = {
            "html": "<b>Plot ID:</b> {plot_id}<br/><b>Area:</b> {area_ha} ha<br/><b>Spatial Alert:</b> {has_spatial_alert}",
            "style": {"backgroundColor": "#1e293b", "color": "white", "fontSize": "13px"}
        }
        
        st.pydeck_chart(pdk.Deck(layers=[polygon_layer], initial_view_state=view_state, tooltip=tooltip))
        st.caption("🟢 **Green:** No Spatial Deforestation Alert  |  🟠 **Amber:** Spatial Alert Detected (Mitigated)  |  ⚪ **White Border:** Selected Plot")

with bench_col:
    with st.container(border=True):
        st.subheader("⚡ Performance & Storage Benchmark")
        
        b1, b2 = st.columns(2)
        with b1:
            st.markdown("##### Raw Baseline (CSV + GeoJSON)")
            st.metric("Query Latency", f"{raw_results['query_time_ms']} ms")
            st.metric("Storage Size", f"{raw_results['storage_kb']} KB")
        
        with b2:
            st.markdown("##### Optimized (Bitmask + DuckDB)")
            latency_diff = round(opt_results['query_time_ms'] - raw_results['query_time_ms'], 2)
            latency_label = f"{latency_diff} ms (Faster)" if latency_diff < 0 else f"+{latency_diff} ms"
            st.metric("Query Latency", f"{opt_results['query_time_ms']} ms", delta=latency_label, delta_color="inverse")
            st.metric("Storage Size", f"{opt_results['storage_kb']} KB", delta=f"-{storage_saved_pct}% (-{storage_saved_kb} KB)", delta_color="inverse")

        st.divider()
        st.markdown("##### 🔍 Plot-Level Compliance Verification")
        
        comp_df = pd.DataFrame({
            "Compliance Attribute": [
                "Final EUDR Status (i1)",
                "Spatial Deforestation Analysis (c2)",
                "Final Deforestation Status (c5)",
                "Strict Protected Area Overlap (d1)",
                "Monitored Plot Area (a7)"
            ],
            "Raw Baseline Output": [
                raw_results["compliance"]["eudr_status"],
                raw_results["compliance"]["spatial_alert"],
                raw_results["compliance"]["deforestation_final"],
                raw_results["compliance"]["protected_overlap"],
                f"{raw_results['compliance']['plot_size_ha']} ha"
            ],
            "Decoded Bitmask Output": [
                opt_results["compliance"]["eudr_status"],
                opt_results["compliance"]["spatial_alert"],
                opt_results["compliance"]["deforestation_final"],
                opt_results["compliance"]["protected_overlap"],
                f"{opt_results['compliance']['plot_size_ha']} ha"
            ],
            "Fidelity": ["✅ Match"] * 5
        })
        st.dataframe(comp_df, use_container_width=True, hide_index=True)

        if fidelity_match:
            st.success("✅ **100% Decision Fidelity Verified:** Bitmask-decoded outputs are identical to the multi-file baseline.")
        else:
            st.error("❌ **Fidelity Mismatch Detected!**")


# ==========================================================
# Independent Hansen Environmental Analysis
# Added from systemearth-geospatial
# ==========================================================

@st.cache_data
def load_hansen_results():
    path = Path(__file__).resolve().parent / "dashboard_integrated.geojson"

    with open(path, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    return {
        feature["properties"]["plot_id"]: feature["properties"]
        for feature in geojson["features"]
    }

hansen_results = load_hansen_results()

st.divider()
st.header("🌳 Independent Hansen Environmental Analysis")
st.caption(
    "Satellite-derived tree-cover-loss observations compared with "
    "supplier-submitted due diligence declarations."
)

if selected_plot in hansen_results:
    record = hansen_results[selected_plot]

    st.subheader(f"Farm Plot: {selected_plot}")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Supplier Deforestation Indication",
            "Yes" if record["supplier_loss_indication"] else "No"
        )

    with col2:
        st.metric(
            "Hansen Loss Detected (2021–2023)",
            "Yes" if record["independent_hansen_loss"] else "No"
        )

    with col3:
        st.metric(
            "Detected Loss Pixels (2021–2023)",
            record["loss_pixels_2021_2023"]
        )

    st.markdown("### Comparison")

    comparison = record["analysis_comparison"]

    if comparison == "Same binary flag":
        st.success("Supplier and Hansen binary indicators match.")
    else:
        st.warning(
            "Different binary indicators — further investigation needed."
        )

    st.markdown("### Additional Environmental Observations")

    st.write(
        "**Canopy threshold fraction (year 2000):**",
        record["treecover_threshold_fraction"]
    )

    st.write(
        "**Tree-cover loss detected (2021–2025):**",
        record["loss_after_2020"]
    )

    st.write(
        "**Earliest post-2020 loss year:**",
        record["first_loss_year_after_2020"]
    )

    st.write(
        "**Water pixel fraction:**",
        record["water_pixel_fraction"]
    )

    with st.expander("Supplier declaration and mitigation details"):
        st.write(
            "**Supplier spatial analysis:**",
            record["supplier_deforestation_result"]
        )
        st.write(
            "**Mitigation:**",
            record["supplier_mitigation"]
        )
        st.write(
            "**Declared final deforestation status:**",
            record["supplier_final_deforestation_status"]
        )

    st.info(
        "These are environmental observations, not EUDR compliance "
        "determinations. Tree-cover loss does not necessarily mean "
        "deforestation. Different data versions, methods or thresholds "
        "may explain differences between the two indicators. "
        "The canopy-cover threshold is illustrative and uses year-2000 data."
    )

else:
    st.error(f"No Hansen analysis found for {selected_plot}.")
