import http.client
import ssl
import json
import csv
import socket
import time

APPLIANCES_CSV = 'appliances.csv'
CONNECTION_STATUS_CSV = 'connection_status.csv'

def check_cloud_status(eh_host, api_key):
    """
    This function sends a GET request to the ExtraHop API to fetch the cloud status of a given appliance.

    Parameters:
    eh_host (str): The hostname or IP address of the ExtraHop appliance.
    api_key (str): The API key for authentication.

    Returns:
    dict: A dictionary containing the cloud status information if the request is successful.

    Raises:
    http.client.BadStatusLine: If the server does not return a valid HTTP response.
    http.client.IncompleteRead: If the server does not send the complete response.
    http.client.HTTPException: If an HTTP-related error occurs.
    ssl.SSLError: If an SSL error occurs.
    json.JSONDecodeError: If the response data cannot be decoded as JSON.
    TimeoutError: If the request times out.
    socket.gaierror: If the host cannot be resolved.
    """
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
    except(http.client.BadStatusLine, http.client.IncompleteRead, http.client.HTTPException, ssl.SSLError, json.JSONDecodeError, TimeoutError, socket.gaierror) as e:
        print(f'Error occured while fetching cloud status for {eh_host}: {e}')
  
def convert_epoch_time(epoch_time):
    """
    Converts an epoch time to a human-readable format.

    Parameters:
    epoch_time (int): The epoch time to convert. This is expected to be in milliseconds.

    Returns:
    str: The converted time in the format "Day, DD Mon YYYY HH:MM:SS +0000".
         If the input is None, returns 'N/A'.
         If an error occurs during conversion, returns 'Invalid Time: <epoch_time>'.

    Raises:
    OSError: If the localtime() function fails to convert the epoch time. 
    """
    if epoch_time is None:
        return 'N/A'
    try:
        # Convert epoch time from milliseconds to seconds
        epoch_time_seconds = epoch_time / 1000
        # Convert the epoch time to a human-readable format
        return time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.localtime(epoch_time_seconds))
    except OSError as e:
        print(f'Error occured while converting epoch time for {epoch_time}: {e}')
        return(f'Invalid Time: {epoch_time}')
    
def main():
    """
    The main function reads the appliances from the CSV file, fetches the cloud status for each appliance,
    and writes the results to a new CSV file.

    Parameters:
    None

    Returns:
    None
    """
    with open(APPLIANCES_CSV, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        with open('cloud_status.csv', 'w', newline='') as new_csvfile:
            writer = csv.DictWriter(new_csvfile, fieldnames=['eh_host', 'connection_status', 'connection_status_color', 'last_active_time'])
            writer.writeheader()
            for row in reader:
                eh_host = row['eh_host']
                api_key = row['api_key']
                cloud_status = check_cloud_status(eh_host, api_key)
                if cloud_status:
                    connection_status = cloud_status['connection_status']
                    connection_status_color = cloud_status['connection_status_color']
                    last_active_time_epoch = cloud_status['last_active_time']
                    last_active_time = convert_epoch_time(last_active_time_epoch)
                    writer.writerow({'eh_host': eh_host, 'connection_status': connection_status, 'connection_status_color': connection_status_color, 'last_active_time': last_active_time})
                else:
                    writer.writerow({'eh_host': eh_host, 'connection_status': 'N/A', 'connection_status_color': 'N/A', 'last_active_time': 'N/A'})

if __name__ == '__main__':
    main()
