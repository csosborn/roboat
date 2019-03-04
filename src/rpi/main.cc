#include <csignal>
#include <iostream>
#include <spdlog/sinks/stdout_color_sinks.h>
#include <spdlog/spdlog.h>

#include <boost/asio.hpp>
#include <boost/thread/thread.hpp>
#include <sqlite3.h>

#include "HelmConnection.hpp"
#include "SQLite3Helpers.hpp"

using boost::asio::executor_work_guard;
using boost::asio::io_context;
using namespace std::chrono_literals;

namespace {
volatile std::sig_atomic_t signalStatus = 0;
const unsigned int kNumAsioThreads = 2;
const char *kHelmSerialPortName = "/dev/ttys003";

auto console = spdlog::stdout_color_mt("captain");
} // namespace

void signal_handler(int signal) {
  signalStatus = signal;
  console->debug("Caught signal {}.", signalStatus);
}

struct RunRecord {
  int id;
  std::string startTime;
  std::string endTime;
};

RunRecord getRun(SQLite3Db &pDb, int id) {
  RunRecord rec = {0, "", ""};
  auto selectStmt = pDb.prepare("SELECT * FROM run WHERE run_id==?");
  selectStmt.bind(1, id);
  if (sqlite3_step(selectStmt) == SQLITE_ROW) {
    rec.id = sqlite3_column_int(selectStmt, 0);
    rec.startTime =
        reinterpret_cast<const char *>(sqlite3_column_text(selectStmt, 1));
    if (sqlite3_column_type(selectStmt, 2) != SQLITE_NULL) {
      rec.endTime =
          reinterpret_cast<const char *>(sqlite3_column_text(selectStmt, 2));
    }
  } else {
    console->error("Couldn't get latest run row.");
  }
  return rec;
}

int main(int argc, char **argv) {
  bool success = true;

  std::signal(SIGINT, signal_handler);

  console->set_level(spdlog::level::debug);
  console->info("Roboat Captain, starting up!");

  bool goodStartup = true;
  int currRunId = 0;

  // Set up sqlite3 and open the database
  SQLite3Environment dbGlobals;

  SQLite3Db roboatDb("roboat.db");

  auto createStmt = roboatDb.prepare(R"QUERY(
    CREATE TABLE IF NOT EXISTS run (
      run_id INTEGER PRIMARY KEY AUTOINCREMENT, 
      start_time TEXT NOT NULL,
      end_time TEXT DEFAULT NULL);
    )QUERY");
  if (sqlite3_step(createStmt) == SQLITE_DONE) {
    console->debug("Run table exists.");
  } else {
    console->error("Did not create run table.");
  }

  auto insertStmt = roboatDb.prepare(R"QUERY(
    INSERT INTO run (start_time, end_time)
    VALUES(DATETIME('now'), NULL);
  )QUERY");
  if (sqlite3_step(insertStmt) == SQLITE_DONE) {
    currRunId = sqlite3_last_insert_rowid(roboatDb);
    console->debug("Inserted new run record ({}).", currRunId);

    auto thisRec = getRun(roboatDb, currRunId);
    if (thisRec.id) {
      console->info("Run id {} spans {} to {}.", thisRec.id, thisRec.startTime,
                    thisRec.endTime);
    }
    auto prevRec = getRun(roboatDb, currRunId - 1);
    if (prevRec.id) {
      console->info("Run id {} spans {} to {}.", prevRec.id, prevRec.startTime,
                    prevRec.endTime);
    }

  } else {
    console->error("Failed to insert new run record.");
  }

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

  // Record end of current run
  auto updateStmt = roboatDb.prepare(
      "UPDATE run SET end_time=DATETIME('now') WHERE run_id==?;");
  updateStmt.bind(1, currRunId);
  if (sqlite3_step(updateStmt) == SQLITE_DONE) {
    console->info("Updated end time for run {}.", currRunId);
  } else {
    console->warn("Update failed: {}", sqlite3_errmsg(roboatDb));
  }

  // Shut down the IO context and thread pool.
  console->debug("Stopping IO context...");
  ioc.stop();

  console->debug("Shutting down thread pool...");
  thread_pool.join_all();

  console->info("Goodbye.");

  return success ? 0 : 1;
}
