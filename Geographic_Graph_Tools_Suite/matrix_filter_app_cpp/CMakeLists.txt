cmake_minimum_required(VERSION 3.16)
project(MatrixFilterApp VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

# Find required Qt6 modules
find_package(Qt6 6.10 REQUIRED COMPONENTS
    Core Gui Widgets
)

add_executable(MatrixFilterApp
    main.cpp
    mainwindow.cpp mainwindow.h
    worker.cpp worker.h
    utils.cpp utils.h
    csv_graph_distance_filter.ui
)

target_link_libraries(MatrixFilterApp PRIVATE Qt6::Core Qt6::Gui Qt6::Widgets)