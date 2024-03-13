import requests #Girard [ExtraHop] - girardo@extrahop.com
from requests.packages.urllib3.exceptions import InsecureRequestWarning #remove if using secure requests & remove verify=False
import json
import pandas as pd

print('*'*33)
print("Starting...")

api_key = '123456789apikey' #apikey for an EDA or ECA
IPaddress = 'ordway' #ip address or hostname for the api request
headers = {'Accept': 'application/json', 'Authorization': 'ExtraHop apikey=' + api_key}
apiEndPoint = '/api/v1/detections/formats'

requests.packages.urllib3.disable_warnings(InsecureRequestWarning) #remove if using secure requests
response = requests.get('https://' + IPaddress + apiEndPoint, headers=headers, verify=False)
print('Status Code from ExtraHop:')
print(response.status_code)
if response.ok:
    result = response.json()

    df_json = pd.json_normalize(result)
    df_json.to_csv('detectionsList.csv')

print('Done')
print('*'*33)
