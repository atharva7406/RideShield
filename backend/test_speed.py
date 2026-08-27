import requests, time
resp = requests.post('http://localhost:8000/auth/login', data={'username': 'vedppalande1357@gmail.com', 'password': 'password'})
if resp.status_code == 200:
  token = resp.json()['access_token']
  start = time.time()
  requests.get('http://localhost:8000/claims', headers={'Authorization': 'Bearer ' + token})
  print('Time:', time.time() - start)
else:
  print('Auth failed', resp.status_code)
