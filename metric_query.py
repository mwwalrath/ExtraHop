#!/usr/bin/python3
import os.path
import requests
import urllib3
import http.client
import base64
import csv
import json
import argparse
import logging
import sys
import time
import ssl
from itertools import zip_longest

# Script Purpose: Metric query and parse to csv
# NOTES:

# If connecting over HopCloud you must set the cookie argument, see argument help below for where to get milk & cookies
# If calling to enterprise/local appliance, set apiKey argument
# If calling to 360 CCP, set id and secret arguments and host to <customerName>.api.cloud.extrahop.com

nline = '\n'

# Argument parsing
parser = argparse.ArgumentParser(
    description='Script Purpose: Metric query and parse to csv')
parser.add_argument('-v', '--verbose', action="store_true", default=False,
                    help='Print debug to console.')
parser.add_argument('-s', '--suppress', action="store_true", default=True,
                    help="Suppress HTTPS warnings. These are suppressed by default.")
parser.add_argument('-H', '--host', default=None,
                    help="Hostname or IP Address of ExtraHop." + nline +
                         "Enterprise Local: 'extrahop.company.com' or '10.2.2.1'" + nline +
                         "360 CCP: 'customerName.api.cloud.extrahop.com'" + nline +
                         "HopCloud Remote Access: someLongString.pdx.ra.hopcloud.extrahop.com")
parser.add_argument('-A', '--apikey',
                    help="API Key of ExtraHop.  Used with --host option")
parser.add_argument('-I', '--id',
                    help="API ID from ExtraHop CCP.  Used with --host option")
parser.add_argument('-S', '--secret',
                    help="API Secret from ExtraHop CCP.  Used with --secret option")
parser.add_argument('-C', '--cookie', default=False,
                    help="If connecting to an on-prem appliance over HopCloud Remote Access, pass the remote access session cookie token in this option." + nline +
                         "Remote connect to the appliance as you normally would and log in." + nline +
                         "Dev Tools > Application > Cookies > Token Value")
parser.add_argument('-i', '--ips', default="device_import_ips_hosts.csv",
                    help="CSV of IPs to query. Default is 'device_import_ips_hosts.csv'")
parser.add_argument('-j', '--json', default=None,
                    help="Path to json file, if it resides in the script directory you only need the filename and extension")
parser.add_argument('-sw', '--search_window_days', default=None,
                    help="Number of days to search back for metrics.")


args = parser.parse_args()

# Build argument variables
verbose = args.verbose
suppress = args.suppress
hostName = args.host
apiKey = args.apikey
apiId = args.id
apiSecret = args.secret
cookie = args.cookie
queryIPs = args.ips
jsonFile = args.json
search_window_days = args.search_window_days


# Build App variables
logLevel = logging.INFO  # Level of logging for console.  INFO, WARNING, ERROR, DEBUG, etc
logApp = 'General Scripts'
date = time.strftime("%Y_%m_%d")
timestr = time.strftime("%Y_%m_%d-%H-%M-%S")


# Create log directory if it does not exist and create logfile name
current_directory = os.getcwd()
final_directory = os.path.join(current_directory, r'metric_query_output')
logFileName = final_directory + "/cmdb_decom_metric_query_" + timestr + ".log"
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

log_dictionary = json.loads(json.dumps(args.__dict__, indent=4))
del log_dictionary['apikey']
del log_dictionary['id']
del log_dictionary['secret']
del log_dictionary['cookie']
logger.info("Executing with arguments: " + json.dumps(log_dictionary))


# load json if passed as argument
if jsonFile:
    with open(jsonFile, encoding='utf-8-sig') as f:
        jsonFile = json.load(f)

# Suppression of HTTP Insecure Warnings is enabled by default in suppress argument
if suppress:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# build appropriate headers
headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }


# Auto sets authentication and cookie headers based on arguments passed
# If connecting over HopCloud you must set the cookie argument, see argument help above for where to get milk & cookies
# If calling to enterprise appliance, set apiKey argument
# If calling to 360 CCP, set id and secret arguments and host to <customerName>.api.cloud.extrahop.com
def setAuthentication():

    if cookie:

        headers['Cookie'] = "token=" + cookie
        logger.info('Cookie Hedaer Set')

    elif '.pdx.ra.hopcloud.extrahop.com' in hostName:

        logger.info('Authentication not properly set, according to your hostName you seem to be attempting to connect over HopCloud' + nline +
                    'If connecting over HopCloud you must set the cookie argument, see argument help at top of script for how to get milk & cookies' + nline +
                    'If calling to enterprise appliance, set apiKey argument' + nline +
                    'If calling to 360 CCP, set id and secret arguments and host to <customerName>.api.cloud.extrahop.com'
                    )

    if apiKey and not (apiId and apiSecret):

        headers['Authorization'] = 'ExtraHop apikey=' + apiKey
        logger.info('Authorization Header set with API Key for Enterprise')

    elif (apiId and apiSecret) and not apiKey:

        token = getToken()

        headers['Authorization'] = "Bearer " + str(token)
        logger.info('Authorization Header set with ID & Secret for 360 CCP')

    else:
        logger.info('Authentication not properly set' + nline +
                    'If connecting over HopCloud you must set the cookie argument, see argument help at top of script for how to get milk & cookies' + nline +
                    'If calling to enterprise appliance, set apiKey argument' + nline +
                    'If calling to 360 CCP, set id and secret arguments and host to <customerName>.api.cloud.extrahop.com'
                    )


