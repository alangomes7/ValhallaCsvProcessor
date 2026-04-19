import os
import logging
import pandas as pd
import numpy as np
import heapq
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtCore import QThread, pyqtSignal

# Import helper functions
from utils import calculate_bearing, do_intersect

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
            # Log Setup will now use the 'log/' subdirectory
            self.logger, self.log_path, file_handler = self.setup_logging(directory)
            self.log_message.emit(f"Processing file: {self.input_file}")

            # Execute processing steps
            # Added filter_by_intersection at the end of the pipeline
            steps = [
                (lambda: self.read_csv(self.input_file), "Reading CSV file..."),
                (self.filter_by_radius, "Applying distance threshold filter..."),
                (self.filter_by_standard_deviation, "Applying standard deviation filter..."),
                (self.filter_by_direction, "Applying direction filter to avoid overlaps..."),
                (self.filter_by_outlier2, "Applying outlier filter..."),
                (self.filter_by_intermediate_nodes, "Applying intermediate routing (Transitive Reduction)..."),
                (self.filter_by_intersection, "Applying intersection filter (removing longest intersecting edges)..."),
                (lambda df: self.save_filtered_data(df, self.input_file), "Saving results...")
            ]

            df = pd.DataFrame()
            progress = 0
            progress_increment = 100 // len(steps)

            # --- FIXED LOOP LOGIC ---
            for i, (step, message) in enumerate(steps):
                self.log_message.emit(message)
                
                # If the DataFrame is empty and we are past the loading stage (index > 0), 
                # we can skip processing or just pass the empty DF.
                if i > 0 and df.empty:
                     self.log_message.emit(f"⚠️ Data is empty at step {i+1}. Skipping processing logic.")
                     df = step(df) 
                elif i == 0:
                    # The first step (read_csv) takes no arguments in the lambda
                    df = step()
                else:
                    # All other steps take df as an argument
                    df = step(df)

                progress += progress_increment
                self.progress_updated.emit(min(progress, 90))
            # ------------------------

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

    def setup_logging(self, input_dir):
        """Create a log file in a 'log' subdirectory and return the logger."""
        # Create log directory if it doesn't exist
        log_dir = os.path.join(input_dir, "log")
        os.makedirs(log_dir, exist_ok=True)

        timestamp = self.get_timestamp()
        log_filename = f"filter_matrix_distance_log_{timestamp}.log"
        log_path = os.path.join(log_dir, log_filename)

        logger = logging.getLogger("matrix_filter")
        logger.setLevel(logging.INFO)
        
        # Clear previous handlers if any
        if logger.hasHandlers():
            logger.handlers.clear()

        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        return logger, log_path, file_handler

    def get_timestamp(self):
        """Return current timestamp string for file naming."""
        return datetime.now().strftime("%y%m%d_%H%M%S")

    def read_csv(self, filepath):
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

    # --- Filtering Logic Methods ---

    def filter_by_radius(self, df):
        """Filter edges based on dynamic radius from origin points"""
        if df.empty:
            return df

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

        if not result_rows:
            self.log_message.emit("⚠️ Warning: Radius filter removed ALL data.")
            return pd.DataFrame(columns=df.columns)

        return pd.DataFrame(result_rows)

    def process_origin_radius(self, origin, group):
        group = group.copy()
        group = group[group[self.config["distance_column"]] > 0]

        if len(group) == 0:
            self.log_message.emit(f"Origin {origin}: No valid edges after removing zero-distance connections.")
            return []

        distance_col = self.config["distance_column"]
        initial_radius = self.config["distance_filter_initial_distance"]
        radius_step = self.config["distance_filter_step"]
        min_edges = self.config["distance_filter_min_edges"]
        max_radius = 100000  # 100 km

        group_sorted = group.sort_values(distance_col)

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

    def filter_by_outlier(self, origin, group, radius_step, multiplier=3, distance_outlier=-1):
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
                distance_outlier = multiplier * radius_step
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
        if df.empty:
            return df

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

        if not result_rows:
            return pd.DataFrame(columns=df.columns)

        return pd.DataFrame(result_rows)

    def process_origin_std_dev(self, origin, group):
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
                break

            max_idx = working_group[distance_col].idxmax()
            working_group = working_group.drop(index=max_idx)
            attempt += 1

        if final_group is None:
            final_group = working_group
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

        final_group_sorted = final_group.sort_values(distance_col)
        return final_group_sorted.to_dict('records')

    def filter_by_direction(self, df):
        """Main direction filter."""
        if df.empty:
            return df

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

        if not result_rows:
            return pd.DataFrame(columns=df.columns)

        return pd.DataFrame(result_rows)

    def process_origin_direction(self, origin, group):
        min_angle = self.config["direction_based_edge_degree"]
        min_edges = self.config["direction_based_min_degree_edges"] - 1

        edges = []
        for _, row in group.iterrows():
            try:
                angle = calculate_bearing(
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

        edges.sort(key=lambda x: x['distance'])

        while len(edges) >= min_edges:
            problematic_pairs = []
            for i in range(len(edges)):
                for j in range(i + 1, len(edges)):
                    angle_diff = abs((edges[i]['angle'] - edges[j]['angle'] + 180) % 360 - 180)
                    if angle_diff < min_angle:
                        problematic_pairs.append((i, j, edges[i]['distance'] + edges[j]['distance']))

            if not problematic_pairs:
                break

            worst_pair = max(problematic_pairs, key=lambda x: x[2])
            i, j, _ = worst_pair

            if edges[i]['distance'] > edges[j]['distance']:
                removed_edge = edges.pop(i)
            else:
                removed_edge = edges.pop(j)

            self.log_message.emit(
                f"Removed edge (distance: {removed_edge['distance']:.1f}m, angle: {removed_edge['angle']:.1f}°) "
                f"from {origin} as it didn't meet angle requirements with another edge"
            )

        result = [e['row'] for e in edges]

        if len(result) < min_edges:
            self.log_message.emit(
                f"Warning: Could not meet angle requirements for origin {origin} "
                f"while keeping minimum {min_edges} edges. Keeping {len(result)} edges."
            )

        return result

    def filter_by_outlier2(self, df):
        if df.empty:
            return df

        origin_cols = self.config["origin_columns"]
        distance_col = self.config["distance_column"]
        radius_step = self.config["distance_filter_step"]

        filtered_rows = []
        total_groups = len(df.groupby(origin_cols))
        processed = 0

        for origin, group in df.groupby(origin_cols):
            if isinstance(group, pd.DataFrame):
                group_dicts = group.to_dict('records')
            else:
                group_dicts = group

            group_sorted = group.sort_values(distance_col)
            filtered_group = self.filter_by_outlier(origin, group_sorted, radius_step, 1, 1000)

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

        if filtered_rows:
            result_df = pd.DataFrame(filtered_rows)
            result_df = result_df[df.columns]
            return result_df

        return pd.DataFrame(columns=df.columns)
    
    def filter_by_intersection(self, df):
        """Remove ALL intersecting edges globally (except return edges),
        cutting the longest ones first.
        """

        if df.empty or len(df) < 2:
            return df

        self.log_message.emit(
            "Applying GLOBAL intersection filter (cut longest, keep return edges)..."
        )

        # 1. Configuration
        olat = self.config["origin_lat_col"]
        olon = self.config["origin_lon_col"]
        dlat = self.config["destination_lat_col"]
        dlon = self.config["destination_lon_col"]
        dist = self.config["distance_column"]

        # 2. Sort ASCENDING (Shortest first)
        # This ensures Short edges get 'saved' first. 
        # If a Long edge intersects a Short one later, the Long one is removed.
        sorted_df = df.sort_values(dist, ascending=True)

        kept_rows = []
        kept_geoms = [] # Cache coordinates for faster lookup

        # 3. Use to_dict('records') to handle column names with spaces/symbols safely
        # This creates a list of dictionaries: [{'Origin - Latitude': 10, ...}, {...}]
        rows = sorted_df.to_dict('records')

        for row in rows:
            # Access by string key (safe for spaces/hyphens)
            p1 = (row[olat], row[olon])
            q1 = (row[dlat], row[dlon])
            
            intersects = False

            # Compare against all previously kept (shorter) edges
            for p2, q2 in kept_geoms:
                
                # ✅ Allow shared endpoints (Connectivity)
                if p1 == p2 or p1 == q2 or q1 == p2 or q1 == q2:
                    continue

                # ✅ Allow return edges
                if p1 == q2 and q1 == p2:
                    continue

                # ❌ Check Geometric Intersection
                if do_intersect(p1, q1, p2, q2):
                    intersects = True
                    break

            if not intersects:
                kept_rows.append(row)
                kept_geoms.append((p1, q1))

        # 4. Reconstruct DataFrame
        result = pd.DataFrame(kept_rows)
        
        # Restore column order if necessary (to_dict might reshuffle keys visually, 
        # though DataFrame constructor usually fixes it)
        if not result.empty:
            result = result[df.columns]

        self.log_message.emit(
            f"Intersection filter complete. Kept {len(result)} out of {len(df)} edges."
        )

        return result
    
    def filter_by_intermediate_nodes(self, df):
        """
        Removes direct edges if a path through intermediate nodes exists
        that is shorter than or roughly equal to the direct edge.
        This forces the graph to behave like a real-world road network.
        """
        if df.empty or len(df) < 2:
            return df

        self.log_message.emit("Applying Intermediate Nodes (Transitive Reduction) filter...")

        olat = self.config["origin_lat_col"]
        olon = self.config["origin_lon_col"]
        dlat = self.config["destination_lat_col"]
        dlon = self.config["destination_lon_col"]
        dist_col = self.config["distance_column"]

        # 1. Build an adjacency list for the directed graph
        # adj[u][v] = {'dist': distance, 'idx': dataframe_index}
        adj = {}
        
        # Using zip is much faster than iterrows() for large DataFrames
        for idx, u_lat, u_lon, v_lat, v_lon, d in zip(
            df.index, df[olat], df[olon], df[dlat], df[dlon], df[dist_col]
        ):
            u = (u_lat, u_lon)
            v = (v_lat, v_lon)
            
            if u not in adj:
                adj[u] = {}
            
            # If there are duplicate edges, keep the shortest one
            if v not in adj[u] or d < adj[u][v]['dist']:
                adj[u][v] = {'dist': d, 'idx': idx}

        edges_to_remove = set()
        
        # Tolerance factor: 1.05 allows an intermediate path to be up to 5% longer 
        # than the direct line, which is standard for real-world road deviations.
        tolerance = 1.05 

        processed = 0
        total_edges = len(df)
        
        # 2. Check each edge to see if a viable intermediate path exists
        for u in adj:
            for v, data in adj[u].items():
                direct_dist = data['dist']
                max_allowed_dist = direct_dist * tolerance
                
                # Dijkstra's algorithm to find a multi-hop path from u to v
                # EXCLUDING the direct edge u -> v
                queue = [(0, u)]
                visited = set()
                has_alternative = False
                
                while queue:
                    current_dist, current_node = heapq.heappop(queue)
                    
                    if current_dist > max_allowed_dist:
                        break # Stop searching if we exceeded the threshold
                        
                    if current_node == v and current_dist > 0:
                        has_alternative = True
                        break
                        
                    if current_node in visited:
                        continue
                    visited.add(current_node)
                    
                    for neighbor, n_data in adj.get(current_node, {}).items():
                        # SKIP the direct edge we are currently evaluating
                        if current_node == u and neighbor == v:
                            continue
                            
                        new_dist = current_dist + n_data['dist']
                        if new_dist <= max_allowed_dist:
                            heapq.heappush(queue, (new_dist, neighbor))
                
                if has_alternative:
                    edges_to_remove.add(data['idx'])
                    
            processed += len(adj[u])
            if processed % 500 == 0:
                self.log_message.emit(f"Processed {processed}/{total_edges} edges for intermediate routing...")

        # 3. Filter the DataFrame by dropping the redundant long lines
        result = df.drop(index=list(edges_to_remove))
        
        self.log_message.emit(
            f"Intermediate Node filter complete. Removed {len(edges_to_remove)} direct bypass edges. "
            f"Kept {len(result)} edges."
        )
        
        return result

    def save_filtered_data(self, df, input_path):
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