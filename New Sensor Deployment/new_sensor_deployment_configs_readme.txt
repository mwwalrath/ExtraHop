DESCRIPTION
This script will read in the new_sensor_deployment_configs.json file for configuration changes, some of which are in the running_config.
It defaults to audit_mode, which will not make any changes to the sensors but will output a json of all the sensors current running_configs.

JSON CONFIGS
This is a list of objects, each object corresponds to a sensor, so therefor you will have to supply the sensor_hostname and sensor_api_key for each sensor you wish to configure.
For each configuration, supply the required data OR leave the list or dictionary empty to omit setting that config.
If you wish to create ODS targets with additional_header Authorization api key, you will need to hardcode the api key into that key value.

PYTHON LIBRARY DEPENDENCIES
requests

JSON LOCATION
The json must be in the same directory as the script in order to pass just the file name to argument -c as seen below.
If it resides elsewhere, you will need to supply the full file path.

EXAMPLE PYTHON CLI ARGUMENTS
-j new_sensor_deployment_configs.json -a False

ARGUMENT DESCRIPTIONS
-j
Path to json sensor config file, if it resides in the script directory you only need the filename and extension
-a
Default True. Will output a json of all sensors' current running_configs. This mode will not run any running_config changes."
To make running_config changes you must set this to False.
-h
Help to see additional optional arguments.
