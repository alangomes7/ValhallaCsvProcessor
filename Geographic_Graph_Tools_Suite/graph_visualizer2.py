import os
import math
import sys
import pandas as pd
import folium
import datetime
# Changed PyQt5 imports to PyQt6
from PyQt6.QtWidgets import (QApplication, QMainWindow, QFileDialog, QMessageBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt # Import Qt for the LineWrapMode
from PyQt6.uic import loadUi

class WorkerThread(QThread):
    """Worker thread for generating the graph network visualization."""
    
    progress_updated = pyqtSignal(int)
    log_message = pyqtSignal(str)
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, input_file):
        super().__init__()
        self.input_file = input_file

    def run(self):
        """Main execution method for the worker thread."""
        try:
            self.log_message.emit("Starting graph network visualization...")
            self.progress_updated.emit(10)

            # Load and process data
            df = self.load_and_process_data()
            self.progress_updated.emit(30)

            # Create map
            m = self.create_map(df)
            self.progress_updated.emit(80)

            # Save map
            output_file = self.save_map(m)
            self.progress_updated.emit(100)

            self.finished.emit(output_file)

        except Exception as e:
            self.error_occurred.emit(str(e))

    def load_and_process_data(self):
        """Load and process the input CSV file."""
        self.log_message.emit("Loading CSV file...")
        df = pd.read_csv(self.input_file)
        df.columns = [col.strip() for col in df.columns]
        
        # Rename columns to standard names
        df.rename(columns={
            "Origin - name": "origin_name",
            "Origin - Latitude": "origin_lat",
            "Origin - Longitude": "origin_lon",
            "Destination - name": "dest_name",
            "Destination - Latitude": "dest_lat",
            "Destination - Longitude": "dest_lon",
            "Distance Drive (meters)": "distance"
        }, inplace=True)

        # Clean and convert coordinates
        for col in ['origin_lat', 'origin_lon', 'dest_lat', 'dest_lon']:
            df[col] = df[col].apply(self.convert_coordinate)

        # Clean and filter
        df = df.dropna(subset=["distance", "origin_lat", "origin_lon", "dest_lat", "dest_lon"])
        df["distance"] = pd.to_numeric(df["distance"], errors="coerce")
        df = df[df["distance"] > 0]

        return df

    def create_map(self, df):
        """Create the Folium map with nodes and edges."""
        self.log_message.emit("Creating map visualization...")
        
        # Gather nodes with additional info
        nodes = {}
        node_info = {}
        for _, row in df.iterrows():
            # Skip rows with invalid coordinates
            if (not isinstance(row["origin_lat"], (int, float))) or \
               (not isinstance(row["origin_lon"], (int, float))) or \
               (not isinstance(row["dest_lat"], (int, float))) or \
               (not isinstance(row["dest_lon"], (int, float))):
                continue
                
            nodes[row["origin_name"]] = (float(row["origin_lat"]), float(row["origin_lon"]))
            nodes[row["dest_name"]] = (float(row["dest_lat"]), float(row["dest_lon"]))
            
            # Store node info for popups
            if row["origin_name"] not in node_info:
                node_info[row["origin_name"]] = {
                    "lat": float(row["origin_lat"]),
                    "lon": float(row["origin_lon"]),
                    "outgoing": [],
                    "incoming": []
                }
            if row["dest_name"] not in node_info:
                node_info[row["dest_name"]] = {
                    "lat": float(row["dest_lat"]),
                    "lon": float(row["dest_lon"]),
                    "outgoing": [],
                    "incoming": []
                }
            
            # Add edge info to nodes
            node_info[row["origin_name"]]["outgoing"].append({
                "destination": row["dest_name"],
                "distance": row["distance"]
            })
            node_info[row["dest_name"]]["incoming"].append({
                "origin": row["origin_name"],
                "distance": row["distance"]
            })

        if not nodes:
            raise ValueError("No valid coordinate data found in the CSV file.")

        # Get distance range for scaling
        min_dist = df["distance"].min()
        max_dist = df["distance"].max()

        # Create map
        first_coords = next(iter(nodes.values()))
        m = folium.Map(location=first_coords, zoom_start=12)

        # Add edge highlighting script early to ensure it's available
        highlight_script = self.create_edge_highlighting_script()
        m.get_root().html.add_child(folium.Element(highlight_script))

        # Create feature groups for different layers
        outgoing_edge_group = folium.FeatureGroup(name="Outgoing Edges", show=True)
        m.add_child(outgoing_edge_group)

        node_group = folium.FeatureGroup(name="Nodes", show=True)
        m.add_child(node_group)

        # Add node markers with click events
        node_elements = []
        for name, info in node_info.items():
            lat, lon = info["lat"], info["lon"]
            
            # Create HTML content for node info
            html_content = f"""
            <div style="font-family: Arial; font-size: 14px;">
                <h4>{name}</h4>
                <p><b>Coordinates:</b> Lat: {lat}, Lon: {lon}</p>
                <b>Outgoing connections:</b>
                <ul>
            """
            
            for edge in info["outgoing"]:
                html_content += f"<li>{edge['destination']} ({edge['distance']:.1f} m)</li>"
            
            html_content += """
                </ul>
                <b>Incoming connections:</b>
                <ul>
            """
            
            for edge in info["incoming"]:
                html_content += f"<li>{edge['origin']} ({edge['distance']:.1f} m)</li>"
            
            html_content += """
                </ul>
                <button onclick="highlightNode('{name}')">Highlight Connections</button>
            </div>
            """.format(name=name.replace("'", "\\'"))
            
            # Create popup with the HTML content
            popup = folium.Popup(html_content, max_width=300)
            
            # Generate a unique ID for this node's marker
            safe_name = name.replace("'", "_").replace('"', '_').replace(' ', '_')
            circle_id = f"circle_{safe_name}"
            
            # Create a circle marker with the popup
            marker = folium.CircleMarker(
                location=[lat, lon],
                radius=6,
                popup=popup,
                color="blue",
                fill=True,
                fill_color="blue",
                fill_opacity=1,
                tooltip=f"{name} (Click to highlight connections)"
            )
            
            # Add the marker to the map
            node_group.add_child(marker)
            
            # Add a script to store the marker object in a variable
            marker_script = f"""
            <script>
            var {circle_id} = {marker.get_name()};
            
            // Set up click handler directly
            {marker.get_name()}.on('click', function() {{
                highlightNode("{name}");
            }});
            </script>
            <div class="node-marker" data-node-id="{name}" data-lat="{lat}" data-lng="{lon}" data-circle-id="{circle_id}" 
                 style="display: none;"></div>
            """
            node_group.add_child(folium.Element(marker_script))
            
            node_elements.append({
                "name": name,
                "safe_name": safe_name,
                "circle_id": circle_id
            })

        # Draw outgoing edges
        edge_counter = 0
        for _, row in df.iterrows():
            # Skip rows with invalid coordinates
            if (not isinstance(row["origin_lat"], (int, float))) or \
               (not isinstance(row["origin_lon"], (int, float))) or \
               (not isinstance(row["dest_lat"], (int, float))) or \
               (not isinstance(row["dest_lon"], (int, float))):
                continue
                
            edge_counter += 1
            o_coords = (float(row["origin_lat"]), float(row["origin_lon"]))
            d_coords = (float(row["dest_lat"]), float(row["dest_lon"]))
            
            # Create straight line
            arc = [o_coords, d_coords]
            
            width = self.scale_width(row["distance"], min_dist, max_dist)
            
            # Create simplified HTML content for edge info
            edge_html = f"""
            <div style="font-family: Arial; font-size: 14px;">
                <h4>{row['origin_name']} - {row['dest_name']}</h4>
            </div>
            """
            
            # Create unique ID for this edge
            safe_origin = row["origin_name"].replace("'", "_").replace('"', '_').replace(' ', '_')
            safe_dest = row["dest_name"].replace("'", "_").replace('"', '_').replace(' ', '_')
            edge_id = f"edge_out_{safe_origin}_to_{safe_dest}_{edge_counter}"
            
            # Create the edge with popup
            edge = folium.PolyLine(
                arc,
                color="green",
                weight=width,
                popup=folium.Popup(edge_html, max_width=300),
                tooltip=f"{row['origin_name']} - {row['dest_name']}"
            )
            
            # Add the edge to the map
            outgoing_edge_group.add_child(edge)
            
            # Add a script to store the edge object
            edge_script = f"""
            <script>
            var {edge_id} = {edge.get_name()};
            
            // Set up hover handlers
            {edge.get_name()}.on('mouseover', function() {{
                highlightEdge("{edge_id}");
            }});
            
            {edge.get_name()}.on('mouseout', function() {{
                var edgeElement = document.querySelector('.edge[data-edge-id="{edge_id}"]');
                if (edgeElement && !edgeElement.hasAttribute('data-highlighted')) {{
                    resetEdgeHighlight("{edge_id}");
                }}
            }});
            </script>
            <div class="edge" data-edge-id="{edge_id}" data-origin="{row['origin_name']}" data-destination="{row['dest_name']}" 
                 style="display: none;"></div>
            """
            outgoing_edge_group.add_child(folium.Element(edge_script))
            
            # Add arrowhead
            self.add_arrowhead(outgoing_edge_group, {
                'locations': arc,
                'color': "green",
                'weight': width
            })

        # Add layer control to toggle edges/nodes
        folium.LayerControl().add_to(m)

        # Add custom legend
        legend = self.create_legend()
        m.get_root().html.add_child(folium.Element(legend))

        # Add auto-zoom button
        auto_zoom_button = self.create_auto_zoom_button()
        m.get_root().html.add_child(folium.Element(auto_zoom_button))

        return m

    def save_map(self, m):
        """Save the map to an HTML file."""
        self.log_message.emit("Saving map...")
        # Generate timestamp for filename
        timestamp = datetime.datetime.now().strftime("%y%m%d-%H%M%S")

        # Save to same folder with timestamp
        output_file = os.path.join(os.path.dirname(self.input_file), f"network_map_{timestamp}.html")
        m.save(output_file)
        
        return output_file

    def convert_coordinate(self, coord):
        """Convert coordinate to float, handling various string formats."""
        if isinstance(coord, (int, float)):
            return float(coord)
        if isinstance(coord, str):
            # Remove any non-numeric characters except minus sign and decimal point
            cleaned = ''.join(c for c in coord if c.isdigit() or c in ['-', '.'])
            if cleaned and cleaned != '-':
                return float(cleaned)
        return None

    def scale_width(self, distance, min_d, max_d, min_w=1.5, max_w=6):
        """Scale line width based on distance."""
        if max_d == min_d:
            return (min_w + max_w) / 2
        return min_w + (distance - min_d) * (max_w - min_w) / (max_d - min_d)

    def add_arrowhead(self, map_obj, line, color='green', size=6):
        """Add arrowhead to a line with adjusted position."""
        if len(line['locations']) < 2:
            return
        
        # Get the last two points of the line
        p1 = line['locations'][-2]
        p2 = line['locations'][-1]
        
        # Calculate a point slightly before the end (90% of the way)
        t = 0.9  # Position 90% from start to end
        adjusted_lat = p1[0] * (1 - t) + p2[0] * t
        adjusted_lon = p1[1] * (1 - t) + p2[1] * t
        
        # Calculate the angle of the line at the end point
        angle = math.atan2(p2[0] - p1[0], p2[1] - p1[1]) * 180 / math.pi
        
        # Add a marker at the adjusted point
        folium.RegularPolygonMarker(
            location=(adjusted_lat, adjusted_lon),
            number_of_sides=3,
            radius=size,
            rotation=angle,
            color=color,
            fill_color=color,
            fill_opacity=1
        ).add_to(map_obj)

    def create_legend(self):
        """Create HTML legend for the map."""
        return """
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 240px; height: 110px; 
                    background-color: white; 
                    border:2px solid gray; 
                    z-index:9999;
                    font-size:14px;
                    padding: 10px;">
            <b>Legend</b><br>
            <svg width="20" height="10"><line x1="0" y1="5" x2="20" y2="5" stroke="green" stroke-width="2"/></svg> Outgoing Edge<br>
            <svg width="20" height="10"><circle cx="10" cy="5" r="5" fill="blue"/></svg> Node<br>
            <br><i>Line thickness ∝ Distance</i>
        </div>
        """

    def create_auto_zoom_button(self):
        """Create HTML button for auto-zooming to all nodes."""
        return """
        <div style="position: fixed; top: 50%; right: 10px; transform: translateY(-50%); z-index:9999;">
            <button onclick="fitMapToNodes()" style="padding: 8px 12px; background-color: white; border: 2px solid #ccc; 
                            border-radius: 4px; font-weight: bold; cursor: pointer;">
                Show All
            </button>
        </div>
        <script>
        function fitMapToNodes() {
            // Get all node markers
            var nodeElements = document.querySelectorAll('.node-marker');
            if (nodeElements.length === 0) return;
            
            // Get bounds
            var bounds = L.latLngBounds();
            nodeElements.forEach(function(nodeElement) {
                var lat = parseFloat(nodeElement.getAttribute('data-lat'));
                var lng = parseFloat(nodeElement.getAttribute('data-lng'));
                bounds.extend([lat, lng]);
            });
            
            // Fit map to bounds with padding
            map.fitBounds(bounds, {padding: [50, 50]});
        }
        </script>
        """

    def create_edge_highlighting_script(self):
        """Create JavaScript for edge highlighting functionality."""
        return """
        <script>
        // Global variables
        var originalStyles = {};
        var currentlyHighlightedNode = null;
        
        // Function to highlight a node and its connected edges
        function highlightNode(nodeId) {
            // Reset previous highlights first
            resetAllHighlights();
            currentlyHighlightedNode = nodeId;
            
            // Find and highlight the node marker
            var nodeMarkers = document.querySelectorAll('.node-marker[data-node-id="' + nodeId + '"]');
            nodeMarkers.forEach(function(nodeMarker) {
                var circleId = nodeMarker.getAttribute('data-circle-id');
                var circle = window[circleId];
                
                if (circle) {
                    // Store original styles
                    originalStyles[circleId] = {
                        color: circle.options.color,
                        fillColor: circle.options.fillColor,
                        radius: circle.options.radius
                    };
                    
                    // Apply highlight style
                    circle.setStyle({
                        color: '#FFFF00',
                        fillColor: '#FFFF00',
                        radius: circle.options.radius * 1.5
                    });
                }
            });
            
            // Highlight outgoing edges
            var outgoingEdges = document.querySelectorAll('.edge[data-origin="' + nodeId + '"]');
            outgoingEdges.forEach(function(edgeElement) {
                var edgeId = edgeElement.getAttribute('data-edge-id');
                var edge = window[edgeId];
                
                if (edge) {
                    // Store original styles
                    originalStyles[edgeId] = {
                        color: edge.options.color,
                        weight: edge.options.weight,
                        opacity: edge.options.opacity
                    };
                    
                    // Apply highlight styles - bright green and thicker
                    edge.setStyle({
                        color: '#00FF00',
                        weight: edge.options.weight * 2,
                        opacity: 1
                    });
                    
                    // Bring highlighted edge to front
                    edge.bringToFront();
                }
            });
        }
        
        // Function to reset all highlights
        function resetAllHighlights() {
            for (var id in originalStyles) {
                var element = window[id];
                if (element) {
                    element.setStyle(originalStyles[id]);
                }
            }
            originalStyles = {};
            currentlyHighlightedNode = null;
        }
        
        // Function to highlight an edge on hover
        function highlightEdge(edgeId) {
            // Don't highlight if a node is already highlighted
            if (currentlyHighlightedNode) return;
            
            var edge = window[edgeId];
            if (edge && !originalStyles[edgeId]) {
                // Store original if not already stored (not currently highlighted)
                originalStyles[edgeId] = {
                    color: edge.options.color,
                    weight: edge.options.weight,
                    opacity: edge.options.opacity
                };
                
                // Highlight style
                edge.setStyle({
                    weight: edge.options.weight * 1.5,
                    opacity: 1
                });
                
                edge.bringToFront();
            }
        }
        
        // Function to reset edge highlight
        function resetEdgeHighlight(edgeId) {
            // Don't reset if a node is highlighted
            if (currentlyHighlightedNode) return;
            
            var edge = window[edgeId];
            if (edge && originalStyles[edgeId]) {
                edge.setStyle(originalStyles[edgeId]);
                delete originalStyles[edgeId];
            }
        }
        
        // Setup all interactions when map is fully loaded
        document.addEventListener('DOMContentLoaded', function() {
            // Setup node click handlers
            document.querySelectorAll('.node-marker').forEach(function(nodeMarker) {
                var nodeId = nodeMarker.getAttribute('data-node-id');
                var circleId = nodeMarker.getAttribute('data-circle-id');
                var circle = window[circleId];
                
                if (circle) {
                    circle.on('click', function() {
                        highlightNode(nodeId);
                    });
                }
            });
            
            // Setup edge hover handlers
            document.querySelectorAll('.edge').forEach(function(edgeElement) {
                var edgeId = edgeElement.getAttribute('data-edge-id');
                var edge = window[edgeId];
                
                if (edge) {
                    edge.on('mouseover', function() {
                        highlightEdge(edgeId);
                    });
                    
                    edge.on('mouseout', function() {
                        resetEdgeHighlight(edgeId);
                    });
                }
            });
        });
        </script>
        """

