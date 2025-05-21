#include "ValhallaCsvProcessor.h"
#include <QtWidgets/QApplication>

int main(int argc, char *argv[])
{
    QApplication a(argc, argv);
    ValhallaCsvProcessor w;
    w.show();
    return a.exec();
}
