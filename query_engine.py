import duckdb
import pandas as pd
import geopandas as gpd
import time
import os

# Constants for file paths
CSV_FILE = "./source/200001-17plots-valid_2025-08-02T09_11_12Z.csv"
GEO_FILE = "./source/200001-17plots-valid.geojson"
PARQUET_FILE = "optimized_plots.parquet"

# Initialize the persistent in-memory DuckDB connection ONCE outside the query timer
CON = duckdb.connect(database=":memory:")

def get_all_plot_ids():
    df = CON.execute(f"SELECT DISTINCT a3_plot_id FROM '{PARQUET_FILE}' ORDER BY a3_plot_id").fetchdf()
    return df["a3_plot_id"].tolist()

def evaluate_eudr_compliance(record):
    return {
        "status": record["i1_eudr_status"],
        "deforestation": record["c5_deforestation_final_status"],
        "protected_overlap": record["d1_strict_protected_area_spatial_analysis_result"],
        "plot_size_ha": float(record["a7_size_of_plot_ha"])
    }

def run_raw_baseline_query(plot_id: str):
    start_time = time.perf_counter()
    
    # Dynamically loading and joining the fragmented raw files (slowest approach)
    df = pd.read_csv(CSV_FILE)
    gdf = gpd.read_file(GEO_FILE)
    merged = gdf.merge(df, left_on="ProductionPlace", right_on="a3_plot_id")
    
    result = merged[merged["a3_plot_id"] == plot_id].iloc[0]
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    raw_bytes = os.path.getsize(CSV_FILE) + os.path.getsize(GEO_FILE)
    raw_kb = round(raw_bytes / 1024, 2)
    
    return {
        "plot_id": result["a3_plot_id"],
        "compliance": evaluate_eudr_compliance(result),
        "geometry": result["geometry"],
        "query_time_ms": round(elapsed_ms, 2),
        "storage_kb": raw_kb,
        "storage_size_display": f"{raw_kb} KB (Raw CSV + GeoJSON)",
    }

def run_optimized_query(plot_id: str):
    start_time = time.perf_counter()
    
    # Querying Parquet using the already-active DuckDB connection (faster approach)
    query = f"SELECT * FROM '{PARQUET_FILE}' WHERE a3_plot_id = '{plot_id}' LIMIT 1"
    result = CON.execute(query).fetchdf().iloc[0]
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    opt_bytes = os.path.getsize(PARQUET_FILE)
    opt_kb = round(opt_bytes / 1024, 2)

    return {
        "plot_id": result["a3_plot_id"],
        "compliance": evaluate_eudr_compliance(result),
        "geometry": result["geometry"],
        "query_time_ms": round(elapsed_ms, 2),
        "storage_kb": opt_kb,
        "storage_size_display": f"{opt_kb} KB (Optimized Parquet)",
    }