class GraphVisualizerApp(QMainWindow):
    """Main application window for Graph Network Visualizer."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Graph Network Visualizer")
        self.setGeometry(100, 100, 600, 400)
        
        # Load UI from file
        self.ui = loadUi(self.resource_path('graph_visualizer2.ui'), self)        
        # Connect signals
        self.ui.browse_button.clicked.connect(self.browse_file)
        self.ui.run_button.clicked.connect(self.run_visualization)
        
        # Initialize variables
        self.input_file = ""
    
    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)
        
    def browse_file(self):
        """Open file dialog to select input CSV file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV file", "", "CSV Files (*.csv)"
        )
        if file_path:
            self.input_file = file_path
            self.ui.file_path_edit.setText(file_path)
            self.log_message(f"Selected file: {file_path}")
    
    def run_visualization(self):
        """Start the visualization process."""
        if not self.input_file:
            QMessageBox.warning(self, "Error", "Please select a CSV file first.")
            return
            
        try:
            self.log_message("Starting visualization...")
            
            # Disable UI during processing
            self.set_ui_enabled(False)
            
            # Create and start worker thread
            self.worker = WorkerThread(self.input_file)
            self.worker.progress_updated.connect(self.ui.progress_bar.setValue)
            self.worker.log_message.connect(self.log_message)
            self.worker.finished.connect(self.visualization_complete)
            self.worker.error_occurred.connect(self.visualization_error)
            self.worker.start()
            
        except Exception as e:
            self.log_message(f"Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"An error occurred:\n{str(e)}")
    
    def visualization_complete(self, output_file):
        """Handle successful completion of visualization."""
        self.log_message(f"Visualization complete! Map saved to:\n{output_file}")
        QMessageBox.information(self, "Success", f"Map successfully saved to:\n{output_file}")
        self.set_ui_enabled(True)
    
    def visualization_error(self, error_message):
        """Handle errors during visualization."""
        self.log_message(f"Error: {error_message}")
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error_message}")
        self.set_ui_enabled(True)
    
    def log_message(self, message):
        """Append message to log with timestamp."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.ui.log_text.append(f"[{timestamp}] {message}")
        # In PyQt6, use .verticalScrollBar().setValue() directly
        self.ui.log_text.verticalScrollBar().setValue(
            self.ui.log_text.verticalScrollBar().maximum()
        )
    
    def set_ui_enabled(self, enabled):
        """Enable or disable UI elements during processing."""
        self.ui.browse_button.setEnabled(enabled)
        self.ui.run_button.setEnabled(enabled)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GraphVisualizerApp()
    window.show()
    sys.exit(app.exec()) # Changed app.exec_() to app.exec() for PyQt6