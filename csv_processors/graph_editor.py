import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, CheckButtons, RadioButtons
import matplotlib.patches as mpatches
from matplotlib.patches import Ellipse
from matplotlib.text import Text
from matplotlib.backend_bases import MouseButton
import numpy as np
from tkinter import Tk, filedialog
from tkinter.ttk import Button as TkButton

class EnhancedGraphVisualizer:
    def __init__(self):
        # Initialize all attributes first
        self.file_path = None
        self.original_data = None
        self.current_data = None
        self.graph = None
        self.excluded_nodes = set()
        self.excluded_edges = set()
        self.highlighted_node = None
        self.selected_edge = None
        self.zoom_factor = 1.0
        self.pan_start = None
        self.current_pos = None
        
        # Create a hidden Tkinter root window
        root = Tk()
        root.withdraw()
        
        # Show file open dialog
        file_path = filedialog.askopenfilename(
            title="Select Graph CSV File",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        
        if not file_path:
            print("No file selected. Exiting.")
            exit()
        
        self.file_path = file_path
        self.original_data = self.load_data()
        self.current_data = self.original_data.copy()
        self.graph = self.create_graph()
        
        # Create figure with larger size
        self.fig, self.ax = plt.subplots(figsize=(14, 12))
        plt.subplots_adjust(bottom=0.25)
        
        # Create UI elements
        self.create_ui()
        
        # Initial draw
        self.redraw_graph()
        
        # Connect event handlers
        self.connect_events()
    
    def load_data(self):
        """Load the CSV data into a DataFrame"""
        return pd.read_csv(self.file_path)
    
    def create_graph(self):
        """Create a networkx graph from the current data"""
        G = nx.DiGraph()
        
        for _, row in self.current_data.iterrows():
            origin = row['Origin - name']
            dest = row['Destination - name']
            edge_key = (origin, dest)
            
            if edge_key in self.excluded_edges:
                continue
                
            if origin in self.excluded_nodes or dest in self.excluded_nodes:
                continue
            
            # Add nodes with attributes if they don't exist
            if origin not in G:
                G.add_node(origin, 
                        lat=row['Origin - Latitude'],
                        lon=row['Origin - Longitude'],
                        pos=(row['Origin - Longitude'], row['Origin - Latitude']))
            
            if dest not in G:
                G.add_node(dest, 
                        lat=row['Destination - Latitude'],
                        lon=row['Destination - Longitude'],
                        pos=(row['Destination - Longitude'], row['Destination - Latitude']))
            
            # Add edge with distance (only if both nodes exist)
            if origin in G and dest in G:
                G.add_edge(origin, dest, distance=row['Distance Drive (meters)'])
        
        return G
    
    def create_ui(self):
        """Create the user interface controls"""
        # Control panel background
        control_ax = plt.axes([0.1, 0.05, 0.8, 0.15])
        control_ax.set_facecolor('lightgray')
        control_ax.axis('off')
        
        # Node exclusion checkboxes (scrollable)
        self.node_check_ax = plt.axes([0.1, 0.05, 0.2, 0.1])
        all_nodes = list(set(self.original_data['Origin - name'].unique()) | 
                        set(self.original_data['Destination - name'].unique()))
        sorted_nodes = sorted(all_nodes)  # Sort the nodes alphabetically
        display_nodes = sorted_nodes[:20]  # Limit to 20 for display
        self.node_checkboxes = CheckButtons(
            self.node_check_ax,
            display_nodes,  # The labels to display
            [True] * len(display_nodes)  # Initial checked states
        )
        self.node_checkboxes.on_clicked(self.toggle_node)
        
        # Mode selector (node/edge selection)
        self.mode_ax = plt.axes([0.35, 0.1, 0.1, 0.05])
        self.mode_selector = RadioButtons(self.mode_ax, ['Node Mode', 'Edge Mode'], active=0)
        self.mode_selector.on_clicked(self.change_mode)
        
        # Remove button
        self.remove_btn = Button(plt.axes([0.35, 0.05, 0.1, 0.04]), 'Remove Selected')
        self.remove_btn.on_clicked(self.remove_selected)
        
        # Save button
        self.save_btn = Button(plt.axes([0.5, 0.1, 0.1, 0.05]), 'Save Graph')
        self.save_btn.on_clicked(self.save_graph)
        
        # Reset button
        self.reset_btn = Button(plt.axes([0.5, 0.05, 0.1, 0.05]), 'Reset Graph')
        self.reset_btn.on_clicked(self.reset_graph)
        
        # Zoom buttons
        self.zoom_in_btn = Button(plt.axes([0.65, 0.1, 0.05, 0.05]), '+')
        self.zoom_in_btn.on_clicked(lambda x: self.adjust_zoom(1.2))
        self.zoom_out_btn = Button(plt.axes([0.7, 0.1, 0.05, 0.05]), '-')
        self.zoom_out_btn.on_clicked(lambda x: self.adjust_zoom(0.8))
        self.reset_zoom_btn = Button(plt.axes([0.75, 0.1, 0.1, 0.05]), 'Reset View')
        self.reset_zoom_btn.on_clicked(self.reset_view)
        
        # Info text
        self.info_text = self.fig.text(0.1, 0.2, "", fontsize=9)
        self.help_text = self.fig.text(0.6, 0.2, 
                                     "Help:\n- Click to select nodes/edges\n- Right-click+drag to pan\n- Scroll to zoom\n- Use buttons to modify graph",
                                     fontsize=9)
    
    def connect_events(self):
        """Connect all event handlers"""
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.fig.canvas.mpl_connect('button_release_event', self.on_release)
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.fig.canvas.mpl_connect('scroll_event', self.on_scroll)
    
    def redraw_graph(self):
        """Redraw the graph with current settings"""
        self.ax.clear()
        
        if not hasattr(self, 'graph') or not self.graph.nodes:
            self.ax.text(0.5, 0.5, "Graph is empty", ha='center', va='center')
            plt.draw()
            return
        
        # Get positions from node attributes
        pos = nx.get_node_attributes(self.graph, 'pos')
        self.current_pos = pos.copy()  # Save current positions
        
        # Normalize edge weights for visualization
        edges = self.graph.edges(data=True)
        if edges:
            distances = [d['distance'] for _, _, d in edges]
            min_dist, max_dist = min(distances), max(distances)
            edge_widths = [5 * (1 - (d['distance'] - min_dist) / (max_dist - min_dist + 1)) + 0.5 
                          for _, _, d in edges]
        else:
            edge_widths = [1] * len(self.graph.edges())
        
        # Draw the graph
        nx.draw_networkx_nodes(self.graph, pos, ax=self.ax, node_size=200, node_color='lightblue')
        nx.draw_networkx_edges(self.graph, pos, ax=self.ax, edge_color='gray', 
                              arrows=True, arrowstyle='->', arrowsize=10,
                              width=edge_widths)
        
        # Draw edge labels (distances)
        edge_labels = {(u, v): f"{d['distance']:.0f}m" 
                      for u, v, d in self.graph.edges(data=True)}
        nx.draw_networkx_edge_labels(self.graph, pos, edge_labels=edge_labels, 
                                   ax=self.ax, font_size=8)
        
        # Draw node labels
        nx.draw_networkx_labels(self.graph, pos, ax=self.ax, font_size=8)
        
        # Highlight selected node and its connections
        if self.highlighted_node and self.highlighted_node in self.graph:
            # Highlight the node
            nx.draw_networkx_nodes(self.graph, pos, nodelist=[self.highlighted_node], 
                                 node_color='red', ax=self.ax, node_size=300)
            
            # Highlight incoming edges
            predecessors = list(self.graph.predecessors(self.highlighted_node))
            if predecessors:
                nx.draw_networkx_edges(self.graph, pos, 
                                     edgelist=[(p, self.highlighted_node) for p in predecessors],
                                     edge_color='green', ax=self.ax, width=3)
            
            # Highlight outgoing edges
            successors = list(self.graph.successors(self.highlighted_node))
            if successors:
                nx.draw_networkx_edges(self.graph, pos, 
                                     edgelist=[(self.highlighted_node, s) for s in successors],
                                     edge_color='blue', ax=self.ax, width=3)
            
            # Update info text
            self.update_node_info(self.highlighted_node)
        
        # Highlight selected edge
        if self.selected_edge and self.selected_edge in self.graph.edges():
            u, v = self.selected_edge
            nx.draw_networkx_edges(self.graph, pos, edgelist=[(u, v)],
                                 edge_color='purple', ax=self.ax, width=4)
            
            # Update info text
            self.update_edge_info(self.selected_edge)
        
        self.ax.set_title("Enhanced Graph Visualizer (Zoom: {:.1f}x)".format(self.zoom_factor))
        self.ax.set_axis_on()
        self.ax.grid(True)
        plt.draw()
    
    def update_node_info(self, node):
        """Update the information display for a node"""
        if node not in self.graph:
            self.info_text.set_text("Node not in current graph")
            return
        
        info = f"Selected Node: {node}\n"
        info += f"Position: Lat={self.graph.nodes[node]['lat']:.6f}, Lon={self.graph.nodes[node]['lon']:.6f}\n"
        info += f"Degree: {self.graph.degree(node)} (In: {self.graph.in_degree(node)}, Out: {self.graph.out_degree(node)})\n\n"
        
        # Incoming connections
        predecessors = list(self.graph.predecessors(node))
        info += f"Incoming connections ({len(predecessors)}):\n"
        for p in predecessors[:5]:  # Limit to 5 for display
            distance = self.graph.edges[(p, node)]['distance']
            info += f"- From {p}: {distance:.2f}m\n"
        if len(predecessors) > 5:
            info += f"- ... and {len(predecessors)-5} more\n"
        
        # Outgoing connections
        successors = list(self.graph.successors(node))
        info += f"\nOutgoing connections ({len(successors)}):\n"
        for s in successors[:5]:  # Limit to 5 for display
            distance = self.graph.edges[(node, s)]['distance']
            info += f"- To {s}: {distance:.2f}m\n"
        if len(successors) > 5:
            info += f"- ... and {len(successors)-5} more\n"
        
        self.info_text.set_text(info)
    
    def update_edge_info(self, edge):
        """Update the information display for an edge"""
        u, v = edge
        if edge not in self.graph.edges():
            self.info_text.set_text("Edge not in current graph")
            return
        
        info = f"Selected Edge: {u} → {v}\n"
        info += f"Distance: {self.graph.edges[edge]['distance']:.2f} meters\n"
        
        # Add node information
        info += f"\nSource Node ({u}):\n"
        info += f"Position: Lat={self.graph.nodes[u]['lat']:.6f}, Lon={self.graph.nodes[u]['lon']:.6f}\n"
        info += f"Degree: {self.graph.degree(u)}\n"
        
        info += f"\nTarget Node ({v}):\n"
        info += f"Position: Lat={self.graph.nodes[v]['lat']:.6f}, Lon={self.graph.nodes[v]['lon']:.6f}\n"
        info += f"Degree: {self.graph.degree(v)}\n"
        
        self.info_text.set_text(info)
    
    def toggle_node(self, label):
        """Toggle node inclusion/exclusion"""
        if label in self.excluded_nodes:
            self.excluded_nodes.remove(label)
        else:
            self.excluded_nodes.add(label)
        
        # Recreate the graph with current exclusions
        self.graph = self.create_graph()
        
        # Clear any selections
        self.highlighted_node = None
        self.selected_edge = None
        
        self.redraw_graph()
    
    def change_mode(self, label):
        """Change between node and edge selection modes"""
        self.highlighted_node = None
        self.selected_edge = None
        self.redraw_graph()
    
    def remove_selected(self, event):
        """Remove the currently selected node or edge"""
        if self.highlighted_node:
            self.excluded_nodes.add(self.highlighted_node)
            self.highlighted_node = None
        elif self.selected_edge:
            self.excluded_edges.add(self.selected_edge)
            self.selected_edge = None
        
        self.graph = self.create_graph()
        self.redraw_graph()
    
    def save_graph(self, event):
        """Save the current graph configuration to CSV"""
        # Create a mask for excluded edges
        excluded_edge_mask = self.original_data.apply(
            lambda row: (row['Origin - name'], row['Destination - name']) in self.excluded_edges,
            axis=1
        )
        
        # Create a mask for excluded nodes
        excluded_node_mask = self.original_data.apply(
            lambda row: (row['Origin - name'] in self.excluded_nodes) or 
                       (row['Destination - name'] in self.excluded_nodes),
            axis=1
        )
        
        # Combine masks
        total_mask = excluded_edge_mask | excluded_node_mask
        
        # Invert mask to keep what's not excluded
        filtered_data = self.original_data[~total_mask]
        
        # Save to file
        save_path = self.file_path.replace('.csv', '_filtered.csv')
        filtered_data.to_csv(save_path, index=False)
        self.info_text.set_text(f"Graph saved to {save_path}")
    
    def reset_graph(self, event):
        """Reset the graph to its original state"""
        self.excluded_nodes = set()
        self.excluded_edges = set()
        self.highlighted_node = None
        self.selected_edge = None
        self.graph = self.create_graph()
        
        # Reset checkboxes
        for label, rect in zip(self.node_checkboxes.labels, self.node_checkboxes.rectangles):
            rect.set_visible(True)
        
        self.redraw_graph()
    
    def reset_view(self, event):
        """Reset the zoom and pan"""
        self.zoom_factor = 1.0
        self.redraw_graph()
    
    def adjust_zoom(self, factor):
        """Adjust the zoom level"""
        self.zoom_factor *= factor
        self.redraw_graph()
    
    def on_click(self, event):
        """Handle mouse clicks to select nodes/edges and start pan"""
        if event.inaxes != self.ax:
            return
            
        if event.button == MouseButton.LEFT:
            # Selection mode depends on radio button
            if self.mode_selector.value_selected == 'Node Mode':
                self.select_node(event)
            else:
                self.select_edge(event)
        elif event.button == MouseButton.RIGHT:
            # Start pan
            self.pan_start = (event.xdata, event.ydata)
    
    def select_node(self, event):
        """Select the closest node to the click"""
        pos = nx.get_node_attributes(self.graph, 'pos')
        if not pos:
            return
            
        # Find the closest node
        min_dist = float('inf')
        closest_node = None
        
        for node, (x, y) in pos.items():
            dist = (event.xdata - x)**2 + (event.ydata - y)**2
            if dist < min_dist:
                min_dist = dist
                closest_node = node
        
        if closest_node:
            self.highlighted_node = closest_node
            self.selected_edge = None
            self.redraw_graph()
    
    def select_edge(self, event):
        """Select the closest edge to the click"""
        pos = nx.get_node_attributes(self.graph, 'pos')
        if not pos or not self.graph.edges():
            return
            
        # Find the closest edge
        min_dist = float('inf')
        closest_edge = None
        
        for u, v in self.graph.edges():
            x1, y1 = pos[u]
            x2, y2 = pos[v]
            
            # Calculate distance from point to line segment
            dist = self.point_to_line_dist(event.xdata, event.ydata, x1, y1, x2, y2)
            
            if dist < min_dist and dist < 0.05:  # Threshold for selection
                min_dist = dist
                closest_edge = (u, v)
        
        if closest_edge:
            self.selected_edge = closest_edge
            self.highlighted_node = None
            self.redraw_graph()
    
    def point_to_line_dist(self, px, py, x1, y1, x2, y2):
        """Calculate distance from point (px,py) to line segment (x1,y1)-(x2,y2)"""
        # Line segment vector
        dx = x2 - x1
        dy = y2 - y1
        
        # Vector from point to start of segment
        pdx = px - x1
        pdy = py - y1
        
        # Dot product
        dot = pdx * dx + pdy * dy
        len_sq = dx * dx + dy * dy
        
        # Parametric position on segment
        param = -1
        if len_sq != 0:
            param = dot / len_sq
        
        if param < 0:
            # Closest to first endpoint
            xx, yy = x1, y1
        elif param > 1:
            # Closest to second endpoint
            xx, yy = x2, y2
        else:
            # Closest to point on segment
            xx = x1 + param * dx
            yy = y1 + param * dy
        
        # Calculate distance
        dx = px - xx
        dy = py - yy
        return np.sqrt(dx * dx + dy * dy)
    
    def on_release(self, event):
        """Handle mouse release (end pan)"""
        self.pan_start = None
    
    def on_motion(self, event):
        """Handle mouse motion (pan)"""
        if self.pan_start is None or event.inaxes != self.ax:
            return
            
        if event.button == MouseButton.RIGHT:
            dx = event.xdata - self.pan_start[0]
            dy = event.ydata - self.pan_start[1]
            
            # Update all node positions
            pos = nx.get_node_attributes(self.graph, 'pos')
            new_pos = {node: (x + dx, y + dy) for node, (x, y) in pos.items()}
            nx.set_node_attributes(self.graph, new_pos, 'pos')
            
            self.pan_start = (event.xdata, event.ydata)
            self.redraw_graph()
    
    def on_scroll(self, event):
        """Handle scroll events for zooming"""
        if event.inaxes != self.ax:
            return
            
        # Zoom factor
        zoom_factor = 1.1 if event.step > 0 else 0.9
        
        # Get current center
        x_center = event.xdata
        y_center = event.ydata
        
        # Scale all node positions relative to center
        pos = nx.get_node_attributes(self.graph, 'pos')
        new_pos = {}
        
        for node, (x, y) in pos.items():
            dx = x - x_center
            dy = y - y_center
            new_x = x_center + dx * zoom_factor
            new_y = y_center + dy * zoom_factor
            new_pos[node] = (new_x, new_y)
        
        nx.set_node_attributes(self.graph, new_pos, 'pos')
        self.zoom_factor *= zoom_factor
        self.redraw_graph()
    
    def show(self):
        """Show the visualization"""
        plt.show()
    
if __name__ == "__main__":
    # Updated usage example:
    visualizer = EnhancedGraphVisualizer()  # No file path needed - dialog will appear
    visualizer.show()