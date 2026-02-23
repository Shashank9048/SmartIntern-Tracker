import requests, datetime
email = 'test_analyze_' + str(datetime.datetime.now().timestamp()) + '@example.com'
res = requests.post('http://127.0.0.1:8000/auth/signup', json={'email': email, 'password': 'pw', 'full_name': 'Tester'})
token = res.json().get('access_token')

headers = {'Authorization': f'Bearer {token}'}
requests.patch('http://127.0.0.1:8000/user/me', json={'resume_text': 'Python, React developer'}, headers=headers)

print('Sending analyze request...')
res_analyze = requests.post('http://127.0.0.1:8000/ai/analyze', json={'job_description': 'Python developer needed'}, headers=headers)
print('Status:', res_analyze.status_code)
print('Response:', res_analyze.text)
