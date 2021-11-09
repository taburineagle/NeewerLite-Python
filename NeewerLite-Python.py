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

# IMPORT BLEAK (this is the library that allows the program to communicate with the lights) - THIS IS NECESSARY!
try:
    from bleak import BleakScanner, BleakClient
except Exception as e:
    print("You need the bleak Python package installed to use NeewerLite-Python.  Bleak is the library that connects to Bluetooth devices.")
    print("Install the Bleak package first before running NeewerLite-Python.")
    sys.exit(0) # you can't use the program itself without Bleak, so kill the program if we don't have it

import sys
import argparse

import asyncio
import threading
import time

from datetime import datetime

# IMPORT THE WINDOWS LIBRARY (if you don't do this, it will throw an exception on Windows only)
try:
    from winrt import _winrt
    _winrt.uninit_apartment()
except Exception as e:
    pass # if there is an exception to this module loading, you're not on Windows

# IMPORT PYSIDE2 (the GUI libraries)
try:
    from PySide2.QtWidgets import QApplication, QMainWindow, QTableWidgetItem
    from PySide2.QtGui import QLinearGradient, QColor
except Exception as e:
    print("You don't have the PySide2 Python library installed.  If you're only running NeewerLite-Python from")
    print("a command-line (from a Raspberry Pi CLI for instance), you don't need this package. If you want to launch")
    print("NeewerLite-Python with the GUI, you need to install the PySide2 package.")

# IMPORT THE GUI ITSELF
try:
    from ui_NeewerLightUI import Ui_MainWindow
except Exception as e:
    pass # don't do anything yet, the GUI can't be imported

# IMPORT THE HTTP SERVER
try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
except Exception as e:
    pass # if there are any HTTP errors, don't do anything yet

sendValue = [] # an array to hold the values to be sent to the light
lastAnimButtonPressed = 1 # which animation button you clicked last - if none, then it defaults to 1 (the police sirens)

