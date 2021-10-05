#############################################################
## NeewerLite-Python
## by Zach Glenwright
#############################################################
##   > https://github.com/taburineagle/Neewer-PythonLite <
#############################################################
## A cross-platform Python script using the bleak and
## PySide2 libraries to control Neewer brand lights via
## Bluetooth on multiple platforms - 
##          Windows, Linux/Ubuntu, MacOS and RPi
#############################################################
## Based on the NeewerLight project by @keefo (Xu Lian)
##   > https://github.com/keefo/NeewerLite <
#############################################################

import sys

try:
    from winrt import _winrt
    _winrt.uninit_apartment()
except Exception as e:
    pass # if there is an exception to this module loading, you're not on Windows

import asyncio
import threading
import time

from bleak import BleakScanner, BleakClient
from datetime import datetime
from PySide2.QtWidgets import QApplication, QMainWindow, QTableWidgetItem
from ui_NeewerLightUI import Ui_MainWindow

sendValue = [] # an array to hold the values to be sent to the light
lastAnimButtonPressed = 1 # which animation button you clicked last - if none, then it defaults to 1 (the police sirens)

availableLights = [] # the list of Neewer lights currently available to control - format: [Bleak Scan Object, Bleak Connection]

threadAction = "" # the current action to take from the thread
setLightUUID = "69400002-B5A3-F393-E0A9-E50E24DCCA99" # the UUID to send information to the light

