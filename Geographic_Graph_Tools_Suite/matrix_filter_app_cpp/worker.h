#ifndef WORKER_H
#define WORKER_H

#include <QThread>
#include <QString>
#include <QMap>
#include <vector>
#include "utils.h"

// Struct to represent a row in the CSV
struct Edge {
    int id;
    QString originName;
    Point origin;
    Point dest;
    double distance;
    QString rawCsvLine;
    bool keep = true;
};

class WorkerThread : public QThread {
    Q_OBJECT
public:
    WorkerThread(const QString& inputFile, QObject* parent = nullptr);

signals:
    void progressUpdated(int percent);
    void logMessage(const QString& msg);
    void finishedProcessing(const QString& outputFile);
    void error(const QString& title, const QString& msg);

protected:
    void run() override;

private:
    QString m_inputFile;
    std::vector<Edge> m_edges;

    void readCsv();
    void writeCsv(const QString& outputFile);
    void filterByKNearest(int k);
    void filterByIntersection();
    void filterByIntermediateNodes();
    void filterByStdevDistance(double multiplier = 2.0);
    void recoverBidirectionalEdges();
};

#endif // WORKER_H