# Description
This script reads in the `new_sensor_deployment_configs.json` file for configuration changes—some of which are in the `running_config`.  
By default, it runs in **audit mode**, which does not make any changes to the sensors but outputs a JSON of all the sensors' current `running_configs`.

---

## JSON Configs
- The JSON file contains a list of objects, where each object corresponds to a sensor.  
- You must supply the `sensor_hostname` and `sensor_api_key` for each sensor you wish to configure.  
- For each configuration, either provide the required data **or** leave the list/dictionary empty to omit setting that config.  
- If you want to create ODS targets with `additional_header Authorization` API key, you will need to hardcode the API key into that `key:value` pair.

---

## Python Library Dependencies
- `requests`

---

## JSON Location
- The JSON file must be in the same directory as this script if you only want to supply the file name to the `-j` argument.  
- If it is located elsewhere, you must supply the full file path.

---

## Example Python CLI Arguments
```bash
python your_script.py -j new_sensor_deployment_configs.json -a False
