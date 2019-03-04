#pragma once

#include <spdlog/spdlog.h>
#include <sqlite3.h>
#include <stdexcept>

class SQLite3Environment {
public:
  SQLite3Environment();
  ~SQLite3Environment();
};

class SQLite3Db;

class SQLite3Statement {
public:
  SQLite3Statement(SQLite3Db &db, const std::string &query);
  ~SQLite3Statement();
  operator sqlite3_stmt *() { return statement; }

  void bind(int placeHolderNum, int value);

private:
  sqlite3_stmt *statement;
};

class SQLite3Db {
public:
  SQLite3Db(const std::string dbFileName);
  ~SQLite3Db();
  operator sqlite3 *() { return pDb; }
  SQLite3Statement prepare(const std::string &query);

private:
  sqlite3 *pDb;
};
