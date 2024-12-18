import http.client
import json
import ssl

eh_host = 'string'
api_key = 'string'
password = 'string'

try:
    connection = http.client.HTTPSConnection(eh_host, 443, context=ssl._create_unverified_context())
    headers = {'accept': 'application/json', 'Authorization': f'ExtraHop apikey={api_key}', 'Content-Type': 'application/json'}
    payload = {'name': 'setup','password': password}
    connection.request('PATCH', '/api/v1/users', headers=headers,payload=json.dumps(payload))
    response = connection.getresponse()
    if response.status == 204:
        print(f'{response.status}: User successfully updated.')
    elif response.status == 401:
        print(f'{response.status}: API key is missing or invalid.')
    elif response.status == 402:
        print(f'{response.status}: The EULA has not been accepted for this appliance.')
except Exception as e:
    print(f'Exception occured while retrieving users: {e}')
