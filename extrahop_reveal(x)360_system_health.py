#!/usr/bin/env python3

# COPYRIGHT 2023 BY EXTRAHOP NETWORKS, INC.
#
# This file is subject to the terms and conditions defined in
# file 'LICENSE', which is part of this source code package.
#
# Created By: Matthew Walrath - Solutions Architect at ExtraHop Networks
# Deployed: 12 March 2023
# Version: 1.0.0
# Version History:
#   1.0.0 - Initial release (Matthew Walrath)
#       Files: LOG_FILENAME.log, appliance_info.csv, appliance_metrics.csv
#       Appliance Info: Appliance Name, Appliance Status, Appliance Type, License Status, License Type, Firmware Version
#       Metrics: Total Active Devices, Average Bit Rate, Top Average Bit Rate, Avergae Packet Rate, Top Average Packet Rate
#       Health checks: Status, License Status, Firmware Version, Product Thresholds (Devices - Advanced Analysis, Bit Rate, Packet Rate)
#
# Future Plans:
#   Add support for additional metrics: duplicate traffic rates and checks, unidirectional traffic, captures drops, desyncs, trigger load, trigger drops, remote messages

import base64
import csv
import datetime
import json
import logging
import os
import requests
import time

########################################
########## USER CONFIGURATION ##########
########################################

# EXTRAHOP API VARIABLES
# The hostname of the Reveal(x) 360 API.
# This hostname is displayed in Reveal(x) 360 on the API Access page under API Endpoint.
# The hostname does not include the /oauth/token.
HOST = 'zurich.api.cloud.extrahop.com'
# The ID of the REST API credentials.
ID = '70bp4l592m0pja6mnmquansgn1'
# The secret of the REST API credentials.
SECRET = 'q5espsb95v6121p6a1u03kna0iqhfitqhplds9c6jmlirai3077'

# LOOKBACK VARIABLES
# The beginning timestamp for the request.
# Return only metrics collected after this time.
# The value is evaluated relative to the current time. 
# https://docs.extrahop.com/current/rest-api-guide/#supported-time-units-
LOOKBACK_DAYS = '1w'

# WARNING THRESHOLD VARIABLES
BIT_RATE_THRESHOLD = 0.8  # 80%
PACKET_RATE_THRESHOLD = 0.8  # 80%

# LOGGING VARIABLES
# "LOG_FILENAME_time.log", "appliance_info.csv", and "appliance_metrics.csv" will be written within PROJECT_FOLDERNAME in the current working directory
LOG_FILENAME = 'extrahop_system_health'
PROJECT_FOLDERNAME = 'ExtraHop System Health Project'
# DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = logging.DEBUG

#################################################
########## DO NOT EDIT BELOW THIS LINE ##########
#################################################

# Build HTTPS token request headers
token_headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

