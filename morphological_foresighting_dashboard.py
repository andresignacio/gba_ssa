import streamlit as st
import geopandas as gpd
import pydeck as pdk
import json
import urllib.parse
import pandas as pd

st.set_page_config(layout="wide", page_title="Philippine Coastal Vulnerability")

st.sidebar.markdown("### 🎛️ Dashboard Controls")

exp_analysis = st.sidebar.expander("🎯 Primary Analysis", expanded=True)
with exp_analysis:
    analysis_mode = st.radio("Analysis Mode", ["🏠 Shelter Loss (Residential)", "🏭 Economic Disruption (Commercial)"], label_visibility="collapsed")
    is_economic_mode = "Economic" in analysis_mode
    
    st.markdown("<hr style='margin: 0.5rem 0; border-color: #334155;'/>", unsafe_allow_html=True)
    
    res_choice = st.radio("Spatial Resolution", ["500m (National)", "250m (Local)"])
    res_val = "500m" if "500m" in res_choice else "250m"

exp_hazard = st.sidebar.expander("🌊 Hazard Overlay", expanded=True)
with exp_hazard:
    show_ssa = st.checkbox("Show SSA4 Hazard Zones (Level 3+)", value=False)
    hazard_opacity = st.slider("Hazard Opacity (%)", min_value=0, max_value=100, value=60) if show_ssa else 0
    alpha_val = int((hazard_opacity / 100) * 255)

exp_thresholds = st.sidebar.expander("🎚️ Risk Thresholds", expanded=True)

exp_map = st.sidebar.expander("🗺️ Map Settings", expanded=False)
with exp_map:
    basemap_choice = st.selectbox("Basemap Style", ["OpenStreetMap", "Satellite (Esri Free)", "Dark Mode (Carto)"], index=1)
    
    st.markdown("<hr style='margin: 0.5rem 0; border-color: #334155;'/>", unsafe_allow_html=True)
    
    enable_3d_terrain = st.checkbox("⛰️ Enable 3D Terrain (DTM)", value=False)
    if enable_3d_terrain:
        terrain_exaggeration = st.slider("Terrain Exaggeration", min_value=1.0, max_value=3.0, value=1.5, step=0.1)
        enable_terrain_shading = st.checkbox("☀️ 3D Shading", value=False)
        
    st.markdown("<hr style='margin: 0.5rem 0; border-color: #334155;'/>", unsafe_allow_html=True)
    map_height = st.slider("Map Canvas Height (px)", min_value=500, max_value=1200, value=700, step=50)

