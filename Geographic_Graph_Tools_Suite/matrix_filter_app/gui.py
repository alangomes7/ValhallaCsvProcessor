import os
import pandas as pd
from datetime import datetime
from PyQt6.QtWidgets import QMainWindow, QMessageBox, QFileDialog
from PyQt6.uic import loadUi

# Import the worker
from worker import WorkerThread

class MatrixFilterApp(QMainWindow):
    """Main application window for the Matrix Distance Filter."""

    def __init__(self):
        super().__init__()
        # Ensure the UI file is in the same directory as this script
        ui_path = os.path.join(os.path.dirname(__file__), 'csv_graph_distance_filter.ui')
        self.ui = loadUi(ui_path, self)
        self.setWindowTitle("Matrix Distance Filter")

        # Initialize attributes
        self.df = pd.DataFrame()
        self.output_path = ""
        self.log_path = ""
        self.worker = None

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
        # Auto-scroll logic is cleaner with PyQt6 accessors
        scrollbar = self.ui.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def save_ui_log_to_file(self, log_file_path=None):
        """Save UI log text content to the log file."""
        # Determine directory for logs
        if not log_file_path:
            directory = os.path.dirname(self.ui.file_path_edit.text()) if self.ui.file_path_edit.text() else "."
            
            # Create 'log' subdirectory if it doesn't exist
            log_dir = os.path.join(directory, "log")
            if not os.path.exists(log_dir):
                try:
                    os.makedirs(log_dir)
                except OSError:
                    log_dir = directory # Fallback if permission denied
            
            timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
            log_file_path = os.path.join(log_dir, f"ui_log_{timestamp}.log")

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
        self.input_file_for_map = input_file
        self.log_message("Filtering process finished.")
        self.log_message(f"Results saved. Total edges remaining: {len(self.df)}")
        self.ui.progress_bar.setValue(100)
        QMessageBox.information(self, "Success", "Filtering completed successfully!")
        self.save_ui_log_to_file(self.log_path)

    def filtering_error(self, title, message):
        """Handle errors during filtering process."""
        self.log_message(f"Error during filtering: {message}")
        QMessageBox.critical(self, title, message)
        self.ui.progress_bar.setValue(0)
        self.save_ui_log_to_file()

    def closeEvent(self, event):
        """Handle application close event."""
        reply = QMessageBox.question(
            self,
            "Exit",
            "Are you sure you want to quit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.save_ui_log_to_file()
            event.accept()
        else:
            event.ignore()