availableLights = [] # the list of Neewer lights currently available to control - format: 
                     # [Bleak Scan Object, Bleak Connection, Custom Name, Last Params, Extend CCT Range]

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
              
        self.ColorModeTabWidget.currentChanged.connect(self.tabChanged)
        self.lightTable.itemSelectionChanged.connect(self.setupSelectionChanged)
  
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

        self.savePrefsButton.clicked.connect(self.savePrefs)

    def checkLightTab(self, selectedLight = -1):
        if self.ColorModeTabWidget.currentIndex() == 0: # if we're on the CCT tab, do the check
            if selectedLight == -1: # if we don't have a light selected
                self.setupCCTBounds(56) # restore the bounds to their default of 56(00)K
            else:
                if availableLights[selectedLight][4] == True: # if we're supposed to be extending the range
                    if self.Slider_CCT_Hue.maximum() == 56: # if we're set to extend the range, but we're still set to 56(00)K, then change the range
                        self.setupCCTBounds(85)
                else:
                    if self.Slider_CCT_Hue.maximum() == 85: # if we're set to NOT extend the range, but we're still set to 85(00)K, then reduce the range
                        self.setupCCTBounds(56)
        elif self.ColorModeTabWidget.currentIndex() == 3: # if we're on the Preferences tab instead
            if selectedLight != -1: # if there is a specific selected light
                self.setupPrefsTab(selectedLight) # update the Prefs tab with the information for that selected light

    def setupCCTBounds(self, gradientBounds):
        self.Slider_CCT_Hue.setMaximum(gradientBounds) # set the max value of the color temperature slider to the new max bounds

        gradient = QLinearGradient(0, 0, 532, 31)

        # SET GRADIENT OF CCT SLIDER IN CHUNKS OF 5 VALUES BASED ON BOUNDARY
        if gradientBounds == 56: # the color temperature boundary is 5600K
            gradient.setColorAt(0.0, QColor(255, 187, 120, 255)) # 3200K
            gradient.setColorAt(0.25, QColor(255, 204, 153, 255)) # 3800K
            gradient.setColorAt(0.50, QColor(255, 217, 182, 255)) # 4400K
            gradient.setColorAt(0.75, QColor(255, 228, 206, 255)) # 5000K
            gradient.setColorAt(1.0, QColor(255, 238, 227, 255)) # 5600K
        else: # the color temperature boundary is 8500K
            gradient.setColorAt(0.0, QColor(255, 187, 120, 255)) # 3200K
            gradient.setColorAt(0.25, QColor(255, 219, 186, 255)) # 4500K
            gradient.setColorAt(0.50, QColor(255, 240, 233, 255)) # 5800K
            gradient.setColorAt(0.75, QColor(243, 242, 255, 255)) # 7100K
            gradient.setColorAt(1.0, QColor(220, 229, 255, 255)) # 8500K
  
        self.CCT_Temp_Gradient_BG.scene().setBackgroundBrush(gradient) # change the gradient to fit the new boundary

    def setupPrefsTab(self, selectedLight):
        self.customNameTF.setText(availableLights[selectedLight][2]) # set the "custom name" field to the custom name of this light

        if availableLights[selectedLight][4] == True:
            self.widerRangeCheck.setChecked(True)
        else:
            self.widerRangeCheck.setChecked(False)

    # CHECK TO SEE WHETHER OR NOT TO ENABLE/DISABLE THE "Connect" BUTTON OR CHANGE THE PREFS TAB
    def setupSelectionChanged(self):
        selectedRows = self.selectedLights() # get the list of currently selected lights

        if len(selectedRows) > 0:
            self.tryConnectButton.setEnabled(True) # if we have a light selected in the table, then enable the "Connect" button

            if len(selectedRows) == 1: # if we have one item selected, then try to restore the last setting sent to it
                self.ColorModeTabWidget.setTabEnabled(3, True) # enable the "Preferences" tab for this light

                currentlySelectedRow = selectedRows[0] # get the row index of the 1 selected item                
                self.checkLightTab(currentlySelectedRow) # if we're on CCT, check to see if this light can use extended values + on Prefs, update Prefs

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
                self.ColorModeTabWidget.setTabEnabled(3, False) # disable the "Preferences" tab, as we have multiple lights selected
        else:            
            self.ColorModeTabWidget.setTabEnabled(3, False) # disable the "Preferences" tab, as we have no lights selected
            self.tryConnectButton.setEnabled(False) # if we have no lights selected, disable the Connect button
            self.checkLightTab() # check to see if we're on the CCT tab - if we are, then restore order

    def savePrefs(self):
        selectedRows = self.selectedLights() # get the list of currently selected lights

        if len(selectedRows) == 1: # if we have 1 selected light
            availableLights[selectedRows[0]][2] = self.customNameTF.text() # set this light's custom name to the text box
            availableLights[selectedRows[0]][4] = self.widerRangeCheck.isChecked() # if the "wider range" box is checked, then allow wider ranges

            if availableLights[selectedRows[0]][2] != "":
                self.setTheTable([availableLights[selectedRows[0]][2] + " (" + availableLights[selectedRows[0]][0].name + ")", 
                                  "", "", ""], selectedRows[0]) # add the custom name to this specific light

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
    def tabChanged(self, i):
        if i == 0 or i == 3: # check the current selected lights on the CCT and Prefs tabs
            currentSelection = self.selectedLights() # get the list of currently selected lights

        if i == 0: # we clicked on the CCT tab
            # CHECK THE CURRENT SELECTED LIGHT TO SEE IF IT CAN USE EXTENDED COLOR TEMPERATURES
            if len(currentSelection) == 1: # if we have just one light selected
                self.checkLightTab(currentSelection[0]) # check the current light's CCT bounds
            else:
                self.checkLightTab() # reset the bounds to the normal values (5600K)
            
            self.computeValueCCT() # calculate the current CCT value
        elif i == 1: # we clicked on the HSL tab
        	self.computeValueHSL() # calculate the current HSL value
        elif i == 2: # we clicked on the ANM tab
            pass # skip this, we don't want the animation automatically triggering when we go to this page
        elif i == 3: # we clicked on the PREFS tab
            if len(currentSelection) == 1: # this tab function ^^ should *ONLY* call if we have just one light selected, but just in *case*
                self.setupPrefsTab(currentSelection[0])
                         
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
                if availableLights[a][2] != "": # the light has a custom name, so add the custom name to the light
                    self.setTheTable([availableLights[a][2] + " (" + availableLights[a][0].name + ")", availableLights[a][0].address, "No", "Waiting to connect..."])
                else: # the light does not have a custom name, so just use the model # of the light
                    self.setTheTable([availableLights[a][0].name, availableLights[a][0].address, "No", "Waiting to connect..."])
            else: # we have previously tried to connect, so we have a Bleak object - so put "waiting to send" as status
                if availableLights[a][2] != "": # the light has a custom name, so add the custom name to the light
                    self.setTheTable([availableLights[a][2] + " (" + availableLights[a][0].name + ")", availableLights[a][0].address, "Yes", "Waiting to send..."])
                else: # the light does not have a custom name, so just use the model # of the light
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
        if currentScan[a].address not in availableLights: # if this specific device is NOT in the globally available list of devices
            printDebugString("Found new light! [" + currentScan[a].name + "] MAC Address: " + currentScan[a].address)
            availableLights.append([currentScan[a], "", "", [], False]) # add it to the global list
            
    return "" # once the device scan is over, set the threadAction to nothing

