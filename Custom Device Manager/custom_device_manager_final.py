import argparse
from datetime import datetime
import csv
import http.client
import json
import logging
import os
import ssl
from time import sleep

# Set up logging

current_datetime = datetime.now().strftime('%Y-%m-%d %H-%M-%S')
log_folder = 'logs'
os.makedirs(log_folder, exist_ok=True)
log_filename = f'custom_device_manager_log_{current_datetime}'
log_file = os.path.join(log_folder, log_filename)
logging.basicConfig(filename=f'{log_file}.log',
                    format='[%(asctime)s] %(levelname)s: %(message)s',
                    filemode='w',
                    level=logging.INFO)
logger = logging.getLogger()

def setup_https_connection(hostname):
    """
    This function sets up an HTTPS connection to the specified hostname.

    Parameters:
    hostname (str): The hostname to establish the connection with.

    Returns:
    connection (http.client.HTTPSConnection): The established HTTPS connection.
        Returns None if the connection cannot be established.

    Raises:
    Exception: If an exception occurs while establishing the connection.
    """
    logger.info(f'Setting up HTTPS connection to {hostname}')
    retries = 3
    for attempt in range(retries):
        try:
            connection = http.client.HTTPSConnection(hostname, 443, context=ssl._create_unverified_context())
            return connection
        except Exception as e:
            logger.error(f'Exception occured while establishing connections to {hostname}: {e}')
            if attempt < retries - 1:
                logger.info(f'Retrying... ({attempt + 1}/{retries})')
                sleep(2)
            else:
                return None


def send_request(connection, method, url, headers, body=None):
    """
    Sends an HTTP request to the specified URL using the provided method, headers, and body.

    Parameters:
    connection (http.client.HTTPSConnection): The HTTPS connection object to send the request.
    method (str): The HTTP method for the request (e.g., 'GET', 'POST', 'PUT', 'DELETE').
    url (str): The URL to send the request to.
    headers (dict): The headers for the request.
    body (str, optional): The body for the request. Defaults to None.

    Returns:
    http.client.HTTPResponse: The response object received from the server.

    Raises:
    Exception: If an exception occurs during the request.
    """
    retries = 3
    logger.debug(f'Sending {method} request to {url} with headers {headers} and body {body}')
    for attempt in range(retries):
        try:
            connection.request(method, url, headers=headers, body=body)
            response = connection.getresponse()
            logger.debug(f'Received response: {response.status} {response.reason}')
            return response
        except Exception as e:
            logger.error(f'Exception occurred during {method} request to {url}: {e}')
            if attempt < retries - 1:
                logger.info(f'Retrying... ({attempt + 1}/{retries})')
                sleep(2)
            else:
                return None

    
def get_custom_devices(connection, hostname, api_key, include_criteria = False):
    """
    Retrieves custom devices from the specified ExtraHop appliance.

    Parameters:
    connection (object): The established HTTPS connection to the appliance.
    hostname (str): The hostname or IP address of the appliance.
    api_key (str): The API key for authentication.
    include_criteria (bool, optional): If True, includes criteria in the response. Defaults to False.

    Returns:
    list: A list of dictionaries representing the custom devices. Each dictionary contains the device's details.
          Returns None if an error occurs.
    """
    logger.info(f'Retrieving custom devices from {hostname}')
    try:
        url = f'/api/v1/customdevices?include_criteria={include_criteria}'
        headers = {
            'accept': 'application/json',
            'Authorization': f'ExtraHop apikey={api_key}'
            }
        response = send_request(connection, 'GET', url, headers)
        if response and response.status == 200:
            logger.info(f'{response.status}: Custom devices successfully retrieved.')
            response_body = response.read()
            custom_devices = json.loads(response_body)
            return custom_devices
        elif response and response.status in [401, 402, 404]:
            logger.error(f'{response.status}: {response.reason}')
            return
        else:
            logger.error(f'{response.status}: {response.reason}')
            return
    except Exception as e:
        logger.error(f'Exception occurred while retrieving custom devices: {e}')
        return

    
def search_device(connection, api_key, device_name):
    """
    This function searches for a device with the given name on the ExtraHop appliance.

    Parameters:
    connection (object): The established HTTPS connection to the appliance.
    api_key (str): The API key for authentication.
    device_name (str): The name of the device to search for.

    Returns:
    dict: A dictionary containing the device's information if found.
          Returns None if the device is not found or an error occurs.
    """
    logger.debug(f'Searching for device: {device_name}...')
    try:
        url = f'/api/v1/devices/search'
        headers = {'accept': 'application/json',
                   'Authorization': f'ExtraHop apikey={api_key}',
                   'Content-Type': 'application/json'}
        payload = {
            'filter': {
                'field': 'name',
                'operand': device_name,
                'operator': '='
            }
        }
        response = send_request(connection, 'POST', url, headers, body=json.dumps(payload))
        if response and response.status == 200:
            logger.debug(f'{response.status}: Device successfully retrieved.')
            response_body = response.read()
            device_information = json.loads(response_body)
            return device_information
        elif response and response.status in [401, 402]:
            logger.error(f'{response.status}: {response.reason}')
            return
        else:
            logger.error(f'{response.status}: {response.reason}')
            return
    except Exception as e:
        logger.error(f'Exception occurred while retrieving device: {e}')
        return

    
