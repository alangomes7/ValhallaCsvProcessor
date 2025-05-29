# 🛠️ Geographic Graph Tools Suite

Here we have **two powerful PyQt6 desktop applications** for working with geographic network data in CSV format:

1. **Graph Network Visualizer** – For visualizing geographic graph networks on interactive maps.
2. **Matrix Distance Filter Application** – For filtering and cleaning geographic distance matrices using advanced criteria.

* These scripts are for filter and generate the graph visualization from the generated file by Valhala Processor.
---

## 📍 1. Graph Network Visualizer

Visualize geographical graph networks from CSV files. This tool reads coordinates and distances and produces an interactive HTML map with nodes and weighted edges using **Folium**.

### ✨ Features

* **CSV Input**: Supports structured CSV with origin-destination points and distances.
* **Interactive Map**: HTML map generation using Folium.
* **Node & Edge Visualization**:

  * Nodes represent geographic locations.
  * Edges represent connections with distance-based thickness.
* **Popups & Highlights**:

  * Node popups with connection details.
  * Click to highlight edges to/from a node.
  * Hover to highlight edges.
* **Legend & Controls**:

  * Built-in legend.
  * "Show All" button to fit map to all nodes.
* **Progress & Logs**: GUI progress bar and real-time logs.
* **User-Friendly Interface**: Built with PyQt6 for easy file selection and operation.

### 🧰 Requirements

Install dependencies with:

```bash
pip install PyQt6 pandas folium
```

### 📂 Input Format

Your CSV should include (case-insensitive column headers):

* `Origin - name`
* `Origin - Latitude`
* `Origin - Longitude`
* `Destination - name`
* `Destination - Latitude`
* `Destination - Longitude`
* `Distance Drive (meters)`

**Example**:

```csv
"Origin - name","Origin - Latitude","Origin - Longitude","Destination - name","Destination - Latitude","Destination - Longitude","Distance Drive (meters)"
"Location A",34.0522,-118.2437,"Location B",34.0535,-118.2541,1200
"Location B",34.0535,-118.2541,"Location C",34.0689,-118.2325,2500
```

### 🚀 How to Run

1. **Save the UI File**: Save `graph_visualizer2.ui` in the same directory as your Python script.
2. **Run the App**:

```bash
python your_script_name.py
```

3. **Use the Interface**:

   * Click "Browse" to select your CSV file.
   * Click "Run Visualization".
   * After completion, an HTML map will be saved with a timestamped filename.

### ⚙️ How It Works

* **PyQt6** for GUI
* **pandas** for data handling
* **Folium** for map rendering
* **Multithreading** keeps UI responsive during map generation

---

## 🧮 2. Matrix Distance Filter Application

A powerful PyQt6 GUI tool for filtering geographic matrix data based on **distance thresholds**, **standard deviation**, and **directional constraints**.

![PyQt6 GUI Application](https://img.shields.io/badge/GUI-PyQt6-green)
![Python 3.x](https://img.shields.io/badge/Python-3.x-blue)

### ✨ Features

* **Multi-Stage Filtering**:

  * Distance thresholds with dynamic radius expansion
  * Outlier removal based on standard deviation
  * Angle-based directional filtering (2-pass)
* **Parallel Processing**:

  * Uses `ThreadPoolExecutor` for origin group processing
  * Progress bar and real-time logs
* **Intuitive GUI**:

  * Tabbed configuration interface
  * Log viewer and visual progress feedback
* **Smart File Handling**:

  * CSV input/output
  * Configurable encoding and delimiters
  * Timestamped filtered output
  * Auto-generated log files

### 🧰 Requirements

Install dependencies:

```bash
pip install PyQt6 pandas numpy folium
```

### 🚀 Installation & Execution

1. Clone/download the repository.
2. Make sure dependencies are installed.
3. Run:

```bash
python matrix_filter_app.py
```

### 📂 Input CSV Format

CSV must contain:

* Origin identification column(s)
* Origin latitude & longitude
* Destination latitude & longitude
* Distance (in meters)

### ⚙️ Configuration Tabs

1. **CSV Settings**:

   * Choose delimiter, quote character, and encoding
2. **Column Settings**:

   * Map CSV columns to expected fields
   * Specify origin ID columns
3. **Filter Settings**:

   * **Distance**: Initial radius, expansion step, min edges
   * **Std. Deviation**: Max allowed SD, min edges to keep
   * **Direction**: Min angle difference, min edges to retain

### 🔄 Filtering Pipeline

1. **Distance Threshold**:

   * Expands radius if minimum edges aren't found
   * Removes outliers
2. **Standard Deviation Filter**:

   * Iteratively removes longest edges until SD is acceptable
3. **Directional Filter**:

   * Two-pass filter for edge angles
   * Preserves shortest paths

### 🧵 Threading Model

* Worker threads perform filtering
* UI remains responsive
* Progress updates handled in real-time

### 🗃️ Output

* `_filtered_[timestamp].csv`
* `[timestamp]_log.txt`
* Real-time log visible in GUI

---

## 📄 License

This project is licensed under the MIT License.

## 🛠 Support

For issues or feature requests, please [open an issue](https://github.com/your-repo/issues).

---

> **Note**: Each application requires its respective `.ui` file in the same directory as the script:
>
> * `graph_visualizer2.ui` for the **Graph Network Visualizer**
> * `csv_graph_distance_filter.ui` for the **Matrix Distance Filter**
