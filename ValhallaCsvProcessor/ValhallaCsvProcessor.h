#pragma once
#include <QtWidgets/QMainWindow>
#include "ui_ValhallaCsvProcessor.h"
#include <QThreadPool>
#include <QFile>
#include <QTextStream>

class ValhallaCsvProcessor : public QMainWindow {
    Q_OBJECT

public:
    ValhallaCsvProcessor(QWidget* parent = nullptr);
    ~ValhallaCsvProcessor();
    static void writeAccumulatedLines(const QString& filePath, const QVector<QString>& lines);

signals:
    void stopRunning();

private slots:
    void on_selectFileButton_clicked();
    void on_runButton_clicked();
    void processCSV(const QString& filePath);
    void logMessage(const QString& msg);

    QString outputPath() const;

    QString endpoint() const;

    QString logPath() const;

private:
    Ui::ValhallaCsvProcessorClass* ui;
    bool m_running = false;
    QString m_filePath;
    QString logFilePath;
    QString outputFilePath;
    mutable QString m_endpoint;
    void writeOutputHeader(const QString& filePath);
};