def metric_query(connection, api_key, device_id):
    """
    This function performs a metric query on a device using the ExtraHop API.

    Parameters:
    connection (object): The established HTTPS connection to the appliance.
    api_key (str): The API key for authentication.
    device_id (str): The ID of the device for which the metric query will be performed.

    Returns:
    dict: A dictionary containing the queried metrics if successful.
          Returns None if an error occurs.
    """
    logger.debug(f'Performing metric query on device id: {device_id}')
    try:
        url = f'/api/v1/metrics'
        headers = {'accept': 'application/json',
                   'Authorization': f'ExtraHop apikey={api_key}',
                   'Content-Type': 'application/json'}
        payload = {
            'cycle': 'auto',
            'from': -1209600000,
            'until': 0,
            'object_type': 'device',
            'object_ids': [device_id],
            'metric_category': 'net',
            'metric_specs': [
                {
                    'name': 'bytes'
                }
            ]
        }
        response = send_request(connection, 'POST', url, headers, body=json.dumps(payload))
        if response and response.status == 200:
            logger.debug(f'{response.status}: Queried metrics successfully retrieved.')
            response_body = response.read()
            device_metrics = json.loads(response_body)
            return device_metrics
        elif response.status in [400, 401, 402]:
            logger.error(f'{response.status}: {response.reason}')
            return
        else:
            logger.error(f'{response.status}: {response.reason}')
            return 
    except Exception as e:
        logger.error(f'Exception occurred while retrieving metrics: {e}')
        return

    
def create_custom_device(connection, api_key, payload):
    """
    This function creates a custom device on the ExtraHop platform.

    Parameters:
    connection (object): The established HTTPS connection to the appliance.
    api_key (str): The API key for authentication.
    payload (dict): The payload containing the details of the custom device to be created.

    Returns:
    None if the custom device creation fails.
    The HTTP response object if the custom device creation is successful.
    """
    name = payload.get('name', '')
    logger.info(f'Creating custom device: {name}')
    try:
        url = '/api/v1/customdevices'
        headers = {'accept': 'application/json', 'Authorization': f'ExtraHop apikey={api_key}', 'Content-Type': 'application/json'}
        response = send_request(connection, 'POST', url, headers, body=json.dumps(payload))
        if response and response.status == 201:
            logger.info(f'{response.status}: Custom device successfully created.')
            return
        elif response and response.status in [400, 401, 402]:
            logger.error(f'{response.status}: {response.reason}')
            return response 
        else:
            logger.error(f'{response.status}: {response.reason}')
            return
    except Exception as e:
        logger.error(f'Exception occured while creating custom device: {e}')
        return

    
def patch_custom_device(connection, api_key, device_id, payload):
    """
    This function patches a custom device on the ExtraHop platform.

    Parameters:
    connection (object): The established HTTPS connection to the appliance.
    api_key (str): The API key for authentication.
    device_id (str): The ID of the device to be patched.
    payload (dict): The payload containing the details of the custom device to be patched.

    Returns:
    None if the custom device patching fails.
    The HTTP response object if the custom device patching is successful.
    """
    name = payload.get('name', '')
    logger.info(f'Patching {name}...')
    try:
        url = f'/api/v1/customdevices/{device_id}'
        headers = {'accept': 'application/json', 'Authorization': f'ExtraHop apikey={api_key}', 'Content-Type': 'application/json'}
        response = send_request(connection, 'PATCH', url, headers, body=json.dumps(payload))
        if response and response.status == 204:
            logger.info(f'{response.status}: Custom device successfully patched.')
            return
        elif response and response.status in [401, 402, 404]:
            logger.error(f'{response.status}: {response.reason}')
            return 
        else:
            logger.error(f'{response.status}: {response.reason}')
            return
    except Exception as e:
        logger.error(f'Exception occurred while creating custom device: {e}')
        return
    
