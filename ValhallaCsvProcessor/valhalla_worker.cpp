#include "valhalla_worker.h"
#include "utils.h"
#include "ValhallaCsvProcessor.h"

#include <QNetworkAccessManager>
#include <QNetworkRequest>
#include <QNetworkReply>
#include <QEventLoop>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QFile>
#include <QTextStream>
#include <QStringList>

ValhallaWorker::ValhallaWorker(const QString& line, const QString& outPath, 
    QSharedPointer<QVector<QString>> accumulatedLines, QMutex* writeMutex){
    m_csvLine = line;
    m_outputPath = outPath;
    m_accumulatedLines = accumulatedLines;
    m_writeMutex = writeMutex;
    setAutoDelete(true);
};

void ValhallaWorker::run() {
    processLine();
}

QAtomicInt ValhallaWorker::lineCounter(0);

QJsonObject ValhallaWorker::sendRequest(const QString& urlStr, const QJsonObject& body, QString& errorInfo) {
    QUrl url(urlStr);
    QNetworkRequest request(url);
    request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");

    QNetworkAccessManager* manager = new QNetworkAccessManager();
    QEventLoop loop;
    QNetworkReply* reply = manager->post(request, QJsonDocument(body).toJson());

    QObject::connect(reply, &QNetworkReply::finished, &loop, &QEventLoop::quit);
    loop.exec();

    QJsonObject jsonResponse;
    if (reply->error() == QNetworkReply::NoError) {
        QByteArray responseData = reply->readAll();
        jsonResponse = QJsonDocument::fromJson(responseData).object();
    }
    else {
        errorInfo = reply->errorString();
    }

    reply->deleteLater();
    manager->deleteLater();
    return jsonResponse;
}

void ValhallaWorker::processResponse(const QJsonObject& json, QString& distance, QString& duration, QString& info) {
    if (json.contains("trip")) {
        QJsonObject trip = json["trip"].toObject();
        QJsonObject summary = trip["summary"].toObject();
        distance = QString::number(summary["length"].toDouble() * 1000); // km to meters
        duration = QString::number(summary["time"].toDouble());
    }
    else {
        info = "Resposta inválida do servidor.";
    }
}

void ValhallaWorker::processLine() {
    QStringList parts = m_csvLine.split(',');

    QString oLat = parts[2], oLon = parts[3];
    QString dLat = parts[5], dLon = parts[6];

    QString url = "http://localhost:8002/route";
    QJsonObject body{
        { "costing", "auto" },
        { "locations", QJsonArray {
            QJsonObject{ { "lat", oLat.toDouble() }, { "lon", oLon.toDouble() } },
            QJsonObject{ { "lat", dLat.toDouble() }, { "lon", dLon.toDouble() } }
        }}
    };

    QString errorInfo;
    QJsonObject jsonResponse = sendRequest(url, body, errorInfo);

    QString distance, duration, status, info, infoLog;
    QString outputLine;

    if (errorInfo.isEmpty()) {
        processResponse(jsonResponse, distance, duration, info);
        infoLog += info + distance + " , " + duration;

        outputLine = parts[0] + "," + parts[1] + "," + parts[2] + "," + parts[3] + "," + parts[4] + "," +
            parts[5] + "," + parts[6] + "," + url + "," + distance + "," + duration + "," +
            "OK" + "," + info + "\n";
        status = "OK";
    }
    else {
        status = "Error";
        infoLog = errorInfo;
        outputLine = parts[0] + "," + parts[1] + "," + parts[2] + "," + parts[3] + "," + parts[4] + "," +
            parts[5] + "," + parts[6] + "," + url + ",,," + status + "," + errorInfo + "\n";
    }

    // Add to accumulated lines with thread-safe access
    {
        QMutexLocker locker(m_writeMutex);
        m_accumulatedLines->append(outputLine);

        // Check if we've reached the batch size
        if (m_accumulatedLines->size() >= 1000) {
            ValhallaCsvProcessor::writeAccumulatedLines(m_outputPath, *m_accumulatedLines);
            m_accumulatedLines->clear();
        }
    }
    QString logMessage = QString("Processed: [%1] %2 -> %3 (%4)").arg(status, parts[1], parts[4], infoLog);
    emit log(logMessage);
}