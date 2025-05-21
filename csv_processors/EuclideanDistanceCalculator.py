import os
import time
import csv
import pandas as pd
import math
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QMessageBox)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.uic import loadUi
import sys, os

class DistanceCalculatorWorker(QThread):
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal(pd.DataFrame, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, input_file, timeout, delay):
        super().__init__()
        self.input_file = input_file
        self.timeout = timeout
        self.delay = delay
        self.df = None

    def run(self):
        try:
            # Read and validate input file
            self.progress_updated.emit(0, "Reading input file...")
            self.df = self.read_csv_file(self.input_file)
            self.initialize_columns(self.df)
            
            missing_before = self.df['Distance Drive (meters)'].isna().sum()
            self.progress_updated.emit(5, f"Found {missing_before} rows with missing distances")
            
            # Process routes
            self.process_distances(self.df)
            
            # Generate output filename
            output_csv = self.get_output_filename()
            self.progress_updated.emit(95, "Saving results...")
            self.save_to_csv(self.df, output_csv)
            
            self.finished.emit(self.df, output_csv)
            
        except Exception as e:
            self.error_occurred.emit(str(e))

    def read_csv_file(self, filepath):
        try:
            return pd.read_csv(filepath, sep=",", encoding="utf-8")
        except UnicodeDecodeError:
            return pd.read_csv(filepath, sep=",", encoding='latin1')

    def initialize_columns(self, df):
        required_columns = [
            'Origin - Latitude',
            'Origin - Longitude',
            'Destination - Latitude',
            'Destination - Longitude'
        ]
        for col in required_columns:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        if 'Distance Drive (meters)' not in df.columns:
            df['Distance Drive (meters)'] = None
        if 'URL de Solic.' not in df.columns:
            df['URL de Solic.'] = None
        df['Distance Drive (meters)'] = pd.to_numeric(df['Distance Drive (meters)'], errors='coerce')

    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate the great-circle distance between two points 
        on the Earth's surface using the Haversine formula.
        Returns distance in meters.
        """
        # Earth radius in meters
        R = 6371000
        
        # Convert degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Differences
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        # Haversine formula
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        
        return distance

    def process_distances(self, df):
        missing = df['Distance Drive (meters)'].isna().sum()
        processed = 0
        
        for idx, row in df.iterrows():
            if not pd.isna(row['Distance Drive (meters)']):
                continue

            try:
                origin_lat = float(row['Origin - Latitude'])
                origin_lon = float(row['Origin - Longitude'])
                dest_lat = float(row['Destination - Latitude'])
                dest_lon = float(row['Destination - Longitude'])
                
                distance = self.haversine_distance(origin_lat, origin_lon, dest_lat, dest_lon)
                df.at[idx, 'Distance Drive (meters)'] = distance
                df.at[idx, 'URL de Solic.'] = "Calculated using Haversine formula"
                processed += 1
                
                # Update progress every 10 rows or when significant progress is made
                if processed % 10 == 0 or processed == missing:
                    progress = int(5 + 90 * (processed / missing)) if missing > 0 else 95
                    self.progress_updated.emit(
                        progress,
                        f"Processed {processed}/{missing} missing distances - {(100 * (1 - (missing - processed) / missing)):.2f}%"
                    )
            except (ValueError, TypeError) as e:
                self.progress_updated.emit(0, f"Skipping invalid coordinates at row {idx}: {str(e)}")
            
            # time.sleep(self.delay)

    def get_output_filename(self):
        base_dir = os.path.dirname(self.input_file)
        base_name = os.path.splitext(os.path.basename(self.input_file))[0]
        timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
        return os.path.join(base_dir, f"{base_name}_distance_processed_{timestamp}.csv")

    def save_to_csv(self, df, output_file):
        try:
            df.to_csv(
                output_file,
                index=False,
                sep=",",
                quoting=csv.QUOTE_NONNUMERIC,
                encoding="utf-8"
            )
            self.progress_updated.emit(100, f"File saved successfully: {output_file}")
        except Exception as e:
            raise Exception(f"Failed to save file {output_file}: {str(e)}")

class EuclideanDistanceCalculator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Euclidean Distance Calculator")
        self.setGeometry(100, 100, 800, 600)
        
        # Load UI from file
        self.ui = loadUi(self.resource_path('EuclideanDistanceCalculator.ui'), self)
        
        # Connect signals
        self.ui.browse_button.clicked.connect(self.browse_file)
        self.ui.calculate_button.setEnabled(True)
        self.ui.calculate_button.clicked.connect(self.start_calculation)
        
        # Initialize variables
        self.input_file = ""
        self.worker = None
    
    @staticmethod
    def resource_path(relative_path):
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)
        
    def browse_file(self):
        """Open file dialog to select input CSV file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Input CSV File", "", "CSV Files (*.csv)"
        )
        if file_path:
            self.input_file = file_path
            self.ui.file_path_edit.setText(file_path)
            self.log_message(f"Selected file: {file_path}")
    
    def start_calculation(self):
        """Start the distance calculation process."""
        if not self.input_file:
            QMessageBox.warning(self, "Warning", "Please select a CSV file first.")
            return
            
        try:
            timeout = self.ui.timeout_spin.value()
            delay = self.ui.delay_spin.value()
            
            start_time = time.time()
            self.log_message("Starting distance calculations...")
            self.set_ui_enabled(False)
            
            # Create and start worker thread
            self.worker = DistanceCalculatorWorker(
                self.input_file,
                timeout=timeout,
                delay=delay
            )
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.finished.connect(self.calculation_complete)
            self.worker.error_occurred.connect(self.calculation_error)
            self.worker.start()
            
        except Exception as e:
            self.log_message(f"Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"An error occurred:\n{str(e)}")
        finally:
            elapsed = time.time() - start_time
            self.log_message(f"⏱️ Total execution time: {timedelta(seconds=elapsed)}")
    
    def update_progress(self, progress, message):
        """Update progress bar and log message."""
        self.ui.progress_bar.setValue(progress)
        self.log_message(message)
    
    def calculation_complete(self, df, output_file):
        """Handle successful completion of calculations."""
        missing_before = df['Distance Drive (meters)'].isna().sum()
        missing_after = df['Distance Drive (meters)'].isna().sum()
        
        self.log_message(f"Calculation complete! {missing_before - missing_after} distances filled.")
        self.log_message(f"Results saved to: {output_file}")
        QMessageBox.information(
            self, 
            "Success", 
            f"Calculation complete!\n\n"
            f"Filled {missing_before - missing_after} distances.\n"
            f"Results saved to:\n{output_file}"
        )
        self.set_ui_enabled(True)
    
    def calculation_error(self, error_message):
        """Handle errors during calculation."""
        self.log_message(f"Error: {error_message}")
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error_message}")
        self.set_ui_enabled(True)
    
    def log_message(self, message):
        """Append message to log with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.ui.log_text.append(f"[{timestamp}] {message}")
        self.ui.log_text.verticalScrollBar().setValue(
            self.ui.log_text.verticalScrollBar().maximum()
        )
    
    def set_ui_enabled(self, enabled):
        """Enable or disable UI elements during processing."""
        self.ui.browse_button.setEnabled(enabled)
        self.ui.timeout_spin.setEnabled(enabled)
        self.ui.delay_spin.setEnabled(enabled)
        self.ui.calculate_button.setEnabled(enabled)

if __name__ == "__main__":
    app = QApplication([])
    window = EuclideanDistanceCalculator()
    window.show()
    app.exec_()