# FOR TESTING PURPOSES
startup_findLights = True # whether or not to look for lights when the program starts
startup_connectLights = True # whether or not to auto-connect to lights after finding them
printDebug = True # show debug messages in the console for all of the program's events

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        global startup_findLights

        QMainWindow.__init__(self)
        self.setupUi(self) # set up the main UI
        self.connectMe() # connect the function handlers to the widgets
        
        if startup_findLights == False: # if we're not set to detect lights on startup, then just automatically compute the value
            self.computeValueCCT()
        else: # if we are, then display the "searching" status on the status bar
            self.statusBar.showMessage("Please wait - searching for Neewer lights...")

        self.show
    
    def connectMe(self):
        self.scanCommandButton.clicked.connect(self.startSelfSearch)
        self.tryConnectButton.clicked.connect(self.startConnect)
              
        self.lightTable.itemSelectionChanged.connect(self.checkConnect)    
        
        self.ColorModeTabWidget.currentChanged.connect(self.autoComputeValue)

        self.Slider_CCT_Hue.valueChanged.connect(self.computeValueCCT)
        self.Slider_CCT_Bright.valueChanged.connect(self.computeValueCCT)

        self.Slider_HSL_1_H.valueChanged.connect(self.computeValueHSL)
        self.Slider_HSL_2_S.valueChanged.connect(self.computeValueHSL)
        self.Slider_HSL_3_L.valueChanged.connect(self.computeValueHSL)

        self.Slider_ANM_Brightness.valueChanged.connect(self.computeValueANM(0))
        self.Button_1_police_A.clicked.connect(lambda: self.computeValueANM(1))
        self.Button_1_police_B.clicked.connect(lambda: self.computeValueANM(2))
        self.Button_1_police_C.clicked.connect(lambda: self.computeValueANM(3))
        self.Button_2_party_A.clicked.connect(lambda: self.computeValueANM(4))
        self.Button_2_party_B.clicked.connect(lambda: self.computeValueANM(5))
        self.Button_2_party_C.clicked.connect(lambda: self.computeValueANM(6))
        self.Button_3_lightning_A.clicked.connect(lambda: self.computeValueANM(7))
        self.Button_3_lightning_B.clicked.connect(lambda: self.computeValueANM(8))
        self.Button_3_lightning_C.clicked.connect(lambda: self.computeValueANM(9))

        self.turnOnButton.clicked.connect(self.turnLightOn)
        self.turnOffButton.clicked.connect(self.turnLightOff)

    # CHECK TO SEE WHETHER OR NOT TO ENABLE/DISABLE THE "Connect" BUTTON
    def checkConnect(self):
        if len(self.lightTable.selectionModel().selectedRows()) > 0:
            self.tryConnectButton.setEnabled(True) # if we have a light selected in the table, then enable the "Connect" button
        else:
            self.tryConnectButton.setEnabled(False) # otherwise, disable it

    # ADD A LIGHT TO THE TABLE VIEW
    def setTheTable(self, infoArray, rowToChange = -1):
        if rowToChange == -1:
            currentRow = self.lightTable.rowCount()       
            self.lightTable.insertRow(currentRow) # if rowToChange is not specified, then we'll make a new row at the end
        else:
            currentRow = rowToChange # change data for the specified row

        if infoArray[0] != "": # the name of the light
            self.lightTable.setItem(currentRow, 0, QTableWidgetItem(infoArray[0]))
        if infoArray[1] != "": # the MAC address of the light
            self.lightTable.setItem(currentRow, 1, QTableWidgetItem(infoArray[1]))
        if infoArray[2] != "": # the Linked status of the light
            self.lightTable.setItem(currentRow, 2, QTableWidgetItem(infoArray[2]))
        if infoArray[3] != "": # the current status message of the light
            self.lightTable.setItem(currentRow, 3, QTableWidgetItem(infoArray[3]))

        self.lightTable.resizeRowsToContents()
             
    # CLEAR ALL LIGHTS FROM THE TABLE VIEW
    def clearTheTable(self):
        if self.lightTable.rowCount() != 0:
            self.lightTable.clearContents()
            self.lightTable.setRowCount(0)

    # TELL THE BACKGROUND THREAD TO START LOOKING FOR LIGHTS
    def startSelfSearch(self):
        global threadAction
        threadAction = "discover"
        
        self.statusBar.showMessage("Please wait - searching for Neewer lights...")

    # TELL THE BACKGROUND THREAD TO START CONNECTING TO LIGHTS
    def startConnect(self):
        global threadAction
        threadAction = "connect"

    # TELL THE BACKGROUND THREAD TO START SENDING TO THE LIGHTS
    def startSend(self):
        global threadAction

        if threadAction == "":
            threadAction = "send"
    
    # IF YOU CLICK ON ONE OF THE TABS, THIS WILL SWITCH THE VIEW/SEND A NEW SIGNAL FROM THAT SPECIFIC TAB
    def autoComputeValue(self, i):
        if i == 0:
        	self.computeValueCCT() # calculate the current CCT value
        elif i == 1:
        	self.computeValueHSL() # calculate the current HSL value
        elif i == 2:
            pass
            # TURNED THIS OFF SO THE ANIMATION DOESN'T IMMEDIATELY TRIGGER WHEN GOING TO THIS PAGE
        	# self.computeValueANM(lastAnimButtonPressed) # calculate the current ANM value, based on the last button pressed

    # COMPUTE A BYTESTRING FOR THE CCT SECTION
    def computeValueCCT(self):
        self.TFV_CCT_Hue.setText(str(self.Slider_CCT_Hue.value()) + "00K")
        
        calculateByteString(colorMode="CCT",\
                            temp=str(int(self.Slider_CCT_Hue.value())),\
                            brightness=str(int(self.Slider_CCT_Bright.value())))

        self.statusBar.showMessage("Current value (CCT Mode): " + updateStatus())
        self.startSend()

    # COMPUTE A BYTESTRING FOR THE HSL SECTION
    def computeValueHSL(self):
        calculateByteString(colorMode="HSL",\
                            HSL_H=str(int(self.Slider_HSL_1_H.value())),\
                            HSL_S=str(int(self.Slider_HSL_2_S.value())),\
                            HSL_L=str(int(self.Slider_HSL_3_L.value())))

        self.statusBar.showMessage("Current value (HSL Mode): " + updateStatus())
        self.startSend()
 
    # COMPUTE A BYTESTRING FOR THE ANIM SECTION
    def computeValueANM(self, buttonPressed):
        global lastAnimButtonPressed

        if buttonPressed == 0:
            buttonPressed = lastAnimButtonPressed
        else:
            # CHANGE THE OLD BUTTON COLOR BACK TO THE DEFAULT COLOR
            if lastAnimButtonPressed == 1:
                self.Button_1_police_A.setStyleSheet("background-color : None")
            elif lastAnimButtonPressed == 2:
                self.Button_1_police_B.setStyleSheet("background-color : None")
            elif lastAnimButtonPressed == 3:
                self.Button_1_police_C.setStyleSheet("background-color : None")
            elif lastAnimButtonPressed == 4:
                self.Button_2_party_A.setStyleSheet("background-color : None")
            elif lastAnimButtonPressed == 5:
                self.Button_2_party_B.setStyleSheet("background-color : None")
            elif lastAnimButtonPressed == 6:    
                self.Button_2_party_C.setStyleSheet("background-color : None")
            elif lastAnimButtonPressed == 7:
                self.Button_3_lightning_A.setStyleSheet("background-color : None")
            elif lastAnimButtonPressed == 8:
                self.Button_3_lightning_B.setStyleSheet("background-color : None")
            elif lastAnimButtonPressed == 9:
                self.Button_3_lightning_C.setStyleSheet("background-color : None")
                
            # CHANGE THE NEW BUTTON COLOR TO SHOW WHICH ANIMATION WE'RE CURRENTLY ON
            if buttonPressed == 1:
                self.Button_1_police_A.setStyleSheet("background-color : aquamarine")
            elif buttonPressed == 2:
                self.Button_1_police_B.setStyleSheet("background-color : aquamarine")
            elif buttonPressed == 3:
                self.Button_1_police_C.setStyleSheet("background-color : aquamarine")
            elif buttonPressed == 4:
                self.Button_2_party_A.setStyleSheet("background-color : aquamarine")
            elif buttonPressed == 5:
                self.Button_2_party_B.setStyleSheet("background-color : aquamarine")
            elif buttonPressed == 6:    
                self.Button_2_party_C.setStyleSheet("background-color : aquamarine")
            elif buttonPressed == 7:
                self.Button_3_lightning_A.setStyleSheet("background-color : aquamarine")
            elif buttonPressed == 8:
                self.Button_3_lightning_B.setStyleSheet("background-color : aquamarine")
            elif buttonPressed == 9:
                self.Button_3_lightning_C.setStyleSheet("background-color : aquamarine")
            
            lastAnimButtonPressed = buttonPressed

        calculateByteString(colorMode="ANM",\
                            brightness=str(int(self.Slider_ANM_Brightness.value())),\
                            animation=str(buttonPressed))

        self.statusBar.showMessage("Current value (ANM Mode): " + updateStatus())
        self.startSend()

    def turnLightOn(self):
        global sendValue
        sendValue = [120, 129, 1, 1, 251]
        self.statusBar.showMessage("Turning light on")
        self.startSend()
                  
    def turnLightOff(self):
        global sendValue
        sendValue = [120, 129, 1, 2, 252]
        self.statusBar.showMessage("Turning light off")
        self.startSend()

    # ==============================================================
    # FUNCTIONS TO RETURN / MODIFY VALUES RUNNING IN THE GUI
    # ==============================================================

    # RETURN THE ROW INDEXES THAT ARE CURRENTLY HIGHLIGHTED IN THE TABLE VIEW
    def selectedLights(self):
        selectionList = []

        if threadAction != "quit":
            currentSelection = self.lightTable.selectionModel().selectedRows()

            for a in range(0, len(currentSelection)):
                selectionList.append(currentSelection[a].row()) # add the row index of the nth selected light to the selectionList array

        return selectionList # return the row IDs that are currently selected, or an empty array ([]) otherwise
     
    # UPDATE THE TABLE WITH THE CURRENT INFORMATION FROM availableLights
    def updateLights(self):
        self.clearTheTable()

        if len(availableLights) != 0: # if we found lights on the last scan
            if self.scanCommandButton.text() == "Scan":
                self.scanCommandButton.setText("Re-scan") # change the "Scan" button to "Re-scan"

            if len(availableLights) == 1: # we found 1 light
                self.statusBar.showMessage("We located 1 Neewer light on the last search")
            elif len(availableLights) > 1: # we found more than 1 light
                self.statusBar.showMessage("We located " + str(len(availableLights)) + " Neewer lights on the last search")            
        else: # if we didn't find any (additional) lights on the last scan
            self.statusBar.showMessage("We didn't locate any Neewer lights on the last search")        

        for a in range(0, len(availableLights)):
            if availableLights[a][1] == "": # the light is not currently linked, so put "waiting to connect" as status
                self.setTheTable([availableLights[a][0].name, availableLights[a][0].address, "No", "Waiting to connect..."])
            else: # we have previously tried to connect, so we have a Bleak object - so put "waiting to send" as status
                self.setTheTable([availableLights[a][0].name, availableLights[a][0].address, "Yes", "Waiting to send..."])

    # THE FINAL FUNCTION TO UNLINK ALL LIGHTS WHEN QUITTING THE PROGRAM
    def closeEvent(self, event):
        global availableLights
        global threadAction

        self.statusBar.showMessage("Quitting program - unlinking from lights...")
        QApplication.processEvents() # force the status bar to update
        
        threadAction = "quit" # stop the background thread
        loop = asyncio.get_event_loop()

        # TRY TO DISCONNECT EACH LIGHT FROM BLUETOOTH BEFORE QUITTING THE PROGRAM COMPLETELY
        for a in range (0, len(availableLights)):
            printDebugString("Unlinking from light #" + str(a) + " (" + str(a + 1) + " of " + str(len(availableLights)) + " lights to unlink)")
            self.statusBar.showMessage("Unlinking from light #" + str(a) + " (" + str(a + 1) + " of " + str(len(availableLights)) + " lights to unlink)...")
            QApplication.processEvents() # force update to show statusbar progress
            
            loop.run_until_complete(disconnectFromLight(a)) # disconnect from each light, one at a time

        printDebugString("Closing the program NOW")

