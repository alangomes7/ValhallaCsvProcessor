""" Matrix Distance Filter Application

This application filters geographic matrix data based on distance thresholds, standard deviation, and direction angles, with a PyQt6 GUI interface. """

import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from math import atan2, degrees
import folium
from PyQt6.QtWidgets import (QApplication, QMainWindow, QMessageBox, QFileDialog) # Changed from PyQt5
from PyQt6.QtCore import QThread, pyqtSignal # Changed from PyQt5
from PyQt6.uic import loadUi
from concurrent.futures import ThreadPoolExecutor, as_completed

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
                (self.filter_by_direction, "Applying direction filter to avoid overlaps..."),
                (self.filter_by_outlier2, "Applying outlier filter..."),
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
        final_group = None

        while len(working_group) >= min_edges and attempt < max_attempts:
            current_std = np.std(working_group[distance_col].values)

            if current_std <= max_std_dev:
                self.log_message.emit(
                    f"✅ Origin {origin}: Kept {len(working_group)} edges after removing {attempt} longest edges\n"
                    f"Final std dev: {current_std:.2f}m (reduced from {original_std:.2f}m)"
                )
                final_group = working_group
                break  # Exit the loop

            # Remove the edge with the longest distance
            max_idx = working_group[distance_col].idxmax()
            working_group = working_group.drop(index=max_idx)
            attempt += 1

        if final_group is None:  # Loop finished without success
            final_group = working_group  # Use the last state of working_group
            if len(final_group) >= min_edges:
                self.log_message.emit(
                    f"⚠️ Origin {origin}: Stopped after {attempt} removals.\n"
                    f"Kept {len(final_group)} edges. Final std dev: {current_std:.2f}m"
                )
            else:
                self.log_message.emit(
                    f"⚠️ Origin {origin}: Could not meet standard deviation requirement after {attempt} removals.\n"
                    f"Returning last valid group with {len(final_group)} edges. Final std dev: {current_std:.2f}m"
                )

        # Ensure the final result is sorted by distance before returning
        final_group_sorted = final_group.sort_values(distance_col)
        return final_group_sorted.to_dict('records')

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
        """Main direction filter that removes edges not meeting angle requirements by removing longest edges."""
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

    def process_origin_direction(self, origin, group):
        """
        Direction filter that enforces angle requirements by removing the longer edge
        from any pair that doesn't meet the angle requirement, preventing overlapping edges.
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

    def filter_by_outlier2(self, df):
        """Wrapper function for the outlier filter to work with the processing steps.
        Applies outlier filtering to each origin group in the DataFrame.
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

class MatrixFilterApp(QMainWindow):
    """Main application window for the Matrix Distance Filter."""

    def __init__(self):
        super().__init__()
        self.ui = loadUi('csv_graph_distance_filter.ui', self)
        self.setWindowTitle("Matrix Distance Filter")

        # Initialize attributes
        self.df = pd.DataFrame()
        self.output_path = ""
        self.log_path = ""

        # Setup UI connections
        self.setup_connections()

    def setup_connections(self):
        """Connect UI signals to slots."""
        self.ui.browse_button.clicked.connect(self.browse_file)
        self.ui.run_button.clicked.connect(self.run_filtering)
        self.ui.clear_log_button.clicked.connect(self.ui.log_text.clear)

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

        self.worker = WorkerThread(input_file, config)
        self.worker.progress_updated.connect(self.ui.progress_bar.setValue)
        self.worker.log_message.connect(self.log_message)
        self.worker.finished.connect(self.filtering_complete)
        # Added error signal connection for better user feedback
        self.worker.error.connect(self.filtering_error)
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
            self.log_message(f"UI log saved to: {log_file_path}")
        except Exception as e:
            self.log_message(f"Error saving UI log: {str(e)}")


    def filtering_complete(self, filtered_df, log_path, input_file):
        """Handle completion of filtering process."""
        self.df = filtered_df
        self.log_path = log_path
        self.input_file_for_map = input_file # Store original input file path
        self.log_message("Filtering process finished.")
        self.log_message(f"Results saved. Total edges remaining: {len(self.df)}")
        self.ui.progress_bar.setValue(100)
        QMessageBox.information(self, "Success", "Filtering completed successfully!")
        self.save_ui_log_to_file(self.log_path) # Save the UI log

    def filtering_error(self, title, message):
        """Handle errors during filtering process."""
        self.log_message(f"Error during filtering: {message}")
        QMessageBox.critical(self, title, message)
        self.ui.progress_bar.setValue(0)
        self.save_ui_log_to_file() # Save the UI log even on error

    def closeEvent(self, event):
        """Handle application close event."""
        reply = QMessageBox.question(
            self,
            "Exit",
            "Are you sure you want to quit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, # Corrected for PyQt6
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes: # Corrected for PyQt6
            # Ensure the UI log is saved on exit
            self.save_ui_log_to_file()
            event.accept()
        else:
            event.ignore()

if __name__ == "__main__":
    app = QApplication(sys.argv) # Still works, but can be QApplication([]) or QApplication()
    window = MatrixFilterApp()
    window.show()
    sys.exit(app.exec()) # Changed app.exec_() to app.exec() for PyQt6