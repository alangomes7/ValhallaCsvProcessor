# ValhallaCsvProcessor

Here we have two desktop programs to process pair of coordinates using Valhalla Docker Server.

**ValhallaCsvProcessor** is a Qt-based desktop application built with C++ that reads a CSV file containing coordinate pairs, sends distance/duration requests to a local [Valhalla routing server](https://github.com/valhalla/valhalla), and saves the results to a structured output file. It also logs the entire process and supports threading for better performance.

## Features

* Graphical interface for selecting input CSV files.
* Configurable Valhalla server endpoint.
* Executes `/route` operations by default (can be extended).
* Displays real-time logs and progress.
* Saves results and logs to disk.
* Lightweight, responsive UI with multithreaded processing using `QThreadPool`.

---

# Geographic Graph Tools Suite

Here we have **two powerful PyQt6 desktop applications** for working with geographic network data in CSV format:

1. **Graph Network Visualizer** – For visualizing geographic graph networks on interactive maps.
2. **Matrix Distance Filter Application** – For filtering and cleaning geographic distance matrices using advanced criteria.

* These scripts are for filter and generate the graph visualization from the generated file by Valhala Processor.
---