# PRINT A DEBUG STRING TO THE CONSOLE, ALONG WITH THE CURRENT TIME
def printDebugString(theString):
    global printDebug

    if printDebug == True:
        now = datetime.now()
        currentTime = now.strftime("%H:%M:%S")

        print("[" + currentTime + "] - " + theString)

# CALCULATE THE BYTESTRING TO SEND TO THE LIGHT
def calculateByteString(**modeArgs):
    global sendValue

    if modeArgs["colorMode"] == "CCT":
        # We're in CCT (color balance) mode
        sendValue = [120, 135, 2, 0, 0, 0]

        sendValue[3] = int(modeArgs["brightness"]) # the brightness value
        sendValue[4] = int(modeArgs["temp"]) # the color temp value, ranging from 32(00K) to 85(00)K - some lights (like the SL-80) can go as high as 8500K
        sendValue[5] = calculateChecksum(sendValue) # compute the checksum
    elif modeArgs["colorMode"] == "HSL":
        # We're in HSL (any color of the spectrum) mode
        sendValue = [120, 134, 4, 0, 0, 0, 0, 0]

        sendValue[3] = int(modeArgs["HSL_H"]) & 255 # hue value, up to 255
        sendValue[4] = (int(modeArgs["HSL_H"]) & 65280) >> 8 # offset value, computed from above value
        sendValue[5] = int(modeArgs["HSL_S"]) # saturation value
        sendValue[6] = int(modeArgs["HSL_L"]) # brightness value
        sendValue[7] = calculateChecksum(sendValue) # compute the checksum
    elif modeArgs["colorMode"] == "ANM":
        # We're in ANM (animation) mode
        sendValue = [120, 136, 2, 0, 0, 0]

        sendValue[3] = int(modeArgs["brightness"]) # brightness value
        sendValue[4] = int(modeArgs["animation"]) # the number of animation you're going to run (check comments above)
        sendValue[5] = calculateChecksum(sendValue) # compute the checksum
    else:        
        sendValue = [0]

