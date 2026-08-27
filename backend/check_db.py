import psycopg2
conn=psycopg2.connect('postgresql://neondb_owner:npg_8pDSXQa2jLkr@ep-hidden-art-azklkp5w.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&hostaddr=52.76.108.241')
cur=conn.cursor()
cur.execute('SELECT COUNT(*) FROM claims')
print(cur.fetchall())
