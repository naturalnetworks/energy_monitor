"""
energy_monitor.py

Depenencies:
    paho-mqtt (https://pypi.org/project/paho-mqtt/)
    sense-hat (https://pypi.org/project/sense-hat/)

Update a SenseHAT LED Matrix with values from a Fronius inverter and Sungrow Battery
obtained from MQTT.

Column 0: Fronius PV Export (Green)
Column 1: Sungrow Export Active Power (Green)
Column 2: Fronius PV Import (Red)
Column 3: Sungrow Purchased Power (Red)
Column 4: Fronius PV Load (orange)
Column 5: Fronius PV Generation (Light Green)
Column 6: Sungrow Battery Charging/Discharging Rate (light purple/purple)
Column 7: Sungrow Battery Level (light blue)

Author: Ben Johns (bjohns@naturalnetworks.net)
"""

import time
import json
import threading
import paho.mqtt.client as mqtt

try:
    from sense_hat import SenseHat
except ImportError:
    print("SenseHAT library not found. Mocking SenseHat functionality.")
    # Define a mock SenseHat class to avoid errors
    class SenseHat:
        def __init__(self):
            pass

        def clear(self):
            pass

        def set_pixel(self, x, y, rgb):
            pass

        def low_light(self):
            pass

sense = SenseHat()
sense.clear()
sense.low_light = True

# Set some LED colours
red = (255, 0, 0)
green = (0, 255, 0)
blue = (0, 0, 255)
darkblue = (0, 0, 139)
lightred = (255,153,153)
lightgreen = (153,255,153)
lightblue = (153,153,255)
purple = (128, 0, 128)
lightpurple = (196, 64, 196)
orange = (255, 165, 0)

# Define MQTT topics and broker
fronius_topic = "home/fronius"
sungrow_topic = "home/sungrow"
device_id = "rpizero.home.arpa"
broker_address = "nas.home.arpa"
broker_port = 1883

# Define a function to print the LED matrix grid
def print_cli_matrix(matrix):
    print('1 2 3 4 5 6 7 8')
    for row in matrix:
        print(' '.join(row))
    print('')

# Initialize a 8x8 grid to represent the LED matrix
cli_matrix = [['O' for _ in range(8)] for _ in range(8)]

# Initialize variables to store cumulative values for Fronius and Sungrow data
cumulative_fronius_values = {
    'f_pvimport': 0,
    'f_pvexport': 0,
    'f_pvload': 0,
    'f_pvgeneration': 0
}

cumulative_sungrow_values = {
    'sg_purchased_power': 0,
    'sg_total_export_active__power': 0,
    'sg_battery_charging_power': 0,
    'sg_battery_discharging_power': 0,
    'sg_battery_level_soc': 0
}

# Define callback function for MQTT message reception
def on_message(client, userdata, msg):
    payload = json.loads(msg.payload)
    if msg.topic == fronius_topic:
        update_cumulative_fronius_values(payload)
    elif msg.topic == sungrow_topic:
        update_cumulative_sungrow_values(payload)
    update_senseHatLED(**cumulative_fronius_values, **cumulative_sungrow_values)

# Function to update cumulative values for Fronius data
def update_cumulative_fronius_values(payload):
    # Update cumulative values with new data from payload
    cumulative_fronius_values['f_pvimport'] = payload.get("pvImport", cumulative_fronius_values['f_pvimport'])
    cumulative_fronius_values['f_pvexport'] = payload.get("pvExport", cumulative_fronius_values['f_pvexport'])
    cumulative_fronius_values['f_pvload'] = payload.get("pvLoad", cumulative_fronius_values['f_pvload'])
    cumulative_fronius_values['f_pvgeneration'] = payload.get("pvGeneration", cumulative_fronius_values['f_pvgeneration'])

# Function to update cumulative values for Sungrow data
def update_cumulative_sungrow_values(payload):
    # Update cumulative values with new data from payload
    cumulative_sungrow_values['sg_purchased_power'] = payload.get("Purchased_Power", cumulative_sungrow_values['sg_purchased_power'])
    cumulative_sungrow_values['sg_total_export_active__power'] = payload.get("Total_Export_Active__Power", cumulative_sungrow_values['sg_total_export_active__power'])
    cumulative_sungrow_values['sg_battery_charging_power'] = payload.get("Battery_Charging_Power", cumulative_sungrow_values['sg_battery_charging_power'])
    cumulative_sungrow_values['sg_battery_discharging_power'] = payload.get("Battery_Discharging_Power", cumulative_sungrow_values['sg_battery_discharging_power'])
    cumulative_sungrow_values['sg_battery_level_soc'] = payload.get("Battery_Level_SOC", cumulative_sungrow_values['sg_battery_level_soc'])

# Function to animate battery charging or discharging
def animate_battery(charge_rate=0, discharge_rate=0, current_soc=0, charging_speed=0.1, discharge_speed=0.1):
    # Calculate the target state of charge based on charge and discharge rates
    target_soc = current_soc + charge_rate - discharge_rate
    
    # Determine direction of animation
    direction = 1 if charge_rate > discharge_rate else -1
    
    # Start animation loop
    for soc in range(current_soc, target_soc + direction, direction):
        # Clear only the current column
        sense.clear()
        
        # Calculate LED position based on SoC
        pixel_y = int((soc / 8) * 7)  # Convert SoC to LED row
        
        # Draw LED bar
        for i in range(pixel_y + 1):
            sense.set_pixel(7, 7 - i, blue)
            cli_matrix[7][7 - i] = 'B'

        # Draw LED bar
        #for i in range(8):
        #    sense.set_pixel(7, 7 - i, blue)
        #    cli_matrix[7][7 - i] = 'b'
            
        
        # Display LED matrix
        if direction == 1:
            time.sleep(charging_speed)
        else:
            time.sleep(discharge_speed)



