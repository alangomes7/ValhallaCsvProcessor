#include "ValhallaCsvProcessor.h"
#include "ui_ValhallaCsvProcessor.h"
#include "src/Core/ValhallaWorker.h"
#include "src/Utils/Utils.h"

#include <QFileDialog>
#include <QDateTime>
#include <QScrollBar>
#include <QDesktopServices>
#include <QUrl>
#include <QDir>
#include <QElapsedTimer>
#include <qmutex.h>

ValhallaCsvProcessor::ValhallaCsvProcessor(QWidget* parent)
    : QMainWindow(parent), ui(new Ui::ValhallaCsvProcessorClass) {
    ui->setupUi(this);
    QThreadPool::globalInstance()->setMaxThreadCount(QThread::idealThreadCount());

    connect(ui->pushButtonBrowse, &QPushButton::clicked, this, &ValhallaCsvProcessor::on_selectFileButton_clicked);
    connect(ui->pushButtonRun, &QPushButton::clicked, this, &ValhallaCsvProcessor::on_runButton_clicked);
    connect(ui->pushButtonClearLog, &QPushButton::clicked, this, [=]() {
        ui->plainTextEditLog->clear();
        });
    connect(ui->pushButtonOpenOutput, &QPushButton::clicked, this, [=]() {
        if (!m_filePath.isEmpty()) {
            QFileInfo fileInfo(m_filePath);
            QString folder = fileInfo.absolutePath();
            QString outputDir = folder + "/output";
            QDir().mkpath(outputDir);
            QDesktopServices::openUrl(QUrl::fromLocalFile(outputDir));
        }
        });

    ui->progressBar->setValue(0);
}

ValhallaCsvProcessor::~ValhallaCsvProcessor() {
    QFile logFile(logFilePath);
    QString textLog = ui->plainTextEditLog->toPlainText();
    if (logFile.open(QIODevice::Append | QIODevice::Text)) {
        QTextStream logfileOut(&logFile);
        logfileOut << textLog;
    }
    delete ui;
}

void ValhallaCsvProcessor::on_selectFileButton_clicked() {
    m_filePath = QFileDialog::getOpenFileName(this, "Select CSV File", "", "*.csv");
    if (!m_filePath.isEmpty()) {
        ui->labelInputFile->setText(m_filePath);
        QFileInfo fileInfo(m_filePath);
        QString folder = fileInfo.absolutePath();
        QString time = timestamp();

        QString logDir = folder + "/logs";
        QString outputDir = folder + "/output";

        // Create directories if they don't exist
        QDir().mkpath(logDir);
        QDir().mkpath(outputDir);

        logFilePath = logDir + "/log_" + time + ".txt";
        outputFilePath = outputDir + "/output_" + time + ".csv";
    }
}

void ValhallaCsvProcessor::on_runButton_clicked() {
    if (!m_running) {
        if (m_filePath.isEmpty()) return;
        m_running = true;
        ui->pushButtonRun->setText("Stop");
        processCSV(m_filePath);
    }
    else {
        m_running = false;
        emit stopRunning();
        ui->pushButtonRun->setText("Start");
    }
}

void ValhallaCsvProcessor::processCSV(const QString& filePath) {
    writeOutputHeader(outputFilePath);

    QFile file(filePath);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) return;

    QTextStream in(&file);
    QStringList lines;
    in.readLine(); // Skip original header
    while (!in.atEnd()) lines.append(in.readLine());

    int total = lines.size();
    ui->progressBar->setMaximum(total);
    ui->progressBar->setValue(0);
    int* count = new int(0);
    QElapsedTimer* timer = new QElapsedTimer();
    timer->start();

    // Shared data structure
    QSharedPointer<QVector<QString>> accumulatedLines(new QVector<QString>());
    QMutex* writeMutex = new QMutex();
    int flushLines = 5000, linesCount = 0;
    for (const QString& line : lines) {
        linesCount++;
        auto* task = new ValhallaWorker(line, outputPath(), endpoint(), accumulatedLines, writeMutex);

        // Connect the stop signal
        connect(this, &ValhallaCsvProcessor::stopRunning, task, &ValhallaWorker::stopRunning);
        connect(task, &ValhallaWorker::log, this, [=](const QString& msg) {
            logMessage(msg);
            ui->progressBar->setValue(++(*count));

            // Flush to file every 5% of progress
            if (linesCount % flushLines == 0) {
                QMutexLocker locker(writeMutex);
                if (!accumulatedLines->isEmpty()) {
                    writeAccumulatedLines(outputPath(), *accumulatedLines);
                    accumulatedLines->clear();
                }
            }

            // Final flush after all lines are processed
            if (ui->progressBar->value() == total) {
                if (!accumulatedLines->isEmpty()) {
                    QMutexLocker locker(writeMutex);
                    awaitDelay(300);
                    writeAccumulatedLines(outputPath(), *accumulatedLines);
                    accumulatedLines->clear();
                }

                qint64 elapsedMs = timer->elapsed();
                QString elapsed = QString("Processing completed in %1 seconds (%2 ms)")
                    .arg(elapsedMs / 1000.0, 0, 'f', 2)
                    .arg(elapsedMs);
                logMessage(elapsed);

                delete timer;
                delete count;
                delete writeMutex;
                ui->pushButtonRun->setText("Start");
            }
            });
        QThreadPool::globalInstance()->start(task);
    }
}


void ValhallaCsvProcessor::writeAccumulatedLines(const QString& filePath, const QVector<QString>& lines) {
    QFile outFile(filePath);
    if (outFile.open(QIODevice::Append | QIODevice::Text)) {
        QTextStream outputFile(&outFile);
        for (const QString& line : lines) {
            outputFile << line;
        }
    }
}

void ValhallaCsvProcessor::writeOutputHeader(const QString& filePath) {
    QFile file(filePath);
    if (file.open(QIODevice::WriteOnly | QIODevice::Text)) {
        QTextStream out(&file);
        out << "Combinations,Origin - name,Origin - Latitude,Origin - Longitude,"
            << "Destination - name,Destination - Latitude,Destination - Longitude,"
            << "URL de Solic.,Distance Drive (meters),Duration Drive (seconds),Status,Status Info\n";
    }
}

void ValhallaCsvProcessor::logMessage(const QString& msg) {
    QString timeStamped = timestampLogs() + " - " + msg;
    ui->plainTextEditLog->appendPlainText(timeStamped);
    ui->plainTextEditLog->verticalScrollBar()->setValue(ui->plainTextEditLog->verticalScrollBar()->maximum());
}

QString ValhallaCsvProcessor::outputPath() const {
    return outputFilePath;
}

QString ValhallaCsvProcessor::endpoint() const {
    m_endpoint = ui->lineEditServer->text() + ui->lineEditOperation->text();
    return m_endpoint;
}

QString ValhallaCsvProcessor::logPath() const {
    return logFilePath;
}
