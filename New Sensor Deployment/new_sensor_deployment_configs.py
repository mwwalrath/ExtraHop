#!/usr/bin/python3
import os.path

import requests
import base64
import json
import argparse
import logging
import sys
import time
import urllib3

# Script Purpose: This script will read in the new_sensor_deployment_configs.json file for configuration changes, some of which are in the running_config.
    # It defaults to audit_mode, which will not make any changes to the sensors but will output a json of all the sensors current running_configs.
# Created By: ExtraHop Solutions Architecture [Evan Schlemmer]
# NOTES:
    # If connecting over HopCloud you must set the cookie argument, see argument help below for where to get milk & cookies
    # If calling to enterprise appliance, set apiKey argument
    # If calling to 360 CCP, set id and secret arguments and host to <customerName>.api.cloud.extrahop.com

nline = '\n'

# Argument parsing
parser = argparse.ArgumentParser(
    description='Reads in a csv of tags to create based on IP or CIDRs. See tags_example.csv for proper CSV formatting.')
parser.add_argument('-v', '--verbose', action="store_true", default=False,
                    help='Print debug to console.')
parser.add_argument('-s', '--suppress', default=True,
                    help="Suppress HTTPS warnings. These are suppressed by default.")
parser.add_argument('-CH', '--consoleHost', default=None,
                    help="Hostname or IP Address of ExtraHop 360 Console. (ie 'company.api.cloud.extraHop.com')")
parser.add_argument('-CA', '--consoleApiKey', default=None,
                    help="API Key from ExtraHop Enterprise Console.  Used with --secret option.")
parser.add_argument('-I', '--id', default=None,
                    help="API ID from ExtraHop CCP.  Used with --secret option.")
parser.add_argument('-S', '--secret', default=None,
                    help="API Secret from ExtraHop CCP.  Used with --id option.")
parser.add_argument('-j', '--json', default=None, required=True,
                    help="Path to json sensor config file, if it resides in the script directory you only need the filename and extension")
parser.add_argument('-a', '--audit_mode', default=True,
                    help="Default True. Will output a json of all sensors' current running_configs. This mode will not run any running_config changes."
                         "To make running_config changes you must set this to False.")

args = parser.parse_args()

# Build argument variables
verbose = args.verbose
suppress = args.suppress
consoleHost = args.consoleHost
consoleApiKey = args.consoleApiKey
apiId = args.id
apiSecret = args.secret
jsonFile = args.json
audit_mode = args.audit_mode

# Handy shorthands
nline = '\n'
epochTimeMs = int(time.time()) * 1000
dayMs = 86400000
weekMs = 604800000
monthMs = 2629800000

# Build App variables
logLevel = logging.INFO  # Level of logging for console.  INFO, WARNING, ERROR, DEBUG, etc
logApp = 'General Scripts'
date = time.strftime("%Y_%m_%d")
timestr = time.strftime("%Y_%m_%d-%H-%M")


# Create log directory if it does not exist and create logfile name
current_directory = os.getcwd()
final_directory = os.path.join(current_directory, r'new_sensor_deployment')
logFileName = final_directory + "/new_sensor_deployment_" + timestr + ".log"
if not os.path.exists(final_directory):
    os.makedirs(final_directory)


# Logging setup
logger = logging.getLogger(logApp)
logFile = logging.FileHandler(logFileName)
logFile.setLevel(logging.DEBUG)
logCon = logging.StreamHandler(sys.stdout)
if verbose:
    logCon.setLevel(logging.DEBUG)
else:
    logCon.setLevel(logLevel)
logFormat = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
logFile.setFormatter(logFormat)
logCon.setFormatter(logFormat)
logger.addHandler(logFile)
logger.addHandler(logCon)
logger.setLevel(logging.DEBUG)
logging.getLogger("http.client").setLevel(logging.WARNING)

log_dictionary = vars(args)
if log_dictionary['consoleApiKey'] != None:
    log_dictionary['consoleApiKey'] = 'REDACTED'
if log_dictionary['id'] != None:
    log_dictionary['id'] = 'REDACTED'
if log_dictionary['secret'] != None:
    log_dictionary['secret'] = 'REDACTED'
logger.info("Executing with arguments: " + json.dumps(log_dictionary))


# load json if passed as argument
if jsonFile:
    with open(jsonFile, encoding='utf-8-sig') as f:
        jsonFile = json.load(f)

