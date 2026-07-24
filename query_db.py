import sqlite3
conn = sqlite3.connect('apps/backend/data/ai_testing.db')
cursor = conn.cursor()

# 查找这个任务
print("=== test_case_generation_runs ===")
cursor.execute("SELECT * FROM test_case_generation_runs WHERE id = 'tcgr-2e24e5624625276c'")
for row in cursor.fetchall():
    print(row)

# 查找列名
print("\n=== test_case_generation_runs columns ===")
cursor.execute("PRAGMA table_info(test_case_generation_runs)")
for row in cursor.fetchall():
    print(row)

# 查找最近的 test_point_generation_runs
print("\n=== Recent test_point_generation_runs ===")
cursor.execute("SELECT id, status, error_message, created_at FROM test_point_generation_runs ORDER BY created_at DESC LIMIT 10")
for row in cursor.fetchall():
    print(row)

# 查找 test_point_generation_runs 列
print("\n=== test_point_generation_runs columns ===")
cursor.execute("PRAGMA table_info(test_point_generation_runs)")
for row in cursor.fetchall():
    print(row)