# MAKE CURRENT BYTESTRING INTO A STRING OF HEX CHARACTERS TO SHOW THE CURRENT VALUE BEING GENERATED BY THE PROGRAM
def updateStatus(splitString = False):
        currentHexString = ""

        if splitString == False: # False is for the status bar (shows the bytestring as one long line)
            for a in range(0, len(sendValue)):
                currentHexString = currentHexString + " " + str(hex(sendValue[a]))
        else: # True is for the table view (split the line in half, show the first 3 on the top line, then the actual payload below)
            for a in range(0, 3):
                currentHexString = currentHexString + " " + str(hex(sendValue[a]))
            
            if sendValue[1] == 134:
                currentHexString = currentHexString + " (HSL)\n"
            elif sendValue[1] == 135:
                currentHexString = currentHexString + " (CCT)\n"
            elif sendValue[1] == 136:
                currentHexString = currentHexString + " (ANM)\n"

            for a in range(3, len(sendValue)):
                currentHexString = currentHexString + " " + str(hex(sendValue[a]))

        return currentHexString

# CALCULATE THE CHECKSUM FROM THE BYTESTRING
def calculateChecksum(sendValue):
    checkSum = 0

    for a in range(0, len(sendValue) - 1):
        if sendValue[a] < 0:
            checkSum = checkSum + int(sendValue[a] + 256)
        else:
            checkSum = checkSum + int(sendValue[a])

    checkSum = checkSum & 255
    return checkSum

