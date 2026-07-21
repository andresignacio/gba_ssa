import streamlit as st
import geopandas as gpd
import pydeck as pdk
import json
import urllib.parse

st.set_page_config(layout="wide", page_title="Morphological Foresighting Digital Twin")

st.title("🌊 Morphological Foresighting Digital Twin")
st.markdown("Visualizing irreversible 'Lost Stock' displacement across the Philippine archipelago.")

with st.expander("📖 How to read this map", expanded=True):
    st.markdown("""
    **Analysis Modes:** Use the toggle in the sidebar to physically decouple the data.
    
    🏠 **Shelter Loss Mode (Yellow ➔ Red):** 
    *   **Height:** Total Exposed Buildings (sheer volume of the neighborhood).
    *   **Color:** % of structures that are destroyed **<120sqm housing**. 
    *   🟨 *Yellow:* Lower displacement risk. 
    *   🟥 *Red:* Severe Displacement Zone (total wipeout of vulnerable housing).
    
    🏭 **Economic Disruption Mode (White ➔ Deep Blue):** 
    *   **Height:** Number of destroyed **>500sqm commercial facilities**.
    *   **Color:** Concentration of commercial loss.
    *   ⬜ *White/Light Blue:* Isolated loss of a single commercial node.
    *   🟦 *Deep Blue:* Severe Economic Wipeout (multiple massive facilities destroyed).
    """)

@st.cache_data
def load_data(resolution):
    try:
        file_path = f"hex_analytics_morph_{resolution}.parquet"
        gdf = gpd.read_parquet(file_path)
        if gdf.crs is None or gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        return gdf
    except Exception as e:
        st.error(f"Error loading {file_path}. Make sure you ran the export script.")
        return None

@st.cache_data
def load_context_layer(file_path):
    try:
        gdf = gpd.read_parquet(file_path)
        if gdf.crs is None or gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        return gdf
    except Exception as e:
        return None

def get_basemap_config(choice):
    if choice == "Dark Mode (Carto)":
        return "carto", "dark"
    elif choice == "OpenStreetMap":
        style = {
            "version": 8,
            "sources": {
                "osm": {
                    "type": "raster",
                    "tiles": ["https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"],
                    "tileSize": 256,
                    "attribution": "© OpenStreetMap Contributors"
                }
            },
            "layers": [{"id": "osm-tiles", "type": "raster", "source": "osm", "minzoom": 0, "maxzoom": 19}]
        }
        uri = "data:application/json;charset=utf-8," + urllib.parse.quote(json.dumps(style))
        return "mapbox", uri
    elif choice == "Satellite (Esri Free)":
        style = {
            "version": 8,
            "sources": {
                "esri": {
                    "type": "raster",
                    "tiles": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
                    "tileSize": 256,
                    "attribution": "Tiles © Esri"
                }
            },
            "layers": [{"id": "esri-tiles", "type": "raster", "source": "esri", "minzoom": 0, "maxzoom": 19}]
        }
        uri = "data:application/json;charset=utf-8," + urllib.parse.quote(json.dumps(style))
        return "mapbox", uri

st.sidebar.header("Map Controls")

basemap_choice = st.sidebar.selectbox(
    "Basemap Style", 
    ["OpenStreetMap", "Satellite (Esri Free)", "Dark Mode (Carto)"],
    index=1) 

res_choice = st.sidebar.radio("Spatial Resolution", ["500m (National)", "250m (Local)"])
res_val = "500m" if "500m" in res_choice else "250m"

gdf = load_data(res_val)
map_layers = []

