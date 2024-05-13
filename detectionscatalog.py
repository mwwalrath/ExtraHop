#!/usr/bin/python3

# COPYRIGHT 2022 BY EXTRAHOP NETWORKS, INC.
#
# This file is subject to the terms and conditions defined in
# file 'LICENSE', which is part of this source code package.

import json
import csv
import time
import requests
from urllib.parse import urlunparse
import base64
import sys

# --- USER DEFINED VARIABLES --- #

HOST = "extrahop-sa.cloud.extrahop.com"
ID = "1kvbc4go50a27g90vvvph0vvh1"
SECRET = "hafnl6biichetb35186te66hn7ap00id0jv0ji25c68cr27ippm"
TOKEN = ""
FILENAME = "detection_formats.csv"

# --- DO NOT EDIT BELOW THIS LINE ---- #

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

def getAuthHeader(force_token_gen = False):
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

def getDetections():
    """
    Method that retrieves detections from the ExtraHop system
        Parameters:
            types (string): Returns detections with the specified type
            limit (number): Returns Returns no more than the specified number of detections
        Returns:
            detections (list): A list of detections
    """
    headers = {"Authorization": getAuthHeader()}
    url = urlunparse(("https", HOST, "/api/v1/detections/formats", "", "", ""))
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        j = r.json()
        #print(json.dumps(j, indent = 4, separators=(". ", " = ")))
        return r.json()
    else:
        print("Failed to retrieve detection formats")
        print(r.status_code)
        print(r.text)

def saveDetections(detections_json, filename):
    """
    Method that saves detections to a CSV file.
        Parameters:
            detections (list): The JSON of detection objects
            filename (str): The filename of the CSV file
    """

    with open(filename, "w") as csvfile:
        csvwriter = csv.writer(csvfile, dialect="excel")
        count = 0
        for detections in detections_json:
            if count == 0:
                headers = detections.keys()
                csvwriter.writerow(headers)
                count += 1
                
            csvwriter.writerow(detections.values())

def main():
    detections = getDetections()
    saveDetections(detections, FILENAME)

if __name__ == "__main__":
    main()