# Product Thresholds Lookup Table
PRODUCT_THRESHOLDS = {
    'name': {
        'EDA10200': {
            'bit_rate_threshold': 100 * 1000 * 1000 * 1000,  # 100 Gbps
            'packet_rate_threshold': 10 * 1000 * 1000,  # 10 million
            'advanced_analysis_device_threshold': 16 * 1000,  # 16 000
            'total_device_threshold': 100 * 1000,  # 100 000
        },
        'EDA9200': {
            'bit_rate_threshold': 50 * 1000 * 1000 * 1000,  # 50 Gbps
            'packet_rate_threshold': 5 * 1000 * 1000,  # 5 million
            'advanced_analysis_device_threshold': 8 * 1000,  # 8 000
            'total_device_threshold': 50 * 1000,  # 50 000
        },
        'EDA8200': {
            'bit_rate_threshold': 25 * 1000 * 1000 * 1000,  # 25 Gbps
            'packet_rate_threshold': 2.5 * 1000 * 1000,  # 2.5 million
            'advanced_analysis_device_threshold': 5.5 * 1000,  # 5 500
            'total_device_threshold': 35 * 1000,  # 35 000
        },
        'EDA6200': {
            'bit_rate_threshold': 10 * 1000 * 1000 * 1000,  # 10 Gbps
            'packet_rate_threshold': 1 * 1000 * 1000,  # 1 million
            'advanced_analysis_device_threshold': 3 * 1000,  # 3 000
            'total_device_threshold': 18 * 1000,  # 18 000
        },
        'EDA4200': {
            'bit_rate_threshold': 5 * 1000 * 1000 * 1000,  # 5 Gbps
            'packet_rate_threshold': 500 * 1000,  # 500 000
            'advanced_analysis_device_threshold': 1.5 * 1000,  # 1 500
            'total_device_threshold': 9 * 1000,  # 9 000
        },
        'EDA1200': {
            'bit_rate_threshold': 1 * 1000 * 1000 * 1000,  # 1 Gbps
            'packet_rate_threshold': 140 * 1000,  # 140 000 
            'advanced_analysis_device_threshold': 250,  # 250
            'total_device_threshold': 750,  # 750
        },
        'EDA8200V': {
            'bit_rate_threshold': 25 * 1000 * 1000 * 1000,  # 25 Gbps
            'packet_rate_threshold': 2.5 * 1000 * 1000,  # 2.5 million
            'advanced_analysis_device_threshold': 5.5 * 1000,  # 5 500
            'total_device_threshold': 35 * 1000,  # 35 000
        },
        'EDA6100V': {
            'bit_rate_threshold': 10 * 1000 * 1000 * 1000,  # 10 Gbps
            'packet_rate_threshold': 1 * 1000 * 1000,  # 1 million
            'advanced_analysis_device_threshold': 3 * 1000,  # 3 000
            'total_device_threshold': 18 * 1000,  # 18 000
        },
        'EDA1100V': {
            'bit_rate_threshold': 1 * 1000 * 1000 * 1000,  # 1 Gbps
            'packet_rate_threshold': 140 * 1000,  # 140 000
            'advanced_analysis_device_threshold': 250,  # 250
            'total_device_threshold': 750,  # 750
        },
    },
}

# Build Logging Variables
current_directory = os.getcwd()
final_directory = os.path.join(current_directory, PROJECT_FOLDERNAME)
timestr = time.strftime("%Y_%m_%d-%H-%M-%S")
final_log_filename = f'{final_directory}/{LOG_FILENAME}_{timestr}.log'
if not os.path.exists(final_directory):
    os.makedirs(final_directory)
log_format = '%(asctime)s [%(levelname)s] %(name)s:%(funcName)s: %(message)s'

# Logging Setup
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
file_handler = logging.FileHandler(final_log_filename)
file_handler.setFormatter(logging.Formatter(log_format))
logger.addHandler(file_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(log_format))
logger.addHandler(console_handler)

