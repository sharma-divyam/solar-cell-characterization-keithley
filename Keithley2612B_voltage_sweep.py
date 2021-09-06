#!/usr/bin/env python
# coding: utf-8

#  Keithley 2612B SMU TFT Characterization

#  Libraries

from keithley2600 import Keithley2600
import numpy as np
import pyvisa
import csv
from datetime import datetime

def get_resources():
    rm = pyvisa.ResourceManager()
    address = rm.list_resources()
    resources = (rm, address)
    return resources

def get_target_volt(start_volt):
    """
    Return the target volt. Check validity of the input.
    :param start_volt: The starting point of the voltage sweep. 
    """
    while True:
        # Keeps asking the user for the valid target volt until they correclty provide one.
        target_volt = float (input ('Set the target voltage (in Volts) for sweep: '))
        return target_volt
        
def get_step_volt(start_volt, target_volt):
    """
    Return the step volt. It is the magnitude of steps in which the sweep will occur. Check validity of the input.
    :param start_volt: The starting point of the voltage sweep. 
    :param target_volt: The end point of the voltage sweep. 
    """
    while True:

        step_volt = float (input ('Set the size of steps (in Volts) of sweep: ')) 
        
        if step_volt <= target_volt - start_volt:
            return step_volt
        else:
            print ('INVALID INPUT: Step must be less than or equal to the difference between starting and target voltage')

def get_integration_time ():
    """
    Return integration time. Check if input is within the range suggested by Keithley2600 manual.
    """
    while True:
        integration_time = float (input('Set the integration time for each data point (in PLC): '))
        if integration_time >= 0.001 and integration_time <= 25:
            return integration_time
        else: 
            print('INVALID INPUT: The integration time must be between 0.001 and 25 PLC.')

def get_sweep_type():
    """
    Return boolean for sweep type based on the character input.
    """
    while True:
        sweep_type = input ('Choose between pulsed and continuous sweep (enter P or C): ')
        if sweep_type == 'P' or sweep_type == 'p':
            return True  
        elif sweep_type == 'C' or sweep_type == 'c':
            return False
        else:
            print ('INVALID INPUT')

def sweep_operation(smu_id, steps_no, measure_delay, nplc, start, end, scan_rate):

    smu_id.timeout = 300000
    
    smu_id.write("errorqueue.clear()")

    print("Scan rate is: " + str(scan_rate))
    # Set source function to DC volts
    smu_id.write ("smua.source.func = smua.OUTPUT_DCVOLTS")
  
    if start > end:
        max = start
        min = end
    else:
        max = end
        min = start
    
    # calculate time per voltage
    scan_interval_time = (((max *1.0000000000 - min * 1.0000000000)/(steps_no - 1)) / (scan_rate/1000))
    
    # Subtract NPLC delay
    scan_interval_time = scan_interval_time - (nplc/50)
    #log.info("Wait time for voltage = %f" % scan_interval_time)
    
    print("Interval time is: " + str(scan_interval_time))
    
    # Set source delay 
    smu_id.write("smua.source.delay = %f" % scan_interval_time)   

    #smu_id.write (f"smua.measure.nplc = {nplc}")
    
    
    # Set current compliance. From my code. This is necessary for measuring our devices. 
    smu_id.write("smua.source.limiti = 30e-3")
    
    
    # Clear the buffers for storage
    smu_id.write ("smua.nvbuffer1.clear()")
    smu_id.write ("smua.nvbuffer2.clear()")
    smu_id.write ("smua.nvbuffer1.clearcache()")
    smu_id.write ("smua.nvbuffer2.clearcache()")
    
    # Configure timestamp collection option. I changed it to buffer1
    smu_id.write ("smua.nvbuffer1.collecttimestamps = 1")

    # We need to include a sweep direction option. 
    # Set the sweep parameters
    smu_id.write (f"smua.trigger.source.linearv ({start}, {end}, {steps_no})")
    smu_id.write("smua.trigger.measure.action = smua.ENABLE")  # ENABLE the sweep


    # Set to measure current, and collect both current and voltage
    smu_id.write ("smua.trigger.measure.iv(smua.nvbuffer1, smua.nvbuffer2)")
    smu_id.write ("smua.trigger.source.action = smua.ENABLE")


    # Set trigger count
    smu_id.write (f"smua.trigger.count = {steps_no}")

    # Turn on output and run
    smu_id.write ("smua.source.output = smua.OUTPUT_ON")
    smu_id.write ("smua.trigger.initiate()")
   
    
    # To check if the sweep is complete. This is necessary. Otherwise python continues executing the rest of the code,
    # while the Keithley is still measuring. We can technically add just a sleep, but I don't fancy using a hardcoded sleep.
    # Users won't want to include the time it should sleep too. Therefore it must be automatic.
    smu_id.write("*OPC?")
    id = smu_id.read()
    print("Initial OPC ID = " + str(id))
    

    while int(id) != 1:
        smu_id.write("*OPC?")
        id = smu_id.read()
        sleep(1)
        print("Current ID = " + str(id))
        
    # Turn output off. We should do this. Otherwise the Keithley holds it at the voltage it stops at.
    # This will affect the measurement of our devices. We cannot leave it under bias for too long due to ionic migration.
    smu_id.write("smua.source.output = smua.OUTPUT_OFF")
    
    ###### GET OUTPUT (TYPE IS STRING) THEN CONVERT TO FLOAT NUMPY ARRAY
    
    # Get the currents
    smu_id.write(f"printbuffer(1, {steps_no}, smua.nvbuffer1.readings)")
    current_string = smu_id.read()

    
    # Get the voltages
    smu_id.write(f"printbuffer(1, {steps_no}, smua.nvbuffer2.readings)")
    voltage_string = smu_id.read()

    
    # Get the timestamps
    smu_id.write(f"printbuffer(1, {steps_no}, smua.nvbuffer1.timestamps)")
    timestamp_string = smu_id.read()
    
    current_string_array = current_string.split(',')
    voltage_string_array = voltage_string.split(',')
    timestamp_string_array = timestamp_string.split(',')
    
    currents = np.array(current_string_array, dtype=float)
    voltages = np.array(voltage_string_array, dtype=float)
    timestamps = np.array(timestamp_string_array, dtype=float)

    output = [voltages, currents, timestamps]

    smu_id.write ("smua.nvbuffer1.clear()")
    smu_id.write ("smua.nvbuffer2.clear()")
    smu_id.write ("smua.nvbuffer1.clearcache()")
    smu_id.write ("smua.nvbuffer2.clearcache()")
    

    return output
    """
    output index -> stored parameter
    0 -> voltage in Volt 
    1 -> current in Ampere
    2 -> timestamps (not sure of the format)
    
    """


