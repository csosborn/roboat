#include <csignal>
#include <iostream>
#include <spdlog/sinks/stdout_color_sinks.h>
#include <spdlog/spdlog.h>

#include <boost/asio.hpp>
#include <boost/thread/thread.hpp>

#include "HelmConnection.hpp"

using boost::asio::executor_work_guard;
using boost::asio::io_context;
using namespace std::chrono_literals;

namespace {
volatile std::sig_atomic_t signalStatus = 0;
const unsigned int kNumAsioThreads = 2;
const char *kHelmSerialPortName = "/dev/ttys003";
} // namespace

auto console = spdlog::stdout_color_mt("captain");

void signal_handler(int signal) {
  signalStatus = signal;
  console->debug("Caught signal {}.", signalStatus);
}

int main(int argc, char **argv) {
  bool success = true;

  std::signal(SIGINT, signal_handler);

  console->set_level(spdlog::level::debug);
  console->info("Roboat Captain, starting up!");

  // Create the IO context and thread pool
  console->debug("Creating IO context...");
  io_context ioc;
  auto ioc_work = boost::asio::make_work_guard(ioc);
  boost::thread_group thread_pool;
  for (auto iThread = 1; iThread <= kNumAsioThreads; iThread++) {
    console->debug("Creating ASIO thread {} of {}...", iThread,
                   kNumAsioThreads);
    thread_pool.create_thread([&ioc] { ioc.run(); });
  }

  bool goodStartup = true;

  // Create and start up the connection to the Helm
  roboat::helm::HelmConnection helm(ioc, kHelmSerialPortName);
  goodStartup = goodStartup && helm.start();

  // If startup was good then enter the main loop. All the real action happens
  // in ASIO work queues, so this is a just a sleepy loop.
  if (goodStartup) {
    bool done = false;
    while (!done) {
      if (signalStatus) {
        console->info("Starting shutdown after catching signal {}.",
                      signalStatus);
        done = true;
        success = true;
      } else {
        std::this_thread::sleep_for(500ms);
      }
    }
  } else {
    success = false;
    console->error("An error occurred during startup. Shutting down...");
  }

  // Shut down the IO context and thread pool.
  console->debug("Stopping IO context...");
  ioc.stop();

  console->debug("Shutting down thread pool...");
  thread_pool.join_all();

  console->info("Goodbye.");

  return success ? 0 : 1;
}
