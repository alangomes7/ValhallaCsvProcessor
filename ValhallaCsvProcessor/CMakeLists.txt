cmake_minimum_required(VERSION 3.31)

# Project definition
project(ValhallaCsvProcessor LANGUAGES CXX)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ==============================================================================
# 1. Output Setup
# ==============================================================================
# Define a "out" folder in the project root for the final standalone files
set(CMAKE_INSTALL_PREFIX "${CMAKE_SOURCE_DIR}/out/${CMAKE_BUILD_TYPE}")

# ==============================================================================
# 2. Qt6 Setup
# ==============================================================================
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_INCLUDE_CURRENT_DIR ON)

find_package(Qt6 6.10 REQUIRED COMPONENTS Core Gui Quick Qml Widgets Tools Core5Compat)

# ==============================================================================
# 3. Sources & Targets
# ==============================================================================

set(PROJECT_SOURCES
    main.cpp
    src/Utils/Utils.cpp
    src/Ui/ValhallaCsvProcessor.cpp
    src/Core/ValhallaWorker.cpp
)

set(PROJECT_HEADERS
    src/Utils/Utils.h
    src/Ui/ValhallaCsvProcessor.h
    src/Core/ValhallaWorker.h
)

set(PROJECT_UI_FILES
    src/Resources/Forms/ValhallaCsvProcessor.ui
)

set(PROJECT_RESOURCE_FILES
    src/Resources/ValhallaCsvProcessor.qrc
)

# Create Executable
qt_add_executable(ValhallaCsvProcessor WIN32
    MANUAL_FINALIZATION
    ${PROJECT_SOURCES}
    ${PROJECT_HEADERS}
    ${PROJECT_UI_FILES}
    ${PROJECT_RESOURCE_FILES}
)

# ADD THIS BLOCK: Tell AutoUic where to find .ui files
set_target_properties(ValhallaCsvProcessor PROPERTIES 
    AUTOUIC_SEARCH_PATHS "${CMAKE_CURRENT_SOURCE_DIR}/src/Resources/Forms"
)

# ==============================================================================
# 4. Debugging & Compiler Flags
# ==============================================================================
if(MSVC)
    target_compile_options(ValhallaCsvProcessor PRIVATE 
        $<$<CONFIG:Debug>:/Zi> 
        $<$<CONFIG:Debug>:/Od>
        $<$<CONFIG:Debug>:/Ob0>
        $<$<CONFIG:Debug>:/RTC1>
    )
    target_link_options(ValhallaCsvProcessor PRIVATE 
        $<$<CONFIG:Debug>:/DEBUG> 
        $<$<CONFIG:Debug>:/OPT:NOREF> 
        $<$<CONFIG:Debug>:/OPT:NOICF>
    )
endif()

if(CMAKE_BUILD_TYPE STREQUAL "Debug")
  target_compile_definitions(ValhallaCsvProcessor PRIVATE QT_QML_DEBUG)
endif()

target_include_directories(ValhallaCsvProcessor PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_BINARY_DIR}
)

target_link_libraries(ValhallaCsvProcessor PRIVATE
    Qt6::Core Qt6::Gui Qt6::Widgets Qt6::Quick Qt6::Qml Qt6::Core5Compat
)

qt_finalize_executable(ValhallaCsvProcessor)

# ==============================================================================
# 5. Installation & Deployment (FIXED FOR STANDALONE)
# ==============================================================================
install(TARGETS ValhallaCsvProcessor
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
)