#pragma once

#include <QObject>
#include <QRunnable>
#include <QString>
#include <qmutex.h>
#include <QJsonObject>
#include <QSharedPointer>
#include <QVector>
#include <QAtomicInt>


class ValhallaWorker : public QObject, public QRunnable {
    Q_OBJECT
    QSharedPointer<QVector<QString>> m_accumulatedLines;
    QMutex* m_writeMutex;
    static QAtomicInt lineCounter;

public:


    ValhallaWorker(const QString& line, const QString& outPath, 
        QSharedPointer<QVector<QString>> accumulatedLines, QMutex* writeMutex);

    void run() override;

    QJsonObject sendRequest(const QString& urlStr, const QJsonObject& body, QString& errorInfo);

    void processResponse(const QJsonObject& json, QString& distance, QString& duration, QString& info);

signals:
    void log(const QString& message);

private:
    QString m_csvLine;
    QString m_outputPath;
    void processLine();

};
