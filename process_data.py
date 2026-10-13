import pandas as pd
import geopandas as gpd

def optimize_raw_data():
    # 1. Load the raw disconnected files
    csv_file = "./source/200001-17plots-valid_2025-08-02T09_11_12Z.csv"
    geo_file = "./source/200001-17plots-valid.geojson"
    
    df = pd.read_csv(csv_file)
    gdf = gpd.read_file(geo_file)
    
    # 2. Merge them into a single dataset on the Plot ID
    merged_gdf = gdf.merge(df, left_on="ProductionPlace", right_on="a3_plot_id")
    
    # 3. Layer Analysis: Keep only essential compliance attributes and drop the bloat
    essential_columns = [
        "a3_plot_id", 
        "a7_size_of_plot_ha",
        "c5_deforestation_final_status", 
        "d1_strict_protected_area_spatial_analysis_result",
        "i1_eudr_status",
        "geometry"
    ]
    optimized_gdf = merged_gdf[essential_columns]
    
    # 4. Export to the compressed GeoParquet architecture
    optimized_gdf.to_parquet("optimized_plots.parquet")
    print("Optimization complete: optimized_plots.parquet generated.")

if __name__ == "__main__":
    optimize_raw_data()