import psycopg2
conn=psycopg2.connect('postgresql://postgres:postgres@localhost:5432/rideshield_db')
cur=conn.cursor()
cur.execute('SELECT email, role FROM users')
for r in cur.fetchall(): print(r)
