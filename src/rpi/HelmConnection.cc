#include "HelmConnection.hpp"
#include <iostream>
#include <spdlog/spdlog.h>

namespace roboat {
namespace helm {

auto console = spdlog::get("captain");

HelmConnection::HelmConnection(io_context &ioc,
                               const std::string &serialPortName)
    : ioc_(ioc), serialPortName_(serialPortName) {
  console->debug("Created helm connection on port {}.", serialPortName_);
}

bool HelmConnection::start() {
  console->debug("Starting helm connection...");
  try {
    serialPort_ = std::make_unique<serial_port>(ioc_, serialPortName_);
    startRead();
    return true;
  } catch (std::exception &e) {
    console->error("Could not start helm connection: {}", e.what());
    return false;
  }
}

void HelmConnection::startRead() {
  async_read_until(*serialPort_.get(), boost::asio::dynamic_buffer(buffer_),
                   '\n',
                   [this](const boost::system::error_code &error,
                          std::size_t bytes_transferred) {
                     handleLine(error, bytes_transferred);
                     startRead();
                   });
}

void HelmConnection::handleLine(const boost::system::error_code &error,
                                std::size_t bytes_transferred) {
  if (!error) {
    std::string line(buffer_.substr(0, bytes_transferred));
    buffer_.erase(0, bytes_transferred);
    console->info("Line: {}", line);
  } else {
    console->warn("Error on handleLine: {} ({})", error.value(),
                  error.category().name());
  }
}

} // namespace helm
} // namespace roboat