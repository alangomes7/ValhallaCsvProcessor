#include "mainwindow.h"
#include <QFileDialog>
#include <QMessageBox>
#include <QDateTime>

MainWindow::MainWindow(QWidget *parent) :
    QMainWindow(parent),
    ui(new Ui::MainWindow),
    worker(nullptr)
{
    ui->setupUi(this);

    connect(ui->browse_button, &QPushButton::clicked, this, &MainWindow::onBrowseClicked);
    connect(ui->run_button, &QPushButton::clicked, this, &MainWindow::onRunClicked);
    connect(ui->clear_log_button, &QPushButton::clicked, ui->log_text, &QTextEdit::clear);
}

MainWindow::~MainWindow() {
    if (worker && worker->isRunning()) {
        worker->wait();
    }
    delete ui;
}

void MainWindow::onBrowseClicked() {
    QString fileName = QFileDialog::getOpenFileName(this, "Select CSV file", "", "CSV Files (*.csv)");
    if (!fileName.isEmpty()) {
        ui->file_path_edit->setText(fileName);
        appendLog("Selected file: " + fileName);
    }
}

void MainWindow::onRunClicked() {
    QString file = ui->file_path_edit->text();
    if (file.isEmpty()) {
        QMessageBox::warning(this, "Error", "Please select a valid CSV file");
        return;
    }

    if (worker && worker->isRunning()) return;

    ui->progress_bar->setValue(0);
    worker = new WorkerThread(file, this);

    connect(worker, &WorkerThread::progressUpdated, ui->progress_bar, &QProgressBar::setValue);
    connect(worker, &WorkerThread::logMessage, this, &MainWindow::appendLog);
    connect(worker, &WorkerThread::finishedProcessing, this, &MainWindow::onWorkerFinished);
    connect(worker, &WorkerThread::error, this, &MainWindow::onWorkerError);
    
    worker->start();
}

void MainWindow::appendLog(const QString& msg) {
    QString timestamp = QDateTime::currentDateTime().toString("HH:mm:ss");
    ui->log_text->append("[" + timestamp + "] " + msg);
}

void MainWindow::onWorkerFinished(const QString& outputFile) {
    QMessageBox::information(this, "Success", "Filtering completed!\nSaved to: " + outputFile);
    worker->deleteLater();
    worker = nullptr;
}

void MainWindow::onWorkerError(const QString& title, const QString& msg) {
    QMessageBox::critical(this, title, msg);
    ui->progress_bar->setValue(0);
    worker->deleteLater();
    worker = nullptr;
}