# Returns a temporary API access token for Reveal(x) 360 authentication
def getToken():

    auth = base64.b64encode(bytes(apiId + ":" + apiSecret, "utf-8")).decode("utf-8")
    token_headers = {
        "Authorization": "Basic " + auth,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    url = "https://" + hostName + "/oauth2/token"
    r = requests.post(url, headers=token_headers, verify=False, data="grant_type=client_credentials")
    logger.info('getToken() Status Code: ' + str(r.status_code))
    #print(r.json())
    return r.json()["access_token"]


def getMetrics(queryPayload):

    metrics = []
    url = "https://" + hostName + "/api/v1/metrics"

    r = requests.post(url, headers=headers, data=json.dumps(queryPayload), verify=False)
    logger.info('getMetrics() Status Code: ' + str(r.status_code))
    r = r.json()

    if 'xid' in r:

        num_results = r['num_results']
        xid = r['xid']
        print(str(num_results + 1) + " Sensors to query, make sure you get the same number of 'getMetricsXid() Status Code: 200' outputs to console/log.")
        urlXid = url + "/next/" + str(xid)
        # logger.info('getMetricsXid() Status Code: ' + str(r.status))
        i = 0

        while i <= num_results:

            rXid = requests.get(urlXid, headers=headers, verify=False)
            i += 1
            logger.info('getMetricsXid() Status Code: ' + str(rXid.status_code))
            rXid = rXid.json()

            if rXid is None:
                break

            if 'stats' in rXid:
                values = rXid['stats']
                for each in values:
                    if len(each['values'][0]) > 0:
                        metrics = metrics + each['values'][0]

        return metrics

    elif 'stats' in r:

        values = r['stats']

        for each in values:
            if len(each['values'][0]) > 0:
                metrics = metrics + each['values'][0]

        return metrics

    else:

        print('No Stats Found')
        return metrics


# Arguments headers, counts, columns, are lists that should have the same ordering so that they line up in csv columns
# columns is usually going to be a list of lists, unless you have one header (ie one column)
# Function Call Example:
    # writeCsv(groupNames, groupMemberCounts, groupIps, filename)
# CSV Output Example:
    # headers[0], headers[1], headers[2]
    # count[0], count[1], count[2]
    # column[0][0], column[1][0], column[2][0]
    # column[0][1], column[1][1], column[2][1]
def writeCsv(headers, counts, columns, filename):

    export_data = zip_longest(*columns, fillvalue='')
    with open(final_directory + '/' + filename + timestr + '.csv', 'w', encoding="ISO-8859-1", newline='') as file:
        write = csv.writer(file)
        write.writerow(headers)
        if counts:
            write.writerow(counts)
        write.writerows(export_data)

# main code below here

def main():

    lookback = int(search_window_days) * 86400000

    setAuthentication()

    metricPayload = {
        "cycle": "auto",
        "from": -lookback,
        "metric_category": "net_detail",
        "metric_specs": [
            {
                "name": "bytes_in"
            }

        ],
        "object_ids": [
            402
        ],
        "object_type": "device_group",
        "until": 0
    }

    # Get & Parse Metrics
    metrics = getMetrics(metricPayload)

    peerIps = []

    for each in metrics:

        ip = each['key']['addr']

        if ip in peerIps:
            continue
        else:
            peerIps.append(ip)


    if len(peerIps) == 0:
        logger.info("\n" + "\n" + "NO MATCHES FOUND: No csv created, try a longer search with args.search_window_days")

    else:
        with open(final_directory + '/metric_query_final_output_' + timestr + '.csv', 'w') as f:
            writer = csv.writer(f)
            for ip in peerIps:
                writer.writerow([ip])

        logger.info("\n" + "\n" + "Check 'metric_query_output' directory for final csv")


# RUN MAIN()

main()