if gdf is not None:
    st.sidebar.subheader("Risk Filters")
    
    analysis_mode = st.sidebar.radio(
        "Analysis Mode (Decoupling)", 
        ["🏠 Shelter Loss (Residential)", "🏭 Economic Disruption (Commercial)"]
    )
    
    min_bldgs = st.sidebar.slider(
        "Minimum Exposed Buildings (Base Filter)", 
        min_value=0, 
        max_value=int(gdf['total_exposed_buildings'].max()), 
        value=50
    )
    
    # DYNAMIC VARIABLES BASED ON MODE
    if "Shelter" in analysis_mode:
        min_residential_loss = st.sidebar.slider(
            "Minimum Residential Loss (%)", 
            min_value=0, 
            max_value=100, 
            value=10
        )
        
        filtered_gdf = gdf[
            (gdf['total_exposed_buildings'] >= min_bldgs) & 
            (gdf['pct_lost_residential'] >= min_residential_loss)
        ].copy()
        
        filtered_gdf['fill_color'] = filtered_gdf['pct_lost_residential'].apply(
            lambda x: [255, max(0, int(255 - (x * 2.5))), 0, 200]
        )
        
        st.sidebar.markdown(f"**Showing {len(filtered_gdf):,} Displacement Hotspots**")
        
        elevation_metric = "total_exposed_buildings"
        elevation_multiplier = 10
        dynamic_tooltip = "<b>Total Exposed Buildings:</b> {total_exposed_buildings} <br/> <b>Lost Residential (<120sqm):</b> {lost_residential} units <br/><b>Residential Loss Rate:</b> {pct_lost_residential}%"
        
    else:
        max_commercial_val = int(gdf['lost_commercial'].max()) if not gdf.empty else 10
        min_commercial = st.sidebar.slider(
            "Minimum Lost Commercial Nodes (>500sqm)", 
            min_value=1, 
            max_value=max_commercial_val, 
            value=1
        )
        
        filtered_gdf = gdf[
            (gdf['total_exposed_buildings'] >= min_bldgs) & 
            (gdf['lost_commercial'] >= min_commercial)
        ].copy()
        
        max_c = filtered_gdf['lost_commercial'].max() if not filtered_gdf.empty and filtered_gdf['lost_commercial'].max() > 0 else 1
        filtered_gdf['fill_color'] = filtered_gdf['lost_commercial'].apply(
            lambda x: [int(255 - (x/max_c)*255), int(255 - (x/max_c)*255), 255, 200] 
        )
        
        st.sidebar.markdown(f"**Showing {len(filtered_gdf):,} Economic Hotspots**")
        
        # In Commercial Mode, height is purely the number of destroyed factories/warehouses
        # We increase the multiplier to 100 so small numbers (1 to 5) still stand out visually
        elevation_metric = "lost_commercial"
        elevation_multiplier = 100 
        dynamic_tooltip = "<b>Lost Commercial Nodes (>500sqm):</b> {lost_commercial} <br/> <i>(Total neighborhood exposure: {total_exposed_buildings} buildings)</i>"

    st.sidebar.markdown("---")
    st.sidebar.subheader("Context Layers")
    
    enable_3d_terrain = st.sidebar.checkbox("⛰️ Enable 3D Terrain (DTM)", value=False)
    
    if enable_3d_terrain:
        terrain_exaggeration = st.sidebar.slider("Terrain Exaggeration (Vertical)", min_value=1.0, max_value=3.0, value=1.5, step=0.1)
        enable_terrain_shading = st.sidebar.checkbox("☀️ Enable Artificial 3D Shading", value=False)
        
        if enable_terrain_shading:
            terrain_material = {"ambient": 0.6, "diffuse": 1.2, "shininess": 0, "specularColor": [0, 0, 0]}
        else:
            terrain_material = {"ambient": 1.0, "diffuse": 0.0, "shininess": 0, "specularColor": [0, 0, 0]}
    else:
        terrain_exaggeration = 1.0
        enable_terrain_shading = False
        terrain_material = False
    
    show_ssa = st.sidebar.checkbox("Show SSA4 Hazard Zones", value=False)
    
    hazard_transparency = st.sidebar.slider("Hazard Transparency (%)", min_value=0, max_value=100, value=40) if show_ssa else 100
    alpha_val = int(((100 - hazard_transparency) / 100) * 255)

    hex_layer = pdk.Layer(
        "GeoJsonLayer",
        data=filtered_gdf,
        pickable=True,
        stroked=False,
        filled=True,
        extruded=True,
        wireframe=True,
        get_elevation=elevation_metric,
        elevation_scale=elevation_multiplier, 
        get_fill_color="fill_color", 
    )

    map_layers.append(hex_layer)

    if enable_3d_terrain:
        TERRAIN_IMAGE = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
        ELEVATION_DECODER = {
            "rScaler": 256 * terrain_exaggeration, 
            "gScaler": 1 * terrain_exaggeration, 
            "bScaler": (1 / 256) * terrain_exaggeration, 
            "offset": -32768 * terrain_exaggeration
        }
        SURFACE_IMAGE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        
        terrain_layer = pdk.Layer(
            "TerrainLayer",
            data=None,  
            elevation_decoder=ELEVATION_DECODER,
            texture=SURFACE_IMAGE,
            elevation_data=TERRAIN_IMAGE,
            material=terrain_material
        )
        map_layers.insert(0, terrain_layer)

    if not filtered_gdf.empty:
        minx, miny, maxx, maxy = filtered_gdf.total_bounds
    else:
        minx, miny, maxx, maxy = 0, 0, 0, 0 

    if show_ssa:
        with st.spinner("Loading Hazard Geometries..."):
            ssa_gdf = load_context_layer("ssa_data_subd.parquet")
            
            if ssa_gdf is not None:
                local_ssa = ssa_gdf.cx[minx:maxx, miny:maxy].copy()
                
                if not local_ssa.empty:
                    st.sidebar.markdown("**Hazard Levels:**")
                    st.sidebar.markdown("🔴 **Level 3** (> 1.5m Inundation)", unsafe_allow_html=True)
                    
                    ssa_layer = pdk.Layer(
                        "GeoJsonLayer",
                        data=local_ssa, 
                        pickable=False,
                        stroked=False,
                        filled=True,
                        extruded=False,  
                        get_fill_color=f"[228, 26, 28, {alpha_val}]",
                        parameters={"depthTest": False} 
                    )
                    
                    if enable_3d_terrain:
                        map_layers.insert(1, ssa_layer)
                    else:
                        map_layers.insert(0, ssa_layer)

    view_state = pdk.ViewState(
        longitude=121.7740, 
        latitude=12.8797,
        zoom=5,
        pitch=45, 
        bearing=0
    )

    provider, style_uri = get_basemap_config(basemap_choice)

    r = pdk.Deck(
        layers=map_layers,
        initial_view_state=view_state,
        map_style=style_uri,
        map_provider=provider,
        tooltip={"html": dynamic_tooltip}
    )

    st.pydeck_chart(r)

    st.subheader("Aggregate Statistics (Displacement Hotspots)")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Hotspot Hexagons", f"{len(filtered_gdf):,}")
    
    total_exposed = int(filtered_gdf['total_exposed_buildings'].sum()) if not filtered_gdf.empty else 0
    total_res = int(filtered_gdf['lost_residential'].sum()) if not filtered_gdf.empty else 0
    total_com = int(filtered_gdf['lost_commercial'].sum()) if not filtered_gdf.empty else 0
    
    col2.metric("Total Exposed", f"{total_exposed:,}")
    col3.metric("Lost Residential (<120sqm)", f"{total_res:,}")
    col4.metric("Lost Commercial (>500sqm)", f"{total_com:,}")