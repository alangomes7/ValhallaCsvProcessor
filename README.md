# ValhallaCsvProcessor

**ValhallaCsvProcessor** is a Qt-based desktop application built with C++ that reads a CSV file containing coordinate pairs, sends distance/duration requests to a local [Valhalla routing server](https://github.com/valhalla/valhalla), and saves the results to a structured output file. It also logs the entire process and supports threading for better performance.

## Features

* Graphical interface for selecting input CSV files.
* Configurable Valhalla server endpoint.
* Executes `/route` operations by default (can be extended).
* Displays real-time logs and progress.
* Saves results and logs to disk.
* Lightweight, responsive UI with multithreaded processing using `QThreadPool`.

## UI Overview

* **Browse CSV**: Select the input CSV file.
* **Server**: Set the Valhalla endpoint URL (default: `http://localhost:8002`).
* **Start**: Begin processing the CSV file.
* **Open Output Folder**: Quickly access the output directory.
* **Log Viewer**: Shows step-by-step processing info.
* **Progress Bar**: Tracks progress.
* **Clear Log**: Clears the log view.

## Requirements

* Qt 6.8 or higher
* C++17 or higher
* Valhalla server running locally (e.g., using Docker)

## CSV Format

Input CSV must contain coordinate pairs per row. For example:

```
from_lat,from_lon,to_lat,to_lon
40.7486,-73.9864,40.7306,-73.9352
...
```

Output CSV includes distance/duration results, written to a timestamped file.

## Build Instructions

1. **Install Qt** (6.8+), CMake, and a C++ compiler (MSVC or GCC).
2. Clone this repo:

   ```bash
   git clone https://github.com/yourusername/ValhallaCsvProcessor.git
   cd ValhallaCsvProcessor
   ```
3. Open the `.pro` file or `.sln` in Qt Creator or Visual Studio with Qt integration.
4. Build and run the project.

## Run Instructions

1. Launch the app.
2. Click **Browse CSV** to load your input file.
3. Confirm or change the **Server** URL.
4. Click **Start** to process routes.
5. View logs and progress in real-time.
6. Click **Open Output Folder** to view the results.

## Output Files

* **Processed CSV**: Includes calculated routes from Valhalla.
* **Log File**: Contains execution details for debugging and auditing.

## Code Structure

| File                          | Description                               |
| ----------------------------- | ----------------------------------------- |
| `ValhallaCsvProcessor.h/.cpp` | Main window logic and UI control          |
| `ui_ValhallaCsvProcessor.h`   | Auto-generated UI header from Qt Designer |
| `.ui` file                    | Qt Designer file defining layout          |
| `writeAccumulatedLines(...)`  | Static utility to append output lines     |

## TODO

* Add support for other Valhalla operations (`/matrix`, `/isoline`, etc.)
* Add error handling and retry logic for failed HTTP requests
* Allow CSV header customization
* Export stats (e.g., average distance)

## License

MIT License | Valhala

---