def delete_custom_device(connection, api_key, hostname, id):
    logger.info(f'Deleting custom device {id} from {hostname}')
    try:
        url = f'/api/v1/customdevices/{id}'
        headers = {
            'accept': 'application/json',
            'Authorization': f'ExtraHop apikey={api_key}'
            }
        response = send_request(connection, 'DELETE', url, headers)
        if response and response.status == 204:
            logger.info(f'{response.status}: Custom device {id} successfully deleted.')
            return
        elif response and response.status in [401, 402, 404]:
            logger.error(f'{response.status}: {response.reason}')
            return
        else:
            logger.error(f'{response.status}: {response.reason}')
            return
    except Exception as e:
        logger.error(f'Exception occurred while deleting custom device: {e}')
        return


def audit_custom_devices(connection, hostname, api_key, verbose=False, include_criteria=False, include_metrics=False):
    """
    Function to retrieve the list of custom devices from ExtraHop API
    and write them to a CSV file.

    Parameters:
    connection (object): The established HTTPS connection to the appliance.
    hostname (str): The hostname of the appliance.
    api_key (str): The API key for authentication.
    verbose (bool, optional): If True, include additional details in the CSV output. Defaults to False.
    include_criteria (bool, optional): If True, include the custom device criteria in the CSV output. Defaults to False.
    include_metrics (bool, optional): If True, include the custom device metrics in the CSV output. Defaults to False.

    Returns:
    None
    """
    logger.info(f'Auditing appliance: {hostname}')
    custom_devices = get_custom_devices(connection, hostname, api_key, include_criteria)
    csv_filename = f'custom_devices_audit_{hostname}.csv'
    with open(csv_filename, mode='w', newline='') as csv_file:
        fieldnames = ['name']
        if verbose:
            fieldnames.extend(['author', 'description', 'disabled', 'extrahop_id', 'id', 'mod_time'])
        if include_criteria:
            fieldnames.extend(['ipaddr', 'ipaddr_direction', 'ipaddr_peer',
                            'src_port_min', 'src_port_max', 'dst_port_min', 'dst_port_max',
                            'vlan_min', 'vlan_max'])
        if include_metrics:
            fieldnames.extend(['bytes'])

        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        for custom_device in custom_devices:
            criteria_list = custom_device.get('criteria', []) if include_criteria else [{}]
            for index, criteria in enumerate(criteria_list):
                device_name = custom_device.get('name', '')
                row = {'name': device_name}
                if verbose:
                    row.update({
                        'author': custom_device.get('author', '') if index == 0 else '',
                        'description': custom_device.get('description', '') if index == 0 else '',
                        'disabled': custom_device.get('disabled', '') if index == 0 else '',
                        'extrahop_id': custom_device.get('extrahop_id', '') if index == 0 else '',
                        'id': custom_device.get('id', '') if index == 0 else '',
                        'mod_time': custom_device.get('mod_time', '') if index == 0 else ''
                    })
                if include_criteria:
                    row.update({
                        'ipaddr': criteria.get('ipaddr', ''),
                        'ipaddr_direction': criteria.get('ipaddr_direction', ''),
                        'ipaddr_peer': criteria.get('ipaddr_peer', ''),
                        'src_port_min': criteria.get('src_port_min', ''),
                        'src_port_max': criteria.get('src_port_max', ''),
                        'dst_port_min': criteria.get('dst_port_min', ''),
                        'dst_port_max': criteria.get('dst_port_max', ''),
                        'vlan_min': criteria.get('vlan_min', ''),
                        'vlan_max': criteria.get('vlan_max', '')
                    })
                if include_metrics:
                    device_info = search_device(connection, api_key, device_name)
                    device_bytes = 0
                    for dev in device_info:
                        if dev.get('role', '') == 'custom':
                            device_metrics = metric_query(connection, api_key, dev.get('id', ''))
                            if device_metrics and 'stats' in device_metrics:
                                for stat in device_metrics['stats']:
                                    device_bytes += sum(stat.get('values', 0))
                                    row.update({
                                        'bytes': device_bytes if index == 0 else ''
                                    })
                writer.writerow(row)
    logger.info(f"Custom devices successfully written to {csv_filename}")


