import requests
resp = requests.post('http://localhost:8000/auth/login', data={'username': 'vedppalande1357@gmail.com', 'password': 'password'})
print(resp.status_code, resp.text)
if resp.status_code == 200:
  token = resp.json()['access_token']
  print('Fetching claims...')
  claims = requests.get('http://localhost:8000/claims', headers={'Authorization': 'Bearer ' + token})
  print(claims.status_code, len(claims.json()))
