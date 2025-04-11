import streamlit as st
import geopandas as gpd
import folium
import zipfile
import os
import tempfile
from streamlit_folium import st_folium
import subprocess

st.set_page_config(layout="wide")
st.title("🧪 Testomgeving Peilimpact")

col1, col2 = st.columns([1, 2])

# Initialiseer session_state
if 'gdf' not in st.session_state:
    st.session_state['gdf'] = None
    st.session_state['zoom'] = False

with col1:
    st.header("📥 Invoer")

    shape_file = st.file_uploader("Upload shapefile (.zip)", type="zip")
    pdf_file = st.file_uploader("Upload PDF-bestand", type="pdf")

    show_shape = st.button("Show shape")
    zoom_to_shape = st.button("Zoom to shape")
    convert_pdf = st.button("Convert PDF")

    if show_shape:
        st.info("🔄 Show shape knop ingedrukt.")

        if shape_file is None:
            st.warning("⚠️ Geen shapefile geüpload.")
        else:
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    zip_path = os.path.join(tmpdir, "shape.zip")
                    with open(zip_path, "wb") as f:
                        f.write(shape_file.read())

                    with zipfile.ZipFile(zip_path, "r") as zip_ref:
                        zip_ref.extractall(tmpdir)
                        all_files = zip_ref.namelist()
                        st.markdown("📂 **Inhoud van ZIP-bestand:**")
                        st.code("\n".join(all_files))

                        # Zoek shapefiles
                        shp_files = [os.path.join(tmpdir, f) for f in all_files if f.endswith(".shp")]


                    if not shp_files:
                        st.error("❌ Geen .shp bestand gevonden in de zip.")
                    else:
                        gdf = gpd.read_file(shp_files[0])
                        gdf = gdf.to_crs(epsg=4326)  # Converteer naar WGS84
                        if gdf.empty:
                            st.error("❌ De shapefile bevat geen geometrieën.")
                        elif gdf.crs is None:
                            st.error("❌ Geen CRS in de shapefile.")
                        elif not gdf.is_valid.all():
                            st.warning("⚠️ Sommige geometrieën zijn ongeldig.")
                        else:
                            st.session_state['gdf'] = gdf
                            st.session_state['zoom'] = False
                            st.success("✅ Shapefile succesvol geladen.")

            except Exception as e:
                st.error(f"❌ Fout bij inlezen shapefile: {e}")

    if zoom_to_shape:
        st.session_state['zoom'] = True
        st.info("🔍 Zoom to shape knop ingedrukt.")

    if convert_pdf:
        if pdf_file is None:
            st.warning("⚠️ Geen PDF geüpload.")
        else:
            st.success("✅ PDF ontvangen. (actie volgt nog)")


    st.header("🔧 MODFLOW 6 Test")

    modflow_zip = st.file_uploader("Upload MODFLOW 6 model (.zip)", type="zip", key="mf6zip")
    run_modflow = st.button("Run MODFLOW 6")

    if run_modflow:
        if modflow_zip is None:
            st.warning("⚠️ Geen modelbestand geüpload.")
        else:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Sla zip op en pak uit
                zip_path = os.path.join(tmpdir, "modflow_model.zip")
                with open(zip_path, "wb") as f:
                    f.write(modflow_zip.read())

                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(tmpdir)

                # Zoek naar .nam bestand
                nam_file = None
                for root, dirs, files in os.walk(tmpdir):
                    for file in files:
                        if file.endswith(".nam"):
                            nam_file = os.path.join(root, file)
                            break

                if nam_file is None:
                    st.error("❌ Geen .nam bestand gevonden in de zip.")
                else:
                    model_dir = os.path.dirname(nam_file)
                    st.info(f"📄 .nam gevonden: `{os.path.basename(nam_file)}`")

                    # Pad naar mf6.exe – PAS DIT AAN indien nodig!
                    mf6_path = "mf6.exe"  # of volledig pad

                    try:
                        result = subprocess.run(
                            [mf6_path, os.path.basename(nam_file)],
                            cwd=model_dir,
                            capture_output=True,
                            text=True,
                            timeout=300  # max 5 min run
                        )
                        st.success("✅ Simulatie uitgevoerd.")
                        st.text("🔧 stdout:")
                        st.code(result.stdout)

                        lst_file = None
                        for file in os.listdir(model_dir):
                            if file.endswith(".lst"):
                                lst_file = os.path.join(model_dir, file)
                                break

                        if lst_file:
                            with open(lst_file, "rb") as f:
                                st.download_button(
                                    label="📥 Download .lst bestand",
                                    data=f,
                                    file_name=os.path.basename(lst_file),
                                    mime="text/plain"
                                )
                        else:
                            st.warning("⚠️ Geen .lst bestand gevonden na simulatie.")

                        if result.stderr:
                            st.text("⚠️ stderr:")
                            st.code(result.stderr)
                    except Exception as e:
                        st.error(f"❌ Fout bij uitvoeren van mf6.exe: {e}")

with col2:
    st.header("🗺️ Kaart")

    gdf = st.session_state['gdf']
    zoom = st.session_state['zoom']

    # Standaard locatie
    map_center = [51.0, 4.0]
    zoom_start = 10

    # Als er een shapefile is en zoom gevraagd wordt
    if gdf is not None and zoom:
        bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
        centroid = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]  # [lat, lon]
        map_center = centroid
        zoom_start = 14  # pas aan indien nodig

    m = folium.Map(location=map_center, zoom_start=zoom_start)

    # Voeg WMS toe
    folium.raster_layers.WmsTileLayer(
        url="https://geo.api.vlaanderen.be/GRB-basiskaart-grijs/wms",
        name="GRB basiskaart grijs",
        fmt="image/png",
        layers="GRB_BSK_GR",
        transparent=True,
        version="1.3.0",
        attr="© AGIV"
    ).add_to(m)

    gdf = st.session_state['gdf']
    if gdf is not None:
        folium.GeoJson(gdf).add_to(m)

        if st.session_state.get('zoom', False):
            bounds = gdf.total_bounds
            m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

    st_folium(m, width=800, height=600)

    if gdf is not None:
        st.markdown("### 🛈 Info")
        st.write(f"📄 Bestand: `{shape_file.name}`")
        st.write(f"📌 Aantal features: {len(gdf)}")
        st.write(f"🌐 CRS: {gdf.crs}")