def get_token() -> str:
    '''
    Method that generates and retrieves a temporary API access token for Reveal(x) 360 authentication.

    Args:
        ID (str): The client ID for the ExtraHop API
        SECRET (str): The client secret for the ExtraHop API
        HOST (str): The hostname of the ExtraHop appliance

    Returns:
        token (str): A temporary API access token
    '''
    auth = base64.b64encode(bytes(f'{ID}:{SECRET}', 'utf-8')).decode('utf-8')
    token_headers = {
        'Authorization': f'Basic {auth}',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    url = f'https://{HOST}/oauth2/token'
    logger.debug('Retrieving temporary API token...')
    try:
        with requests.post(url, headers=token_headers, data='grant_type=client_credentials') as r:
            r.raise_for_status()
            token = r.json()['access_token']
            logger.debug('Temporary API token successfully retrieved.\n')
            return token
    except requests.exceptions.HTTPError as err:
        try:
            error_json = err.response.json()
            error_message = error_json.get('error_message', str(err))
            status_code = err.response.status_code
            logger.error(f"HTTP error {status_code} retrieving token from Reveal(x) 360: {error_message}")
        except Exception:
            logger.error(f"HTTP error {err.response.status_code} retrieving token from Reveal(x) 360: {str(err)}")
        raise
    except requests.exceptions.RequestException as err:
        logger.error(f'Unexpected error retrieving token from Reveal(x) 360: {err}')
        raise

def set_authentication_header(token: str):
    '''
    Sets the 'Authorization' header for API requests using the provided authentication token.

    Args:
        token (str): A temporary API access token.

    Returns:
        None
    '''
    token_headers['Authorization'] = f'Bearer {token}'
    logger.debug('Authorization Header set for Reveal(x) 360.\n')

def get_epoch_time(times: list, values: list) -> datetime:
    '''
    Method that finds the index of the highest value in the values list and uses that index to get the corresponding value in the times list.
    It then converts that value into epoch time format and returns it as a datetime object.

    Args:
        times (list): A list of timestamp values in milliseconds.
        values (list): A list of integer or float values.

    Returns:
        epoch_time (datetime): The epoch time as a datetime object of the highest value in the values list.
    '''
    index = values.index(max(values))
    timestamp = times[index]
    epoch_time = datetime.datetime.fromtimestamp(timestamp / 1000)
    #logger.debug(epoch_time)
    return epoch_time

def get_appliances() -> list[dict[str, str]]:
    '''
    Method that retrieves information about ExtraHop appliances connected to the Reveal(x) 360 CCP.

    Returns:
        list[dict[str, str]]: A list of dictionaries, each containing the following keys and values:
        - name (str): The user-defined nickname of the appliance.
        - platform (str): The hardware platform of the appliance.
        - license_platform (str): The hardware platform used for licensing the appliance.
        - license_status (str): The current license status of the appliance.
        - firmware_version (str): The firmware version of the appliance.
        - status_message (str): The current status message of the appliance.
    '''
    logger.debug('Retrieving appliance information...')
    url = f'https://{HOST}/api/v1/appliances'
    try:
        r = requests.get(url, headers=token_headers)
        r.raise_for_status()
        #formatted_json = json.dumps(r.json(), indent=4, sort_keys=True)
        #print(formatted_json)
        appliance_info = [
            {
                'name': appliance.get('nickname', ''),
                'id': appliance.get('id', ''),
                'platform': appliance.get('platform', ''),
                'license_platform': appliance.get('license_platform', ''),
                'license_status': appliance.get('license_status', ''),
                'firmware_version': appliance.get('firmware_version', ''),
                'status_message': appliance.get('status_message', ''),
            }
            for appliance in r.json()
        ]
        logger.debug(f'{len(appliance_info)} appliances successfully queried.\n')
        return appliance_info
    except requests.exceptions.HTTPError as err:
        try:
            error_json = err.response.json()
            error_message = error_json.get('error_message', str(err))
            status_code = err.response.status_code
            logger.error(f"HTTP error {status_code} retrieving appliances from Reveal(x) 360: {error_message}")
        except Exception:
            logger.error(f"HTTP error {err.response.status_code} retrieving appliances from Reveal(x) 360: {str(err)}")
        raise
    except Exception as err:
        logger.error(f'Unexpected error retrieving appliances from Reveal(x) 360: {err}')
        raise

def get_networks() -> list[dict[str, str]]:
    '''
    Method that retrieves information about ExtraHop networks connected to the Reveal(x) 360 CCP.
    Networks are correlated to the network interface card that receives input from all of the objects identified by the ExtraHop system.
    On a console, each connected sensor is identified as a network capture. For more information, see Networks.
    
    Returns:
        list[dict[str, str]]: A list of dictionaries, each containing the following keys and values:
        - name (str): The user-defined name of the appliance.
        - id (str): Unique identifier of the network.
    '''
    logger.debug('Retrieving networks information...')
    url = f'https://{HOST}/api/v1/networks'
    try:
        r = requests.get(url, headers=token_headers)
        r.raise_for_status()
        #formatted_json = json.dumps(r.json(), indent=4, sort_keys=True)
        #print(formatted_json)
        networks_info = [
            {
                'name': network.get('name', ''),
                'id': network.get('id', ''),
            }
            for network in r.json()
        ]
        logger.debug(f'{len(networks_info)} networks successfully queried.\n')
        return networks_info
    except requests.exceptions.HTTPError as err:
        try:
            error_json = err.response.json()
            error_message = error_json.get('error_message', str(err))
            status_code = err.response.status_code
            logger.error(f"HTTP error {status_code} retrieving networks from Reveal(x) 360: {error_message}")
        except Exception:
            logger.error(f"HTTP error {err.response.status_code} retrieving networks from Reveal(x) 360: {str(err)}")
        raise
    except Exception as err:
        logger.error(f'Unexpected error retrieving networks from Reveal(x) 360: {err}')
        raise

def get_metrics(metric_payload: dict) -> list[dict[str, str]]:
    '''
    Method that retrieves total metrics from the ExtraHop system.

    Args:
        metric_payload (dict): A dictionary containing the payload parameters to be sent to the Reveal(x) 360 API.

    Returns:
        list[dict[str, str]]: A list of metric objects.
    '''
    url = f'https://{HOST}/api/v1/metrics'
    try:
        r = requests.post(url, headers=token_headers, json=metric_payload)
        r.raise_for_status()
        metric_stats = r.json()
        return metric_stats['stats']
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 401:
            logger.error(f"Authentication error retrieving metrics from Reveal(x) 360: {err.response.text}")
            token = get_token()
            set_authentication_header(token)
            return get_metrics(metric_payload)
        else:
            try:
                error_json = err.response.json()
                error_message = error_json.get('error_message', str(err))
                status_code = err.response.status_code
                logger.error(f"HTTP error {status_code} retrieving metrics from Reveal(x) 360: {error_message}")
            except Exception:
                logger.error(f"HTTP error {err.response.status_code} retrieving metrics from Reveal(x) 360: {str(err)}")
            raise
    except Exception as err:
        logger.error(f'Unexpected error retrieving metrics from Reveal(x) 360: {err}')
        raise

def get_metrics_total(metric_payload: dict) -> list[dict[str, str]]:
    '''
    Method that retrieves total metrics from the ExtraHop system.

    Args:
        metric_payload (dict): A dictionary containing the payload parameters to be sent to the Reveal(x) 360 API.

    Returns:
        list[dict[str, str]]: A list of metric objects.
    '''
    url = f'https://{HOST}/api/v1/metrics/total'
    try:
        r = requests.post(url, headers=token_headers, json=metric_payload)
        r.raise_for_status()
        metric_stats = r.json()
        return metric_stats['stats']
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 401:
            logger.error(f"Authentication error retrieving metrics from Reveal(x) 360: {err.response.text}")
            token = get_token()
            set_authentication_header(token)
            return get_metrics_total(metric_payload)
        else:
            try:
                error_json = err.response.json()
                error_message = error_json.get('error_message', str(err))
                status_code = err.response.status_code
                logger.error(f"HTTP error {status_code} retrieving metrics from Reveal(x) 360: {error_message}")
            except Exception:
                logger.error(f"HTTP error {err.response.status_code} retrieving metrics from Reveal(x) 360: {str(err)}")
            raise
    except Exception as err:
        logger.error(f'Unexpected error retrieving metrics from Reveal(x) 360: {err}')
        raise

def get_active_devices(appliance: dict) -> int:
    '''
    Method that retrieves active devices for the appliance.

    Args:
        appliance (dict): A dictionary containing appliance information.

    Returns:
        total_active_devices (int): The total number of active devices.
    '''
    appliance_id = appliance.get('id',)
    metrics_device_counts_payload = {
        'metric_category': 'bridge',
        'object_type': 'system',
        'metric_specs': [
            {'name': 'l3_device_active'},
            {'name': 'l2_device_active'},
            {'name': 'gateway_device_active'},
            {'name': 'custom_device_active'}
        ],
        'object_ids': [appliance_id],
        'from': f'-{LOOKBACK_DAYS}',
        'cycle': 'auto',
    }

    metrics_device_counts = get_metrics(metrics_device_counts_payload)
    if metrics_device_counts:
        active_device_counts = []
        for metrics in metrics_device_counts:
            active_device_counts.append(metrics['values'])

        highest_active_device_count = max(active_device_counts, key=sum)

        total_active_devices = sum(highest_active_device_count)
        logger.debug(f'Total active device: {total_active_devices}')
        return total_active_devices

def check_active_devices(appliance: dict, total_active_devices: int, product_thresholds: dict):
    '''
    Method that performs active device check versus product thresholds.

    Args:
        appliance (dict): A dictionary containing appliance information.
        total_active_devices (int): The total number of active devices.
        product_thresholds (dict): A dictionary containing product thresholds.

    Returns:
        None
    '''
    if total_active_devices == 0:
        logger.critical(f'No active active devices found on {appliance["name"]}, check feed.')
    elif total_active_devices > product_thresholds['total_device_threshold']:
        logger.critical(f'Number of active devices above standard analysis threshold on {appliance["name"]}, this will cause your devices to be in a state of limited information (Discovery Mode).')
    elif product_thresholds['advanced_analysis_device_threshold'] < total_active_devices < product_thresholds['total_device_threshold']:
        logger.warning(f'Number of active devices above advanced analysis threshold on {appliance["name"]}, this will cause your devices to be in a state of limited information (Standard Mode).')

def get_appliance_rates(appliance: dict) -> tuple[int, int, int, int]:
    '''
    Method that retrieves appliance rates for the appliance.

    Args:
        appliance (dict): A dictionary containing appliance information.

    Returns:
        tuple: A tuple containing average bit rate (Gbps), average packet rate (packets/s),
               top average bit rate (Gbps), and top average packet rate (packets/s).
    '''
    network_id = appliance.get('network_id')
    metrics_payload_average_byte_packet_rate = {
        'metric_category': 'net',
        'object_type': 'capture',
        'metric_specs': [
            {'name': 'bytes'},
            {'name': 'pkts'},
        ],
        'object_ids': [network_id],
        'from': f'-{LOOKBACK_DAYS}',
        'cycle': 'auto'  # 1hr
    }

    metrics_average_byte_packet_rate = get_metrics(metrics_payload_average_byte_packet_rate)
    if metrics_average_byte_packet_rate:
        byte_rates = []
        packet_rates = []
        times = []
        for metrics in metrics_average_byte_packet_rate:
            byte_rates.append(metrics['values'][0])
            packet_rates.append(metrics['values'][1])
            times.append(metrics['time'])

        total_byte_rate = sum(byte_rates)
        total_packet_rate = sum(packet_rates)
        average_byte_rate = total_byte_rate / len(byte_rates)
        average_packet_rate = total_packet_rate / len(packet_rates)

        top_average_byte_rate = max(byte_rates)
        top_average_packet_rate = max(packet_rates)

        top_average_byte_rate_epoch_time = get_epoch_time(times, byte_rates)
        top_average_packet_rate_epoch_time = get_epoch_time(times, packet_rates)

        average_byte_rate_per_second = average_byte_rate / 60 / 60
        average_packet_rate_per_second = round(average_packet_rate / 60 / 60)
        top_average_byte_rate_per_second = top_average_byte_rate / 60 / 60
        top_average_packet_rate_per_second = round(top_average_packet_rate / 60 / 60)

        average_bit_rate_per_second = average_byte_rate_per_second * 8
        top_average_bit_rate_per_second = top_average_byte_rate_per_second * 8

        average_bit_rate_Gbps = round(average_bit_rate_per_second / 1000 / 1000 / 1000, 2)
        top_average_bit_rate_Gbps = round(top_average_bit_rate_per_second / 1000 / 1000 / 1000, 2)

    else:
        average_bit_rate_Gbps = 0
        average_packet_rate_per_second = 0
        top_average_bit_rate_Gbps = 0
        top_average_byte_rate_epoch_time = None
        top_average_packet_rate_per_second = 0
        top_average_packet_rate_epoch_time = None

    logger.debug(f'Average bit rate: {average_bit_rate_Gbps} Gbps')
    logger.debug(f'Top average bit rate: {top_average_bit_rate_Gbps} Gbps @ {top_average_byte_rate_epoch_time}')

    logger.debug(f'Average packet rate: {average_packet_rate_per_second}/s')
    logger.debug(f'Top average packet rate: {top_average_packet_rate_per_second}/s @ {top_average_packet_rate_epoch_time}')

    return average_bit_rate_Gbps, average_packet_rate_per_second, top_average_bit_rate_Gbps, top_average_packet_rate_per_second

def check_appliance_rates(appliance: dict, top_average_bit_rate_Gbps: float, top_average_packet_rate_per_second: float, product_thresholds: dict):
    """
    Evaluates the appliance's bit and packet rates against the specified product thresholds and logs warnings or critical messages accordingly.

    This function checks if the top average bit rate and top average packet rate are within the acceptable range, nearing the product threshold, or exceeding the product threshold.
    It logs appropriate warning or critical messages based on the comparison.

    Args:
        appliance (dict): A dictionary representing the appliance with its attributes, such as name and platform.
        top_average_bit_rate_Gbps (float): The top average bit rate (in Gbps) of the appliance.
        top_average_packet_rate_per_second (float): The top average packet rate per second of the appliance.
        product_thresholds (dict): A dictionary containing the 'bit_rate_threshold' and 'packet_rate_threshold' for the appliance.

    Returns:
        None
    """
    # Perform bit rate check versus product thresholds
    if top_average_bit_rate_Gbps == 0:
        logger.critical(f'No bit rate detected on {appliance["name"]}, check feed.')
    elif (product_thresholds['bit_rate_threshold'] * BIT_RATE_THRESHOLD) < top_average_bit_rate_Gbps < product_thresholds['bit_rate_threshold']:
            logger.warning(f'Bit rate nearing product threshold (< 80%) on {appliance["name"]}.')
    elif top_average_bit_rate_Gbps > product_thresholds['bit_rate_threshold']:
            logger.critical(f'Bit rate is over the product threshold on {appliance["name"]}, this may cause drops.')

    # Perform packet rate check versus product thresholds
    if top_average_packet_rate_per_second == 0:
        logger.critical(f'No packet rate detected on {appliance["name"]}, check feed.')
    elif (product_thresholds['packet_rate_threshold'] * PACKET_RATE_THRESHOLD) < top_average_packet_rate_per_second < product_thresholds['packet_rate_threshold']:
            logger.warning(f'Packet rate nearing product threshold (< 80%) on {appliance["name"]}.')
    elif top_average_packet_rate_per_second > product_thresholds['packet_rate_threshold']:
            logger.critical(f'Packet rate is over the product threshold on {appliance["name"]}, this will cause drops.')    

def write_to_csv(appliance_info: list):
    '''
    Method that writes a list of dictionaries containing appliance information to two CSV files: appliance_info.csv and appliance_metrics.csv.
    The function takes a list of dictionaries as input, where each dictionary represents an appliance with its attributes.
    The function then iterates over each dictionary in the list and writes its attribute values to the corresponding CSV file using Python's csv module.

    Args:
        appliance_info (list): A list of dictionaries representing appliances and their attributes.
    
    Returns:
        None
    '''

    file_path = os.path.join(final_directory, 'appliance_info.csv')
    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(
            [
            'Name',
            'Platform',
            'License Platform',
            'Status Message',
            'License Status',
            'Firmware Version',
            ]
        )
        for appliance in appliance_info:
            writer.writerow([appliance.get('name', ''),
                             appliance.get('platform', ''),
                             appliance.get('license_platform', ''),
                             appliance.get('status_message', ''),
                             appliance.get('license_status', ''),
                             appliance.get('firmware_version', ''),])
            
    file_path = os.path.join(final_directory, 'appliance_metrics.csv')
    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(
            [
            'Name',
            'Total Active Devices',
            'Average Bit Rate (Gbps)',
            'Top Average Bit Rate (Gbps)',
            'Average Packet Rate/sec',
            'Top Average Packet Rate/sec',
            ]
        )
        for appliance in appliance_info:
            writer.writerow([appliance.get('name', ''),
                             appliance.get('total_active_devices', ''),
                             appliance.get('average_bit_rate_Gbps', ''),
                             appliance.get('top_average_bit_rate_Gbps', ''),
                             appliance.get('average_packet_rate_per_second', ''),
                             appliance.get('top_average_packet_rate_per_second', '')])

def main():
    '''
    Script that retrieves information about ExtraHop appliances connected to the Reveal(x) 360 CCP
    and performs a series of health checks.
    '''
    # Get API token and set authentication header
    token = get_token()
    set_authentication_header(token)

    # Retrieve information about ExtraHop appliances
    appliance_info = get_appliances()

    # Retrieve network IDs
    #logger.debug('Retrieving network IDs...')
    network_info = get_networks()
    for appliance in appliance_info:
        for network in network_info:
            if appliance['name'] == network['name']:
                appliance['network_id'] = network['id']
                break
    
    # Pull the current firmware version of the 'command' platform
    for appliance in appliance_info:
        if appliance.get('platform', '') == 'command':
            logger.debug('Checking firmware version of the command platform...')
            command_platform_firmware_version = appliance.get('firmware_version', '')
            logger.info(f'Command platform firmware version: {command_platform_firmware_version}\n')
            break

    # Review appliance and add additional metrics to appliance_info
    for appliance in appliance_info:
        logger.debug(f'Reviewing {appliance["name"]}:')

        # Check appliance status
        #logger.debug('Checking appliance status...')
        if appliance.get('status_message', '') != 'Online':
            logger.critical(f"{appliance['name']} is not currently online: {appliance['status_message']}")
        
        # Check license status
        #logger.debug('Checking license status...')
        if appliance.get('license_status', '') != 'Nominal':
            logger.warning(f"{appliance['name']} has a non-nominal license status: {appliance['license_status']}")

        # Check firmware version
        #logger.debug('Checking firmware version...')
        if appliance.get('firmware_version', '') != command_platform_firmware_version:
            logger.warning(f"{appliance['name']} not on the latest firmware version: {appliance['firmware_version']}")

        # Retrieve product thresholds
        #logger.debug('Retrieving appliance thresholds...')
        if appliance.get('platform') in ('discover'):
            product_thresholds = PRODUCT_THRESHOLDS.get('name', {}).get(appliance.get('license_platform'))
            #logger.debug(product_thresholds)

        # Retrieves and checks total active device
        total_active_devices = None
        if appliance.get('platform') in ('discover') and appliance.get('status_message') == 'Online':
            total_active_devices = get_active_devices(appliance)
            check_active_devices(appliance, total_active_devices, product_thresholds)

        # Retrieve and check bit and packet rates
        average_bit_rate_Gbps = None
        top_average_bit_rate_Gbps = None
        average_packet_rate_per_second = None
        top_average_packet_rate_per_second = None
        if appliance.get('platform') in {'discover'} and appliance.get('network_id') and appliance.get('status_message') == 'Online':
            average_bit_rate_Gbps, average_packet_rate_per_second, top_average_bit_rate_Gbps, top_average_packet_rate_per_second = get_appliance_rates(appliance)
            check_appliance_rates(appliance, top_average_bit_rate_Gbps, top_average_packet_rate_per_second, product_thresholds)

        # Append appliance_info
        appliance['total_active_devices'] = total_active_devices
        appliance['average_bit_rate_Gbps'] = average_bit_rate_Gbps
        appliance['top_average_bit_rate_Gbps'] = top_average_bit_rate_Gbps
        appliance['average_packet_rate_per_second'] = average_packet_rate_per_second
        appliance['top_average_packet_rate_per_second'] = top_average_packet_rate_per_second

        logger.debug(f'Review of {appliance["name"]} completed.\n')

    # Write data to CSV file
    write_to_csv(appliance_info)

if __name__ == '__main__':
    main()
