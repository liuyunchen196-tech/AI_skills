# duckdb-skills 本地环境说明（WorkBuddy 适配）

本机**没有** `duckdb` 命令行，三个 duckdb 技能（query / attach-db / read-file）执行 Bash 步骤时
请改用下列 Python 入口，SQL 语法保持不变。

## 解释器与依赖

```
PY = C:/Users/liuwust/.workbuddy/binaries/python/envs/data/Scripts/python.exe
```

已安装：duckdb 1.5.6、pandas 3.0.6、openpyxl 3.1.5，并已下载 `sqlite` 扩展（可读 .db 文件）。

## 等价调用方式

**执行查询**（替代 `duckdb -c "SQL"`）：

```bash
"C:/Users/liuwust/.workbuddy/binaries/python/envs/data/Scripts/python.exe" -c "
import duckdb, sys
con = duckdb.connect()
con.execute('INSTALL sqlite; LOAD sqlite;')
print(con.sql(sys.stdin.read()).df().to_string())
" <<'SQL'
SELECT * FROM t LIMIT 10;
SQL
```

**读取 SQLite 库**（替代 `duckdb file.db`）：

```sql
LOAD sqlite;
ATTACH 'D:/path/to/movies.db' AS src (TYPE SQLITE, READ_ONLY);
SELECT * FROM src.movies LIMIT 5;
```

**读取 Excel / CSV / Parquet**：`SELECT * FROM '文件.xlsx'`、`'文件.csv'`、`'文件.parquet'`
（Excel 需要 `INSTALL excel; LOAD excel;`，已在环境中预装）。

**多库整合**：多次 `ATTACH ... AS a / AS b`，再 `JOIN`，这就是 attach-db 技能要表达的形态。

## 注意

- 技能原文里的 `duckdb -init "$STATE_DIR/state.sql"`、`find`、`duckdb -c` 在本机不适用，
  直接换成上面的 Python 一次性调用即可，不必维护 state.sql。
- 写数据库时用 `ATTACH ... (TYPE SQLITE)` 后 `COPY ... TO` 或 `.execute("CREATE TABLE ...")`，
  但 **SQLite 目标只支持整表写入**，改行/删行建议仍用 Python 的 `sqlite3` 模块。
