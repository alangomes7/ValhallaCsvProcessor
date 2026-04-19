#include "worker.h"
#include <QFile>
#include <QTextStream>
#include <QFileInfo>
#include <QDir>
#include <QDateTime>
#include <algorithm>
#include <queue>
#include <unordered_map>
#include <set>
#include <cmath>
#include <numeric>

WorkerThread::WorkerThread(const QString& inputFile, QObject* parent)
    : QThread(parent), m_inputFile(inputFile) {}

void WorkerThread::run() {
    try {
        emit logMessage("Starting processing...");
        readCsv();

        filterByStdevDistance(2.0); 
        emit progressUpdated(20);

        filterByKNearest(10);
        emit progressUpdated(40);

        filterByIntermediateNodes();
        emit progressUpdated(70);

        filterByIntersection();
        emit progressUpdated(90);

        // --- NEW STEP: Recover the reverse edges ---
        recoverBidirectionalEdges();
        emit progressUpdated(95);
        // -------------------------------------------

        QFileInfo info(m_inputFile);
        QString timestamp = QDateTime::currentDateTime().toString("yyMMdd_HHmmss");
        QString outPath = info.absolutePath() + "/" + info.baseName() + "_filtered_" + timestamp + ".csv";
        
        writeCsv(outPath);
        emit progressUpdated(100);
        emit finishedProcessing(outPath);

    } catch (const std::exception& e) {
        emit error("Processing Error", e.what());
    }
}

void WorkerThread::readCsv() {
    QFile file(m_inputFile);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        throw std::runtime_error("Cannot open CSV file");
    }

    QTextStream in(&file);
    QString header = in.readLine(); // skip header for parsing, but save it in writeCsv
    int id = 0;

    while (!in.atEnd()) {
        QString line = in.readLine();
        QStringList cols = line.split(','); 
        
        // Safety check: Ensure the row has at least up to the Distance column (index 8)
        if(cols.size() < 9) continue; 

        Edge e;
        e.id = id++;
        e.rawCsvLine = line;
        
        // Updated mapping to match your expected CSV format:
        // 0: Combinations
        // 1: Origin - name
        // 2: Origin - Latitude
        // 3: Origin - Longitude
        // 4: Destination - name
        // 5: Destination - Latitude
        // 6: Destination - Longitude
        // 7: URL de Solic.
        // 8: Distance Drive (meters)
        
        e.originName = cols[1];
        e.origin.lat = cols[2].toDouble();
        e.origin.lon = cols[3].toDouble();
        e.dest.lat = cols[5].toDouble();
        e.dest.lon = cols[6].toDouble();
        e.distance = cols[8].toDouble();
        
        m_edges.push_back(e);
    }
    emit logMessage(QString("Loaded %1 edges.").arg(m_edges.size()));
}

void WorkerThread::filterByIntersection() {
    emit logMessage("Applying Intersection Filter (cutting longest crossing edges)...");
    
    // FIX: Extract active edges as pointers so we don't destroy the original m_edges ordering
    std::vector<Edge*> activeEdges;
    for (auto& edge : m_edges) {
        if (edge.keep) activeEdges.push_back(&edge);
    }

    // Sort ascending by distance (shortest first)
    std::sort(activeEdges.begin(), activeEdges.end(), [](const Edge* a, const Edge* b){
        return a->distance < b->distance;
    });

    std::vector<Edge*> keptEdges;

    for (Edge* edge : activeEdges) {
        bool intersects = false;
        
        for (Edge* kept : keptEdges) {
            // Allow shared endpoints (connectivity)
            if (edge->origin == kept->origin || edge->origin == kept->dest ||
                edge->dest == kept->origin || edge->dest == kept->dest) {
                continue;
            }

            if (Utils::doIntersect(edge->origin, edge->dest, kept->origin, kept->dest)) {
                intersects = true;
                break;
            }
        }

        if (!intersects) {
            keptEdges.push_back(edge);
        } else {
            edge->keep = false;
        }
    }
    emit logMessage(QString("Intersection filter kept %1 edges.").arg(keptEdges.size()));
}

void WorkerThread::filterByIntermediateNodes() {
    emit logMessage("Applying Transitive Reduction (Intermediate Nodes)...");

    // Point hash for unordered_map
    auto hash = [](const Point& p) { 
        return std::hash<double>()(p.lat) ^ (std::hash<double>()(p.lon) << 1); 
    };
    auto eq = [](const Point& p1, const Point& p2) { 
        return p1 == p2; 
    };

    using AdjList = std::unordered_map<Point, std::vector<Edge*>, decltype(hash), decltype(eq)>;
    AdjList adj(100, hash, eq);

    for (auto& edge : m_edges) {
        if (edge.keep) adj[edge.origin].push_back(&edge);
    }

    double tolerance = 1.05;
    int removed = 0;

    for (auto& edge : m_edges) {
        if (!edge.keep) continue;

        double maxAllowed = edge.distance * tolerance;
        
        // Dijkstra setup
        using PDI = std::pair<double, Point>;
        std::priority_queue<PDI, std::vector<PDI>, std::greater<PDI>> pq;
        std::unordered_map<Point, double, decltype(hash), decltype(eq)> dists(100, hash, eq);

        pq.push({0.0, edge.origin});
        dists[edge.origin] = 0.0;
        bool hasAlternative = false;

        while (!pq.empty()) {
            auto [currentDist, currentPoint] = pq.top();
            pq.pop();

            if (currentDist > maxAllowed) break;
            if (currentPoint == edge.dest && currentDist > 0) {
                hasAlternative = true;
                break;
            }

            if (currentDist > dists[currentPoint]) continue;

            for (Edge* neighborEdge : adj[currentPoint]) {
                
                if (!neighborEdge->keep) continue;
                // Skip the direct edge we are evaluating
                if (currentPoint == edge.origin && neighborEdge->dest == edge.dest) continue;

                double newDist = currentDist + neighborEdge->distance;
                if (newDist <= maxAllowed) {
                    if (dists.find(neighborEdge->dest) == dists.end() || newDist < dists[neighborEdge->dest]) {
                        dists[neighborEdge->dest] = newDist;
                        pq.push({newDist, neighborEdge->dest});
                    }
                }
            }
        }

        if (hasAlternative) {
            edge.keep = false;
            removed++;
        }
    }
    emit logMessage(QString("Intermediate node filter removed %1 edges.").arg(removed));
}