# Suppression of HTTP Insecure Warnings is enabled by default in suppress argument
if suppress:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# build appropriate headers
headers_OnDemand = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }


# Auto sets authentication and cookie headers based on arguments passed
# If connecting over HopCloud you must set the cookie argument, see argument help above for where to get milk & cookies
# If calling to enterprise appliance, set apiKey argument
# If calling to 360 CCP, set id and secret arguments and host to <customerName>.api.cloud.extrahop.com
def getToken_OnDemand(hostOnDemand, apiIdOnDemand, apiSecretOnDemand):

    auth = base64.b64encode(bytes(apiIdOnDemand + ":" + apiSecretOnDemand, "utf-8")).decode("utf-8")
    token_headers = {
        "Authorization": "Basic " + auth,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    url = "https://" + hostOnDemand + "/oauth2/token"
    r = requests.post(url, headers=token_headers, verify=False, data="grant_type=client_credentials")
    logger.info('getToken_OnDemand() Status Code: ' + str(r.status_code))

    return r.json()["access_token"]


def setAuthentication_OnDemand(hostOnDemand, apiKeyOnDemand=None, apiIdOnDemand=None, apiSecretOnDemand=None, cookieOnDemand=None):

    if cookieOnDemand:

        headers_OnDemand['Cookie'] = "token=" + cookieOnDemand
        logger.info('Cookie Hedaer Set')

    elif '.pdx.ra.hopcloud.extrahop.com' in hostOnDemand:

        logger.info('Authentication not properly set, according to your hostName you seem to be attempting to connect over HopCloud remote access.' + nline +
                    'If connecting over HopCloud, you must set the cookie argument.' 
                    'See --help cookie argument for where to find the milk & cookies.'
                    )

    if apiKeyOnDemand and not (apiIdOnDemand and apiSecretOnDemand):

        headers_OnDemand['Authorization'] = 'ExtraHop apikey=' + apiKeyOnDemand
        logger.info('Authorization Header set with API Key for Enterprise')

    elif (apiIdOnDemand and apiSecretOnDemand) and not apiKeyOnDemand:

        tokenOnDemand = getToken_OnDemand(hostOnDemand, apiIdOnDemand, apiSecretOnDemand)

        headers_OnDemand['Authorization'] = "Bearer " + tokenOnDemand
        logger.info('Authorization Header set with ID & Secret for 360 CCP')

    else:
        logger.info('Authentication not properly set' + nline +
                    'If connecting over HopCloud you must set the cookie argument, see cookie argument help for where to get milk & cookies' + nline +
                    'If calling to enterprise appliance, set apiKey argument' + nline +
                    'If calling to 360 CCP, set id and secret arguments and host to <customerName>.api.cloud.extrahop.com'
                    )


def getRunningConfig(hostname):

    url = "https://" + hostname + "/api/v1/runningconfig"
    r = requests.get(url, verify=False, headers=headers_OnDemand)
    logger.info('getRunningConfig() Status Code: ' + str(r.status_code))
    #print(r.json())
    return r.json()


def replaceRunningConfig(hostname, postData):

    url = "https://" + hostname + "/api/v1/runningconfig"
    r = requests.put(url, verify=False, headers=headers_OnDemand, data=json.dumps(postData))
    logger.info('replaceRunningConfig() Status Code: ' + str(r.status_code))
    return r.status_code


# Outputs info for all connected appliances: display name, hostname, nickname, platform, id, uuid
# WARNING FOR THE ARGUMENT BELOW: This may print sensitive information to the log file
    # BE SURE TO DELETE LOG WHEN NO LONGER NEEDED
# If you want to print the returned json of all appliances, pass True for logJson
def getAppliances(hostName):
    # needed for ap audit
    url = "https://" + hostName + "/api/v1/appliances"
    appliances = requests.get(url, headers=headers_OnDemand, verify=False)

    logger.info('BEGIN getAppliances() Output' + nline)

    for each in appliances.json():
        logger.info(nline +
              'Display Name: ' + each['display_name'] + nline +
              'Hostname: ' + each['hostname'] + nline +
              'Nickname: ' + each['nickname'] + nline +
              'Platform: ' + each['platform'] + nline +
              'Firmware: ' + each['firmware_version'] + nline +
              'ID: ' + str(each['id']) + nline +
              'UUID: ' + each['uuid'] + nline +
              '<<<<<<<<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>>>')

    logger.info('END getAppliances() Output')

    return appliances.json()


# Transfer management to Console for things like Analysis Priorities, Tuning Parameters, Records, Network Localities, etc.
def setConsoleManagement(hostname):

    ecaId = None

    appliances = getAppliances()
    for each in appliances:
        if each['platform'] == 'command':
            ecaId = each['id']

    post_data = {'manager': ecaId}

    url = "https://" + hostname + "/api/v1/analysispriority/0/manager"
    r = requests.patch(url, headers=headers_OnDemand, data=json.dumps(post_data), verify=False)
    logger.info('setConsoleManagement() Status Code: ' + str(r.status_code))
    #print(r.json())
    #return r.json()


def setDns(runningConfig, server_list):

    runningConfig['dns'] = {}

    if server_list[0]:
        runningConfig['dns']['dns'] = server_list[0]
    if server_list[1]:
        runningConfig['dns']['dns2'] = server_list[1]

    return runningConfig

# At least one NTP server is required.
# If you wish to keep the ExtraHop defaults as backups use:
    # second='1.extrahop.pool.ntp.org'
    # third='2.extrahop.pool.ntp.org'
    # fourth='3.extrahop.pool.ntp.org'
def setNtp(runningConfig, server_list):

    runningConfig['ntp']['servers'] = server_list

    return runningConfig


# Server is required
def setSmtp(runningConfig, server_list, port=25, sender='alerts@extrahop.com'):


    runningConfig['email_notification'] = {}
    if server_list:
        runningConfig['email_notification']['smtp_server'] = server_list[0]
    if port:
        runningConfig['email_notification']['smtp_port'] = port
    if sender:
        runningConfig['email_notification']['notification_sender'] = sender

    runningConfig['email_notification']['smtp_encryption'] = 'none'
    runningConfig['email_notification']['validate_certs'] = 'disabled'
    runningConfig['email_notification']['report_sender'] = 'null'
    runningConfig['email_notification']['smtp_enable_auth'] = False
    runningConfig['email_notification']['smtp_username'] = 'null'
    # print(runningConfig)
    return runningConfig


def setDefaultNotificationGroup(hostname, emailList):

    post_data = {
        "email_addresses": [],
        "system_notifications": True
    }

    for each in emailList:
        post_data["email_addresses"].append(each)

    #print(str(post_data))

    url = "https://" + hostname + "/api/v1/emailgroups/1"
    r = requests.patch(url, headers=headers_OnDemand, data=json.dumps(post_data), verify=False)
    logger.info('setDefaultNotificationGroup() Status Code: ' + str(r.status_code))


# Set password policy to strict and set password expiration time
def setStrictPasswords(runningConfig, enable=False, dasysToExpiry=60):

    if enable:

        secondsToExpiry = dasysToExpiry * 86400

        runningConfig['password'] = {
            'expiration_time': secondsToExpiry,
            'strict': True
            }
        #print(runningConfig)
        return runningConfig

    else:
        logger.info("setStrictPasswords() passowrd policy remains weak, run function again with True if you don't lack discipline")


# Set IPs/CIDRs in Discover by IP
def setRemoteIps(runningConfig, ipList):

    runningConfig['capture']['device_ip_discover_networks'] = ipList
    runningConfig['capture']['device_ip_discover'] = True
    #print(runningConfig)
    return runningConfig


# Set custom port names in Protocol Classification
def setProtocols(runningConfig, portDictionary):

    protoName = list(portDictionary.keys())
    ports = list(portDictionary.values())
    i = 0

    while i < len(ports):

        portSplit = ports[i].split(':')

        runningConfig['capture']['app_proto'][protoName[i]] = {
            "ports": [{"dstport": portSplit[1], "ipproto": portSplit[0], "loose_init": True, "srcport": "0"}]}

        i += 1

    return runningConfig


# Remember that the same precedence must also be set on the Console
def setDisplayNamePrecedance(runningConfig, precedence_list):

    runningConfig['ui'] = {
        "display_name_field_precedence": precedence_list
    }

    #print('Running Config: ' + str(running_config))

    return runningConfig


def getOdsTargets(hostname):

    url = "https://" + hostname + "/api/v1/odstargets"
    r = requests.get(url, verify=False, headers=headers_OnDemand)
    logger.info('getOdsTargets() Status Code: ' + str(r.status_code))
    #print(r.json())
    return r.json()


# Argument takes a list of target objects, consider using the API Explorer to get an example object
def createHttpOdsTarget(hostname, targetList):

    existingTargets = []

    odsTargets = getOdsTargets(hostname)

    for each in odsTargets:

        existingTargets.append(each['name'])

    for each in targetList:

        if each['name'] in existingTargets:

            logger.info('Target by this name ' + each['name'] + ' already exists')
            continue

        else:

            url = "https://" + hostname + "/api/v1/odstargets/http"
            r = requests.post(url, headers=headers_OnDemand, data=json.dumps(each), verify=False)
            logger.info('createHttpOdsTarget() Status Code: ' + str(r.status_code))


def saveRunningConfig(hostname):

    url = "https://" + hostname + "/api/v1/runningconfig/save"
    r = requests.post(url, verify=False, headers=headers_OnDemand)
    logger.info('saveRunningConfig() Status Code: ' + str(r.status_code))


def restartCapture(hostname):

    url = "https://" + hostname + "/api/v1/extrahop/processes/excap/restart"
    r = requests.post(url, headers=headers_OnDemand, verify=False)
    logger.info('restartCapture() Status Code: ' + str(r.status_code))


def writeJson(filename, jsonData):

    with open(final_directory + '/' + filename + '_' + timestr + '.json', 'w', encoding='utf-8') as f:
        json.dump(jsonData, f, ensure_ascii=False, indent=4)


def main():

    if audit_mode == True:

        logging.info(f"YOU ARE RUNNING IN AUDIT_MODE, running_config changes will NOT be made.")

        audit = {}

        for each in jsonFile:

            sensor_hostname = each['sensor_hostname']
            sensor_api_key = each['sensor_api_key']

            setAuthentication_OnDemand(sensor_hostname, sensor_api_key)

            running_config = getRunningConfig(sensor_hostname)

            audit[sensor_hostname] = running_config

        writeJson('sensor_running_config_audits', audit)

    else:

        logging.warning(
            f"Please ensure PPCAP disks on all sensors have been enabled before configuring System Health Notifications. "
            f"Otherwise you will get a 'bad didk' email notification."
            + nline + "Proceed?")
        c = input("(y/n)")
        if c == "y":

            for each in jsonFile:

                sensor_hostname = each['sensor_hostname']
                sensor_api_key = each['sensor_api_key']

                setAuthentication_OnDemand(sensor_hostname, sensor_api_key)

                if len(each['odsTargets']) > 0:
                    createHttpOdsTarget(sensor_hostname, each['odsTargets'])

                if len(each['default_notification_group']) > 0:
                    setDefaultNotificationGroup(sensor_hostname, each['default_notification_group'])

                #setConsoleManagement()

                running_config = getRunningConfig(sensor_hostname)

                if len(each['ntp']) > 0:
                    setNtp(running_config, each['ntp'])

                elif len(each['smtp']) > 4:
                    logging.warning(f"You can only enter a max of 4 NTP servers. Correct this in your json for sensor " + sensor_hostname + " and run again.")

                if len(each['dns']) > 0 and len(each['dns']) < 3:
                    setDns(running_config, each['dns'])

                elif len(each['smtp']) > 2:
                    logging.warning(f"You can only enter a max of 2 DNS servers. Correct this in your json for sensor " + sensor_hostname + " and run again.")

                if len(each['smtp']) == 1:
                    setSmtp(running_config, each['smtp'])

                elif len(each['smtp']) > 1:
                    logging.warning(f"You can only enter a single SMTP server. Correct this in your json for sensor " + sensor_hostname + " and run again.")

                if len(list(each['classification_protocols'].keys())) > 0:
                    setProtocols(running_config, each['classification_protocols'])

                if len(each['displayname_precedence']) > 0:
                    setDisplayNamePrecedance(running_config, each['displayname_precedence'])

                # Arguments below will need to be reviewed for each new sensor
                if len(each['remote_ips']) > 0:
                    setRemoteIps(running_config, each['remote_ips'])

                # Setting strict password policy, clear arguments to leave weakness
                #setStrictPasswords(running_config, False)

                replaceRunningConfig(sensor_hostname, running_config)

                saveRunningConfig(sensor_hostname)
                time.sleep(2)

                # This results in momentary loss of data, so be sure to get approval
                restartCapture(sensor_hostname)


main()