# CONNECT (LINK) TO A LIGHT
async def connectToLight(selectedLight, updateGUI=True):
    global availableLights
    isConnected = False # whether or not the light is connected
    returnValue = "" # the value to return to the thread (in GUI mode, a string) or True/False (in CLI mode, a boolean value)

    printDebugString("Attempting to link to light " + str(selectedLight) + " [" + availableLights[selectedLight][0].name + "] MAC Address: " + availableLights[selectedLight][0].address)

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
        printDebugString("Error linking to light " + str(selectedLight) + " [" + availableLights[selectedLight][0].name + "] MAC Address: " + availableLights[selectedLight][0].address)
        print(e)

        if updateGUI == True:
            mainWindow.setTheTable(["", "", "No", "There was an error connecting to the light"], selectedLight) # there was an issue connecting this specific light to Bluetooh, so show that
        else:
            returnValue = False # if we're in CLI mode, and there is an error connecting to the light, return False

    if isConnected == True:
        printDebugString("Successfully linked to light " + str(selectedLight) + " [" + availableLights[selectedLight][0].name + "] MAC Address: " + availableLights[selectedLight][0].address)

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
        printDebugString("Error unlinking from light " + str(selectedLight)  + " [" + availableLights[selectedLight][0].name + "] MAC Address: " + availableLights[selectedLight][0].address)
        print(e)
    
    try:
        if not availableLights[selectedLight][1].is_connected: # if the current light is NOT connected, then we're good
            if updateGUI == False:
                returnValue = True # if we're in CLI mode, then return False if there is an error disconnecting
    
            printDebugString("Successfully unlinked from light " + str(selectedLight)  + " [" + availableLights[selectedLight][0].name + "] MAC Address: " + availableLights[selectedLight][0].address)
    except AttributeError:
        printDebugString("Light " + str(selectedLight) + " has no Bleak object attached to it, so not attempting to disconnect from it")
    
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