void WorkerThread::filterByStdevDistance(double multiplier) {
    emit logMessage(QString("Applying Standard Deviation Distance Filter (Multiplier: %1)...").arg(multiplier));

    std::vector<double> activeDistances;
    activeDistances.reserve(m_edges.size());
    
    for (const auto& edge : m_edges) {
        if (edge.keep) {
            activeDistances.push_back(edge.distance);
        }
    }

    if (activeDistances.empty()) return;

    // 1. Calculate Mean
    double sum = std::accumulate(activeDistances.begin(), activeDistances.end(), 0.0);
    double mean = sum / activeDistances.size();

    // 2. Calculate Standard Deviation (Population)
    double sqSum = 0.0;
    for (double dist : activeDistances) {
        sqSum += (dist - mean) * (dist - mean);
    }
    double stdev = std::sqrt(sqSum / activeDistances.size());

    // 3. Define the cutoff threshold
    double threshold = mean + (multiplier * stdev);
    
    emit logMessage(QString("   -> Mean: %1m | StDev: %2m | Cutoff Threshold: %3m")
                    .arg(mean, 0, 'f', 2)
                    .arg(stdev, 0, 'f', 2)
                    .arg(threshold, 0, 'f', 2));

    // 4. Remove edges that exceed the threshold
    int removedCount = 0;
    for (auto& edge : m_edges) {
        if (edge.keep && edge.distance > threshold) {
            edge.keep = false;
            removedCount++;
        }
    }

    emit logMessage(QString("StDev filter removed %1 outlier edges.").arg(removedCount));
}

void WorkerThread::recoverBidirectionalEdges() {
    emit logMessage("Recovering bidirectional edges to complete digraph...");

    // Create a fast lookup map using the (Origin, Dest) pair as the key
    std::map<std::pair<Point, Point>, Edge*> edgeMap;
    for (auto& edge : m_edges) {
        edgeMap[{edge.origin, edge.dest}] = &edge;
    }

    // Collect all edges that survived the filters
    std::vector<Edge*> currentlyKept;
    for (auto& edge : m_edges) {
        if (edge.keep) {
            currentlyKept.push_back(&edge);
        }
    }

    int recoveredCount = 0;

    // For every kept edge A -> B, ensure B -> A is also kept
    for (Edge* keptEdge : currentlyKept) {
        auto revIt = edgeMap.find({keptEdge->dest, keptEdge->origin});
        
        // If the reverse edge exists in the original dataset but was filtered out
        if (revIt != edgeMap.end()) {
            if (!revIt->second->keep) {
                revIt->second->keep = true; // Restore the reverse edge
                recoveredCount++;
            }
        }
    }

    emit logMessage(QString("Recovered %1 reverse edges.").arg(recoveredCount));
}

void WorkerThread::writeCsv(const QString& outputFile) {
    QFile file(outputFile);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Text)) return;
    QTextStream out(&file);

    // Dummy Header (use original header in real implementation)
    out << "Origin Name,Origin Lat,Origin Lon,Dest Lat,Dest Lon,Distance\n";

    int keptCount = 0;
    for (const auto& edge : m_edges) {
        if (edge.keep) {
            out << edge.rawCsvLine << "\n";
            keptCount++;
        }
    }
    emit logMessage(QString("Saved %1 edges to %2").arg(keptCount).arg(outputFile));
}

void WorkerThread::filterByKNearest(int k) {
    if (k <= 0) {
        emit logMessage("Invalid K value. Must be greater than 0.");
        return;
    }

    emit logMessage(QString("Applying K-Nearest filter (keeping top %1 shortest per origin)...").arg(k));

    std::map<QString, std::vector<Edge*>> edgesByOrigin;

    for (auto& edge : m_edges) {
        if (edge.keep) {
            edgesByOrigin[edge.originName].push_back(&edge);
        }
    }

    int removedCount = 0;

    for (auto& pair : edgesByOrigin) {
        auto& nodeEdges = pair.second;

        std::sort(nodeEdges.begin(), nodeEdges.end(),
                  [](const Edge* a, const Edge* b) {
                      return a->distance < b->distance;
                  });

        for (size_t i = static_cast<size_t>(k); i < nodeEdges.size(); ++i) {
            if (nodeEdges[i]->keep) {
                nodeEdges[i]->keep = false;
                removedCount++;
            }
        }
    }

    emit logMessage(QString("Distance filter removed %1 edges.").arg(removedCount));
}