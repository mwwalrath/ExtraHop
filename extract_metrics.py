#!/usr/bin/python3

import json
import csv
import time
import requests
from urllib.parse import urlunparse
import base64
import sys

# The IP address or hostname of the ExtraHop appliance or Reveal(x) 360 API
# This hostname is displayed in Reveal(x) 360 on the API Access page under API Endpoint.
# The hostname does not include the /oauth/token.
HOST = "zurich.api.cloud.extrahop.com"

# For Reveal(x) 360 authentication
# The ID of the REST API credentials.
ID = "70bp4l592m0pja6mnmquansgn1"
# The secret of the REST API credentials.
SECRET = "q5espsb95v6121p6a1u03kna0iqhfitqhplds9c6jmlirai3077"
# A global variable for the temporary API access token (leave blank)
TOKEN = ""

# The filepath of the CSV file to save metrics to
FILENAME = "output.csv"

def getToken():
    """
    Method that generates and retrieves a temporary API access token for Reveal(x) 360 authentication.
        Returns:
            str: A temporary API access token
    """
    auth = base64.b64encode(bytes(ID + ":" + SECRET, "utf-8")).decode("utf-8")
    headers = {
        "Authorization": "Basic " + auth,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    url = urlunparse(("https", HOST, "/oauth2/token", "", "", ""))
    r = requests.post(
        url,
        headers=headers,
        data="grant_type=client_credentials",
    )
    try:
        return r.json()["access_token"]
    except:
        print(r.text)
        print(r.status_code)
        print("Error retrieveing token from Reveal(x) 360")
        sys.exit()


def getAuthHeader(force_token_gen=False):
    """
    Method that adds an authorization header for a request. For Reveal(x) 360, adds a temporary access
    token. For self-managed appliances, adds an API key.
        Parameters:
            force_token_gen (bool): If true, always generates a new temporary API access token for the request
        Returns:
            header (str): The value for the header key in the headers dictionary
    """
    global TOKEN
    if TOKEN == "" or force_token_gen == True:
        TOKEN = getToken()
    return f"Bearer {TOKEN}"


def getMetrics(cycle, metric_category, name, object_ids, object_type):
    """
    Method that retrieves metrics from the ExtraHop system
        Parameters:
            cycle (str): The aggregation period for metrics
            metric_category (str): The category of object to retrieve metrics for
            name (str): The name of the metric to retrieve
            object_ids (list): A list of numeric IDs that identify the objects to retrieve metrics for
            object_type (str): The type of object to retrieve metrics for
        Returns:
            metrics (list): A list of metric objects
    """
    data = {
        "cycle": cycle,
        "metric_category": metric_category,
        "metric_specs": [{"name": name}],
        "object_ids": object_ids,
        "object_type": object_type,
    }
    headers = {"Authorization": getAuthHeader()}
    url = urlunparse(("https", HOST, "/api/v1/metrics", "", "", ""))
    r = requests.post(url, headers=headers, json=data)
    if r.status_code == 200:
        return r.json()
 #       print(
 #           f'Extracted {str(len(j["stats"]))} metrics from {str(j["from"])} until {str(j["until"])}'
 #       )
 #       return j["stats"]
    else:
        print("Failed to retrieve metrics")
        print(r.status_code)
        print(r.text)


def saveMetrics(metrics, filename):
    """
    Method that saves metrics to a CSV file.
        Parameters:
            metrics (list): The list of metric objects
            filename (str): The filename of the CSV file
    """
    with open(filename, "w") as csvfile:
        csvwriter = csv.writer(csvfile, dialect="excel")
        headers = []
        for header in metrics[0]:
            headers.append(header)
        csvwriter.writerow(headers)
        for metric in metrics:
            metric["time"] = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(metric["time"] / 1000)
            )
            metric["values"] = str(metric["values"][0])
            csvwriter.writerow(list(metric.values()))


def main():
    metrics = getMetrics("1hr", "http_server", "rsp", [1907], "device")
    saveMetrics(metrics, FILENAME)


if __name__ == "__main__":
    main()
