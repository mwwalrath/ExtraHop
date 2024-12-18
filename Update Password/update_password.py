import http.client
import json
import ssl
import logging
from datetime import datetime
import os

eh_host = 'string'
api_key = 'string'
password = 'string'

# Set up logging

current_datetime = datetime.now().strftime('%Y-%m-%d %H-%M-%S')
log_folder = 'logs'
os.makedirs(log_folder, exist_ok=True)
log_filename = f'update_password_log_{current_datetime}'
log_file = os.path.join(log_folder, log_filename)
logging.basicConfig(filename=f'{log_file}.log',
                    format='[%(asctime)s] %(levelname)s: %(message)s',
                    filemode='w',
                    level=logging.INFO)
logger = logging.getLogger()

# Main Script

logger.info('Starting update password script')

try:
    logger.info('Attempting to update password')
    connection = http.client.HTTPSConnection(eh_host, 443, context=ssl._create_unverified_context())
    headers = {'accept': 'application/json', 'Authorization': f'ExtraHop apikey={api_key}', 'Content-Type': 'application/json'}
    payload = {'name': 'setup','password': password}
    connection.request('PATCH', '/api/v1/users', headers=headers, body=json.dumps(payload))
    response = connection.getresponse()
    if response.status == 204:
        logger.info(f'{response.status}: User successfully updated.')
    elif response.status == 401:
        logger.error(f'{response.status}: API key is missing or invalid.')
    elif response.status == 402:
        logger.error(f'{response.status}: The EULA has not been accepted for this appliance.')
    else:
        logger.error(f'{response.status}: {response.reason}: {response.read()}')
except Exception as e:
    logger.error(f'Exception occured while retrieving users: {e}')

logger.info('Update password script completed')
