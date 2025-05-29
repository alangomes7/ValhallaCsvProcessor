#!/bin/bash

TILE_DIR="./valhalla_tiles"
OSM_DIR="./osm"
CONFIG="./valhalla.json"

mkdir -p "$TILE_DIR"

if [ -f "$TILE_DIR/tiles.tar" ]; then
  echo "[INFO] tiles.tar already exists. Skipping tile build."
  exit 0
fi

docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "$(pwd)/$OSM_DIR:/custom_files" \
  -v "$(pwd)/$TILE_DIR:/data/valhalla" \
  -v "$(pwd)/valhalla.json:/valhalla/valhalla.json" \
  ghcr.io/gis-ops/docker-valhalla/valhalla:latest \
  valhalla_build_tiles -c /valhalla/valhalla.json /custom_files/*.osm.pbf

docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "$(pwd)/$TILE_DIR:/data/valhalla" \
  -v "$(pwd)/valhalla.json:/valhalla/valhalla.json" \
  ghcr.io/gis-ops/docker-valhalla/valhalla:latest \
  valhalla_build_extract -c /valhalla/valhalla.json -v
