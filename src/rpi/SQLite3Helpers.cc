#include "SQLite3Helpers.hpp"

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
    : statement(NULL) {
  auto res =
      sqlite3_prepare_v3(db, query.c_str(), query.size(), 0, &statement, NULL);
  if (res != SQLITE_OK) {
    throw std::runtime_error(std::string("Could not prepare statement: ") +
                             sqlite3_errmsg(db));
  }
}

SQLite3Statement::~SQLite3Statement() { sqlite3_finalize(statement); }

void SQLite3Statement::bind(int placeHolderNum, int value) {
  if (sqlite3_bind_int(statement, placeHolderNum, value) != SQLITE_OK) {
    throw std::runtime_error(
        "Failed to bind integer value in prepared statement.");
  }
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
