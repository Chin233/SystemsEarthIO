import duckdb
import pandas as pd
import geopandas as gpd
import time
import os
from shapely import wkb

CSV_FILE = "./source/200001-17plots-valid_2025-08-02T09_11_12Z.csv"
GEO_FILE = "./source/200001-17plots-valid.geojson"
PARQUET_FILE = "optimized_plots.parquet"

# Persistent in-memory connection initialised outside the query timer
CON = duckdb.connect(database=":memory:")

def get_all_plot_ids():
    df = CON.execute(f"SELECT DISTINCT a3_plot_id FROM '{PARQUET_FILE}' ORDER BY a3_plot_id").fetchdf()
    return df["a3_plot_id"].tolist()

def get_all_plots_geodata():
    """Fetches all plots from Parquet for map overview rendering."""
    df = CON.execute(f"SELECT * FROM '{PARQUET_FILE}' ORDER BY a3_plot_id").fetchdf()
    records = []
    for _, row in df.iterrows():
        geom = wkb.loads(bytes(row["geometry"]))
        has_alert = bool(int(row["compliance_bitmask"]) & 8)
        records.append({
            "plot_id": row["a3_plot_id"],
            "area_ha": round(float(row["a7_size_of_plot_ha"]), 2),
            "has_spatial_alert": has_alert,
            "coordinates": [[list(coord) for coord in geom.exterior.coords]],
            "centroid_lon": geom.centroid.x,
            "centroid_lat": geom.centroid.y
        })
    return records

def evaluate_raw_compliance(record):
    return {
        "eudr_status": "Compliant" if str(record["i1_eudr_status"]).startswith("a.") else "Non-Compliant",
        "spatial_alert": "Alert Detected (Hansen 21-23)" if str(record["c2_deforestation_spatial_analysis_result"]).startswith("b.") else "No Indication",
        "deforestation_final": "Deforestation-Free" if str(record["c5_deforestation_final_status"]).startswith("a.") else "Flagged",
        "protected_overlap": "No Overlap" if str(record["d1_strict_protected_area_spatial_analysis_result"]).startswith("a.") else "Overlap Detected",
        "plot_size_ha": round(float(record["a7_size_of_plot_ha"]), 2)
    }

def decode_bitmask_compliance(bitmask: int, area_ha: float):
    return {
        "eudr_status": "Compliant" if (bitmask & 1) else "Non-Compliant",
        "spatial_alert": "Alert Detected (Hansen 21-23)" if (bitmask & 8) else "No Indication",
        "deforestation_final": "Deforestation-Free" if (bitmask & 2) else "Flagged",
        "protected_overlap": "No Overlap" if (bitmask & 4) else "Overlap Detected",
        "plot_size_ha": round(float(area_ha), 2)
    }

def run_raw_baseline_query(plot_id: str):
    start_time = time.perf_counter()
    
    df = pd.read_csv(CSV_FILE)
    gdf = gpd.read_file(GEO_FILE)
    merged = gdf.merge(df, left_on="ProductionPlace", right_on="a3_plot_id")
    
    result = merged[merged["a3_plot_id"] == plot_id].iloc[0]
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    raw_bytes = os.path.getsize(CSV_FILE) + os.path.getsize(GEO_FILE)
    raw_kb = round(raw_bytes / 1024, 2)
    
    return {
        "plot_id": result["a3_plot_id"],
        "compliance": evaluate_raw_compliance(result),
        "geometry": result["geometry"],
        "query_time_ms": round(elapsed_ms, 2),
        "storage_kb": raw_kb,
        "storage_size_display": f"{raw_kb} KB (Raw CSV + GeoJSON)",
    }

def run_optimized_query(plot_id: str):
    start_time = time.perf_counter()
    
    query = f"SELECT * FROM '{PARQUET_FILE}' WHERE a3_plot_id = '{plot_id}' LIMIT 1"
    result = CON.execute(query).fetchdf().iloc[0]
    compliance = decode_bitmask_compliance(int(result["compliance_bitmask"]), result["a7_size_of_plot_ha"])
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    opt_bytes = os.path.getsize(PARQUET_FILE)
    opt_kb = round(opt_bytes / 1024, 2)

    return {
        "plot_id": result["a3_plot_id"],
        "compliance": compliance,
        "geometry": result["geometry"],
        "query_time_ms": round(elapsed_ms, 2),
        "storage_kb": opt_kb,
        "storage_size_display": f"{opt_kb} KB (Bitmask GeoParquet)",
    }