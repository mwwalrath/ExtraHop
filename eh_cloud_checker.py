import http.client
import ssl
import json
import csv

APPLIANCES_CSV = 'appliances.csv'
CONNECTION_STATUS_CSV = 'connection_status.csv'

def check_cloud_status(eh_host, api_key):
    try:
        connection = http.client.HTTPSConnection(eh_host, 443, context=ssl._create_unverified_context())
        headers = {
            'accept': 'application/json',
            'Authorization': 'ExtraHop apikey=' + api_key
        }
        connection.request('GET', '/api/v1/appliances/0/cloudservices', headers=headers)
        response = connection.getresponse()
        if response.status == 200:
            data = response.read()
            cloud_status = json.loads(data.decode('utf-8'))
            return cloud_status
        else:
            print(f'Error occured while fetching cloud status for {eh_host}: {response.status} {response}')
    except(http.client.BadStatusLine, http.client.IncompleteRead, http.client.HTTPException, ssl.SSLError, json.JSONDecodeError) as e:
        print(f'Error occured while fetching cloud status for {eh_host}: {e}')
        return None

def main():
    with open(APPLIANCES_CSV, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        with open('cloud_status.csv', 'w') as new_csvfile:
            writer = csv.DictWriter(new_csvfile, fieldnames=['eh_host', 'connection_status', 'connection_status_color', 'last_active_time'])
            writer.writeheader()
            for row in reader:
                eh_host = row['eh_host']
                api_key = row['api_key']
                cloud_status = check_cloud_status(eh_host, api_key)
                if cloud_status:
                    connection_status = cloud_status['connection_status']
                    connection_status_color = cloud_status['connection_status_color']
                    last_active_time = cloud_status['last_active_time']
                    writer.writerow({'eh_host': eh_host, 'connection_status': connection_status, 'connection_status_color': connection_status_color, 'last_active_time': last_active_time})
                else:
                    writer.writerow({'eh_host': eh_host, 'connection_status': 'N/A', 'connection_status_color': 'N/A', 'last_active_time': 'N/A'})

if __name__ == '__main__':
    main()
