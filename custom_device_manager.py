import argparse
from datetime import datetime
import csv
import http.client
import json
import logging
import ssl
import sys
import os

# Set up logging

current_datetime = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
str_current_datetime = str(current_datetime)

script_directory = os.path.dirname(os.path.abspath(sys.argv[0]))
script_filename = os.path.basename(script_directory).split('/')[-1]

log_folder = 'logs'
os.makedirs(log_folder, exist_ok=True)
log_filename = f'{script_filename}_logfile_{str_current_datetime}'
log_file = os.path.join(log_folder, log_filename)
logging.basicConfig(filename=f'{log_file}.log',
                    format='[%(asctime)s] %(levelname)s: %(message)s',
                    filemode='w',
                    level=logging.DEBUG)
logger = logging.getLogger()

def get_custom_devices(hostname, api_key, include_criteria = True):
    logger.info(f'Retrieving all custom devices from {hostname}')
    try:
        connection = http.client.HTTPSConnection(hostname, 443, context=ssl._create_unverified_context())
        url = f'/api/v1/customdevices?include_criteria={include_criteria}'
        headers = {'accept': 'application/json',
                   'Authorization': f'ExtraHop apikey={api_key}'}
        connection.request('GET', url, headers=headers)
        response = connection.getresponse()
        if response.status == 200:
            logger.info(f'{response.status}: Custom devices successfully retrieved.')
            response_body = response.read()
            custom_devices = json.loads(response_body)
            return custom_devices
        elif response.status == 401:
            logger.error(f'{response.status}: API key is missing or invalid.')
            return None
        elif response.status == 402:
            logger.error(f'{response.status}: The EULA has not been accepted for this appliance.')
            return None
        elif response.status == 404:
            logger.error(f'{response.status}: Requested resource could not be found.')
            return None
        else:
            logger.error(f'{response.status}: {response.reason}')
            logger.error(f'{response.read()}')
            return None
    except Exception as e:
        logger.error(f'Exception occurred while retrieving custom devices: {e}')

def search_devices(hostname, api_key, device_name):
    logger.debug(f'Searching for device: {device_name}...')
    try:
        connection = http.client.HTTPSConnection(hostname, 443, context=ssl._create_unverified_context())
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
        connection.request('POST', url, headers=headers, body=json.dumps(payload))
        response = connection.getresponse()
        if response.status == 200:
            logger.debug(f'{response.status}: Device successfully retrieved.')
            response_body = response.read()
            device_information = json.loads(response_body)
            return device_information
        elif response.status == 401:
            logger.error(f'{response.status}: API key is missing or invalid.')
            return None
        elif response.status == 402:
            logger.error(f'{response.status}: The EULA has not been accepted for this appliance.')
            return None
        else:
            logger.error(f'{response.status}: {response.reason}')
            logger.error(f'{response.read()}')
            return None
    except Exception as e:
        logger.error(f'Exception occurred while retrieving device: {e}')

def metric_query(hostname, api_key, device_id):
    logger.debug(f'Performing metric query on device id: {device_id}')
    try:
        connection = http.client.HTTPSConnection(hostname, 443, context=ssl._create_unverified_context())
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
        connection.request('POST', url, headers=headers, body=json.dumps(payload))
        response = connection.getresponse()
        if response.status == 200:
            logger.debug(f'{response.status}: Queried metrics successfully retrieved.')
            response_body = response.read()
            device_metrics = json.loads(response_body)
            return device_metrics
        elif response.status == 400:
            logger.error(f'{response.status}: The specified metric query is invalid')
            return None
        elif response.status == 401:
            logger.error(f'{response.status}: API key is missing or invalid.')
            return None
        elif response.status == 402:
            logger.error(f'{response.status}: The EULA has not been accepted for this appliance.')
            return None
        else:
            logger.error(f'{response.status}: {response.reason}')
            logger.error(f'{response.read()}')
            return None
    except Exception as e:
        logger.error(f'Exception occurred while retrieving metrics: {e}')

def create_custom_device(hostname, api_key, payload):
    name = payload.get('name', '')
    logger.info(f'Creating custom device: {name}')
    try:
        connection = http.client.HTTPSConnection(hostname, 443, context=ssl._create_unverified_context())
        url = '/api/v1/customdevices'
        headers = {'accept': 'application/json', 'Authorization': f'ExtraHop apikey={api_key}', 'Content-Type': 'application/json'}
        connection.request('POST', url, headers=headers, body=json.dumps(payload))
        response = connection.getresponse()
        if response.status == 201:
            logger.info(f'{response.status}: Custom device successfully created.')
            return True
        elif response.status == 401:
            logger.error(f'{response.status}: API key is missing or invalid.')
            return False
        elif response.status == 402:
            logger.error(f'{response.status}: The EULA has not been accepted for this appliance.')
            return False
        else:
            logger.error(f'{response.status}: {response.reason}')
            logger.error(f'{response.read()}')
            return False
    except Exception as e:
        logger.error(f'Exception occured while creating custom device: {e}')
        return None

