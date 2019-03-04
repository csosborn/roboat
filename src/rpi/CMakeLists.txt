
add_executable(captain main.cc HelmConnection.cc SQLite3Helpers.cc)
target_link_libraries(captain PUBLIC
    CONAN_PKG::boost
    CONAN_PKG::spdlog
    CONAN_PKG::fmt
    CONAN_PKG::sqlite3)
