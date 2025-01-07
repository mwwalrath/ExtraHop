# ExtraHop Password Update Script

This Python script automates the process of updating the `setup` user's password across multiple ExtraHop appliances. Appliance details (IP/FQDN and API keys) are stored in a CSV file for iteration.

---

## Features

1. **Automated Password Update**  
   Updates the password of the `setup` user on all appliances listed in the CSV file.

2. **Logging**  
   Logs all script activities, errors, and results to a timestamped log file.

---

## Requirements

- **Python Version:** 3.x
- **Libraries:** Built-in libraries (`http.client`, `json`, `ssl`, `logging`, `datetime`, `os`).

---

## Setup and Configuration

### 1. CSV File: `appliances.csv`
The script uses `appliances.csv` to retrieve the appliance details. The CSV file should have the following headers:
- `eh_host`: IP or FQDN of the appliance.
- `api_key`: API key for accessing the appliance.

Example:
```csv
eh_host,api_key
192.168.1.1,example_api_key_1
192.168.1.2,example_api_key_2
```

### 2. Password Configuration
Update the `password` variable in the script to set the new password for the `setup` user.

### 3. Logging Directory
Logs will be saved in the `logs` folder within the script's directory. Ensure the script has permissions to create this folder and write log files.

### 4. Execution
Run the script using:
```bash
python3 script_name.py
```

---

## How It Works

1. **Read `appliances.csv`**  
   The script reads the appliance details (`eh_host` and `api_key`) from the CSV file.

2. **Update Password**  
   For each appliance, the script sends a `PATCH` request to update the password of the `setup` user.

3. **Log Results**  
   All script activities, including successes and errors, are logged in a timestamped log file.

---

## Logs

Logs are saved in the `logs` folder with a filename format of `update_password_log_<timestamp>.log`. Logs include:
- Connection details.
- Status of password updates.
- Any errors encountered during execution.

---

## Notes

- **Authentication:** Ensure the API keys in `appliances.csv` have sufficient privileges to update the `setup` user's password.
- **Error Handling:** The script logs detailed errors for failed operations, including invalid API keys, permissions issues, and network errors.
- **Safety:** This script is designed to update the `setup` user only.

---

## License

This script is subject to the terms and conditions defined in the `LICENSE` file included in this source code package.
## Support

For issues or questions, contact your administrator or refer to the ExtraHop documentation.
```
