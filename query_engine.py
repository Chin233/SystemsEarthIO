import duckdb
import pandas as pd
import geopandas as gpd
import time
import os

CSV_FILE = "./source/200001-17plots-valid_2025-08-02T09_11_12Z.csv"
GEO_FILE = "./source/200001-17plots-valid.geojson"
PARQUET_FILE = "optimized_plots.parquet"

def get_duckdb_connection():
    con = duckdb.connect(database=":memory:")
    try:
        con.execute("INSTALL spatial; LOAD spatial;")
    except:
        pass
    return con

def get_all_plot_ids():
    con = get_duckdb_connection()
    df = con.execute(f"SELECT a3_plot_id FROM '{PARQUET_FILE}' ORDER BY a3_plot_id").fetchdf()
    return df["a3_plot_id"].tolist()

def evaluate_eudr_compliance(record):
    # Dynamically reads the real compliance statuses from the CSV
    return {
        "status": record["i1_eudr_status"],
        "deforestation": record["c5_deforestation_final_status"],
        "protected_overlap": record["d1_strict_protected_area_spatial_analysis_result"],
        "plot_size_ha": record["a7_size_of_plot_ha"]
    }

def run_raw_baseline_query(plot_id: str):
    start_time = time.perf_counter()
    
    # The "Slow" Way: Dynamically loading and joining the fragmented raw files
    df = pd.read_csv(CSV_FILE)
    gdf = gpd.read_file(GEO_FILE)
    merged = gdf.merge(df, left_on="ProductionPlace", right_on="a3_plot_id")
    
    # Find the specific plot
    result = merged[merged["a3_plot_id"] == plot_id].iloc[0]
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # Dynamically measure the raw storage footprint
    raw_bytes = os.path.getsize(CSV_FILE) + os.path.getsize(GEO_FILE)
    raw_kb = round(raw_bytes / 1024, 2)
    
    return {
        "plot_id": result["a3_plot_id"],
        "compliance": evaluate_eudr_compliance(result),
        "geometry": result["geometry"],
        "query_time_ms": round(elapsed_ms, 2),
        "storage_size_display": f"{raw_kb} KB (Raw CSV + GeoJSON)",
    }

def run_optimized_query(plot_id: str):
    start_time = time.perf_counter()
    
    # The "Fast" Way: Querying the streamlined Parquet file with DuckDB
    con = get_duckdb_connection()
    query = f"SELECT * FROM '{PARQUET_FILE}' WHERE a3_plot_id = '{plot_id}'"
    result = con.execute(query).fetchdf().iloc[0]
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # Dynamically measure the optimized storage footprint
    opt_bytes = os.path.getsize(PARQUET_FILE)
    opt_kb = round(opt_bytes / 1024, 2)

    return {
        "plot_id": result["a3_plot_id"],
        "compliance": evaluate_eudr_compliance(result),
        "geometry": result["geometry"],
        "query_time_ms": round(elapsed_ms, 2),
        "storage_size_display": f"{opt_kb} KB (Optimized Parquet)",
    }