# FIND NEW LIGHTS
async def findDevices():
    global availableLights
    printDebugString("Searching for new lights")
  
    currentScan = [] # add all the current scan's lights detected to a standby array (to check against the main one)
    devices = await BleakScanner.discover() # scan all available Bluetooth devices nearby

    for d in devices: # go through all of the devices Bleak just found
        try:
            d.name.index("NEEWER") # try to see if the current device has the name "NEEWER" in it
        except ValueError:
            pass # if the current device doesn't ^^^^, then this error is thrown
        else:
            currentScan.append(d) # and if it finds the phrase, add it to this session's available lights

    for a in range(0, len(currentScan)): # scan the newly found NEEWER devices
        if currentScan[a] not in availableLights: # if this specific device is NOT in the globally available list of devices
            availableLights.append([currentScan[a], ""]) # add it to the global list, leaving item 2 for the Bleak connection object
 
    return "" # once the device scan is over, set the threadAction to nothing

# CONNECT (LINK) TO A LIGHT
async def connectToLight(selectedLight):
    global availableLights

    printDebugString("Attempting to link to light " + str(selectedLight))

    # FILL THE [1] ELEMENT OF THE availableLights ARRAY WITH THE BLEAK CONNECTION
    if availableLights[selectedLight][1] == "":
        availableLights[selectedLight][1] = BleakClient(availableLights[selectedLight][0])

    try:
        if not availableLights[selectedLight][1].is_connected: # if the current device isn't linked to Bluetooth
            await availableLights[selectedLight][1].connect() # try connecting it
            printDebugString("Successfully linked to light " + str(selectedLight))
            mainWindow.setTheTable(["", "", "Yes", "Waiting to send..."], selectedLight) # if it's successful, show that in the table
        else:
            printDebugString("Light " + str(selectedLight) + " is already linked, so not trying to re-link")
            mainWindow.setTheTable(["", "", "Yes", "Light is already linked!\nWaiting to send..."], selectedLight) # the device is *already* linked, so show that
    except Exception as e:
        printDebugString("Error linking to light " + str(selectedLight))
        print(e)
        mainWindow.setTheTable(["", "", "No", "There was an error connecting to the light"], selectedLight) # there was an issue connecting this specific light to Bluetooh, so show that
      
    return "" # once the connection is over, then set threadAction to nothing

