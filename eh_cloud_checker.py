import http.client
import ssl
import json
import csv

APPLIANCES_CSV = 'appliances.csv'
CONNECTION_STATUS_CSV = 'connection_status.csv'

def check_cloud_status(eh_host, api_key, connection, headers):
    connection = http.client.HTTPSConnection(eh_host, 443, contect=ssl._create_unverified_context())
    headers = {
        'accept': 'application/json',
        'Authorization': 'ExtraHop apikey=' + api_key
    }
    connection.request('GET', '/api/v1/appliances/0/cloudservices', headers=headers)
    response = connection.getresponse()
    data = response.read()
    array = json.loads(data.decode('utf-8'))
    return array

def main():
    with open(APPLIANCES_CSV, 'r') as csvfile:
        with open('cloud_status.csv', 'w') as new_csvfile:
            reader = csv.DictReader(csvfile)
            writer = csv.DictWriter(new_csvfile, fieldnames=['eh_host', 'connection_status', 'connection_status_color', 'last_activity_time'])
            writer.writeheader()
            for row in reader:
                eh_host = row['eh_host']
                api_key = row['api_key']
                cloud_status = check_cloud_status(eh_host, api_key)
                connection_status = cloud_status['connection_status']
                connection_status_color = cloud_status['connection_status_color']
                last_activity_time = cloud_status['last_activity_time']
                writer.writerow({'eh_host': eh_host, 'connection_status': connection_status, 'connection_status_color': connection_status_color, 'last_activity_time': last_activity_time})

if __name__ == '__main__':
    main()