st.markdown(f"""
    <style>
        .block-container {{ padding-top: 1rem !important; padding-bottom: 1rem !important; max-width: 95% !important; }}
        h1 {{ font-size: 1.8rem !important; margin-bottom: 0 !important; padding-bottom: 0 !important; }}
        .subtitle {{ color: #64748b; font-size: 1rem; margin-top: 0; margin-bottom: 1rem; }}
        [data-testid="stDeckGlJsonChart"] {{ height: {map_height}px !important; }}
        [data-testid="stDeckGlJsonChart"] iframe {{ height: {map_height}px !important; }}
        [data-testid="stSidebar"] .streamlit-expanderHeader {{ padding-top: 0.5rem; padding-bottom: 0.5rem; font-weight: 600; }}
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1>🌊 Morphological Foresighting Digital Twin</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtitle'>A Scenario-Based Exposure & 'Lost Stock' Analytics Platform.</p>", unsafe_allow_html=True)

@st.cache_data
def load_data(resolution):
    try:
        file_path = f"hex_analytics_morph_{resolution}.parquet"
        gdf = gpd.read_parquet(file_path)
        if gdf.crs is None or gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        return gdf
    except Exception as e:
        st.error(f"Error loading {file_path}. Make sure it is in the same folder as this script.")
        return None

@st.cache_data
def load_hazard_geojson(file_path):
    try:
        gdf = gpd.read_parquet(file_path)
        if gdf.crs is None or gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
            
        if 'haz' in gdf.columns:
            gdf['haz'] = gdf['haz'].astype(float)
        elif 'ssa_level' in gdf.columns:
            gdf['ssa_level'] = gdf['ssa_level'].astype(float)
            
        # Returning the dictionary representation prevents expensive re-serialization on every render
        return gdf.__geo_interface__
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

gdf = load_data(res_val)
map_layers = []

if gdf is not None:
    with exp_thresholds:
        max_exp = int(gdf['total_exposed_buildings'].max()) if not gdf.empty else 100
        min_bldgs = st.slider("Minimum Exposed Buildings", min_value=0, max_value=max_exp, value=50)
        
        if is_economic_mode:
            st.markdown("""
                <div style="background-color: #0f172a; color: #ffffff; padding: 12px; border-radius: 6px; border: 1px solid #3b82f6; font-size: 14px; line-height: 1.4; margin-bottom: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                    🟦 <b>Economic Mode:</b> Showing Commercial Nodes (>500sqm) facing total operational loss.
                </div>
            """, unsafe_allow_html=True)
            
            max_com = int(gdf['lost_commercial'].max()) if not gdf.empty else 10
            min_loss = st.slider("Minimum Lost Commercial Nodes", min_value=0, max_value=max_com, value=1)
            
            filtered_gdf = gdf[
                (gdf['total_exposed_buildings'] >= min_bldgs) & 
                (gdf['lost_commercial'] >= min_loss)
            ].copy()
            
            filtered_gdf['render_height'] = filtered_gdf['lost_commercial'] * 50
            filtered_gdf['fill_color'] = filtered_gdf['lost_commercial'].apply(lambda x: [30, 136, 229, 220])
            dynamic_tooltip = "<b>Lost Commercial Nodes:</b> {lost_commercial} facilities"
            keep_cols = ['geometry', 'lost_commercial', 'render_height', 'fill_color']
        else:
            st.markdown("""
                <div style="background-color: #450a0a; color: #ffffff; padding: 12px; border-radius: 6px; border: 1px solid #ef4444; font-size: 14px; line-height: 1.4; margin-bottom: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                    🟥 <b>Shelter Mode:</b> Showing Vulnerable Residential structures (<120sqm) facing total structural failure.
                </div>
            """, unsafe_allow_html=True)
            
            min_loss = st.slider("Minimum Residential Loss (%)", min_value=0, max_value=100, value=10)
            
            filtered_gdf = gdf[
                (gdf['total_exposed_buildings'] >= min_bldgs) & 
                (gdf['pct_lost_residential'] >= min_loss)
            ].copy()
            
            filtered_gdf['render_height'] = filtered_gdf['total_exposed_buildings']
            filtered_gdf['fill_color'] = filtered_gdf['pct_lost_residential'].apply(lambda x: [255, max(0, int(255 - (x * 2.5))), 0, 200])
            dynamic_tooltip = "<b>Total Exposed Buildings:</b> {total_exposed_buildings} <br/> <b>Lost Residential Stock:</b> {lost_residential} units <br/> <b>Residential Loss Rate:</b> {pct_lost_residential}%"
            keep_cols = ['geometry', 'total_exposed_buildings', 'lost_residential', 'pct_lost_residential', 'render_height', 'fill_color']
        
        st.markdown(f"**Showing {len(filtered_gdf):,} Hotspots**")
        
        # Subset the dataframe to drastically reduce the payload sent to the JS rendering engine
        keep_cols = [c for c in keep_cols if c in filtered_gdf.columns]
        render_gdf = filtered_gdf[keep_cols]

    if enable_3d_terrain:
        TERRAIN_IMAGE = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
        ELEVATION_DECODER = {
            "rScaler": 256 * terrain_exaggeration, 
            "gScaler": 1 * terrain_exaggeration, 
            "bScaler": (1 / 256) * terrain_exaggeration, 
            "offset": -32768 * terrain_exaggeration
        }
        SURFACE_IMAGE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        
        terrain_kwargs = {
            "elevation_decoder": ELEVATION_DECODER,
            "texture": SURFACE_IMAGE,
            "elevation_data": TERRAIN_IMAGE,
        }
        
        if enable_terrain_shading:
            terrain_kwargs["material"] = {
                "ambient": 0.6,
                "diffuse": 1.2,
                "shininess": 0,
                "specularColor": [0, 0, 0]
            }
        else:
            terrain_kwargs["material"] = {
                "ambient": 1.0,
                "diffuse": 0.0,
                "shininess": 0,
                "specularColor": [0, 0, 0]
            }
            
        terrain_layer = pdk.Layer("TerrainLayer", **terrain_kwargs)
        map_layers.insert(0, terrain_layer)

    hex_layer = pdk.Layer(
        "GeoJsonLayer",
        data=render_gdf,
        pickable=True,
        stroked=False,
        filled=True,
        extruded=True,
        wireframe=True,
        get_elevation="render_height",
        elevation_scale=10, 
        get_fill_color="fill_color",
        parameters={"depthTest": False} if enable_3d_terrain else {}
    )
    map_layers.append(hex_layer)

    if show_ssa:
        with st.spinner("Loading Hazard Geometries..."):
            ssa_geojson = load_hazard_geojson("ssa_data_subd.parquet")
            
            if ssa_geojson is not None:
                ssa_layer = pdk.Layer(
                    "GeoJsonLayer",
                    data=ssa_geojson, 
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
            else:
                with exp_hazard:
                    st.error("ssa_data_subd.parquet not found.")

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
        tooltip={"html": dynamic_tooltip},
        height=map_height
    )

    st.pydeck_chart(r, width='stretch')
    
    overflow_height = map_height - 500
    if overflow_height > 0:
        st.markdown(f"<div style='height: {overflow_height}px; width: 100%; pointer-events: none;'></div>", unsafe_allow_html=True)

    st.subheader("Aggregate Statistics (Displacement Hotspots)")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Hotspot Hexagons", f"{len(filtered_gdf):,}")
    
    total_exposed = int(filtered_gdf['total_exposed_buildings'].sum()) if not filtered_gdf.empty else 0
    total_res = int(filtered_gdf['lost_residential'].sum()) if 'lost_residential' in filtered_gdf.columns and not filtered_gdf.empty else 0
    total_com = int(filtered_gdf['lost_commercial'].sum()) if 'lost_commercial' in filtered_gdf.columns and not filtered_gdf.empty else 0
    
    col2.metric("Total Exposed", f"{total_exposed:,}")
    col3.metric("Lost Residential", f"{total_res:,}")
    col4.metric("Lost Commercial", f"{total_com:,}")
