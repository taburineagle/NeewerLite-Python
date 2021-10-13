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
import argparse

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

availableLights = [] # the list of Neewer lights currently available to control - format: [Bleak Scan Object, Bleak Connection, Custom Name, Last Params]

threadAction = "" # the current action to take from the thread
setLightUUID = "69400002-B5A3-F393-E0A9-E50E24DCCA99" # the UUID to send information to the light

maxNumOfAttempts = 6 # the maximum attempts CLI mode will attempt before quitting out

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

        self.Slider_ANM_Brightness.valueChanged.connect(lambda: self.computeValueANM(0))
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
        selectedRows = self.lightTable.selectionModel().selectedRows()

        if len(selectedRows) > 0:
            self.tryConnectButton.setEnabled(True) # if we have a light selected in the table, then enable the "Connect" button

            if len(selectedRows) == 1: # if we have one item selected, then try to restore the last setting sent to it
                currentlySelectedRow = selectedRows[0].row() # get the row index of the 1 selected item

                # RECALL LAST SENT SETTING FOR THIS PARTICULAR LIGHT, IF A SETTING EXISTS
                if availableLights[currentlySelectedRow][3] != []:
                    sendValue = availableLights[currentlySelectedRow][3] # make the current "sendValue" the last set parameter so it doesn't re-send it on re-load

                    if sendValue[1] == 135:
                        self.setUpGUI(colorMode="CCT",
                                      brightness=sendValue[3],
                                      temp=sendValue[4])
                    elif sendValue[1] == 134:
                        self.setUpGUI(colorMode="HSL",
                                      hue=sendValue[3] + (256 * sendValue[4]),
                                      sat=sendValue[5],
                                      brightness=sendValue[6])
                    elif sendValue[1] == 136:
                        self.setUpGUI(colorMode="ANM",
                                      brightness=sendValue[3],
                                      scene=sendValue[4])
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
            pass # we don't want the animation automatically triggering when we go to this page
          
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
    
    # SET UP THE GUI BASED ON COMMAND LINE ARGUMENTS
    def setUpGUI(self, **modeArgs):
        if modeArgs["colorMode"] == "CCT":
            self.ColorModeTabWidget.setCurrentIndex(0)

            self.Slider_CCT_Hue.setValue(modeArgs["temp"])
            self.Slider_CCT_Bright.setValue(modeArgs["brightness"])

            self.computeValueCCT()
        elif modeArgs["colorMode"] == "HSL":
            self.ColorModeTabWidget.setCurrentIndex(1)

            self.Slider_HSL_1_H.setValue(modeArgs["hue"])
            self.Slider_HSL_2_S.setValue(modeArgs["sat"])
            self.Slider_HSL_3_L.setValue(modeArgs["brightness"])
            
            self.computeValueHSL()
        elif modeArgs["colorMode"] == "ANM":
            self.ColorModeTabWidget.setCurrentIndex(2)

            self.Slider_ANM_Brightness.setValue(modeArgs["brightness"])
            self.computeValueANM(modeArgs["scene"])

def testValid(theParam, theValue, defaultValue, startBounds, endBounds):
    if theParam == "temp":
        if len(theValue) > 1: # if the temp has at least 2 characters in it
            theValue = theValue[:2] # take the first 2 characters of the string to convert into int
        else: # it either doesn't have enough characters, or isn't a number
            printDebugString(" >> error with --temp specified (not enough digits or not a number), so falling back to default value of " + str(defaultValue))
            theValue = defaultValue # default to 56(00)K for color temperature

    try: # try converting the string into an integer and processing the bounds
        theValue = int(theValue) # the value is assumed to be within the bounds, so we check it...

        if theValue < startBounds or theValue > endBounds: # the value is not within bounds, so there's an error
            if theValue < startBounds: # if the value specified is below the starting boundary, make it the starting boundary
                printDebugString(" >> --" + theParam + " (" + str(theValue) + ") isn't between the bounds of " + str(startBounds) + " and " + str(endBounds) + ", so falling back to closest boundary of " + str(startBounds))
                theValue = startBounds
            elif theValue > endBounds: # if the value specified is above the ending boundary, make it the ending boundary
                printDebugString(" >> --" + theParam + " (" + str(theValue) + ") isn't between the bounds of " + str(startBounds) + " and " + str(endBounds) + ", so falling back to closest boundary of " + str(endBounds))
                theValue = endBounds
        
        return theValue # return the within-bounds value
    except ValueError: # if the string can not be converted, then return the defaultValue
        printDebugString(" >> --" + theParam + " specified is not a number - falling back to default value of " + str(defaultValue))
        return defaultValue # return the default value

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
            #TODO: Check a preferences file here for custom light names for element [2]
            availableLights.append([currentScan[a], "", "", []]) # add it to the global list, leaving item 2 for the Bleak connection object
 
    return "" # once the device scan is over, set the threadAction to nothing