def create_custom_devices_from_csv(connection, hostname, api_key, custom_devices_csv, patch=False):
    """
    This function reads a CSV file containing custom device details, creates them on the ExtraHop platform,
    and optionally patches existing devices with the same name.

    Parameters:
    connection (object): The established HTTPS connection to the appliance.
    hostname (str): The hostname of the appliance.
    api_key (str): The API key for authentication.
    custom_devices_csv (str): The path to the CSV file containing custom device details.
    patch (bool, optional): If True, overwrite existing custom devices when found. Defaults to False.

    Returns:
    None
    """
    if patch == True:
        global confirm_all_patches
    
    custom_devices = get_custom_devices(connection, hostname, api_key, verbose = True)
    with open(custom_devices_csv, mode='r') as csv_file:
        new_devices = list(csv.DictReader(csv_file))

    processed_devices = {}
    for new_device in new_devices:

        name = new_device.get('name', '')
        if name not in processed_devices:
            processed_devices[name] = {
                'name': name,
                'author': 'API Automation',
                'description': new_device.get('description', ''),
                'disabled': new_device.get('disabled', 'false').lower(),
                'criteria': []
            }
        criteria_keys = ['ipaddr', 'ipaddr_direction', 'ipaddr_peer', 'src_port_min', 'src_port_max', 'dst_port_min', 'dst_port_max', 'vlan_min', 'vlan_max']
        criteria = {key: new_device[key] for key in criteria_keys if new_device.get(key, '').strip()}
        if criteria:
            processed_devices[name]['criteria'].append(criteria)

    for device_payload in processed_devices.values():
        final_payload = {
            "name": device_payload['name'],
            "author": device_payload['author'],
            "description": device_payload['description'],
            "disabled": device_payload['disabled'],
            "criteria": device_payload['criteria']
        }
        logger.info(f'Creating device: {device_payload['name']}')
        response = create_custom_device(connection, api_key, final_payload)

        if response.reason['detail'] == f'A custom device with the name {name} already exists' and patch == True:
            user_input = ''
            valid_options = ['yes', 'no', 'all']
            while user_input not in valid_options:
                user_input = input(f'Do you want to patch the device "{name}"? (yes/no/all): ').strip().lower()
                if user_input not in valid_options:
                    logger.warning(f"Invalid input. Please enter one of the following: {', '.join(valid_options)}")

            if user_input == 'no':
                logger.info(f'Skipping patch for device {name}.')
                continue
            elif user_input == 'all':
                confirm_all_patches = True

            if confirm_all_patches or user_input == 'yes':
                device_id = custom_devices[f'{name}']['id']
                patch_custom_device(connection, api_key, device_id, final_payload)


def delete_custom_devices_from_csv(connection, hostname, api_key, custom_devices_csv):

    custom_devices = get_custom_devices(connection, hostname, api_key, verbose = True)
    with open(custom_devices_csv, mode='r') as csv_file:
        custom_devices = list(csv.DictReader(csv_file))

def main():
    logger.info('Initializing Custom Device Manager...')
    parser = argparse.ArgumentParser(description = 'Manage ExtraHop Custom Devices')
    parser.add_argument('--appliances', type = str, help = 'Path to CSV file containing appliance hostnames and API keys')
    parser.add_argument('--create', type = str, help = 'Path to CSV file containing custom devices to create on the platform')
    parser.add_argument('--delete', type = str, help = 'Path to CSV file containing custom devices to delete from the platform')
    parser.add_argument('--patch', action = 'store_true', help = 'If enabled, overwrite existing custom devices when found')
    parser.add_argument('--audit', action = 'store_true', help = 'Audit custom devices on the appliances defined in the CSV file')
    parser.add_argument('--verbose', action = 'store_true', help = 'Include additional details in the CSV output')
    parser.add_argument('--include_criteria', action = 'store_true', help = 'Indicates whether the custom device criteria should be included')
    parser.add_argument('--include_metrics', action = 'store_true', help = 'Indicates whether the custom device metrics should be included')
    parser.add_argument('--log-level', type=str, default='INFO', help='Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
    
    args = parser.parse_args()
    logger.setLevel(args.log_level.upper())

    logger.info('Parsing arguments...')
    logger.debug(f'Appliances CSV: {args.appliances}')
    logger.debug(f'Audit: {args.audit}')
    logger.debug(f'Verbose: {args.verbose}')
    logger.debug(f'Include Criteria: {args.include_criteria}')
    logger.debug(f'Include Metrics: {args.include_metrics}')
    logger.debug(f'Create: {args.create}')
    logger.debug(f'Patch: {args.patch}')

    if args.appliances:
        with open(args.appliances, mode = 'r') as csv_file:
            appliances = list(csv.DictReader(csv_file))

        for appliance in appliances:
            hostname = appliance.get('hostname')
            api_key = appliance.get('api_key')
            if hostname and api_key:
                logger.info(f'Processing tasks on appliance: {hostname}')
                connection = setup_https_connection(hostname)
                if connection and args.audit:
                    audit_custom_devices(
                        connection,
                        hostname, api_key,
                        verbose = args.verbose,
                        include_criteria = args.include_criteria,
                        include_metrics = args.include_metrics
                        )
                if connection and args.create:
                    create_custom_devices_from_csv(
                        connection,
                        hostname,
                        api_key,
                        args.create,
                        patch = args.patch
                        )
                if connection and args.delete:
                    delete_custom_devices_from_csv(
                        connection,
                        hostname,
                        api_key,
                        args.delete
                    )

if __name__ == '__main__':
    main()
