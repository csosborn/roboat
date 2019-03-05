#include "SQLite3Helpers.hpp"
#include "fmt/format.h"

SQLite3Environment::SQLite3Environment() {
  if (SQLITE_OK != sqlite3_initialize()) {
    throw std::runtime_error("Could not initialize sqlite3.");
  }
  spdlog::get("captain")->debug("Initialized SQLite3 environment.");
}
SQLite3Environment::~SQLite3Environment() {
  sqlite3_shutdown();
  spdlog::get("captain")->debug("Shut down SQLite3 environment.");
}

SQLite3Statement::SQLite3Statement(SQLite3Db &db, const std::string &query)
    : statement_(NULL), db_(db) {
  auto res =
      sqlite3_prepare_v3(db, query.c_str(), query.size(), 0, &statement_, NULL);
  if (res != SQLITE_OK) {
    throw std::runtime_error(
        fmt::format("Could not prepare statement: {}", db_.errorMessage()));
  }
}

SQLite3Statement::~SQLite3Statement() { sqlite3_finalize(statement_); }

void SQLite3Statement::bind(int placeHolderNum, int value) {
  if (sqlite3_bind_int(statement_, placeHolderNum, value) != SQLITE_OK) {
    throw std::runtime_error(
        "Failed to bind integer value in prepared statement.");
  }
}

int SQLite3Statement::step() {
  int ret = sqlite3_step(statement_);
  switch (ret) {
  case SQLITE_DONE:
    sqlite3_reset(statement_);
    break;
  case SQLITE_MISUSE:
    throw std::runtime_error(
        fmt::format("Misuse of prepared statement: {}", db_.errorMessage()));
    break;
  default:
    break;
  }
  return ret;
}

SQLite3Db::SQLite3Db(const std::string dbFileName) : pDb(NULL) {
  if (SQLITE_OK == sqlite3_open_v2(dbFileName.c_str(), &pDb,
                                   SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE,
                                   NULL)) {
    spdlog::get("captain")->debug("Successfully opened database \"{}\".",
                                  dbFileName);
  } else {
    throw std::runtime_error("Could not open/create database.");
  }
};

SQLite3Db::~SQLite3Db() {
  if (pDb) {
    spdlog::get("captain")->debug("Closing database...");
    sqlite3_close(pDb);
  }
}

SQLite3Statement SQLite3Db::prepare(const std::string &query) {
  return SQLite3Statement(*this, query);
}

std::string SQLite3Db::errorMessage() {
  return std::string(sqlite3_errmsg(pDb));
}