def processCommands(listToProcess=[]):
    inStartupMode = False # if we're in startup mode (so report that to the log), start as False initially to be set to True below

    # SET THE CURRENT LIST TO THE sys.argv SYSTEM PARAMETERS LIST IF A LIST ISN'T SPECIFIED
    # SO WE CAN USE THIS SAME FUNCTION TO PARSE HTML ARGUMENTS USING THE HTTP SERVER AND COMMAND-LINE ARGUMENTS
    if len(listToProcess) == 0: # if there aren't any elements in the list, then check against sys.argv
        listToProcess = sys.argv[1:] # the list to parse is the system args minus the first one
        inStartupMode = True

    # ADD DASHES TO ANY PARAMETERS THAT DON'T CURRENTLY HAVE THEM AS WELL AS
    # CONVERT ALL ARGUMENTS INTO lower case (to allow ALL CAPS arguments to parse correctly)
    for a in range(0, len(listToProcess)):
        if listToProcess[a] != "-h" and listToProcess[a][:2] != "--": # if the dashes aren't in the current item (and it's not the -h flag)
            if listToProcess[a][:1] == "-": # if the current parameter only has one dash (typed wrongly)
                listToProcess[a] = "--" + listToProcess[a][1:].lower() # then remove that, and add the double dash and switch to lowercase
            else: # the parameter has no dashes at all, so add them
                listToProcess[a] = "--" + listToProcess[a].lower() # add the dashes + switch to lowercase to properly parse as arguments below
        else: # if the dashes are already in the current item
            listToProcess[a] = listToProcess[a].lower() # we don't need to add dashes, so just switch to lowercase

    # DELETE ANY INVALID ARGUMENTS FROM THE COMMAND LINE BEFORE RUNNING THE ARGUMENT PARSER
    # TO CLEAN UP THE ARGUMENT LIST AND ENSURE THE PARSER CAN STILL RUN WHEN INVALID ARGUMENTS ARE PRESENT
    if inStartupMode == True:
        acceptable_arguments = ["--http", "--cli", "--silent", "--light", "--mode", "--temp", "--hue", 
        "--sat", "--bri", "--luminance", "--scene", "--animation", "--help"]
    else: # if we're doing HTTP processing, we don't need the http, cli, silent and help flags, so toss 'em
        acceptable_arguments = ["--light", "--mode", "--temp", "--hue", "--sat", "--bri", "--luminance", 
        "--scene", "--animation", "--list", "--discover", "--link"]
   
    # KICK OUT ANY PARAMETERS THAT AREN'T IN THE "ACCEPTABLE ARGUMENTS" LIST
    for a in range(len(listToProcess) - 1, -1, -1):
        if not any(x in listToProcess[a] for x in acceptable_arguments): # if the current argument is invalid
            if inStartupMode == True:
                if listToProcess[a] != "-h": # and the argument isn't "-h" (for help)
                    listToProcess.pop(a) # delete the invalid argument from the list
            else: # if we're not in startup mode, then also delete the "-h" flag
                listToProcess.pop(a) # delete the invalid argument from the list
    
    # IF THERE ARE NO VALID PARAMETERS LEFT TO PARSE, THEN RETURN THAT TO THE HTTP SERVER
    if inStartupMode == False and len(listToProcess) == 0:
        printDebugString("There are no usable parameters from the HTTP request!")
        return []

    # FORCE VALUES THAT NEED PARAMETERS TO HAVE ONE, AND VALUES THAT REQUIRE NO PARAMETERS TO HAVE NONE
    for a in range(0, len(listToProcess)):
        if listToProcess[a].find("--silent") != -1: 
            listToProcess[a] = "--silent"
        elif listToProcess[a].find("--cli") != -1: 
            listToProcess[a] = "--cli"
        elif listToProcess[a].find("--html") != -1: 
            listToProcess[a] = "--html"
        elif listToProcess[a].find("--list") != -1: 
            listToProcess[a] = "--list"
        elif listToProcess[a].find("--discover") != -1: 
            listToProcess[a] = "--discover"
        elif listToProcess[a] == "--link": 
            listToProcess[a] = "--link=-1"

    # PARSE THE ARGUMENT LIST FOR CUSTOM PARAMETERS
    parser = argparse.ArgumentParser()
    
    parser.add_argument("--http", action="store_true", help="Use an HTTP server to send commands to Neewer lights using a web browser")

    # HTML SERVER SPECIFIC PARAMETERS
    if inStartupMode == False:
        parser.add_argument("--list", action="store_true") # list the currently available lights to the HTTP server
        parser.add_argument("--discover", action="store_true") # tell the HTTP server to search for newly added lights
        parser.add_argument("--link", default=-1) # link a specific light to NeewerPython-Lite

    parser.add_argument("--cli", action="store_false", help="Don't show the GUI at all, just send command and quit")
    parser.add_argument("--silent", action="store_false", help="Don't show any debug information in the console")
    parser.add_argument("--light", default="", help="The MAC Address (XX:XX:XX:XX:XX:XX) of the light you want to send a command to or ALL to find and control all lights (only valid when also using --cli switch)")
    parser.add_argument("--mode", default="CCT", help="[DEFAULT: CCT] The current control mode - options are HSL, CCT and either ANM or SCENE")
    parser.add_argument("--temp", "--temperature", default="56", help="[DEFAULT: 56(00)K] (CCT mode) - the color temperature (3200K+) to set the light to")
    parser.add_argument("--hue", default="240", help="[DEFAULT: 240] (HSL mode) - the hue (0-360 degrees) to set the light to")
    parser.add_argument("--sat", "--saturation", default="100", help="[DEFAULT: 100] (HSL mode) The saturation (color intensity) to set the light to")
    parser.add_argument("--bri", "--brightness", "--luminance", default="100", help="[DEFAULT: 100] (CCT/HSL/ANM mode) The brightness (luminance) to set the light to")
    parser.add_argument("--scene", "--animation", default="1", help="[DEFAULT: 1] (ANM or SCENE mode) The animation (1-9) to use in Scene mode")
    args = parser.parse_args(listToProcess)
    
    if args.silent == True:
        if inStartupMode == True:
            printDebugString("Starting program with command-line arguments")
        else:
            printDebugString("Processing HTTP arguments")
            args.cli = False # we're running the CLI, so no GUI (TODO: possibly make HTTP server and GUI work in tandem)
            args.silent = printDebug # we're not changing the silent flag, pass on the current printDebug setting

    if args.http == True:
        return ["HTTP", args.silent] # special mode - don't do any other mode/color/etc. processing, just jump into running the HTML server
       
    if inStartupMode == False:
        # HTTP specific parameter returns!
        if args.list == True:
            return["list"] # list the currently available lights
    
        if args.discover == True:
            return["discover"] # discover new lights

        if args.link != -1:
            return["link", args.link] # return the value defined by the parameter
        
    if args.mode == "cct":
        return [args.cli, args.silent, args.light, "CCT",
                testValid("temp", args.temp, 56, 32, 85),
                testValid("bri", args.bri, 100, 0, 100)]
    elif args.mode == "hsl":
        return [args.cli, args.silent, args.light, "HSL",
                testValid("hue", args.hue, 240, 0, 360),
                testValid("sat", args.sat, 100, 0, 100),
                testValid("bri", args.bri, 100, 0, 100)]
    elif args.mode in ("anm", "scene"):
        return [args.cli, args.silent, args.light, "ANM",
                testValid("scene", args.scene, 1, 1, 9),
                testValid("bri", args.bri, 100, 0, 100)]
    else:
        print ("Improper mode selected with --mode command - valid entries are CCT, HSL or either ANM or SCENE")
        sys.exit(0)

