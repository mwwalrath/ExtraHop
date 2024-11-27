# ExtraHop Custom Device Manager

## Overview

This script manages **ExtraHop Custom Devices** by interacting with the ExtraHop REST API. It enables auditing, retrieving device metrics, searching, creating, patching, and deleting custom devices using data from CSV files.

The script logs detailed information about operations, with robust error-handling mechanisms to ensure traceability of issues.

## Features

- **Audit Custom Devices:** Retrieve and export details of existing custom devices from ExtraHop appliances.
- **Search for Devices:** Search for devices by name using the ExtraHop REST API.
- **Metric Querying:** Query metrics for a specific device.
- **Create Custom Devices:** Create custom devices on ExtraHop appliances using data from a CSV file.
- **Patch Custom Devices:** Update existing custom devices if they already exist (supports user confirmation or batch updating).
- **Delete Custom Devices:** Delete custom devices based on data from a CSV file.

## Requirements

- Python 3.6+
- ExtraHop REST API access
- ExtraHop API key for authentication

## Setup

1. Clone this repository or copy the script into a new `.py` file.
2. Install any missing dependencies (such as `argparse`, if not available by default).
3. Ensure your environment has access to the ExtraHop appliance with the necessary API permissions.

## Logging

The script generates a log file in the `logs` directory, named based on the script name and current datetime. Logs provide information about the flow of operations, successes, and errors encountered.

## Usage

The script is used to audit and manage custom devices on ExtraHop appliances. It can be invoked via command-line with different options for auditing, creating, patching, deleting, and more.

### Command-Line Arguments

| Argument             | Description                                                                                 |
|----------------------|---------------------------------------------------------------------------------------------|
| `--appliances`       | Path to the CSV file containing appliance hostnames and API keys.                           |
| `--audit`            | Audit the existing custom devices on the appliance(s).                                      |
| `--verbose`          | Include additional details in the CSV output for auditing purposes.                         |
| `--include_criteria` | Include the custom device criteria while auditing.                                          |
| `--include_metrics`  | Include custom device metrics in the audit output.                                          |
| `--create`           | Path to the CSV file containing custom devices to be created.                               |
| `--patch`            | Update existing custom device if it already exists.                                         |
| `--delete`           | Path to the CSV file containing custom devices to be deleted.                               |
| `--log-level`        | Set the logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). Defaults to `INFO`.|

### Example Usage

1. **Auditing Custom Devices:**

    ```sh
    python custom_device_manager.py --appliances appliances.csv --audit --verbose --include_criteria --include_metrics
    ```

    This command will audit custom devices from the ExtraHop appliance(s) listed in `appliances.csv`.

2. **Creating Custom Devices from CSV:**

    ```sh
    python custom_device_manager.py --appliances appliances.csv --create custom_devices.csv
    ```

    This command will create custom devices on ExtraHop appliance(s) using the list provided in `custom_devices.csv`.

3. **Patching Existing Custom Devices:**

    ```sh
    python custom_device_manager.py --appliances appliances.csv --create custom_devices.csv --patch
    ```

    This command will create custom devices and patch them if they already exist.

4. **Deleting Custom Devices from CSV:**

    ```sh
    python custom_device_manager.py --appliances appliances.csv --delete custom_devices_to_delete.csv
    ```

    This command will delete custom devices listed in `custom_devices_to_delete.csv`.

### CSV File Format

The script works with CSV files to load appliance and custom device information.

#### Appliances CSV:

The CSV should include the following headers:

| hostname    | api_key |
|-------------|---------|

#### Custom Devices CSV (Create/Patch:

The CSV should include the following headers:

| name | description | criteria |
|------|-------------|----------|

Criteria should include one or more of the following fields

| ipaddr_direction | ipaddr_peer | src_port_min | src_port_max | dst_port_min | dst_port_max | vlan_min | vlan_max |
|------------------|-------------|--------------|--------------|--------------|--------------|----------|----------|

#### Custom Devices CSV (Delete):

The CSV should include the following header:

| name |
|------|

## Error Handling

The script contains mechanisms to catch and log exceptions, including HTTP error responses and unexpected situations. Refer to the generated logs to troubleshoot issues.

## Dependencies

The script uses the following modules:

- **argparse**: For parsing command-line arguments.
- **http.client**: To interact with the ExtraHop REST API.
- **csv**: For handling CSV files used to store and retrieve appliance and custom device information.
- **logging**: For logging the execution details and errors.
- **ssl**: To create unverified SSL contexts for HTTPS connections.

## Disclaimer

This script is provided as-is with no warranty. Please test it in a non-production environment before running on live systems.