# DISCONNECT FROM A LIGHT
async def disconnectFromLight(selectedLight):
    try:
        if availableLights[selectedLight][1] != "": # if the current light has a Bleak object associated with it, then try to disconnect from it
            await availableLights[selectedLight][1].disconnect()
            printDebugString("Successfully unlinked from light " + str(selectedLight))
        else: # we don't have an active link, so skip this one
            printDebugString("Light " + str(selectedLight) + " isn't linked, so not attempting to disconnect")
    except Exception as e:
        printDebugString("Error unlinking from light " + str(selectedLight))
        print(e)
       
    return "" # once disconnection is over, then set threadAction to nothing

# WRITE TO A LIGHT
async def writeToLight():
    startTimer = time.time() # the start of the triggering
    printDebugString("Going into send mode")

    try:
        selectedLights = mainWindow.selectedLights() # get the list of currently selected lights from the GUI table
        currentSendValue = [] # initialize the value check
        
        # if there are lights selected (otherwise just dump out), and the delay timer is less than it's maximum, then try to send to the lights selected
        while (len(selectedLights) > 0 and time.time() - startTimer < 1) :
            if currentSendValue != sendValue: # if the current value is different than what was last sent to the light, then send a new one
                currentSendValue = sendValue # get this value before sending to multiple lights, to ensure the same value is sent to each one

                for a in range(0, len(selectedLights)): # try to write each light in turn, and show the current data being sent to them in the table
                    if availableLights[selectedLights[a]][1] != "":
                        await availableLights[int(selectedLights[a])][1].write_gatt_char(setLightUUID, bytearray(currentSendValue), False)
                        mainWindow.setTheTable(["", "", "", "Sent: " + updateStatus(True)], int(selectedLights[a]))
                    else:
                        mainWindow.setTheTable(["", "", "", "Light isn't linked yet, can't send to it"], int(selectedLights[a]))
                
                startTimer = time.time() # if we sent a value, then reset the timer
           
            await asyncio.sleep(0.05) # wait 1/20th of a second to give the Bluetooth bus a little time to recover
            selectedLights = mainWindow.selectedLights() # re-acquire the current list of selected lights
    except Exception as e:
        printDebugString("There was an error communicating with the light.")
        print(e)

    printDebugString("Leaving send mode and going back to background thread")
    return ""

# THE BACKGROUND WORKER THREAD
def workerThread(_loop):
    global threadAction
    
    if startup_findLights == True: # if we're set to find lights at startup, then automatically set the thread to discovery mode
        threadAction = "discover"

    while True:
        printDebugString("Background Thread Running")
        time.sleep(0.25)
        
        if threadAction == "quit":
            printDebugString("Stopping the background thread")
            break # stop the background thread before quitting the program            
        elif threadAction == "discover":
            threadAction = _loop.run_until_complete(findDevices()) # add new lights to the main array
            mainWindow.updateLights() # tell the GUI to update its list of available lights

            if startup_connectLights == True: # if we're set to automatically link to the lights on startup, then do it here
                for a in range(len(availableLights)):                    
                    threadAction = _loop.run_until_complete(connectToLight(a)) # connect to each light in turn                    
        elif threadAction == "connect":
            selectedLights = mainWindow.selectedLights() # get the list of currently selected lights

            for a in range(len(mainWindow.selectedLights())): # and try to link to each of those lights
                threadAction = _loop.run_until_complete(connectToLight(selectedLights[a]))                
        elif threadAction == "send":
            threadAction = _loop.run_until_complete(writeToLight()) # write a value to the light(s) - the selectedLights() section is in the write loop itself for responsiveness

if __name__ == '__main__':
    app = QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()

    loop = asyncio.get_event_loop()
    workerThread = threading.Thread(target=workerThread, args=(loop,), name="workerThread")
    workerThread.start()
       
    ret = app.exec_()    
    sys.exit( ret )