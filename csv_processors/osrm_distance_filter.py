""" Matrix Distance Filter Application

This application filters geographic matrix data based on distance thresholds, standard deviation, and direction angles, with a PyQt5 GUI interface. """

import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from math import atan2, degrees
import folium
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import (QApplication, QMainWindow, QMessageBox, QFileDialog)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.uic import loadUi
from concurrent.futures import ThreadPoolExecutor, as_completed
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

class WorkerThread(QThread):
    """Worker thread for performing filtering operations in the background."""

    progress_updated = pyqtSignal(int)
    log_message = pyqtSignal(str)
    finished = pyqtSignal(pd.DataFrame, str, str)
    error = pyqtSignal(str, str)

    def __init__(self, input_file, config):
        super().__init__()
        self.input_file = input_file
        self.config = config
        self.logger = None
        self.log_path = None

    def run(self):
        """Main execution method for the worker thread."""
        file_handler = None
        try:
            directory = os.path.dirname(self.input_file)
            self.logger, self.log_path, file_handler = self.setup_logging(directory)
            self.log_message.emit(f"Processing file: {self.input_file}")

            # Execute processing steps
            steps = [
                (lambda: self.read_csv(self.input_file), "Reading CSV file..."),
                (self.filter_by_radius, "Applying distance threshold filter..."),
                (self.filter_by_standard_deviation, "Applying standard deviation filter..."),
                (self.filter_by_direction, "Applying direction filter..."),
                (self.filter_by_direction2, "Applying final direction filter..."),
                (self.filter_by_outlier2, "Applying outlier filter..."),  # Added self.
                (lambda df: self.save_filtered_data(df, self.input_file), "Saving results...")
            ]

            df = pd.DataFrame()
            progress = 0
            progress_increment = 100 // len(steps)

            for step, message in steps:
                self.log_message.emit(message)
                df = step(df) if not df.empty else step()
                progress += progress_increment
                self.progress_updated.emit(min(progress, 90))

            self.log_message.emit("Processing completed successfully")
            self.finished.emit(df, self.log_path, self.input_file)
            self.progress_updated.emit(100)

        except Exception as e:
            self.log_message.emit(f"Error: {str(e)}")
            self.error.emit("Processing failed", str(e))
        finally:
            if file_handler:
                file_handler.flush()
                file_handler.close()
            if self.logger:
                for handler in self.logger.handlers:
                    handler.flush()
                    handler.close()
                logging.shutdown()

    def setup_logging(self, log_dir):
        """Create a log file and return the logger."""
        timestamp = self.get_timestamp()
        log_filename = f"filter_matrix_distance_log_{timestamp}.log"
        log_path = os.path.join(log_dir, log_filename)

        logger = logging.getLogger("matrix_filter")
        logger.setLevel(logging.INFO)

        file_handler = logging.FileHandler(log_path)
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        return logger, log_path, file_handler

    def get_timestamp(self):
        """Return current timestamp string for file naming."""
        return datetime.now().strftime("%y%m%d_%H%M%S")

    def read_csv(self, filepath):
        """Read the CSV and validate required columns."""
        try:
            self.log_message.emit(f"Attempting to read CSV file: {filepath}")
            df = pd.read_csv(
                filepath, 
                sep=self.config["separator"], 
                quotechar=self.config["quotechar"], 
                encoding=self.config["encoding"]
            )
            self.log_message.emit(f"Successfully loaded CSV with {len(df)} rows.")

            required_cols = self.config["origin_columns"] + [
                self.config["distance_column"],
                self.config["origin_lat_col"],
                self.config["origin_lon_col"],
                self.config["destination_lat_col"],
                self.config["destination_lon_col"]
            ]
            missing = [col for col in required_cols if col not in df.columns]
            if missing:
                error_msg = f"Missing required columns in CSV: {missing}"
                self.log_message.emit(error_msg)
                raise ValueError(error_msg)

            return df
        except Exception as e:
            error_msg = f"Error reading CSV file: {str(e)}"
            self.log_message.emit(error_msg)
            raise

    def filter_by_radius(self, df):
        """Filter edges based on dynamic radius from origin points"""
        
        result_rows = []
        grouped = df.groupby(self.config["origin_columns"])
        total_groups = len(grouped)
        self.log_message.emit(f"Processing {total_groups} origin groups with radius filter...")
        
        with ThreadPoolExecutor() as executor:
            futures = []
            for i, (origin, group) in enumerate(grouped, 1):
                futures.append(executor.submit(
                    self.process_origin_radius, 
                    origin, group.copy()
                ))
                if i % 100 == 0 or i == total_groups:
                    self.log_message.emit(f"Submitted {i}/{total_groups} origin groups for processing")
            
            for future in as_completed(futures):
                result_rows.extend(future.result())
                
        return pd.DataFrame(result_rows)

    def process_origin_radius(self, origin, group):
        """Process a single origin's group for radius-based filtering."""
        group = group.copy()
        group = group[group[self.config["distance_column"]] > 0]
        
        if len(group) == 0:
            self.log_message.emit(f"Origin {origin}: No valid edges after removing zero-distance connections.")
            return []
        
        # Get configuration parameters
        distance_col = self.config["distance_column"]
        initial_radius = self.config["distance_filter_initial_distance"]
        radius_step = self.config["distance_filter_step"]
        min_edges = self.config["distance_filter_min_edges"]
        max_radius = 100000  # 100 km
        
        # Sort edges by distance
        group_sorted = group.sort_values(distance_col)
        
        # Start with initial radius and expand until we have enough edges
        current_radius = initial_radius
        while current_radius <= max_radius:
            filtered = group_sorted[group_sorted[distance_col] <= current_radius]
            
            edge_count = len(filtered)
            if edge_count >= min_edges:
                self.log_message.emit(
                    f"✅ {origin} - Found {edge_count} edges within {current_radius}m radius (minimum: {min_edges})"
                )
                filtered = self.filter_by_outlier(origin, filtered, radius_step, 3)
                if isinstance(filtered, list):
                    return filtered
                return filtered.to_dict('records')
            
            current_radius += radius_step
        
        self.log_message.emit(
            f"⚠️ {origin} - Could not find {min_edges} edges within maximum radius of {max_radius}m. "
            f"Returning all {len(group_sorted)} edges."
        )
        return group_sorted.to_dict('records')

    def filter_by_outlier(self, origin, group, radius_step, multiplier = 3, distance_outlier = -1):
        """Remove outlier edge if the top distance is significantly higher than the next two."""
        if isinstance(group, list):
            return group
        
        group = group.copy()
        group = group[group[self.config["distance_column"]] > 0]
        
        if len(group) <= 2:
            return group.to_dict("records")
        
        distance_col = self.config["distance_column"]
        sorted_group = group.sort_values(by=distance_col, ascending=False)
        distances = sorted_group[distance_col].values
        
        if len(distances) >= 3:
            top_values = distances[:3]
            first = top_values[0]
            second = top_values[1]

            if distance_outlier <= -1:
                distance_outlier =  multiplier * radius_step
                distance_outlier_registered = first - second
            
                if distance_outlier_registered > distance_outlier:
                    sorted_group = sorted_group.iloc[1:]
                    self.log_message.emit(
                        f"🧹 {origin} - Removed outlier edge with distance {first} "
                        f"(too far from next values: {distance_outlier:.2f}m) - "
                        f"Keep {len(sorted_group)} edges."
                    )
            else:

                distance_outlier_registered = (first - second) * multiplier
                if distance_outlier_registered > distance_outlier:
                    sorted_group = sorted_group.iloc[1:]
                    self.log_message.emit(
                        f"🧹 {origin} - Removed outlier edge with distance {first} "
                        f"(too far from next values: {distance_outlier:.2f}m) - "
                        f"Keep {len(sorted_group)} edges."
                    )

        
        return sorted_group.to_dict("records")

    def filter_by_standard_deviation(self, df):
        """Filter out distance outliers using standard deviation."""
        result_rows = []
        grouped = df.groupby(self.config["origin_columns"])
        total_groups = len(grouped)
        self.log_message.emit(f"Processing {total_groups} origin groups with standard deviation filter...")

        with ThreadPoolExecutor() as executor:
            futures = []
            for i, (origin, group) in enumerate(grouped, 1):
                futures.append(executor.submit(
                    self.process_origin_std_dev, 
                    origin, group.copy()
                ))
                if i % 100 == 0 or i == total_groups:
                    self.log_message.emit(f"Submitted {i}/{total_groups} origin groups for processing")

            for future in as_completed(futures):
                result_rows.extend(future.result())
        
        return pd.DataFrame(result_rows)

    def process_origin_std_dev(self, origin, group):
        """Filters edges by removing the longest edges until standard deviation is acceptable."""
        distance_col = self.config["distance_column"]
        min_edges = self.config["standard_deviation_filter_min_edges"]
        max_std_dev = self.config["standard_deviation_filter_max_threshold"]

        if len(group) < min_edges:
            self.log_message.emit(f"⚠️ Origin {origin}: Only {len(group)} edges (need {min_edges}). Keeping all.")
            return group.to_dict('records')

        working_group = group.copy()
        original_std = np.std(working_group[distance_col].values)
        attempt = 0
        max_attempts = 1000
        current_std = original_std

        while len(working_group) >= min_edges and attempt < max_attempts:
            current_std = np.std(working_group[distance_col].values)

            if current_std <= max_std_dev:
                self.log_message.emit(
                    f"✅ Origin {origin}: Kept {len(working_group)} edges after removing {attempt} longest edges\n"
                    f"Final std dev: {current_std:.2f}m (reduced from {original_std:.2f}m)"
                )
                return working_group.to_dict('records')

            # Remove the edge with the longest distance
            max_idx = working_group[distance_col].idxmax()
            working_group = working_group.drop(index=max_idx)
            attempt += 1

        if len(working_group) >= min_edges:
            self.log_message.emit(
                f"⚠️ Origin {origin}: Stopped after {attempt} removals.\n"
                f"Kept {len(working_group)} edges. Final std dev: {current_std:.2f}m"
            )
            return working_group.to_dict('records')
        else:
            self.log_message.emit(
                f"⚠️ Origin {origin}: Could not meet standard deviation requirement after {attempt} removals.\n"
                f"Returning last valid group with {len(working_group)} edges. Final std dev: {current_std:.2f}m"
            )
            return working_group.to_dict('records')

    def calculate_bearing(self, lat1, lon1, lat2, lon2):
        """Calculate angle (bearing) between two points in degrees."""
        delta_lon = np.radians(lon2 - lon1)
        lat1 = np.radians(lat1)
        lat2 = np.radians(lat2)

        x = np.sin(delta_lon) * np.cos(lat2)
        y = np.cos(lat1) * np.sin(lat2) - (np.sin(lat1) * np.cos(lat2) * np.cos(delta_lon))
        angle = atan2(x, y)
        return degrees(angle) % 360

    def filter_by_direction(self, df):
        """Main direction filter that processes all origin groups."""
        result_rows = []
        grouped = df.groupby(self.config["origin_columns"])
        total_groups = len(grouped)
        self.log_message.emit(f"Processing {total_groups} origin groups with direction filter...")

        with ThreadPoolExecutor() as executor:
            futures = []
            for i, (origin, group) in enumerate(grouped, 1):
                futures.append(executor.submit(
                    self.process_origin_direction, 
                    origin, group.copy()
                ))
                if i % 100 == 0 or i == total_groups:
                    self.log_message.emit(f"Submitted {i}/{total_groups} origin groups for processing")

            for future in as_completed(futures):
                result_rows.extend(future.result())

        return pd.DataFrame(result_rows)

    def filter_by_direction2(self, df):
        """Final direction filter that removes edges not meeting angle requirements by removing longest edges."""
        result_rows = []
        grouped = df.groupby(self.config["origin_columns"])
        total_groups = len(grouped)
        self.log_message.emit(f"Processing {total_groups} origin groups with final direction filter...")

        with ThreadPoolExecutor() as executor:
            futures = []
            for i, (origin, group) in enumerate(grouped, 1):
                futures.append(executor.submit(
                    self.process_origin_direction2, 
                    origin, group.copy()
                ))
                if i % 100 == 0 or i == total_groups:
                    self.log_message.emit(f"Submitted {i}/{total_groups} origin groups for processing")

            for future in as_completed(futures):
                result_rows.extend(future.result())

        return pd.DataFrame(result_rows)

    def process_origin_direction2(self, origin, group):
        """
        Final direction filter that strictly enforces angle requirements by removing the longest edge
        from any pair that doesn't meet the angle requirement, while preserving as many short edges as possible.
        
        Args:
            origin: Origin identifier
            group: DataFrame with edges for this origin
            
        Returns:
            List of filtered rows that meet angle requirements
        """
        min_angle = self.config["direction_based_edge_degree"]
        min_edges = self.config["direction_based_min_degree_edges"] -1
        
        # Prepare edges with angles and distances
        edges = []
        for _, row in group.iterrows():
            try:
                angle = self.calculate_bearing(
                    row[self.config["origin_lat_col"]],
                    row[self.config["origin_lon_col"]],
                    row[self.config["destination_lat_col"]],
                    row[self.config["destination_lon_col"]],
                )
                edges.append({
                    'row': row,
                    'angle': angle,
                    'distance': row[self.config["distance_column"]]
                })
            except KeyError as e:
                self.log_message.emit(f"Missing required column: {str(e)}")
                continue
        
        if not edges:
            self.log_message.emit(f"Warning: No valid edges found for origin {origin}")
            return []

        # Sort edges by distance (shortest first)
        edges.sort(key=lambda x: x['distance'])
        
        # Keep removing problematic edges until angle requirements are met or we reach minimum edges
        while len(edges) >= min_edges:
            # Find all pairs that don't meet angle requirements
            problematic_pairs = []
            for i in range(len(edges)):
                for j in range(i+1, len(edges)):
                    angle_diff = abs((edges[i]['angle'] - edges[j]['angle'] + 180) % 360 - 180)
                    if angle_diff < min_angle:
                        # Store the indices and the distance sum (to help decide which to remove)
                        problematic_pairs.append((i, j, edges[i]['distance'] + edges[j]['distance']))
            
            if not problematic_pairs:
                break  # All angle requirements are met
                
            # Find the pair with the largest distance sum (most problematic pair)
            worst_pair = max(problematic_pairs, key=lambda x: x[2])
            i, j, _ = worst_pair
            
            # Remove the longer edge from this pair
            if edges[i]['distance'] > edges[j]['distance']:
                removed_edge = edges.pop(i)
            else:
                removed_edge = edges.pop(j)
                
            self.log_message.emit(
                f"Removed edge (distance: {removed_edge['distance']:.1f}m, angle: {removed_edge['angle']:.1f}°) "
                f"from {origin} as it didn't meet angle requirements with another edge"
            )
        
        # Convert back to list of rows
        result = [e['row'] for e in edges]
        
        if len(result) < min_edges:
            self.log_message.emit(
                f"Warning: Could not meet angle requirements for origin {origin} "
                f"while keeping minimum {min_edges} edges. Keeping {len(result)} edges."
            )
        
        return result
    
    def process_origin_direction(self, origin, group):
        """
        Process direction filtering while preserving shortest edges.
        1. Sort edges by distance (shortest first)
        2. Check angle requirements
        3. Remove longest edge if requirements not met
        4. Repeat until valid or min edges reached
        """
        min_angle = self.config["direction_based_edge_degree"]
        min_edges = self.config["direction_based_min_degree_edges"]
        
        # Convert group to DataFrame if it isn't already
        if not isinstance(group, pd.DataFrame):
            group = pd.DataFrame(group)
        
        # Prepare edges with angles and sort by distance (shortest first)
        edges = []
        for _, row in group.iterrows():
            try:
                angle = self.calculate_bearing(
                    row[self.config["origin_lat_col"]],
                    row[self.config["origin_lon_col"]],
                    row[self.config["destination_lat_col"]],
                    row[self.config["destination_lon_col"]],
                )
                edges.append({
                    'row': row,
                    'angle': angle,
                    'distance': row[self.config["distance_column"]]
                })
            except KeyError as e:
                self.log_message.emit(f"Missing required column: {str(e)}")
                continue
        
        if not edges:
            self.log_message.emit(f"Warning: No valid edges found for origin {origin}")
            return []

        edges.sort(key=lambda x: x['distance'])  # Sort by distance (shortest first)

        # Filtering loop
        while len(edges) > min_edges:
            # Check if current edges meet angle requirements
            if self.check_angles([e['angle'] for e in edges], min_angle):
                break
                
            # Remove longest remaining edge (last in sorted list)
            removed = edges.pop()
            self.log_message.emit(
                f"Removed edge to ({removed['row'][self.config['destination_lat_col']]:.4f}, "
                f"{removed['row'][self.config['destination_lon_col']]:.4f}) | "
                f"Distance: {removed['distance']:.1f}m | "
                f"Angle: {removed['angle']:.1f}°"
            )
        
        # Convert back to list of rows
        result = [e['row'] for e in edges]
        
        if len(result) < min_edges:
            self.log_message.emit(
                f"Warning: Only {len(result)} edges remain for origin {origin} "
                f"(minimum required: {min_edges})"
            )
        
        return result
    
    def filter_by_outlier2(self, df):
        """Wrapper function for the outlier filter to work with the processing steps.
        Applies outlier filtering to each origin group in the DataFrame.
        
        Args:
            df: Input DataFrame containing edge data
            
        Returns:
            DataFrame with outliers removed
        """
        if df.empty:
            return df
        
        # Get configuration parameters
        origin_cols = self.config["origin_columns"]
        distance_col = self.config["distance_column"]
        radius_step = self.config["distance_filter_step"]
        
        # Prepare results storage
        filtered_rows = []
        total_groups = len(df.groupby(origin_cols))
        processed = 0
        
        # Process each origin group
        for origin, group in df.groupby(origin_cols):
            # Convert group to list of dicts if needed
            if isinstance(group, pd.DataFrame):
                group_dicts = group.to_dict('records')
            else:
                group_dicts = group

            group_sorted = group.sort_values(distance_col)
            
            # Apply outlier filter
            filtered_group = self.filter_by_outlier(origin, group_sorted, radius_step, 1, 1000)
            
            # Handle return type (could be list or DataFrame)
            if isinstance(filtered_group, pd.DataFrame):
                filtered_rows.extend(filtered_group.to_dict('records'))
            elif isinstance(filtered_group, list):
                filtered_rows.extend(filtered_group)
            else:
                self.log_message.emit(f"Unexpected return type from filter_by_outlier for origin {origin}")
                filtered_rows.extend(group_dicts)
            
            processed += 1
            if processed % 100 == 0 or processed == total_groups:
                self.log_message.emit(f"Processed {processed}/{total_groups} origin groups for outlier filtering")
        
        # Convert back to DataFrame
        if filtered_rows:
            result_df = pd.DataFrame(filtered_rows)
            # Ensure we maintain original column order
            result_df = result_df[df.columns]
            return result_df
        
        return pd.DataFrame(columns=df.columns)
    
    def check_angles(self, angles, min_angle):
        """Check if all angle pairs meet minimum separation."""
        for i in range(len(angles)):
            for j in range(i+1, len(angles)):
                diff = abs((angles[i] - angles[j] + 180) % 360 - 180)
                if diff < min_angle:
                    return False
        return True

    def check_angle_requirements(self, rows_with_angles_dist, min_angle):
        """
        Check if all angle pairs meet the minimum angle requirement.
        
        Args:
            rows_with_angles_dist: List of tuples (row, angle, distance)
            min_angle: Minimum required angle difference in degrees
            
        Returns:
            bool: True if all angle pairs meet requirement, False otherwise
        """
        for i in range(len(rows_with_angles_dist)):
            for j in range(i+1, len(rows_with_angles_dist)):
                angle_diff = abs((rows_with_angles_dist[i][1] - rows_with_angles_dist[j][1] + 180) % 360 - 180)
                if angle_diff < min_angle:
                    return False
        return True

    def find_longest_edge(self, rows_with_angles_dist):
        """
        Find the index of the edge with the longest distance.
        
        Args:
            rows_with_angles_dist: List of tuples (row, angle, distance)
            
        Returns:
            int: Index of the longest edge
        """
        max_dist = -1
        longest_idx = 0
        for idx, (_, _, dist) in enumerate(rows_with_angles_dist):
            if dist > max_dist:
                max_dist = dist
                longest_idx = idx
        return longest_idx

    def save_filtered_data(self, df, input_path):
        """Save filtered data to new CSV file with timestamp."""
        directory, filename = os.path.split(input_path)
        name, _ = os.path.splitext(filename)
        timestamp = self.get_timestamp()
        output_filename = f"{name}_filtered_{timestamp}.csv"
        output_path = os.path.join(directory, output_filename)

        self.log_message.emit(f"Saving filtered data to {output_path}...")
        df.to_csv(
            output_path,
            sep=self.config["separator"],
            quotechar=self.config["quotechar"],
            encoding=self.config["encoding"],
            index=False,
            quoting=1
        )
        self.log_message.emit(f"Successfully saved filtered CSV to {output_path}")
        return df

