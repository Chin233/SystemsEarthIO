import pandas as pd
import geopandas as gpd

def optimize_raw_data():
    csv_file = "./source/200001-17plots-valid_2025-08-02T09_11_12Z.csv"
    geo_file = "./source/200001-17plots-valid.geojson"
    
    df = pd.read_csv(csv_file)
    gdf = gpd.read_file(geo_file)
    merged = gdf.merge(df, left_on="ProductionPlace", right_on="a3_plot_id")
    
    # Bitmask Encoding Strategy: Pack 4 compliance layers into a single 1-byte uint8 integer
    # Bit 0 (1): EUDR Compliant (i1)
    # Bit 1 (2): Final Status Deforestation-Free (c5)
    # Bit 2 (4): No Strict Protected Area Overlap (d1)
    # Bit 3 (8): Spatial Deforestation Alert Detected (c2)
    bitmask = (
        (merged["i1_eudr_status"].str.startswith("a.").astype("uint8") * 1) +
        (merged["c5_deforestation_final_status"].str.startswith("a.").astype("uint8") * 2) +
        (merged["d1_strict_protected_area_spatial_analysis_result"].str.startswith("a.").astype("uint8") * 4) +
        (merged["c2_deforestation_spatial_analysis_result"].str.startswith("b.").astype("uint8") * 8)
    ).astype("uint8")

    optimized_gdf = gpd.GeoDataFrame({
        "a3_plot_id": merged["a3_plot_id"],
        "a7_size_of_plot_ha": merged["a7_size_of_plot_ha"].astype("float32"),
        "compliance_bitmask": bitmask,
        "geometry": merged["geometry"]
    }, crs="EPSG:4326")
    
    # Export with Zstandard compression and without index bloat
    optimized_gdf.to_parquet("optimized_plots.parquet", compression="zstd", index=False)
    print("Optimization complete: bitmask-encoded optimized_plots.parquet generated.")

if __name__ == "__main__":
    optimize_raw_data()