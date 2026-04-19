cmake_minimum_required(VERSION 3.21)

project(DisasterPathwayManager LANGUAGES CXX)

# ==============================================================================
# 1. Global C++ Settings
# ==============================================================================
# Enforce C++20 standard and disable compiler-specific extensions
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ==============================================================================
# 2. Output & Installation Paths
# ==============================================================================
# Route final installed files to out/Debug, out/Release, etc.
set(CMAKE_INSTALL_PREFIX "${CMAKE_SOURCE_DIR}/out/${CMAKE_BUILD_TYPE}")

# ==============================================================================
# 3. Qt6 Configuration
# ==============================================================================
# Enable Qt's automated build tools for MOC, RCC, and UIC
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_INCLUDE_CURRENT_DIR ON)

# Find required Qt6 modules
find_package(Qt6 6.10 REQUIRED COMPONENTS
    Core Gui Quick Qml Widgets Positioning Location Core5Compat Tools
)

# ==============================================================================
# 4. Build Optimizations
# ==============================================================================
# Reduce rebuild times by skipping certain dependency checks
set(CMAKE_SKIP_RULE_DEPENDENCY ON)
set(CMAKE_SKIP_INSTALL_RPATH ON)

# Enable Unity Builds (Jumbo builds) to significantly speed up compilation
set(CMAKE_UNITY_BUILD ON)
set(CMAKE_UNITY_BUILD_BATCH_SIZE 16)

# Exclude specific files from Unity Build if they cause conflicts or take too long
set_source_files_properties(
    src/Ui/DisasterPathwayManager.cpp
    src/Ui/Controller/MapViewController.cpp
    PROPERTIES SKIP_UNITY_BUILD_INCLUSION ON
)

# ==============================================================================
# 5. External Dependencies (Subdirectories)
# ==============================================================================
# Include OptFrame library, excluding it from the default build target
add_subdirectory(src/lib/optframe EXCLUDE_FROM_ALL)

# Ensure OptFrame is strictly excluded from default builds
if(TARGET optframe)
    set_property(TARGET optframe PROPERTY EXCLUDE_FROM_DEFAULT_BUILD ON)
endif()

# ==============================================================================
# 6. Project Files (Sources, Headers, UI, Resources)
# ==============================================================================
set(PROJECT_SOURCES
    # main
    main.cpp

    # Utils
    src/Utils/Utils.cpp

    # UI / Controllers
    src/Ui/DisasterPathwayManager.cpp
    src/Ui/UtilsUi/UtilsUi.cpp
    src/Ui/Controller/MapTabController.cpp
    src/Ui/Controller/SearchTabController.cpp
    src/Ui/Controller/RoutesTabController.cpp
    src/Ui/Controller/MapViewController.cpp
    src/Ui/DataManager/RouteSessionManager.cpp

    # Models
    src/Models/UtilsModel/UtilsModel.cpp
    src/Models/Atomic/Status.cpp
    src/Models/Atomic/Node.cpp
    src/Models/Atomic/Edge.cpp
    src/Models/Atomic/Vehicle.cpp
    src/Models/Graph.cpp
    src/Models/Way/Path.cpp
    src/Models/Way/Route.cpp
    src/Models/Dto/UtilsDto.cpp
    src/Models/Dto/EdgeDto.cpp
    src/Models/Dto/NodeDto.cpp

    # Optframe-based
    src/Core/Optframe/EngineSearch.cpp
    src/Core/Optframe/Utils/UtilsOptframe.cpp
    src/Core/Optframe/Problem/Context/Builder.cpp
    src/Core/Optframe/Problem/Context/Context.cpp
    src/Core/Optframe/Problem/Evaluator/Evaluator.cpp
    src/Core/Optframe/Problem/Representation/Definitions.cpp
    src/Core/Optframe/Problem/Constructive/Constructive.cpp
    # src/Core/Optframe/Problem/Constructive/CandidateListBuilder.cpp
    # src/Core/Optframe/Problem/Constructive/ConstructionResultBuilder.cpp
    # src/Core/Optframe/Problem/Constructive/RouteExpander.cpp
    # src/Core/Optframe/Problem/Constructive/RouteValidator.cpp
    # src/Core/Optframe/Search/InitialSearch/SteinerTSPBaseInitialSearch.cpp
    # src/Core/Optframe/Search/InitialSearch/SteinerTSPGreedyInitialSearch.cpp
    # src/Core/Optframe/Search/InitialSearch/SteinerTSPInitialSearchFactory.cpp
    # src/Core/Optframe/Search/InitialSearch/SteinerTSPSemiGreedyInitialSearch.cpp
    # src/Core/Optframe/Search/Neighborhood/SteinerTSPNeighborhoods.cpp
    # src/Core/Optframe/Search/Neighborhood/Moves/SteinerTSPDelete.cpp
    # src/Core/Optframe/Search/Neighborhood/Moves/SteinerTSPInsert.cpp
    # src/Core/Optframe/Search/Neighborhood/Moves/SteinerTSPReplace.cpp
    # src/Core/Optframe/Search/Neighborhood/Moves/SteinerTSPShift.cpp
    # src/Core/Optframe/Search/Neighborhood/Moves/SteinerTSPSwap.cpp
    # src/Core/Optframe/Search/Neighborhood/Moves/SteinerTSPTwoOpt.cpp
    # src/Core/Optframe/Search/LocalSearch/SteinerTSPLocalSearchManager.cpp
    # src/Core/Optframe/Search/LocalSearch/Improvements/SteinerTSPExtendedFirstImprovement.cpp
)

