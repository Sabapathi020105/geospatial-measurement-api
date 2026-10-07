"""Generate sample geospatial files (KML and Shapefile .zip) for testing and evaluation."""

import os
import zipfile
from pathlib import Path
import fiona
from fiona.crs import from_epsg
from shapely.geometry import Polygon, LineString, Point, mapping

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)


def create_sample_kmls():
    # 1. Polygons KML (e.g. Campus parcels in San Francisco: lon ~ -122.4, lat ~ 37.7)
    kml_polygons = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Urban Parcels</name>
    <Placemark id="parcel_01">
      <name>North Quad</name>
      <description>Green lawn and park area</description>
      <ExtendedData>
        <Data name="zone"><value>Commercial-A</value></Data>
        <Data name="tax_id"><value>9042</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -122.4194,37.7749,0
              -122.4184,37.7749,0
              -122.4184,37.7759,0
              -122.4194,37.7759,0
              -122.4194,37.7749,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark id="parcel_02">
      <name>South Plaza</name>
      <description>Paved square area</description>
      <ExtendedData>
        <Data name="zone"><value>Public-B</value></Data>
        <Data name="tax_id"><value>9043</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -122.4200,37.7730,0
              -122.4170,37.7730,0
              -122.4170,37.7745,0
              -122.4200,37.7745,0
              -122.4200,37.7730,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
"""
    with open(SAMPLE_DIR / "sample_polygons.kml", "w", encoding="utf-8") as f:
        f.write(kml_polygons)

    # 2. LineStrings KML (e.g. Roads)
    kml_lines = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>City Transit Routes</name>
    <Placemark id="route_101">
      <name>Market Street Main Corridor</name>
      <description>Primary arterial line</description>
      <ExtendedData>
        <Data name="route_type"><value>Bus</value></Data>
        <Data name="frequency_mins"><value>10</value></Data>
      </ExtendedData>
      <LineString>
        <coordinates>
          -122.4194,37.7749,0
          -122.4150,37.7780,0
          -122.4100,37.7810,0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark id="route_102">
      <name>Mission Spur</name>
      <description>Secondary feeder line</description>
      <LineString>
        <coordinates>
          -122.4194,37.7749,0
          -122.4194,37.7710,0
          -122.4160,37.7680,0
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""
    with open(SAMPLE_DIR / "sample_linestrings.kml", "w", encoding="utf-8") as f:
        f.write(kml_lines)

    # 3. Points KML (Stations/Landmarks - measurement not applicable)
    kml_points = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Weather Monitoring Stations</name>
    <Placemark id="station_alpha">
      <name>Station Alpha</name>
      <Point>
        <coordinates>-122.4194,37.7749,15</coordinates>
      </Point>
    </Placemark>
    <Placemark id="station_beta">
      <name>Station Beta</name>
      <Point>
        <coordinates>-122.4150,37.7780,18</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""
    with open(SAMPLE_DIR / "sample_points.kml", "w", encoding="utf-8") as f:
        f.write(kml_points)

    # 4. Mixed Geometries KML (Polygons + LineStrings + Points)
    kml_mixed = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>City Survey Comprehensive</name>
    <Placemark id="feat_poly">
      <name>Reservoir Area</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -122.450,37.750,0
              -122.440,37.750,0
              -122.440,37.760,0
              -122.450,37.760,0
              -122.450,37.750,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark id="feat_line">
      <name>Aqueduct Line</name>
      <LineString>
        <coordinates>
          -122.450,37.755,0
          -122.430,37.755,0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark id="feat_pt">
      <name>Pumping Station</name>
      <Point>
        <coordinates>-122.445,37.755,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""
    with open(SAMPLE_DIR / "sample_mixed.kml", "w", encoding="utf-8") as f:
        f.write(kml_mixed)


def create_sample_shapefiles():
    temp_shp_dir = SAMPLE_DIR / "_temp_shp"
    temp_shp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Polygon shapefile in EPSG:4326 (Parcels)
    schema_poly = {
        "geometry": "Polygon",
        "properties": {"name": "str:50", "zone": "str:20", "lot_num": "int"},
    }
    poly_shp_path = temp_shp_dir / "parcels.shp"
    crs_4326 = from_epsg(4326)

    polys = [
        (
            Polygon([(-122.4194, 37.7749), (-122.4184, 37.7749), (-122.4184, 37.7759), (-122.4194, 37.7759), (-122.4194, 37.7749)]),
            {"name": "Building Block 1", "zone": "R-1", "lot_num": 101},
        ),
        (
            Polygon([(-122.4170, 37.7740), (-122.4150, 37.7740), (-122.4150, 37.7760), (-122.4170, 37.7760), (-122.4170, 37.7740)]),
            {"name": "Commercial Block 2", "zone": "C-2", "lot_num": 102},
        ),
    ]

    with fiona.open(str(poly_shp_path), "w", driver="ESRI Shapefile", crs=crs_4326, schema=schema_poly) as layer:
        for geom, props in polys:
            layer.write({"geometry": mapping(geom), "properties": props})

    # Zip the shapefile (.shp, .shx, .dbf, .cpg, .prj)
    poly_zip = SAMPLE_DIR / "sample_parcels_shp.zip"
    with zipfile.ZipFile(poly_zip, "w") as zf:
        for f in temp_shp_dir.glob("parcels.*"):
            zf.write(f, arcname=f.name)

    # 2. LineString shapefile in EPSG:4326 (Roads)
    schema_line = {
        "geometry": "LineString",
        "properties": {"road_name": "str:50", "lanes": "int", "speed_kph": "int"},
    }
    line_shp_path = temp_shp_dir / "roads.shp"
    lines = [
        (
            LineString([(-122.4200, 37.7700), (-122.4150, 37.7750), (-122.4100, 37.7800)]),
            {"road_name": "Sunset Highway", "lanes": 4, "speed_kph": 80},
        ),
        (
            LineString([(-122.4150, 37.7750), (-122.4050, 37.7750)]),
            {"road_name": "Central Cross", "lanes": 2, "speed_kph": 50},
        ),
    ]

    with fiona.open(str(line_shp_path), "w", driver="ESRI Shapefile", crs=crs_4326, schema=schema_line) as layer:
        for geom, props in lines:
            layer.write({"geometry": mapping(geom), "properties": props})

    line_zip = SAMPLE_DIR / "sample_roads_shp.zip"
    with zipfile.ZipFile(line_zip, "w") as zf:
        for f in temp_shp_dir.glob("roads.*"):
            zf.write(f, arcname=f.name)

    # 3. Create an invalid zip (missing .shp)
    invalid_zip = SAMPLE_DIR / "sample_invalid_no_shp.zip"
    with zipfile.ZipFile(invalid_zip, "w") as zf:
        zf.writestr("readme.txt", "This zip has no shapefile")

    # Clean up temp files
    for f in temp_shp_dir.iterdir():
        f.unlink()
    temp_shp_dir.rmdir()


if __name__ == "__main__":
    create_sample_kmls()
    create_sample_shapefiles()
    print("Sample datasets successfully generated in:", SAMPLE_DIR)
