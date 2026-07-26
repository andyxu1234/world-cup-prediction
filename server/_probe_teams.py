import pymysql
c = pymysql.connect(host='47.101.167.103', port=3306, user='root',
                    password='xuzhenyu123', database='football_prediction', connect_timeout=10)
cur = c.cursor()
cur.execute("SHOW COLUMNS FROM teams")
print("TEAMS_COLUMNS:", [r[0] for r in cur.fetchall()])
cur.execute("SELECT * FROM teams LIMIT 3")
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print("  ", {k: v for k, v in zip(cols, r) if k in ('id', 'name', 'cn_name')})
c.close()