set(PROJECT_HEADERS
    # Utils
    src/Utils/Utils.h

    # UI
    src/Ui/DisasterPathwayManager.h
    src/Ui/UtilsUi/UtilsUi.h
    src/Ui/Controller/MapTabController.h
    src/Ui/Controller/SearchTabController.h
    src/Ui/Controller/RoutesTabController.h
    src/Ui/Controller/MapViewController.h
    src/Ui/DataManager/RouteSessionManager.h

    # Models
    src/Models/UtilsModel/UtilsModel.h
    src/Models/Atomic/Status.h
    src/Models/Atomic/Node.h
    src/Models/Atomic/Edge.h
    src/Models/Atomic/Vehicle.h
    src/Models/Graph.h
    src/Models/Way/Path.h
    src/Models/Way/Route.h
    src/Models/Dto/MapTypes.h
    src/Models/Dto/UtilsDto.h
    src/Models/Dto/EdgeInfoDto.h
    src/Models/Dto/EdgeDto.h
    src/Models/Dto/NodeDto.h

    # Optframe
    src/Core/Optframe/EngineSearch.h
    src/Core/Optframe/Utils/UtilsOptframe.h
    src/Core/Optframe/Problem/Context/Context.h
    src/Core/Optframe/Problem/Context/Builder.h
    src/Core/Optframe/Problem/Evaluator/Evaluator.h
    # src/Core/Optframe/Problem/Constructive/SteinerTSPConstructive.h
    # src/Core/Optframe/Problem/Constructive/CandidateListBuilder.h
    # src/Core/Optframe/Problem/Constructive/ConstructionResultBuilder.h
    # src/Core/Optframe/Problem/Constructive/RouteExpander.h
    src/Core/Optframe/Problem/Constructive/Constructive.h
    src/Core/Optframe/Problem/Representation/Representation.h
    src/Core/Optframe/Problem/Representation/Definitions.h
    # src/Core/Optframe/Search/InitialSearch/SteinerTSPBaseInitialSearch.h
    # src/Core/Optframe/Search/InitialSearch/SteinerTSPGreedyInitialSearch.h
    # src/Core/Optframe/Search/InitialSearch/SteinerTSPInitialSearchFactory.h
    # src/Core/Optframe/Search/InitialSearch/SteinerTSPSemiGreedyInitialSearch.h
    # src/Core/Optframe/Search/Neighborhood/SteinerTSPNeighborhoods.h
    # src/Core/Optframe/Search/Neighborhood/Moves/SteinerTSPDelete.h
    # src/Core/Optframe/Search/Neighborhood/Moves/SteinerTSPInsert.h
    # src/Core/Optframe/Search/Neighborhood/Moves/SteinerTSPReplace.h
    # src/Core/Optframe/Search/Neighborhood/Moves/SteinerTSPShift.h
    # src/Core/Optframe/Search/Neighborhood/Moves/SteinerTSPSwap.h
    # src/Core/Optframe/Search/Neighborhood/Moves/SteinerTSPTwoOpt.h
    # src/Core/Optframe/Search/LocalSearch/SteinerTSPLocalSearchManager.h
    # src/Core/Optframe/Search/LocalSearch/Improvements/SteinerTSPExtendedFirstImprovement.h
)