# CONNECT (LINK) TO A LIGHT
async def connectToLight(selectedLight, updateGUI=True):
    global availableLights
    isConnected = False # whether or not the light is connected
    returnValue = "" # the value to return to the thread (in GUI mode, a string) or True/False (in CLI mode, a boolean value)

    printDebugString("Attempting to link to light " + str(selectedLight))

    # FILL THE [1] ELEMENT OF THE availableLights ARRAY WITH THE BLEAK CONNECTION
    if availableLights[selectedLight][1] == "":
        availableLights[selectedLight][1] = BleakClient(availableLights[selectedLight][0])
        await asyncio.sleep(0.25) # wait just a short time before trying to connect

    try:
        if not availableLights[selectedLight][1].is_connected: # if the current device isn't linked to Bluetooth
            isConnected = await availableLights[selectedLight][1].connect() # try connecting it (and return the connection status)
        else:
            isConnected = True # the light is already connected, so mark it as being connected
    except Exception as e:
        printDebugString("Error linking to light " + str(selectedLight))
        print(e)

        if updateGUI == True:
            mainWindow.setTheTable(["", "", "No", "There was an error connecting to the light"], selectedLight) # there was an issue connecting this specific light to Bluetooh, so show that
        else:
            returnValue = False # if we're in CLI mode, and there is an error connecting to the light, return False

    if isConnected == True:
        printDebugString("Successfully linked to light " + str(selectedLight))

        if updateGUI == True:
            mainWindow.setTheTable(["", "", "Yes", "Waiting to send..."], selectedLight) # if it's successful, show that in the table
        else:
            returnValue = True  # if we're in CLI mode, and there is no error connecting to the light, return True
    else:
        returnValue = False # the light is not connected

    return returnValue # once the connection is over, then set threadAction to nothing

# DISCONNECT FROM A LIGHT
async def disconnectFromLight(selectedLight, updateGUI=True):
    returnValue = "" # same as above, string for GUI mode and boolean for CLI mode, default to blank string

    try:
        if availableLights[selectedLight][1].is_connected: # if the current light is connected
            await availableLights[selectedLight][1].disconnect()
    except Exception as e:
        returnValue = False # if we're in CLI mode, then return False if there is an error disconnecting
        printDebugString("Error unlinking from light " + str(selectedLight))
        print(e)

    if not availableLights[selectedLight][1].is_connected: # if the current light is NOT connected, then we're good
        if updateGUI == False:
            returnValue = True # if we're in CLI mode, then return False if there is an error disconnecting
    
        printDebugString("Successfully unlinked from light " + str(selectedLight))
    
    return returnValue    

