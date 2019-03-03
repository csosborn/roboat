#include <boost/asio.hpp>
#include <memory>
#include <spdlog/spdlog.h>

namespace roboat {
namespace helm {

using boost::asio::deadline_timer;
using boost::asio::executor_work_guard;
using boost::asio::io_context;
using boost::asio::serial_port;
using boost::asio::streambuf;

class HelmConnection {
public:
  HelmConnection(io_context &ioc, const std::string &serialPortName);
  bool start();

private:
  void startRead();
  void handleLine(const boost::system::error_code &error,
                  std::size_t bytes_transferred);

  io_context &ioc_;
  std::string serialPortName_;
  std::unique_ptr<serial_port> serialPort_;
  std::string buffer_;
};

} // namespace helm
} // namespace roboat