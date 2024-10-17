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
        headers = {'accept': 'application/json', 'Authorization': f'ExtraHop apikey={api_key}'}
        url = f'/api/v1/customdevices?include_criteria={include_criteria}'
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

def audit_custom_devices(hostname, api_key, include_criteria=True):
    """
    Function to retrieve the list of custom devices from ExtraHop API
    and write them to a CSV file.
    """
    custom_devices = get_custom_devices(hostname, api_key, include_criteria)
    if not custom_devices:
        logger.info(f'No custom devices detected on {hostname}')
        return

    csv_filename = f'custom_devices_audit_{hostname}.csv'
    
    with open(csv_filename, mode='w', newline='') as csv_file:
        if include_criteria:
            fieldnames = ['name', 'author', 'description', 'disabled', 'extrahop_id', 'id', 'mod_time',
                          'ipaddr', 'ipaddr_direction', 'ipaddr_peer',
                          'src_port_min', 'src_port_max', 'dst_port_min', 'dst_port_max',
                          'vlan_min', 'vlan_max']
        else:
            fieldnames = ['name', 'author', 'description', 'disabled', 'extrahop_id', 'id', 'mod_time']
        
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        
        for device in custom_devices:
            if include_criteria:
                criteria_list = device.get('criteria', [])
                for index, criteria in enumerate(criteria_list):
                    if index == 0:
                        writer.writerow({
                            'name': device.get('name', ''),
                            'author': device.get('author', ''),
                            'description': device.get('description', ''),
                            'disabled': device.get('disabled', ''),
                            'extrahop_id': device.get('extrahop_id', ''),
                            'id': device.get('id', ''),
                            'mod_time': device.get('mod_time', ''),
                            'name': device.get('name', ''),
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
                    else:
                        writer.writerow({
                            'name': '',
                            'author': '',
                            'description': '',
                            'disabled': '',
                            'extrahop_id': '',
                            'id': '',
                            'mod_time': '',
                            'name': '',
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
            else:
                writer.writerow({
                    'name': device.get('name', ''),
                    'author': device.get('author', ''),
                    'description': device.get('description', ''),
                    'disabled': device.get('disabled', ''),
                    'extrahop_id': device.get('extrahop_id', ''),
                    'id': device.get('id', ''),
                    'mod_time': device.get('mod_time', '')
                })
    logging.info(f"Custom devices successfully written to {csv_filename}")

def main():
    parser = argparse.ArgumentParser(description='Manage ExtraHop Custom Devices')
    parser.add_argument('--audit', type=str, help='Path to CSV file containing appliance hostnames and API keys for auditing custom devices')
    parser.add_argument('--include_criteria', type=bool, default=True, help='Indicates whether the custom device criteria should be included')
    parser.add_argument('--include_metrics', type=bool, default=False, help='Indicates whether the custom device metrics should be included')
    args = parser.parse_args()

    if args.audit:
        with open(args.audit, mode='r') as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                hostname = row.get('hostname')
                api_key = row.get('api_key')
                if hostname and api_key:
                    audit_custom_devices(hostname, api_key, include_criteria=args.include_criteria)

if __name__ == '__main__':
    main()
