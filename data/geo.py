import requests
import pandas as pd
import geopandas as gpd
from shapely import wkt


NTA_GEOJSON_URL = "https://data.cityofnewyork.us/resource/9nt8-h7nd.geojson"
NTA_FILE = "nyc_nta.geojson"

def load_nta(filepath: str = NTA_FILE) -> gpd.GeoDataFrame:
    """
    Load NTA boundary GeoDataFrame from local file.
    Downloads from NYC Open Data if file not found.
    """
    try:
        nta = gpd.read_file(filepath)
    except Exception:
        print(f"Downloading NTA boundaries from NYC Open Data...")
        r = requests.get(NTA_GEOJSON_URL, timeout=60)
        r.raise_for_status()
        with open(filepath, "w") as f:
            f.write(r.text)
        nta = gpd.read_file(filepath)

    return nta.to_crs(epsg=4326)

def assign_nta_311(data_311: pd.DataFrame, nta: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Assign ntaname to 311 complaints via lat/lon spatial join."""
    gdf = gpd.GeoDataFrame(
        data_311,
        geometry=gpd.points_from_xy(data_311["longitude"], data_311["latitude"]),
        crs="EPSG:4326"
    )
    return gpd.sjoin(gdf, nta[["ntaname", "geometry"]], how="left", predicate="within")


def assign_nta_crime(data_crime: pd.DataFrame, nta: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Assign ntaname to crime records.
    Filters to rows with valid lat/lon before spatial join.
    Records without coords are dropped here (NYPD geocoding lag).
    """
    has_coords = data_crime["latitude"].notna() & data_crime["longitude"].notna()
    data_with_coords = data_crime[has_coords].copy()

    gdf = gpd.GeoDataFrame(
        data_with_coords,
        geometry=gpd.points_from_xy(data_with_coords["longitude"], data_with_coords["latitude"]),
        crs="EPSG:4326"
    )
    return gpd.sjoin(gdf, nta[["ntaname", "geometry"]], how="left", predicate="within")


def assign_nta_crashes(data_crashes: pd.DataFrame, nta: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Assign ntaname to crash records via lat/lon spatial join."""
    gdf = gpd.GeoDataFrame(
        data_crashes,
        geometry=gpd.points_from_xy(data_crashes["longitude"], data_crashes["latitude"]),
        crs="EPSG:4326"
    )
    return gpd.sjoin(gdf, nta[["ntaname", "geometry"]], how="left", predicate="within")


def assign_nta_subway(data_subway: pd.DataFrame, nta: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Assign ntaname to subway stations via lat/lon spatial join."""
    gdf = gpd.GeoDataFrame(
        data_subway,
        geometry=gpd.points_from_xy(data_subway["longitude"], data_subway["latitude"]),
        crs="EPSG:4326"
    )
    return gpd.sjoin(gdf, nta[["ntaname", "geometry"]], how="left", predicate="within")


def assign_nta_traffic(data_traffic: pd.DataFrame, nta: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Assign ntaname to traffic sensors via WKT geometry.
    Traffic data uses NYC local CRS (EPSG:2263) — converted to WGS84 before join.
    """
    data_traffic = data_traffic.copy()
    data_traffic["geometry"] = data_traffic["wktgeom"].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(data_traffic, geometry="geometry", crs="EPSG:2263")
    gdf = gdf.to_crs("EPSG:4326")
    return gpd.sjoin(gdf, nta[["ntaname", "geometry"]], how="left", predicate="within")


def assign_nta_pedestrian(data_pedestrian: pd.DataFrame, nta: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Assign ntaname to pedestrian count locations via WKT geometry."""
    data_pedestrian = data_pedestrian.copy()
    data_pedestrian["geometry"] = data_pedestrian["the_geom"].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(data_pedestrian, geometry="geometry", crs="EPSG:4326")
    return gpd.sjoin(gdf, nta[["ntaname", "geometry"]], how="left", predicate="within")

def get_nta_centroids(nta: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Compute centroid lat/lon for each NTA.
    Used to pull one weather forecast per neighborhood.

    Returns DataFrame with columns: [ntaname, latitude, longitude]
    """
    nta_proj = nta.to_crs(epsg=3857)  # project for accurate centroid
    centroids = nta_proj.copy()
    centroids["geometry"] = centroids.centroid
    centroids = centroids.to_crs(epsg=4326)

    return pd.DataFrame({
        "ntaname":   centroids["ntaname"],
        "latitude":  centroids.geometry.y,
        "longitude": centroids.geometry.x
    }).reset_index(drop=True)


def attach_nta_centroids(
    df: pd.DataFrame,
    geojson_path: str = NTA_FILE
) -> pd.DataFrame:
    """Merge NTA centroid lat/lon onto a dataframe keyed by ntaname."""
    out = df.copy()
    has_coords = (
        "latitude" in out.columns
        and "longitude" in out.columns
        and out["latitude"].notna().all()
        and out["longitude"].notna().all()
    )
    if has_coords:
        return out

    centroids = get_nta_centroids(load_nta(geojson_path))
    out = out.drop(columns=[c for c in ("latitude", "longitude") if c in out.columns])
    return out.merge(centroids, on="ntaname", how="left")

def run_spatial_joins(
    data_311: pd.DataFrame,
    data_crime: pd.DataFrame,
    data_crashes: pd.DataFrame,
    data_subway: pd.DataFrame,
    data_traffic: pd.DataFrame,
    data_pedestrian: pd.DataFrame,
    nta: gpd.GeoDataFrame
) -> dict:
    """
    Run all spatial joins in one call.
    Returns dict of GeoDataFrames with ntaname assigned.
    """
    print("Assigning NTAs to 311...")
    gdf_311 = assign_nta_311(data_311, nta)

    print("Assigning NTAs to crime...")
    gdf_crime = assign_nta_crime(data_crime, nta)

    print("Assigning NTAs to crashes...")
    gdf_crashes = assign_nta_crashes(data_crashes, nta)

    print("Assigning NTAs to subway...")
    gdf_subway = assign_nta_subway(data_subway, nta)

    print("Assigning NTAs to traffic...")
    gdf_traffic = assign_nta_traffic(data_traffic, nta)

    print("Assigning NTAs to pedestrian...")
    gdf_pedestrian = assign_nta_pedestrian(data_pedestrian, nta)

    return {
        "gdf_311":        gdf_311,
        "gdf_crime":      gdf_crime,
        "gdf_crashes":    gdf_crashes,
        "gdf_subway":     gdf_subway,
        "gdf_traffic":    gdf_traffic,
        "gdf_pedestrian": gdf_pedestrian
    }
