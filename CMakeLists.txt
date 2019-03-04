cmake_minimum_required(VERSION 3.11)

set(VERSION_MAJOR 0)
set(VERSION_MINOR 1)
set(VERSION_PATCH 0)

string(CONCAT PROJECT_VERSION
              "${VERSION_MAJOR}"
              ".${VERSION_MINOR}"
              ".${VERSION_PATCH}")

project(roboat VERSION ${PROJECT_VERSION} LANGUAGES C CXX)

if(${CMAKE_SOURCE_DIR} STREQUAL ${CMAKE_BINARY_DIR})
  message(
    FATAL_ERROR
      "In-source builds not allowed. Please make a build directory and run \
      CMake from there. You may need to remove CMakeCache.txt.")
endif()

set(CMAKE_CXX_STANDARD 17)

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

# Set visibility settings globally
set(CMAKE_CXX_VISIBILITY_PRESET hidden)
set(VISIBILITY_INLINES_HIDDEN TRUE)

set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} ${CMAKE_SOURCE_DIR}/cmake/modules)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup(TARGETS)

# Main project
add_subdirectory(src)
