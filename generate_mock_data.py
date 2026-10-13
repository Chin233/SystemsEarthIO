import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
import random

def create_mock_data():
    # Base coordinates roughly centered in Thailand
    start_lon, start_lat = 100.0, 15.0
    
    plots = []
    attributes = []
    
    for i in range(15):
        # Generate small square polygons, shifting slightly for each plot
        lon = start_lon + (i * 0.01)
        lat = start_lat + (i * 0.01)
        poly = Polygon([
            (lon, lat), 
            (lon + 0.005, lat), 
            (lon + 0.005, lat + 0.005), 
            (lon, lat + 0.005)
        ])
        plots.append(poly)
        
        # Generate randomized EUDR compliance metrics
        attributes.append({
            "plot_id": f"P-{str(i+1).zfill(4)}",
            "forest_baseline_2020": random.choice([True, False]),
            "deforestation_alerts": random.choice([0, 0, 1, 3]), # Weighted towards zero alerts
            "protected_area_overlap": random.choice([True, False, False]) # Weighted towards False
        })

    # Assemble into a GeoDataFrame with standard WGS84 coordinate reference system
    gdf = gpd.GeoDataFrame(attributes, geometry=plots, crs="EPSG:4326")

    # Export to GeoParquet format
    file_name = "mock_plots.parquet"
    gdf.to_parquet(file_name)
    print(f"Success: {file_name} generated with {len(gdf)} plots.")

if __name__ == "__main__":
    create_mock_data()