# WRITE TO A LIGHT - optional arguments for the CLI version (GUI version doesn't use either of these)
async def writeToLight(selectedLights=0, updateGUI=True):
    returnValue = "" # same as above, return value "" for GUI, or boolean for CLI

    startTimer = time.time() # the start of the triggering
    printDebugString("Going into send mode")

    try:
        if updateGUI == True:
            selectedLights = mainWindow.selectedLights() # get the list of currently selected lights from the GUI table
        else:
            # TODO - CLI: if we're specifying multiple lights here, then we don't need to do the conversion to list (as it's already one)
            selectedLights = [selectedLights] # convert asked-for light to list

        currentSendValue = [] # initialize the value check
        
        # if there are lights selected (otherwise just dump out), and the delay timer is less than it's maximum, then try to send to the lights selected
        while (len(selectedLights) > 0 and time.time() - startTimer < 0.4) :
            if currentSendValue != sendValue: # if the current value is different than what was last sent to the light, then send a new one
                currentSendValue = sendValue # get this value before sending to multiple lights, to ensure the same value is sent to each one

                for a in range(0, len(selectedLights)): # try to write each light in turn, and show the current data being sent to them in the table
                    if availableLights[selectedLights[a]][1] != "":
                        try:
                            await availableLights[int(selectedLights[a])][1].write_gatt_char(setLightUUID, bytearray(currentSendValue), False)

                            if updateGUI == True:
                                mainWindow.setTheTable(["", "", "", "Sent: " + updateStatus(True)], int(selectedLights[a]))

                                # STORE THE CURRENTLY SENT VALUE TO THE MAIN ARRAY TO RECALL LATER
                                availableLights[selectedLights[a]][3] = currentSendValue                                
                            else:
                                returnValue = True # we successfully wrote to the light
                        except Exception as e:
                            mainWindow.setTheTable(["", "", "", "Error Sending to light!"], int(selectedLights[a]))
                    else:
                        if updateGUI == True:
                            mainWindow.setTheTable(["", "", "", "Light isn't linked yet, can't send to it"], int(selectedLights[a]))
                        else:
                            returnValue = 0 # the light is not linked, even though it *should* be if it gets to this point, so this is an odd error
                
                startTimer = time.time() # if we sent a value, then reset the timer
           
            await asyncio.sleep(0.05) # wait 1/20th of a second to give the Bluetooth bus a little time to recover
            
            if updateGUI == True:
                selectedLights = mainWindow.selectedLights() # re-acquire the current list of selected lights
    except Exception as e:
        printDebugString("There was an error communicating with the light.")
        print(e)

        if updateGUI == True:
            returnValue = False # there was an error writing to this light, so return false to the CLI

    if updateGUI == True:
        if threadAction != "quit": # if we've been asked to quit somewhere else in the program
            printDebugString("Leaving send mode and going back to background thread")
        else:
            printDebugString("The program has requested to quit, so we're not going back to the background thread")
            returnValue = "quit"

    return returnValue

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

def processCommands():
    # DELETE ANY INVALID ARGUMENTS FROM THE COMMAND LINE BEFORE RUNNING THE ARGUMENT PARSER
    # TO CLEAN UP THE ARGUMENT LIST TO ENSURE THE PARSER CAN STILL RUN WHEN INVALID ARGUMENTS ARE PRESENT
    acceptable_arguments = ["--cli", "--silent", "--light", "--mode", "--temp", "--hue", 
    "--sat", "--bri", "--luminance", "--scene", "--animation", "--help"]

    for a in range(len(sys.argv) - 1, 0, -1):
        if not any(x in sys.argv[a] for x in acceptable_arguments): # if the current argument is invalid
            if sys.argv[a] != "-h": # and the argument isn't "-h" (for help)
                sys.argv.pop(a) # delete the invalid argument from the list
 
    # PARSE THE ARGUMENT LIST FOR CUSTOM PARAMETERS
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", action="store_false", help="Don't show the GUI at all, just send command and quit")
    parser.add_argument("--silent", action="store_false", help="Don't show any debug information in the console")
    parser.add_argument("--light", default="", help="The MAC Address (XX:XX:XX:XX:XX:XX) of the light you want to send a command to or ALL to find and control all lights (only valid when also using --cli switch)")
    parser.add_argument("--mode", default="CCT", help="[DEFAULT: CCT] The current control mode - options are HSL, CCT and either ANM or SCENE")
    parser.add_argument("--temp", "--temperature", default="56", help="[DEFAULT: 56(00)K] (CCT mode) - the color temperature (3200K+) to set the light to")
    parser.add_argument("--hue", default="240", help="[DEFAULT: 240] (HSL mode) - the hue (0-360 degrees) to set the light to")
    parser.add_argument("--sat", "--saturation", default="100", help="[DEFAULT: 100] (HSL mode) The saturation (color intensity) to set the light to")
    parser.add_argument("--bri", "--brightness", "--luminance", default="100", help="[DEFAULT: 100] (CCT/HSL/ANM mode) The brightness (luminance) to set the light to")
    parser.add_argument("--scene", "--animation", default="1", help="[DEFAULT: 1] (ANM or SCENE mode) The animation (1-9) to use in Scene mode")
    args = parser.parse_args()

    if args.silent == True:
        printDebugString("Starting program with command-line arguments:")

    if args.mode == "CCT":
        return [args.cli, args.silent, args.light, args.mode, 
                testValid("temp", args.temp, 56, 32, 85),
                testValid("bri", args.bri, 100, 0, 100)]
    elif args.mode == "HSL":
        return [args.cli, args.silent, args.light, args.mode, 
                testValid("hue", args.hue, 240, 0, 360),
                testValid("sat", args.sat, 100, 0, 100),
                testValid("bri", args.bri, 100, 0, 100)]
    elif args.mode in ("ANM", "SCENE"):
        return [args.cli, args.silent, args.light, "ANM", 
                testValid("scene", args.scene, 1, 1, 9),
                testValid("bri", args.bri, 100, 0, 100)]
    else:
        print ("Improper mode selected with --mode command - valid entries are CCT, HSL or either ANM or SCENE")
        sys.exit(0)

