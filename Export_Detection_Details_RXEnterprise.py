import requests
import csv
import base64
import datetime
import os
from urllib.parse import urlunparse
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


HOST = ""
Revealx360 = False
API_KEY = ""
Lookback_Days = 14

def getToken():
    #Method that generates and retrieves a temporary API access token for Reveal(x) 360 authentication.
    #Returns: A temporary API access token
    auth = base64.b64encode(bytes(ID + ":" + SECRET, "utf-8")).decode("utf-8")
    headers = {
        "Authorization": "Basic " + auth,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    url = urlunparse(("https", HOST, "/oauth2/token", "", "", ""))
    r = requests.post(url, headers=headers, data="grant_type=client_credentials")
    if r.status_code == 200:
        return r.json()["access_token"]
    else:
        return 0

def getDetectionProperties(token):
    url = urlunparse(("https", HOST, "/api/v1/detections/formats", "", "", ""))
    headers = {"Authorization": token}
    r = requests.get(url, headers=headers, verify=False)
    if r.status_code == 200:
        return r.json()
    else:
        print("Failed to retrieve Detection Properties!")
        print(r.text)
        print(status_code)
        
def ctime():
    current_date = datetime.datetime.today().strftime('%Y%m%d')
    return current_date

def pdaytime(days):
    previous_date = datetime.datetime.today() - datetime.timedelta(days=days)
    previous_date = previous_date.strftime('%Y%m%d')
    return previous_date


if Revealx360:
    token = getToken()
    token = "Bearer " + token
else:
    token = "ExtraHop apikey=%s" % API_KEY


previous_file_exists = False

print("Checking if there's any detection catalogs csv file in the past 7 days...")
for i in range(1, Lookback_Days):
    if os.path.exists(pdaytime(i) + '_Detections_List.csv'):
        previous_filename = pdaytime(i) + '_Detections_List.csv'
        previous_file_exists = True
        break

if previous_file_exists:
    print("Previous Detection Catalog file exists as " + previous_filename + "!!")
    Previous_detection_names = []
    Previous_user_created_detections = 0
    with open(previous_filename, mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            Previous_detection_names.append(row['Detection Name'])
            if row['User_Created'] == "TRUE":
                Previous_user_created_detections += 1
else:
    print("Previous Detection Catalog file do not exist!!")

Detections = getDetectionProperties(token)
Detection_names = []

with open(ctime() + '_Detections_List.csv', mode='w') as Detections_List:
    Detection_write = csv.writer(Detections_List, delimiter=',', quotechar='"')
    Detection_write.writerow(['Detection Name', 'Author', 'User_Created', 'Mitre Categories'])

    user_created_detections = 0
    for Detection in Detections:
        Detection_names.append(Detection['display_name'])
        Detection_write.writerow([Detection['display_name'], Detection['author'], Detection['is_user_created'], Detection['mitre_categories']])
        if Detection['is_user_created']:
            user_created_detections += 1

total_number_of_detections = len(Detections)

with open(ctime() + '_Detections_Changelog.log', mode='w') as log:
    print("Total number of Detections: " + str(total_number_of_detections))
    print("Total number of inbuilt ExtraHop Detections: " + str(total_number_of_detections - user_created_detections))
    print("Total number of custom user detections: " + str(user_created_detections))
    log.write("Total number of Detections: " + str(total_number_of_detections) + '\n')
    log.write("Total number of inbuilt ExtraHop Detections: " + str(total_number_of_detections - user_created_detections) + '\n')
    log.write("Total number of custom user detections: " + str(user_created_detections) + '\n')

    if previous_file_exists:
        previous_total_number_of_detections = len(Previous_detection_names)
        difference_detections_length = abs(previous_total_number_of_detections - total_number_of_detections)
        print("Previous number of detections: " + str(previous_total_number_of_detections))
        log.write("Previous number of detections: " + str(previous_total_number_of_detections) + '\n')

        Additional_Detections_from_previous = set(Previous_detection_names) - set(Detection_names)
        Additional_Detections_from_latest = set(Detection_names) - set(Previous_detection_names)
        print("\nDetections found in previous catalog compared to latest catalog: ")
        log.write("\nDetections found in previous catalog compared to latest catalog: \n")
        for detection in Additional_Detections_from_previous:
            print(detection)
            log.write(detection + "\n")

        print("\nAdditional detections found in latest catalog: ")
        log.write("\nAdditional detections found in latest catalog: \n")
        for detection in Additional_Detections_from_latest:
            print(detection)
            log.write(detection + "\n")
    else:
        print("No previous detection catalogs found!!")
        log.write("No previous detection catalogs found!!\n")