def processHTMLCommands(paramsList):
    paramsList = processCommands(paramsList) # process the commands returned from the HTTP parameters
    
    print(paramsList)

    if len(paramsList) == 0:
        return [] # if there are no valid parameters returned from above, return an empty list of parameters back to the HTTP function
    else:
        pass # do the actual processing here

    loop = asyncio.get_event_loop()

    if paramsList[0] == "discover": # we asked to discover new lights
        loop.run_until_complete(findDevices()) # find the lights available to control
                
        # try to connect to each light
        for a in range(0, len(availableLights)):
            loop.run_until_complete(connectToLight(a, False))
    elif paramsList[0] == "link": # we asked to connect to a specific light
        pass
    elif paramsList[0] == "list": # we asked to list the currently available lights
        print(availableLights)
    else: # we want to write a value to a specific light
        if paramsList[3] == "CCT": # calculate CCT bytestring
            calculateByteString(colorMode=paramsList[3], temp=paramsList[4], brightness=paramsList[5])
        elif paramsList[3] == "HSL": # calculate HSL bytestring
            calculateByteString(colorMode=paramsList[3], HSL_H=paramsList[4], HSL_S=paramsList[5], HSL_L=paramsList[6])
        elif paramsList[3] == "ANM": # calculate ANM/SCENE bytestring
            calculateByteString(colorMode=paramsList[3], animation=paramsList[4], brightness=paramsList[5])

        try: # if the specified light is just an index, then return the light you asked for
            currentLight = int(paramsList[2])

            # if the specified index is a negative index or beyond the range of lights available, then it's not valid
            if currentLight < 0 or currentLight > len(availableLights):
                currentLight = -1
        except ValueError: # we're most likely asking for a MAC address instead of an integer index
            currentLight = -1

            for a in range(0, len(availableLights)):
                if paramsList[2].upper() == availableLights[a][0].address.upper(): # if the MAC address specified matches the current light
                    currentLight = a
                    break
                else:
                    print(availableLights[a][0].address.upper())
            
        if currentLight != -1:
            loop.run_until_complete(writeToLight(currentLight, False))
        else:
            print("Could not find that light!")

    return paramsList

class MyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        # TODO, possibly: Add check here to make sure URL arguments aren't absolutely huge, to avoid a buffer overrun error
        # /NeewerLite-Python/mode=HSL|hue=120|sat=100|bri=100|light=XX:XX:XX:XX:XX:XX:XX is 78 characters, so the URL should
        # theoretically not be any longer than, say 120 characters total - you'd send a command to one light at a time - look
        # into this!  Maybe a slightly longer allowance if you're sending to multiple lights (possibly in the light= parameter)
        # separated into multiple light MAC addresses, like light=XX:XX:XX:XX:XX:XX:XX:XX;YY:YY:YY:YY:YY:YY:YY:YY, etc. for no
        # more than... 4 lights possibly?  6?

        acceptableURL = "/NeewerLite-Python/"

        if acceptableURL in self.path: # if the URL contains "/NeewerLite-Python/" then it's a valid URL
            paramsList = self.path.replace(acceptableURL, "").split("|") # split the included parameters into a list
            paramsList = processHTMLCommands(paramsList)
          
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            self.wfile.write(bytes("<html><head><title>NeewerLite-Python HTTP Server</title></head>", "utf-8"))
            self.wfile.write(bytes("<body>", "utf-8"))

            if len(paramsList) == 0: # if we have no valid parameters, then say that in the error report
                self.wfile.write(bytes("<h1>Invalid request!</h1>", "utf-8"))
                self.wfile.write(bytes("Last Request: <em>" + self.path + "</em><br>", "utf-8"))
                self.wfile.write(bytes("You didn't provide any valid parameters in the last URL.  To send multiple parameters to NeewerLite-Python, separate each one with a | character.<br><br>", "utf-8"))
                self.wfile.write(bytes("Valid parameters to use -<br>", "utf-8"))
                self.wfile.write(bytes("<strong>list</strong> - list the current lights NeewerPython-Lite has available to it<br>", "utf-8"))
                self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/list</em><br>", "utf-8"))
                self.wfile.write(bytes("<strong>discover</strong> - tell NeewerLite-Python to scan for new lights<br>", "utf-8"))
                self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/discover</em><br>", "utf-8"))
                self.wfile.write(bytes("<strong>link=</strong> - (value: <em>index of light to link to</em>) manually link to a specific light<br>", "utf-8"))
                self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/link=0</em><br>", "utf-8"))
                self.wfile.write(bytes("<strong>light=</strong> - the MAC address or index of the light you want to send a command to<br>", "utf-8"))
                self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/light=11:22:33:44:55:66</em><br>", "utf-8"))
                self.wfile.write(bytes("<strong>mode=</strong> - the mode (value: <em>HSL, CCT, and either ANM or SCENE</em>) - the color mode to switch the light to<br>", "utf-8"))
                self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/mode=CCT</em><br>", "utf-8"))
                self.wfile.write(bytes("(CCT mode only) <strong>temp=</strong> or <strong>temperature=</strong> - (value: <em>3200 to 8500</em>) the color temperature in CCT mode to set the light to<br>", "utf-8"))
                self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/temp=5200</em><br>", "utf-8"))
                self.wfile.write(bytes("(HSL mode only) <strong>hue=</strong> - (value: <em>0 to 360</em>) the hue value in HSL mode to set the light to<br>", "utf-8"))
                self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/hue=240</em><br>", "utf-8"))
                self.wfile.write(bytes("(HSL mode only) <strong>sat=</strong> or <strong>saturation=</strong> - (value: <em>0 to 100</em>) the color saturation value in HSL mode to set the light to<br>", "utf-8"))
                self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/sat=65</em><br>", "utf-8"))
                self.wfile.write(bytes("(ANM/SCENE mode only) <strong>scene=</strong> - (value: <em>1 to 9</em>) which animation (scene) to switch the light to<br>", "utf-8"))
                self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/scene=3</em><br>", "utf-8"))
                self.wfile.write(bytes("(CCT/HSL/ANM modes) <strong>bri=</strong>, <strong>brightness=</strong> or <strong>luminance=</strong> - (value: <em>0 to 100</em>) how bright you want the light<br>", "utf-8"))
                self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/brightness=80</em><br>", "utf-8"))
                self.wfile.write(bytes("<br><br>More examples -<br>", "utf-8"))
                self.wfile.write(bytes("&nbsp;&nbsp;Set the light with MAC address <em>11:22:33:44:55:66</em> to <em>CCT</em> mode, with a color temperature of <em>5200</em> and brightness of <em>40</em><br>", "utf-8"))
                self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;<em>http://(server address)/NeewerLite-Python/light=11:22:33:44:55:66|mode=CCT|temp=5200|bri=40</em><br><br>", "utf-8"))
                self.wfile.write(bytes("&nbsp;&nbsp;Set the light with MAC address <em>11:22:33:44:55:66</em> to <em>HSL</em> mode, with a hue of <em>70</em>, saturation of <em>50</em> and brightness of <em>10</em><br>", "utf-8"))
                self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;<em>http://(server address)/NeewerLite-Python/light=11:22:33:44:55:66|mode=HSL|hue=70|sat=50|bri=10</em><br><br>", "utf-8"))
                self.wfile.write(bytes("&nbsp;&nbsp;Set the <em>first light available</em> (which uses index 0) to <em>SCENE</em> mode, using the <em>first</em> animation and brightness of <em>55</em><br>", "utf-8"))
                self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;<em>http://(server address)/NeewerLite-Python/light=0|mode=SCENE|scene=1|bri=55</em><br>", "utf-8"))
            else:
                self.wfile.write(bytes("<h1>Request Successful!</h1>", "utf-8"))
                self.wfile.write(bytes("Last Request: <em>" + self.path + "</em><br><br>", "utf-8"))

                self.wfile.write(bytes("Provided Parameters:<br>", "utf-8"))

                for a in range(0, len(paramsList)):
                    self.wfile.write(bytes("&nbsp;&nbsp;" + str(paramsList[a]) + "<br>", "utf-8"))

            self.wfile.write(bytes("</body></html>", "utf-8"))
        else:
            self.send_error(404, "The URL you specified (" + self.path + ") was not correct.  The NeewerLite-Python HTTP server only accepts URLs starting with /NeewerLite-Python/ and a list of parameters after the forward slash, separated by a | character in between each specified parameter.  An example of a correct URL would be: http://(server IP address):8080/NeewerLite-Python/mode=HSL|hue=120|sat=60|brightness=20|light=XX:XX:XX:XX:XX:XX")

if __name__ == '__main__':
    loop = asyncio.get_event_loop() # get the current asyncio loop
    cmdReturn = [True] # initially set to show the GUI interface over the CLI interface

    if len(sys.argv) > 1: # if we have more than 1 argument on the command line (the script itself is argument 1), then process switches
        cmdReturn = processCommands()
        printDebug = cmdReturn[1] # if we use the --quiet option, then don't show debug strings in the console

        # START HTTP SERVER HERE AND SIT IN THIS LOOP UNTIL THE END
        if cmdReturn[0] == "HTTP":
            webServer = HTTPServer(("", 8080), MyServer)

            try:
                printDebugString("Starting the HTTP Server on Port 8080...")
                printDebugString("-------------------------------------------------------------------------------------")

                '''
                loop.run_until_complete(findDevices()) # find the lights available to control
                
                # try to connect to each light
                for a in range(0, len(availableLights)):
                    loop.run_until_complete(connectToLight(a, False))
                '''

                # start the HTTP server and wait for requests
                webServer.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                printDebugString("Stopping the HTTP Server...")
                webServer.server_close()

            sys.exit(0)            

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
                printDebugString(" > CLI >> MAC Address of light to send command to: " + cmdReturn[2].upper())
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