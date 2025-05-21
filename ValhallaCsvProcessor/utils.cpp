#include "utils.h"
#include <QDateTime>
#include <QEventLoop>
#include <QTimer>

QString timestamp() {
    return QDateTime::currentDateTime().toString("yyyyMMdd_HHmmss");
}

QString timestampLogs() {
    return QDateTime::currentDateTime().toString("yyyy/MM/dd - HH:mm:ss:zzz");
}

void awaitDelay(int milliseconds) {
    QEventLoop loop;
    QTimer::singleShot(milliseconds, &loop, &QEventLoop::quit);
    loop.exec();
}