set(PROJECT_UI_FILES      src/Resources/Forms/DisasterPathwayManager.ui)
set(PROJECT_RESOURCE_FILES src/Resources/DisasterPathwayManager.qrc)

# ==============================================================================
# 7. Executable Target Definition
# ==============================================================================
qt_add_executable(DisasterPathwayManager
    WIN32
    MANUAL_FINALIZATION
    ${PROJECT_SOURCES}
    ${PROJECT_HEADERS}
    ${PROJECT_UI_FILES}
    ${PROJECT_RESOURCE_FILES}
)

# Specify where the AUTOUIC compiler should look for .ui files
set_target_properties(DisasterPathwayManager PROPERTIES
    AUTOUIC_SEARCH_PATHS "${CMAKE_CURRENT_SOURCE_DIR}/src/Resources/Forms"
)

# ==============================================================================
# 8. Target Includes & Linking
# ==============================================================================
target_include_directories(DisasterPathwayManager PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_BINARY_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/src/lib/optframe/include
)

target_link_libraries(DisasterPathwayManager PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Widgets
    Qt6::Quick
    Qt6::Qml
    Qt6::Positioning
    Qt6::Location
    Qt6::Core5Compat
)

# ==============================================================================
# 9. Compiler-Specific Settings (MSVC)
# ==============================================================================
if(MSVC)
    # PDB format for debugging
    set(CMAKE_MSVC_DEBUG_INFORMATION_FORMAT "$<$<CONFIG:Debug,RelWithDebInfo>:ProgramDatabase>")

    # Add MSVC-specific compiler flags (/MP for multi-processor compilation)
    target_compile_options(DisasterPathwayManager PRIVATE /MP)

    # Avoid Windows.h macro pollution (min/max conflicts)
    target_compile_definitions(DisasterPathwayManager PRIVATE
        WIN32_LEAN_AND_MEAN
        NOMINMAX
    )

    # Use precompiled headers to speed up parsing of standard/Qt headers
    target_precompile_headers(DisasterPathwayManager PRIVATE
        <QtCore>
        <QtGui>
        <QtWidgets>
        <vector>
        <string>
        <memory>
        <algorithm>
    )
endif()

# Finalize the Qt executable (must be called after target setup when using MANUAL_FINALIZATION)
qt_finalize_executable(DisasterPathwayManager)

# ==============================================================================
# 10. Installation
# ==============================================================================
install(TARGETS DisasterPathwayManager
    RUNTIME DESTINATION bin
    CONFIGURATIONS Debug RelWithDebInfo
)

# Install PDB files alongside the executable for MSVC debugging
if(MSVC)
    install(FILES $<TARGET_PDB_FILE:DisasterPathwayManager>
        DESTINATION bin
        CONFIGURATIONS Debug RelWithDebInfo
        OPTIONAL
    )
endif()