class PlotCanvas(FigureCanvas):
    """Custom widget for displaying matplotlib plots."""
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig, self.ax = plt.subplots(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)

    def plot_histogram(self, data, title, xlabel, ylabel):
        """Plot a histogram of the given data."""
        self.ax.clear()
        self.ax.hist(data, bins=30, color='skyblue', edgecolor='black')
        self.ax.set_title(title)
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        self.draw()

class MatrixFilterApp(QMainWindow):
    """Main application window for the Matrix Distance Filter."""
    
    def __init__(self):
        super().__init__()
        self.ui = loadUi('osrm_distance_filter.ui', self)
        self.setWindowTitle("Matrix Distance Filter")
        
        # Initialize attributes
        self.df = pd.DataFrame()
        self.output_path = ""
        self.log_path = ""
        
        # Setup UI connections
        self.setup_connections()
        
        # Initialize plot canvas
        self.plot_canvas = PlotCanvas(self.ui.visualization_tab)
        self.ui.visualization_layout.addWidget(self.plot_canvas)
        
        # Disable buttons initially
        self.toggle_visualization_buttons(False)

    def setup_connections(self):
        """Connect UI signals to slots."""
        self.ui.browse_button.clicked.connect(self.browse_file)
        self.ui.run_button.clicked.connect(self.run_filtering)
        self.ui.plot_distance_button.clicked.connect(self.plot_distance_distribution)
        self.ui.plot_angle_button.clicked.connect(self.plot_angle_distribution)
        self.ui.show_map_button.clicked.connect(self.show_map)
        self.ui.clear_log_button.clicked.connect(self.ui.log_text.clear)

    def toggle_visualization_buttons(self, enabled):
        """Enable/disable visualization buttons."""
        self.ui.plot_distance_button.setEnabled(enabled)
        self.ui.plot_angle_button.setEnabled(enabled)
        self.ui.show_map_button.setEnabled(enabled)

    def browse_file(self):
        """Open file dialog to select input CSV file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV file", "", "CSV Files (*.csv)"
        )
        if file_path:
            self.ui.file_path_edit.setText(file_path)
            self.log_message(f"Selected file: {file_path}")

    def run_filtering(self):
        """Start the filtering process in a worker thread."""
        input_file = self.ui.file_path_edit.text()
        if not input_file or not os.path.exists(input_file):
            QMessageBox.warning(self, "Error", "Please select a valid CSV file")
            return
            
        config = self.get_config_from_ui()
        self.log_message("Starting filtering process...")
        self.toggle_visualization_buttons(False)
        
        self.worker = WorkerThread(input_file, config)
        self.worker.progress_updated.connect(self.ui.progress_bar.setValue)
        self.worker.log_message.connect(self.log_message)
        self.worker.finished.connect(self.filtering_complete)
        self.worker.start()

    def get_config_from_ui(self):
        """Get configuration parameters from UI elements."""
        return {
            "separator": self.ui.separator_edit.text(),
            "quotechar": self.ui.quotechar_edit.text(),
            "encoding": self.ui.encoding_edit.text(),
            "distance_column": self.ui.distance_col_edit.text(),
            "origin_columns": [col.strip() for col in self.ui.origin_cols_edit.text().split(",")],
            "destination_lat_col": self.ui.dest_lat_edit.text(),
            "destination_lon_col": self.ui.dest_lon_edit.text(),
            "origin_lat_col": self.ui.origin_lat_edit.text(),
            "origin_lon_col": self.ui.origin_lon_edit.text(),
            "distance_filter_initial_distance": self.ui.dist_init_spin.value(),
            "distance_filter_step": self.ui.dist_step_spin.value(),
            "distance_filter_min_edges": self.ui.dist_min_edges_spin.value(),
            "standard_deviation_filter_max_threshold": self.ui.std_max_thresh_spin.value(),
            "standard_deviation_filter_min_edges": self.ui.std_min_edges_spin.value(),
            "direction_based_edge_degree": self.ui.dir_degree_spin.value(),
            "direction_based_min_degree_edges": self.ui.dir_min_edges_spin.value(),
        }

    def log_message(self, message):
        """Append message to log with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.ui.log_text.append(f"[{timestamp}] {message}")
        self.ui.log_text.verticalScrollBar().setValue(
            self.ui.log_text.verticalScrollBar().maximum()
        )

    def save_ui_log_to_file(self, log_file_path=None):
        """Save UI log text content to the log file."""
        if not log_file_path and hasattr(self, 'log_path') and self.log_path:
            log_file_path = self.log_path
        
        if not log_file_path:
            directory = os.path.dirname(self.ui.file_path_edit.text()) if self.ui.file_path_edit.text() else "."
            timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
            log_file_path = os.path.join(directory, f"ui_log_{timestamp}.log")
        
        try:
            log_content = self.ui.log_text.toPlainText()
            with open(log_file_path, 'w', encoding='utf-8') as log_file:
                log_file.write(log_content)
            print(f"UI log saved to: {log_file_path}")
        except Exception as e:
            print(f"Error saving UI log: {str(e)}")
    
    def filtering_complete(self, df, log_path, input_path):
        """Handle completion of filtering process."""
        self.df = df
        self.log_path = log_path
        self.config = self.get_config_from_ui()
        
        if not df.empty:
            directory = os.path.dirname(input_path)
            name, _ = os.path.splitext(os.path.basename(input_path))
            timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
            self.output_path = os.path.join(directory, f"{name}_filtered_{timestamp}.csv")
            
            self.log_message(f"Processing complete. Results saved to: {self.output_path}")
            self.toggle_visualization_buttons(True)
            self.save_ui_log_to_file(log_path)
        else:
            self.log_message("Processing failed")
    
    def closeEvent(self, event):
        """Handle application close event."""
        self.save_ui_log_to_file()
        logging.shutdown()
        event.accept()

    def plot_distance_distribution(self):
        """Plot histogram of distance distribution."""
        if self.df.empty or not hasattr(self, 'config'):
            self.log_message("Error: No data available for plotting")
            return
            
        try:
            distances = self.df[self.config["distance_column"]]
            self.plot_canvas.plot_histogram(
                distances,
                "Distance Distribution",
                "Distance (meters)",
                "Frequency"
            )
            self.log_message("Plotted distance distribution histogram")
        except Exception as e:
            self.log_message(f"Error plotting distance distribution: {str(e)}")
            
    def plot_angle_distribution(self):
        """Plot histogram of angle distribution."""
        if self.df.empty or not hasattr(self, 'config'):
            self.log_message("Error: No data available for plotting")
            return
            
        try:
            angles = []
            for _, row in self.df.iterrows():
                angle = calculate_bearing(
                    row[self.config["origin_lat_col"]],
                    row[self.config["origin_lon_col"]],
                    row[self.config["destination_lat_col"]],
                    row[self.config["destination_lon_col"]],
                )
                angles.append(angle)
                
            self.plot_canvas.plot_histogram(
                angles,
                "Angle Distribution",
                "Angle (degrees)",
                "Frequency"
            )
            self.log_message("Plotted angle distribution histogram")
        except Exception as e:
            self.log_message(f"Error plotting angle distribution: {str(e)}")
            
    def show_map(self):
        """Display interactive map with origin-destination connections."""
        if self.df.empty or not hasattr(self, 'config'):
            self.log_message("Error: No data available for mapping")
            return
            
        try:
            first_row = self.df.iloc[0]
            map_center = [first_row[self.config["origin_lat_col"]], first_row[self.config["origin_lon_col"]]]
            
            m = folium.Map(location=map_center, zoom_start=12)
            
            sample_size = min(100, len(self.df))
            sample_df = self.df.sample(sample_size)
            
            for _, row in sample_df.iterrows():
                origin = [row[self.config["origin_lat_col"]], row[self.config["origin_lon_col"]]]
                dest = [row[self.config["destination_lat_col"]], row[self.config["destination_lon_col"]]]
                
                folium.Marker(origin, popup="Origin").add_to(m)
                folium.Marker(dest, popup="Destination").add_to(m)
                folium.PolyLine([origin, dest], color="blue").add_to(m)
            
            map_file = os.path.join(os.path.dirname(self.output_path), "map.html")
            m.save(map_file)
            
            import webbrowser
            webbrowser.open(f"file://{os.path.abspath(map_file)}")
            self.log_message(f"Map saved and opened: {map_file}")
        except Exception as e:
            self.log_message(f"Error creating map: {str(e)}")
            
def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calculate angle (bearing) between two points in degrees."""
    delta_lon = np.radians(lon2 - lon1)
    lat1 = np.radians(lat1)
    lat2 = np.radians(lat2)

    x = np.sin(delta_lon) * np.cos(lat2)
    y = np.cos(lat1) * np.sin(lat2) - (np.sin(lat1) * np.cos(lat2) * np.cos(delta_lon))
    angle = atan2(x, y)
    return degrees(angle) % 360

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MatrixFilterApp()
    window.show()
    sys.exit(app.exec_())