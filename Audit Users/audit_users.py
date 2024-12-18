#!/usr/bin/python3

# COPYRIGHT 2024 BY EXTRAHOP NETWORKS, INC.
#
# This file is subject to the terms and conditions defined in
# file 'LICENSE', which is part of this source code package.

import csv
from datetime import datetime
import http.client
import json
import logging
import os
import ssl
import sys

######### USER DEFINED VARIABLES #########

# List of appliances by IP or FQDN (eh_host) and API keys (api_key)
APPLIANCES_CSV = 'appliances.csv'

# Output csv file containing list of all unique user IDs
USERS_CSV = 'user_audit.csv'

# Input csv file containing list of unique user IDs to delete from all appliances
INACTIVE_USERS_CSV = 'inactive_users.csv'

# Set to True to audit users and create a CSV file
AUDIT_USERS = False

# Set to True to delete users from a CSV file
DELETE_USERS = True

########## MAIN CODE - DO NOT EDIT ##########

##### DATETIME #####

current_datetime = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
str_current_datetime = str(current_datetime)

##### DIRECTORIES #####

script_directory = os.path.dirname(os.path.abspath(sys.argv[0]))
script_filename = os.path.basename(script_directory).split('/')[-1]
appliances_csv_filepath = os.path.join(script_directory, APPLIANCES_CSV)
users_csv_filepath = os.path.join(script_directory, USERS_CSV)
inactive_users_csv_filepath = os.path.join(script_directory, INACTIVE_USERS_CSV)

##### LOGGING #####

log_filename = f'{script_filename}_logfile_{str_current_datetime}'
log_path = os.path.join(script_directory, log_filename)
logging.basicConfig(filename=f'{log_path}.log',
                    format='%(asctime)s %(levelname)s: %(message)s',
                    filemode='w')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

##### FUNCTIONS #####

def getUsers(eh_host, api_key):
    try:
        logger.info(f'Retriving all active users accounts on {eh_host}...')
        connection = http.client.HTTPSConnection(eh_host, 443, context=ssl._create_unverified_context())
        headers = {
            'accept': 'application/json',
            'Authorization': f'ExtraHop apikey={api_key}'
        }
        connection.request('GET', '/api/v1/users', headers=headers,)
        response = connection.getresponse()
        if response.status == 200:
            logger.info(f'{response.status}: Users successfully retrieved.')
            data = response.read()
            users = json.loads(data.decode('utf-8'))
            return users
        elif response.status == 401:
            logger.error(f'{response.status}: API key is missing or invalid.')
            return None
        elif response.status == 402:
            logger.error(f'{response.status}: The EULA has not been accepted for this appliance.')
            return None
    except Exception as e:
        logger.error(f'Exception occured while retrieving users: {e}')
        return None
    
def deleteUser(eh_host, api_key, username):
    try:
        logger.info(f'Deleting "{username}"...')
        connection = http.client.HTTPSConnection(eh_host, 443, context=ssl._create_unverified_context())
        headers = {
            'accept': 'application/json',
            'Authorization': f'ExtraHop apikey={api_key}'
        }
        connection.request('DELETE', f'/api/v1/users/{username}?dest_user=setup', headers=headers,)
        response = connection.getresponse()
        if response.status == 204:
            logger.info(f'{response.status}: User successfully deleted.')
            return True
        elif response.status == 401:
            logger.error(f'{response.status}: API key is missing or invalid.')
            return None
        elif response.status == 402:
            logger.error(f'{response.status}: The EULA has not been accepted for this appliance.')
            return None
        elif response.status == 403:
            logger.error(f'{response.status}: The user does not have permission to delete other users.')
            return None
        elif response.status == 404:
            logger.error(f'{response.status}: Requested resource could not be found')
            return None        
        elif response.status == 405:
            logger.error(f'{response.status}: Cannot delete the user that owns the key used to send the request.')
            return None
    except Exception as e:
        logger.error(f'Exception occured while retrieving users: {e}')
        return None
            
def auditUsers():
    logger.info('Auditing users...')
    with open(appliances_csv_filepath, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        users_full=[]
        for row in reader:
            eh_host = row['eh_host']
            api_key = row['api_key']
            logger.info(f'Auditing {eh_host}...')  
            users = getUsers(eh_host, api_key)
            if users:
                for user in users:
                    username = user['username']
                    if username != 'setup' and username != 'shell':
                        users_full.append(username)
                users_full = list(set(users_full))
                logger.debug(f'Running list of unique active users: {users_full}')
        with open(users_csv_filepath, 'w', newline='') as new_csvfile:
            writer = csv.DictWriter(new_csvfile, fieldnames=['username'])
            writer.writeheader()
            users_full.sort()
            logger.info(f'Writing {users_full} to CSV')
            for user in users_full:
                writer.writerow({'username': user})

def deleteUsers():
    logger.info(f'Reading inactive users from {INACTIVE_USERS_CSV}')
    with open(inactive_users_csv_filepath, 'r', newline='') as inactive_users_csvfile:
        reader_1 = csv.DictReader(inactive_users_csvfile)
        inactive_users = []
        for row in reader_1:
            username = row['username']
            inactive_users.append(username)  
        logger.info(f'Inactive users: {inactive_users}')      
    with open(appliances_csv_filepath, 'r') as appliances_csvfile:
        reader_2 = csv.DictReader(appliances_csvfile)
        for row in reader_2:
            eh_host = row['eh_host']
            api_key = row['api_key']
            logger.info(f'Auditing {eh_host}...')
            active_users = []  
            users = getUsers(eh_host, api_key)
            if users:
                for user in users:
                    active_user = user['username']
                    if active_user != 'setup' and active_user != 'shell':
                        active_users.append(active_user)
                logger.info(f'Active users: {active_users}')
            logger.info(f'Comparing active users on {eh_host} to list of inactive users')
            username_matches = list(set(active_users) & set(inactive_users))
            logger.info(f'Matching users: {username_matches}')
            if username_matches:
                logger.info(f'Removing matches  from {eh_host}...')
                for username in username_matches:
                    deleteUser(eh_host, api_key, username)
            else:
                logger.info(f'No inactive users on {eh_host}')
    
##### MAIN FUNCTION #####

def main(AUDIT_USERS = True, DELETE_USERS = False):
    try:
        if AUDIT_USERS:
            DELETE_USERS = False
            auditUsers()

        if DELETE_USERS:
            AUDIT_USERS = False
            deleteUsers()

    except Exception as e:
        logger.error(f'Exception occured while running script: {e}')

if __name__ == '__main__':
    main(AUDIT_USERS, DELETE_USERS)
