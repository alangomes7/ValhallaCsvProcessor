#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include "ui_csv_graph_distance_filter.h"
#include "worker.h"

class MainWindow : public QMainWindow {
    Q_OBJECT

public:
    explicit MainWindow(QWidget *parent = nullptr);
    ~MainWindow();

private slots:
    void onBrowseClicked();
    void onRunClicked();
    void appendLog(const QString& msg);
    void onWorkerFinished(const QString& outputFile);
    void onWorkerError(const QString& title, const QString& msg);

private:
    Ui::MainWindow *ui;
    WorkerThread *worker;
};

#endif // MAINWINDOW_H