def audit_custom_devices(appliances_csv, verbose=False, include_criteria=False, include_metrics=False):
    """
    Function to retrieve the list of custom devices from ExtraHop API
    and write them to a CSV file.
    """
    with open(appliances_csv, mode='r') as csv_file:
            appliances_reader = csv.DictReader(csv_file)
            for appliance in appliances_reader:
                hostname = appliance.get('eh_host')
                logger.info(f'Auditing appliance: {hostname}...')
                api_key = appliance.get('api_key')
                if hostname and api_key:
                    custom_devices = get_custom_devices(hostname, api_key, include_criteria)
                    if not custom_devices:
                        logger.info('No custom devices detected.')
                        return

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
                        
                        for device in custom_devices:
                            criteria_list = device.get('criteria', []) if include_criteria else [{}]
                            for index, criteria in enumerate(criteria_list):
                                row = {'name': device.get('name', '')}
                                if verbose:
                                    row.update({
                                        'author': device.get('author', '') if index == 0 else '',
                                        'description': device.get('description', '') if index == 0 else '',
                                        'disabled': device.get('disabled', '') if index == 0 else '',
                                        'extrahop_id': device.get('extrahop_id', '') if index == 0 else '',
                                        'id': device.get('id', '') if index == 0 else '',
                                        'mod_time': device.get('mod_time', '') if index == 0 else ''
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
                                    device_name = device.get('name', '')
                                    device_info = search_devices(hostname, api_key, device_name)
                                    device_bytes = 0
                                    for dev in device_info:
                                        if dev.get('role', '') == 'custom':
                                            device_metrics = metric_query(hostname, api_key, dev.get('id', ''))
                                            if device_metrics and 'stats' in device_metrics:
                                                for stat in device_metrics['stats']:
                                                    device_bytes += sum(stat.get('values', 0))
                                    row.update({
                                        'bytes': device_bytes if index == 0 else ''
                                    })
                                writer.writerow(row)
                    logging.info(f"Custom devices successfully written to {csv_filename}")

def create_custom_devices_from_csv(appliances_csv, custom_devices_csv):
    with open(appliances_csv, mode='r') as csv_file_1:
        appliances_reader = csv.DictReader(csv_file_1)
        for appliance in appliances_reader:
            hostname = appliance.get('hostname')
            api_key = appliance.get('api_key')
            if hostname and api_key:
                logger.info(f'Creating custom devices on appliance: {hostname}')
                devices = {}
                with open(custom_devices_csv, mode='r') as csv_file_2:
                    devices_reader = csv.DictReader(csv_file_2)
                    for device in devices_reader:
                        name = device.get('name', '')
                        if name not in devices:
                            devices[name] = {
                                'name': name,
                                'author': device.get('author', ''),
                                'description': device.get('description', ''),
                                'disabled': device.get('disabled', 'false').lower() == 'true',
                                'criteria': []
                            }
                        criteria = {}
                        if device.get('ipaddr', '').strip():
                            criteria['ipaddr'] = device.get('ipaddr', '')
                        if device.get('ipaddr_direction', '').strip():
                            criteria['ipaddr_direction'] = device.get('ipaddr_direction', '')
                        if device.get('ipaddr_peer', '').strip():
                            criteria['ipaddr_peer'] = device.get('ipaddr_peer', '')
                        if device.get('src_port_min', '').strip():
                            criteria['src_port_min'] = int(device.get('src_port_min', 0))
                        if device.get('src_port_max', '').strip():
                            criteria['src_port_max'] = int(device.get('src_port_max', 0))
                        if device.get('dst_port_min', '').strip():
                            criteria['dst_port_min'] = int(device.get('dst_port_min', 0))
                        if device.get('dst_port_max', '').strip():
                            criteria['dst_port_max'] = int(device.get('dst_port_max', 0))
                        if device.get('vlan_min', '').strip():
                            criteria['vlan_min'] = int(device.get('vlan_min', 0))
                        if device.get('vlan_max', '').strip():
                            criteria['vlan_max'] = int(device.get('vlan_max', 0))

                        if criteria:
                            devices[name]['criteria'].append(criteria)

                for device_name, device_payload in devices.items():
                    final_payload = {
                        "author": device_payload['author'],
                        "name": 'API Automation',
                        "description": device_payload['description'],
                        "disabled": device_payload['disabled'],
                        "criteria": device_payload['criteria']
                    }
                    logger.info(f'Creating device: {device_name}')
                    create_custom_device(hostname, api_key, final_payload)

def main():
    logger.info('Initializing Custom Device Manager...')
    parser = argparse.ArgumentParser(description='Manage ExtraHop Custom Devices')
    parser.add_argument('--appliances', type=str, help='Path to CSV file containing appliance hostnames and API keys')
    parser.add_argument('--audit', action='store_true', help='Indicates if we are auditing custom devices')
    parser.add_argument('--verbose', action='store_true', help='Include additional details in the CSV output')
    parser.add_argument('--include_criteria', action='store_true', help='Indicates whether the custom device criteria should be included')
    parser.add_argument('--include_metrics', action='store_true', help='Indicates whether the custom device metrics should be included')
    parser.add_argument('--create', type=str, help='Path to CSV file containing custome devices to be created')
    parser.add_argument('--patch', action='store_true', help='Indicates if script should update the custom device if it already exisits.')
    args = parser.parse_args()

    logger.info('Parsing arguments...')
    logger.info(f'Appliances CSV: {args.appliances}')
    logger.info(f'Audit: {args.audit}')
    logger.info(f'Verbsoe: {args.verbose}')
    logger.info(f'Include Criteria: {args.include_criteria}')
    logger.info(f'Include Metrics: {args.include_metrics}')
    logger.info(f'Create: {args.create}')

    if args.audit and args.appliances:
        logger.info('Starting Custom Device Audit...')
        audit_custom_devices(args.appliances, args.verbose, args.include_criteria, args.include_metrics)

    if args.create and args.appliances:
        logger.info('Creating Custom Devices...')
        create_custom_devices_from_csv(args.appliances, args.create)


if __name__ == '__main__':
    main()
