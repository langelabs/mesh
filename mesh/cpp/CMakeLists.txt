cmake_minimum_required(VERSION 3.18...3.24)
project(lange_mesh VERSION 0.1.0 LANGUAGES CXX)

find_package(nlohmann_json 3.12 CONFIG QUIET)
if(NOT nlohmann_json_FOUND)
    include(FetchContent)
    FetchContent_Declare(nlohmann_json
        URL https://github.com/nlohmann/json/releases/download/v3.12.0/json.tar.xz
        URL_HASH SHA256=42f6e95cad6ec532fd372391373363b62a14af6d771056dbfc86160e6dfff7aa
    )
    FetchContent_MakeAvailable(nlohmann_json)
endif()

add_library(lange_mesh
    src/messages.cpp
    src/router.cpp
    src/tool_group.cpp
    src/types.cpp
)
add_library(lange_mesh::lange_mesh ALIAS lange_mesh)
target_include_directories(lange_mesh PUBLIC include)
target_compile_features(lange_mesh PUBLIC cxx_std_17)
target_link_libraries(lange_mesh PRIVATE nlohmann_json::nlohmann_json)

if(CMAKE_SOURCE_DIR STREQUAL PROJECT_SOURCE_DIR)
    include(CTest)
    if(BUILD_TESTING)
        add_executable(lange_mesh_tests tests/reference_tests.cpp)
        target_link_libraries(lange_mesh_tests PRIVATE lange_mesh nlohmann_json::nlohmann_json)
        add_test(NAME lange_mesh_tests COMMAND lange_mesh_tests "${CMAKE_CURRENT_SOURCE_DIR}/../../tests")
    endif()
endif()