# Connecting the instrument

rm = get_resources()[0]
address_list = get_resources()[1]

if len(address_list) == 0:
    print ('No device connected')
    
else:
    print ('VISA address of the connected devices are:')
    
    for i in range(len(address_list)):
        print (f"{i}: {address_list[i]}")
    
    
    is_valid_input = False
    
    while not is_valid_input:

        get_address_existence = input ('Is the VISA address of the SMU listed? (Y/N): ').lower()

        if get_address_existence == 'y':
            is_valid_input = True
            smu_index = int(input('Enter the index number of the SMU: '))
            smu = rm.open_resource(address_list[smu_index])
            is_connected = True
            print ('Connected successfully!')

            print ('VOLTAGE SWEEP PARAMETERS:')

            # Voltage sweep parameters

            # Source voltage from Channel A

            start_volt = float (input ('Set the starting voltage (in Volts) for sweep: '))

            target_volt = get_target_volt(start_volt)
            
            steps_num = int (input ('Enter the number of steps: '))

            integration_time = get_integration_time()
            
            measure_delay = 0

            #pulsed = get_sweep_type()

            scan_rate = float(input ('Enter scan rate in mV/s: '))
            
            # VI measurement
            print ('Voltage sweep being conducted...')
            test_output = sweep_operation (smu, steps_num, measure_delay, integration_time, start_volt, target_volt, scan_rate) 
            end_time = datetime.now()
            print (f"Sweep successfully completed on {end_time}.")

            # scan rate 
            # (Unsure of the data type of measured voltage and timestamps. This will only work if both are float or int)   
    
            del_t = np.empty((1,steps_num))
            print("The test_output value is: " + str(test_output[0]))
            print("The length is: " + str(len(test_output[2])))
            for i in range(len(test_output[2])):
                del_t[0][i] = test_output[2][i] - test_output[2][0]

            print("del t = " + str(del_t))

            scan_rate = np.polyfit(del_t[0], test_output[0], 1)[0]

            print (f"The scan rate of the sweep operation was {scan_rate} V/s")

              

            # Data acquisition
            vi_output = [test_output[0], test_output[1], test_output[2]]
            title = str (input('Give a title for the test conducted: '))
            vi_output_transpose = np.transpose(vi_output)
            file_path = str (input('Give file path and file name (with .csv extension) to record the data: '))
            headers = ['Voltage (in Volt)', 'Current (in Ampere)', 'Timestamp']

            with open(file_path, 'w+') as csv_file:
                write = csv.writer(csv_file)
                write.writerow(title)
                write.writerow(headers)
                write.writerows(vi_output_transpose)
                write.writerow(f"Date and Time of measurement: {end_time }")

        
        elif get_address_existence == 'n': 
            is_valid_input = True
            print ('Please ensure that the SMU is connected properly')


        else: 
            print ('INVALID INPUT')
