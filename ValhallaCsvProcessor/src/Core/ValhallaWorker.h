#pragma once
#include <QObject>
#include <QRunnable>
#include <QString>
#include <QMutex>
#include <QJsonObject>
#include <QSharedPointer>
#include <QVector>
#include <QAtomicInt>
#include <atomic>

class ValhallaWorker : public QObject, public QRunnable {
    Q_OBJECT

public:
    ValhallaWorker(
        const QString& line,
        const QString& outPath,
        const QString& endpoint,
        QSharedPointer<QVector<QString>> accumulatedLines,
        QMutex* writeMutex
    );

    void run() override;
    QJsonObject sendRequest(const QString& urlStr, const QJsonObject& body, QString& errorInfo);
    void processResponse(const QJsonObject& json, QString& distance, QString& duration, QString& info);

signals:
    void log(const QString& message);

public slots:
    void stopRunning();  // Public slot for cancellation

private:
    QString m_csvLine;
    QString m_outputPath;
    QString m_endpoint;
    QSharedPointer<QVector<QString>> m_accumulatedLines;
    QMutex* m_writeMutex;
    std::atomic<bool> m_stopRequested{ false };  // Atomic flag for thread-safe cancellation
    static QAtomicInt lineCounter;

    void processLine();
};