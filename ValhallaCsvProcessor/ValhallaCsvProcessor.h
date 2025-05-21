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

private slots:
    void on_selectFileButton_clicked();
    void processCSV(const QString& filePath);
    void logMessage(const QString& msg);

    QString outputPath() const;

    QString logPath() const;

private:
    Ui::ValhallaCsvProcessorClass* ui;
    QString logFilePath;
    QString outputFilePath;
    void writeOutputHeader(const QString& filePath);
};
