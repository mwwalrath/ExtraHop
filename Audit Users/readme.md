# ExtraHop User Management Script

This Python script facilitates the auditing and deletion of user accounts across multiple ExtraHop appliances. It provides an automated way to manage user accounts based on predefined CSV files.

---

## Features

1. **Audit User Accounts**  
   Retrieve all active user accounts from the specified appliances and generate a CSV file listing all unique usernames.

2. **Delete Inactive User Accounts**  
   Remove specified inactive user accounts from the appliances based on a provided CSV file.

3. **Logging**  
   Logs all script activities, errors, and results in a detailed log file.

---

## Requirements

- **Python Version:** 3.x
- **Libraries:** Built-in libraries (`csv`, `datetime`, `http.client`, `json`, `logging`, `os`, `ssl`, `sys`).

---

## Setup and Configuration

### 1. CSV Files
The script relies on the following CSV files:

- `appliances.csv`  
  Contains a list of ExtraHop appliances with the following headers:
  - `eh_host`: IP or FQDN of the appliance
  - `api_key`: API key for accessing the appliance

- `user_audit.csv`  
  (Output) Generated file containing all unique user IDs from the appliances during the audit process.

- `inactive_users.csv`  
  Contains a list of user accounts to be deleted with the following header:
  - `username`: Username to delete.

### 2. User Configuration
Modify the following variables in the script as needed:
- `AUDIT_USERS`: Set to `True` to audit user accounts and generate a CSV file.
- `DELETE_USERS`: Set to `True` to delete user accounts listed in `inactive_users.csv`.

### 3. Execution
Run the script using:
```
python3 script_name.py