if __name__ == '__main__':
    loop = asyncio.get_event_loop() # get the current asyncio loop
    cmdReturn = [True] # initially set to show the GUI interface over the CLI interface

    if len(sys.argv) > 1: # if we have more than 1 argument on the command line (the script itself is argument 1), then process switches
        cmdReturn = processCommands()
        printDebug = cmdReturn[1] # if we use the --quiet option, then don't show debug strings in the console
      
        printDebugString(" > Launch GUI: " + str(cmdReturn[0]))
        printDebugString(" > Show Debug Strings on Console: " + str(cmdReturn[1]))

        printDebugString(" > Mode: " + cmdReturn[3])

        if cmdReturn[3] == "CCT":
            printDebugString(" > Color Temperature: " + str(cmdReturn[4]) + "00K")
            printDebugString(" > Brightness: " + str(cmdReturn[5]))
        elif cmdReturn[3] == "HSL":
            printDebugString(" > Hue: " + str(cmdReturn[4]))
            printDebugString(" > Saturation: " + str(cmdReturn[5]))
            printDebugString(" > Brightness: " + str(cmdReturn[6]))
        elif cmdReturn[3] == "ANM":
            printDebugString(" > Scene: " + str(cmdReturn[4]))
            printDebugString(" > Brightness: " + str(cmdReturn[5]))

        if cmdReturn[0] == False: # if we're not showing the GUI, we need to specify a MAC address
            if cmdReturn[2] != "":
                printDebugString("-------------------------------------------------------------------------------------")
                printDebugString(" > CLI >> MAC Address of light to send command to: " + cmdReturn[2])
                availableLights = [[cmdReturn[2], ""]]
            else:
                printDebugString("-------------------------------------------------------------------------------------")
                printDebugString(" > CLI >> You did not specify a light to send the command to - use the --light switch")
                printDebugString(" > CLI >> and write either a MAC Address (XX:XX:XX:XX:XX:XX) to a Neewer light or")
                printDebugString(" > CLI >> ALL to send to all available Neewer lights found by Bluetooth")
                printDebugString("-------------------------------------------------------------------------------------")
                          
    if cmdReturn[0] == True: # launch the GUI with the command-line arguments
        app = QApplication(sys.argv)
        mainWindow = MainWindow()

        # SET UP GUI BASED ON COMMAND LINE ARGUMENTS
        if len(cmdReturn) > 1:
            if cmdReturn[3] == "CCT": # set up the GUI in CCT mode with specified parameters (or default, if none)
                mainWindow.setUpGUI(colorMode=cmdReturn[3], temp=cmdReturn[4], brightness=cmdReturn[5])
            elif cmdReturn[3] == "HSL": # set up the GUI in HSL mode with specified parameters (or default, if none)
                mainWindow.setUpGUI(colorMode=cmdReturn[3], hue=cmdReturn[4], sat=cmdReturn[5], brightness=cmdReturn[6])
            elif cmdReturn[3] == "ANM": # set up the GUI in ANM mode with specified parameters (or default, if none)
                mainWindow.setUpGUI(colorMode=cmdReturn[3], scene=cmdReturn[4], brightness=cmdReturn[5])
                       
        mainWindow.show()
        
        # START THE BACKGROUND THREAD
        workerThread = threading.Thread(target=workerThread, args=(loop,), name="workerThread")
        workerThread.start()
       
        ret = app.exec_()    
        sys.exit( ret )
    else: # don't launch the GUI, send command to a light/lights and quit out
        if len(cmdReturn) > 1:
            if cmdReturn[3] == "CCT": # calculate CCT bytestring
                calculateByteString(colorMode=cmdReturn[3], temp=cmdReturn[4], brightness=cmdReturn[5])
            elif cmdReturn[3] == "HSL": # calculate HSL bytestring
                calculateByteString(colorMode=cmdReturn[3], HSL_H=cmdReturn[4], HSL_S=cmdReturn[5], HSL_L=cmdReturn[6])
            elif cmdReturn[3] == "ANM": # calculate ANM/SCENE bytestring
                calculateByteString(colorMode=cmdReturn[3], animation=cmdReturn[4], brightness=cmdReturn[5])

        if availableLights != []:
            printDebugString(" > CLI >> Bytestring to send to light:" + updateStatus())
           
            # CONNECT TO THE LIGHT AND SEND INFORMATION TO IT
            isFinished = False
            numOfAttempts = 1

            while isFinished == False:
                printDebugString("-------------------------------------------------------------------------------------")
                printDebugString(" > CLI >> Attempting to connect to light (attempt " + str(numOfAttempts) + " of " + str(maxNumOfAttempts) + ")")
                printDebugString("-------------------------------------------------------------------------------------")
                isFinished = loop.run_until_complete(connectToLight(0, False))

                if numOfAttempts < maxNumOfAttempts:
                    numOfAttempts = numOfAttempts + 1
                else:
                    printDebugString("Error connecting to light " + str(maxNumOfAttempts) + " times - quitting out")
                    sys.exit(1)

            isFinished = False
            numOfAttempts = 1
        
            while isFinished == False:
                printDebugString("-------------------------------------------------------------------------------------")
                printDebugString(" > CLI >> Attempting to write to light (attempt " + str(numOfAttempts) + " of " + str(maxNumOfAttempts) + ")")
                printDebugString("-------------------------------------------------------------------------------------")
                isFinished = loop.run_until_complete(writeToLight(0, False))
                
                if numOfAttempts < maxNumOfAttempts:
                    numOfAttempts = numOfAttempts + 1
                else:
                    printDebugString("Error writing to light " + str(maxNumOfAttempts) + " times - quitting out")
                    sys.exit(1)

            isFinished = False
            numOfAttempts = 1

            while isFinished == False:
                printDebugString("-------------------------------------------------------------------------------------")
                printDebugString(" > CLI >> Attempting to disconnect from light (attempt " + str(numOfAttempts) + " of " + str(maxNumOfAttempts) + ")")
                printDebugString("-------------------------------------------------------------------------------------")
                isFinished = loop.run_until_complete(disconnectFromLight(0))
                
                if numOfAttempts < maxNumOfAttempts:
                    numOfAttempts = numOfAttempts + 1
                else:
                    printDebugString("Error disconnecting from light " + str(maxNumOfAttempts) + " times - quitting out")
                    sys.exit(1)
        else:
            printDebugString("-------------------------------------------------------------------------------------")
            printDebugString(" > CLI >> Calculated bytestring:" + updateStatus())

        sys.exit(0)