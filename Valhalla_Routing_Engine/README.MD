---

# 🚗 Valhalla Routing Engine Setup

This project sets up [Valhalla](https://github.com/valhalla/valhalla), an open-source routing engine, using Docker. It includes scripts and configuration for:

* Building Valhalla tiles from OpenStreetMap `.osm.pbf` files.
* Running a Valhalla server using Docker Compose.

---

## 📁 Project Structure

```bash
.
├── osm/                    # Directory for input .osm.pbf files
├── valhalla_tiles/         # Output directory for generated Valhalla tiles
├── valhalla.json           # Valhalla configuration file
├── build_tiles.sh          # Bash script to generate tiles and extract data
├── docker-compose.yml      # Docker Compose setup to run Valhalla server
```

---

## ⚙️ Requirements

* [Docker](https://docs.docker.com/get-docker/)
* [Docker Compose](https://docs.docker.com/compose/install/)
* One or more `.osm.pbf` files inside the `osm/` directory.

---

## 🚀 Getting Started

### 1. Place OSM Data

Place your `.osm.pbf` files into the `osm/` directory. Example:

```bash
./osm/brazil-latest.osm.pbf
```

### 2. Configure Valhalla

Ensure your `valhalla.json` configuration file is present in the root directory. You can use [Valhalla’s config generator](https://github.com/valhalla/valhalla/blob/master/valhalla.json) or adjust as needed.

### 3. Build Valhalla Tiles

Run the tile-building script:

```bash
chmod +x build_tiles.sh
./build_tiles.sh
```

* This will generate tiles into the `valhalla_tiles/` folder.
* If `tiles.tar` already exists, the script will skip reprocessing.

### 4. Start the Valhalla Server

```bash
docker-compose up -d
```

Valhalla will be available on:
📡 **[http://localhost:8002](http://localhost:8002)**

---

## 🧪 Test Your Setup

You can test if the server is running using:

```bash
curl http://localhost:8002/route
```

Or, using the [Valhalla API docs](https://valhalla.readthedocs.io/en/latest/api/overview/).

---

## 🧼 Stopping & Cleanup

To stop the container:

```bash
docker-compose down
```

To remove built tiles:

```bash
rm -rf valhalla_tiles/*
```

---

## 📝 Notes

* `build_tiles.sh` uses `valhalla_build_tiles` and `valhalla_build_extract` from the Docker container.
* If you add new `.osm.pbf` files or modify the config, re-run the script.
* Valhalla automatically uses multithreading to speed up tile building.

---

## 📄 License

This setup uses the open-source [Valhalla](https://github.com/valhalla/valhalla) project, licensed under the MIT License.

---