# Function to update SenseHat LED Matrix with energy data
def update_senseHatLED(
    f_pvimport,
    f_pvexport,
    f_pvload,
    f_pvgeneration,
    sg_purchased_power,
    sg_total_export_active__power,
    sg_battery_charging_power,
    sg_battery_discharging_power,
    sg_battery_level_soc
    ):

    # Convert Sungrow energy values from kilowatts to watts
    sg_purchased_power *= 1000
    sg_total_export_active__power *= 1000
    sg_battery_charging_power *= 1000
    sg_battery_discharging_power *= 1000

    # Define a dictionary to hold the variable names and their corresponding values
    variables = {
        "f_pvimport": f_pvimport,
        "f_pvexport": f_pvexport,
        "f_pvgeneration": f_pvgeneration,
        "f_pvload": f_pvload,
        "sg_purchased_power": sg_purchased_power,
        "sg_total_export_active__power": sg_total_export_active__power,
        "sg_battery_charging_power": sg_battery_charging_power,
        "sg_battery_discharging_power": sg_battery_discharging_power,
    }

    # Loop through each variable and perform the division operation
    for key, value in variables.items():
        # Divide the value by the corresponding divisor
        variables[key] = int(value / 625)
        # Limit the value to a maximum of 8 LEDs
        variables[key] = min(variables[key], 8)

    # Extract the updated values from the dictionary
    led_f_pvimport = variables["f_pvimport"]
    led_f_pvexport = variables["f_pvexport"]
    led_f_pvgeneration = variables["f_pvgeneration"]
    led_f_pvload = variables["f_pvload"]
    led_sg_purchased_power = variables["sg_purchased_power"]
    led_sg_total_export_active__power = variables["sg_total_export_active__power"]
    led_sg_battery_charging_power = variables["sg_battery_charging_power"]
    led_sg_battery_discharging_power = variables["sg_battery_discharging_power"]
    
    # Convert battery level from percentage (0 - 100) to number of LEDs (8)
    led_sg_battery_level_soc = int(sg_battery_level_soc/12.5)

    # logger.debug("update_senseHatLED params now: " + str(pvimport) + ", " + str(pvexport) + ", " + str(pvload) + ", " + str(pvgeneration))

    # Clear LED Matrix
    sense.clear()

    # Clear LED Matrix
    global cli_matrix
    cli_matrix = [['O' for _ in range(8)] for _ in range(8)]

    # Starting with Fronius PV export and Sungrow Export
    if led_f_pvexport > 0:
        for i in range(led_f_pvexport):
            sense.set_pixel(0, i, green)
            cli_matrix[0][i] = 'G'
    if led_sg_total_export_active__power > 0:
        for i in range(led_sg_total_export_active__power):
            sense.set_pixel(1, i, green)
            cli_matrix[1][i] = 'G'

    # Then Fronius PV import and Sungrow Import
    if led_f_pvimport > 0:
        for i in range(led_f_pvimport):
            sense.set_pixel(2, i, red)
            cli_matrix[2][i] = 'R'
    if led_sg_purchased_power > 0:
        for i in range(led_sg_purchased_power):
            sense.set_pixel(3, i, red)
            cli_matrix[3][i] = 'R'

    # Then Fronius Self Consumption and Generation
    if led_f_pvload > 0:
        for i in range(led_f_pvload):
            sense.set_pixel(4, i, orange)
            cli_matrix[4][i] = 'r'
    if led_f_pvgeneration > 0:
        for i in range(led_f_pvgeneration):
            sense.set_pixel(5, i, lightgreen)
            cli_matrix[5][i] = 'g'

    # Then Sungrow Battery Charging and Discharging
    if led_sg_battery_discharging_power > 0:
        for i in range(led_sg_battery_discharging_power):
            sense.set_pixel(6, i, purple)
            cli_matrix[6][i] = 'P'
    elif led_sg_battery_charging_power > 0:
        for i in range(led_sg_battery_charging_power):
            sense.set_pixel(6, i, lightpurple)
            cli_matrix[6][i] = 'p'

    # Then Sungrow Battery Level
    if led_sg_battery_level_soc > 0:
        for i in range(led_sg_battery_level_soc):
            sense.set_pixel(7, i, darkblue)
            cli_matrix[7][i] = 'B'


    # Optionally, Sungrow Battery Charging, animated
    # animate_battery(led_sg_battery_charging_power, led_sg_battery_discharging_power, led_sg_battery_level_soc)

    # Print the LED matrix grid - remark this out when no longer testing
    print_cli_matrix(cli_matrix)

def main():
    # Initialize MQTT client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(broker_address, broker_port, 60)
    client.subscribe(fronius_topic)
    client.subscribe(sungrow_topic)
    client.on_message = on_message
    client.loop_start()

    # Start the animation loop in a separate thread
    # animation_thread = threading.Thread(target=animate_battery)
    # animation_thread.daemon = True  # Set the thread as a daemon so it terminates when the main thread exits
    # animation_thread.start()

    # Main loop to keep the program running
    while True:
        time.sleep(0.1)

# Check if the script is executed as the main program
if __name__ == "__main__":
    main()