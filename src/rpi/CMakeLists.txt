
add_executable(captain main.cc HelmConnection.cc)
target_link_libraries(captain PUBLIC
    boost::boost
    spdlog::spdlog
    fmt::fmt)
