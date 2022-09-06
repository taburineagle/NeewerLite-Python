#############################################################
## NeewerLite-Python ver. 0.12
## by Zach Glenwright
############################################################
## > https://github.com/taburineagle/NeewerLite-Python/ <
############################################################
## A cross-platform Python script using the bleak and
## PySide2 libraries to control Neewer brand lights via
## Bluetooth on multiple platforms -
##          Windows, Linux/Ubuntu, MacOS and RPi
############################################################
## Originally based on the NeewerLight project by @keefo
##      > https://github.com/keefo/NeewerLite <
############################################################

import os
import sys
import math # used for calculating the RGB values of color temperatures
import tempfile

import argparse
import platform # used to determine which OS we're using for MAC address/GUID listing

import asyncio
import threading
import time

from datetime import datetime

# IMPORT BLEAK (this is the library that allows the program to communicate with the lights) - THIS IS NECESSARY!
try:
    from bleak import BleakScanner, BleakClient
except ModuleNotFoundError as e:
    print(" ===== CAN NOT FIND BLEAK LIBRARY =====")
    print(" You need the bleak Python package installed to use NeewerLite-Python.")
    print(" Bleak is the library that connects the program to Bluetooth devices.")
    print(" Please install the Bleak package first before running NeewerLite-Python.")
    print()
    print(" To install Bleak, run either pip or pip3 from the command line:")
    print("    pip install bleak")
    print("    pip3 install bleak")
    print()
    print(" Or visit this website for more information:")
    print("    https://pypi.org/project/bleak/")
    sys.exit(1) # you can't use the program itself without Bleak, so kill the program if we don't have it

# IMPORT THE WINDOWS LIBRARY (if you don't do this, it will throw an exception on Windows only)
if platform.system() == "Windows": # try to load winrt if we're on Windows
    try:
        from winrt import _winrt
        _winrt.uninit_apartment()
    except Exception as e:
        pass # if there is an exception to this module loading, you're not on Windows

importError = 0 # whether or not there's an issue loading PySide2 or the GUI file

# IMPORT PYSIDE2 (the GUI libraries)
try:
    from PySide2.QtCore import Qt, QItemSelectionModel
    from PySide2.QtGui import QLinearGradient, QColor, QKeySequence
    from PySide2.QtWidgets import QApplication, QMainWindow, QTableWidgetItem, QShortcut, QMessageBox

except Exception as e:
    importError = 1 # log that we can't find PySide2

# IMPORT THE GUI ITSELF
try:
    from ui_NeewerLightUI import Ui_MainWindow
except Exception as e:
    if importError != 1: # if we don't already have a PySide2 issue
        importError = 2 # log that we can't find the GUI file - which, if the program is downloaded correctly, shouldn't be an issue

# IMPORT THE HTTP SERVER
try:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import urllib.parse # parsing custom light names in the HTTP server
except Exception as e:
    pass # if there are any HTTP errors, don't do anything yet

CCTSlider = -1 # the current slider moved in the CCT window - 1 - Brightness / 2 - Hue / -1 - Both Brightness and Hue
sendValue = [120, 135, 2, 20, 56, 157] # an array to hold the values to be sent to the light - the default is CCT / 5600K / 20%
lastAnimButtonPressed = 1 # which animation button you clicked last - if none, then it defaults to 1 (the police sirens)
lastSelection = [] # the current light selection (this is for snapshot preset entering/leaving buttons)
lastSortingField = -1 # the last field used for sorting purposes

availableLights = [] # the list of Neewer lights currently available to control
# List Subitems (for ^^^^^^):
# [0] - Bleak Scan Object (can use .name / .rssi / .address to get specifics)
# [1] - Bleak Connection (the actual Bluetooth connection to the light itself)
# [2] - Custom Name for Light (string)
# [3] - Last Used Parameters (list)
# [4] - The range of color temperatures to use in CCT mode (list, min, max) <- changed in 0.12
# [5] - Whether or not to send Brightness and Hue independently for old lights (boolean)
# [6] - Whether or not this light has been manually turned ON/OFF (boolean)
# [7] - The Power and Channel data returned for this light (list)

# Light Preset ***Default*** Settings (for sections below):
# NOTE: The list is 0-based, so the preset itself is +1 from the subitem
# [0] - [CCT mode] - 5600K / 20%
# [1] - [CCT mode] - 3200K / 20%
# [2] - [CCT mode] - 5600K / 0% (lights are on, but set to 0% brightness)
# [3] - [HSI mode] - 0° hue / 100% saturation / 20% intensity (RED)
# [4] - [HSI mode] - 240° hue / 100% saturation / 20% intensity (BLUE)
# [5] - [HSI mode] - 120° hue / 100% saturation / 20% intensity (GREEN)
# [6] - [HSI mode] - 300° hue / 100% saturation / 20% intensity (PURPLE)
# [7] - [HSI mode] - 160° hue / 100% saturation / 20% intensity (CYAN)

# The list of **default** light presets for restoring and checking against
defaultLightPresets = [
    [[-1, [5, 20, 56]]],
    [[-1, [5, 20, 32]]],
    [[-1, [5, 0, 56]]],
    [[-1, [4, 20, 0, 100]]],
    [[-1, [4, 20, 240, 100]]],
    [[-1, [4, 20, 120, 100]]],
    [[-1, [4, 20, 300, 100]]],
    [[-1, [4, 20, 160, 100]]]    
    ]

# A list of preset mode settings - custom file will overwrite
customLightPresets = [
    [[-1, [5, 20, 56]]],
    [[-1, [5, 20, 32]]],
    [[-1, [5, 0, 56]]],
    [[-1, [4, 20, 0, 100]]],
    [[-1, [4, 20, 240, 100]]],
    [[-1, [4, 20, 120, 100]]],
    [[-1, [4, 20, 300, 100]]],
    [[-1, [4, 20, 160, 100]]]    
    ]

threadAction = "" # the current action to take from the thread
asyncioEventLoop = None # the current asyncio loop

setLightUUID = "69400002-B5A3-F393-E0A9-E50E24DCCA99" # the UUID to send information to the light
notifyLightUUID = "69400003-B5A3-F393-E0A9-E50E24DCCA99" # the UUID for notify callbacks from the light

receivedData = "" # the data received from the Notify characteristic

# SET FROM THE PREFERENCES FILE ON LAUNCH
findLightsOnStartup = True # whether or not to look for lights when the program starts
autoConnectToLights = True # whether or not to auto-connect to lights after finding them
printDebug = True # show debug messages in the console for all of the program's events
maxNumOfAttempts = 6 # the maximum attempts the program will attempt an action before erroring out
rememberLightsOnExit = False # whether or not to save the currently set light settings (mode/hue/brightness/etc.) when quitting out
rememberPresetsOnExit = True # whether or not to save the custom preset list when quitting out
acceptable_HTTP_IPs = [] # the acceptable IPs for the HTTP server, set on launch by prefs file
customKeys = [] # custom keymappings for keyboard shortcuts, set on launch by the prefs file
whiteListedMACs = [] # whitelisted list of MAC addresses to add to NeewerLite-Python
enableTabsOnLaunch = False # whether or not to enable tabs on startup (even with no lights connected)

lockFile = tempfile.gettempdir() + os.sep + "NeewerLite-Python.lock"
anotherInstance = False # whether or not we're using a new instance (for the Singleton check)
globalPrefsFile = os.path.dirname(os.path.abspath(sys.argv[0])) + os.sep + "light_prefs" + os.sep + "NeewerLite-Python.prefs" # the global preferences file for saving/loading
customLightPresetsFile = os.path.dirname(os.path.abspath(sys.argv[0])) + os.sep + "light_prefs" + os.sep + "customLights.prefs"

# FILE LOCKING FOR SINGLE INSTANCE
def singleInstanceLock():
    global anotherInstance

    try:
        lf = os.open(lockFile, os.O_WRONLY | os.O_CREAT | os.O_EXCL) # try to get a file spec to lock the "running" instance

        with os.fdopen(lf, 'w') as lockfile:
            lockfile.write(str(os.getpid())) # write the PID of the current running process to the temporary lockfile
    except IOError: # if we had an error acquiring the file descriptor, the file most likely already exists.
        anotherInstance = True
    
def singleInstanceUnlockandQuit(exitCode):
    try:
        os.remove(lockFile) # try to delete the lockfile on exit
    except FileNotFoundError: # if another process deleted it, then just error out
        printDebugString("Lockfile not found in temp directory, so we're going to skip deleting it!")

    sys.exit(exitCode) # quit out, with the specified exitCode

def doAnotherInstanceCheck():
    if anotherInstance == True: # if we're running a 2nd instance, but we shouldn't be
        print("You're already running another instance of NeewerLite-Python.")
        print("Please close that copy first before opening a new one.")
        print()
        print("To force opening a new instance, add --force_instance to the command line.")
        sys.exit(1)

try: # try to load the GUI
    class MainWindow(QMainWindow, Ui_MainWindow):
        def __init__(self):
            QMainWindow.__init__(self)
            self.setupUi(self) # set up the main UI
            self.connectMe() # connect the function handlers to the widgets

            if enableTabsOnLaunch == False: # if we're not supposed to enable tabs on launch, then disable them all
                self.ColorModeTabWidget.setTabEnabled(0, False) # disable the CCT tab on launch
                self.ColorModeTabWidget.setTabEnabled(1, False) # disable the HSI tab on launch
                self.ColorModeTabWidget.setTabEnabled(2, False) # disable the SCENE tab on launch
                self.ColorModeTabWidget.setTabEnabled(3, False) # disable the LIGHT PREFS tab on launch
                self.ColorModeTabWidget.setCurrentIndex(0)

            if findLightsOnStartup == True: # if we're set up to find lights on startup, then indicate that
                self.statusBar.showMessage("Please wait - searching for Neewer lights...")
            else:
                self.statusBar.showMessage("Welcome to NeewerLite-Python!  Hit the Scan button above to scan for lights.")

            if platform.system() == "Darwin": # if we're on MacOS, then change the column text for the 2nd column in the light table
                self.lightTable.horizontalHeaderItem(1).setText("Light UUID")

            # IF ANY OF THE CUSTOM PRESETS ARE ACTUALLY CUSTOM, THEN MARK THOSE BUTTONS AS CUSTOM
            if customLightPresets[0] != defaultLightPresets[0]:
                if customLightPresets[0][0][0] == -1: # if the current preset is custom, but a global, mark it that way
                    self.customPreset_0_Button.markCustom(0)
                else: # the current preset is a snapshot preset
                    self.customPreset_0_Button.markCustom(0, 1)
            if customLightPresets[1] != defaultLightPresets[1]:
                if customLightPresets[1][0][0] == -1:
                    self.customPreset_1_Button.markCustom(1)
                else:
                    self.customPreset_1_Button.markCustom(1, 1)
            if customLightPresets[2] != defaultLightPresets[2]:
                if customLightPresets[2][0][0] == -1:
                    self.customPreset_2_Button.markCustom(2)
                else:
                    self.customPreset_2_Button.markCustom(2, 1)
            if customLightPresets[3] != defaultLightPresets[3]:
                if customLightPresets[3][0][0] == -1:
                    self.customPreset_3_Button.markCustom(3)
                else:
                    self.customPreset_3_Button.markCustom(3, 1)
            if customLightPresets[4] != defaultLightPresets[4]:
                if customLightPresets[4][0][0] == -1:
                    self.customPreset_4_Button.markCustom(4)
                else:
                    self.customPreset_4_Button.markCustom(4, 1)
            if customLightPresets[5] != defaultLightPresets[5]:
                if customLightPresets[5][0][0] == -1:
                    self.customPreset_5_Button.markCustom(5)
                else:
                    self.customPreset_5_Button.markCustom(5, 1)
            if customLightPresets[6] != defaultLightPresets[6]:
                if customLightPresets[6][0][0] == -1:
                    self.customPreset_6_Button.markCustom(6)
                else:
                    self.customPreset_6_Button.markCustom(6, 1)
            if customLightPresets[7] != defaultLightPresets[7]:
                if customLightPresets[7][0][0] == -1:
                    self.customPreset_7_Button.markCustom(7)
                else:
                    self.customPreset_7_Button.markCustom(7, 1)
                
            self.show

        def connectMe(self):
            self.turnOffButton.clicked.connect(self.turnLightOff)
            self.turnOnButton.clicked.connect(self.turnLightOn)

            self.scanCommandButton.clicked.connect(self.startSelfSearch)
            self.tryConnectButton.clicked.connect(self.startConnect)

            self.ColorModeTabWidget.currentChanged.connect(self.tabChanged)
            self.lightTable.itemSelectionChanged.connect(self.selectionChanged)

            # Allow clicking on the headers for sorting purposes
            horizHeaders = self.lightTable.horizontalHeader()
            horizHeaders.setSectionsClickable(True)
            horizHeaders.sectionClicked.connect(self.sortByHeader)

            # COMMENTS ARE THE SAME THE ENTIRE WAY DOWN THIS CHAIN
            self.customPreset_0_Button.clicked.connect(lambda: recallCustomPreset(0)) # when you click a preset
            self.customPreset_0_Button.rightclicked.connect(lambda: self.saveCustomPresetDialog(0)) # when you right-click a preset
            self.customPreset_0_Button.enteredWidget.connect(lambda: self.highlightLightsForSnapshotPreset(0)) # when the mouse enters the widget
            self.customPreset_0_Button.leftWidget.connect(lambda: self.highlightLightsForSnapshotPreset(0, True)) # when the mouse leaves the widget
            self.customPreset_1_Button.clicked.connect(lambda: recallCustomPreset(1))
            self.customPreset_1_Button.rightclicked.connect(lambda: self.saveCustomPresetDialog(1))
            self.customPreset_1_Button.enteredWidget.connect(lambda: self.highlightLightsForSnapshotPreset(1))
            self.customPreset_1_Button.leftWidget.connect(lambda: self.highlightLightsForSnapshotPreset(1, True))
            self.customPreset_2_Button.clicked.connect(lambda: recallCustomPreset(2))
            self.customPreset_2_Button.rightclicked.connect(lambda: self.saveCustomPresetDialog(2))
            self.customPreset_2_Button.enteredWidget.connect(lambda: self.highlightLightsForSnapshotPreset(2))
            self.customPreset_2_Button.leftWidget.connect(lambda: self.highlightLightsForSnapshotPreset(2, True))
            self.customPreset_3_Button.clicked.connect(lambda: recallCustomPreset(3))
            self.customPreset_3_Button.rightclicked.connect(lambda: self.saveCustomPresetDialog(3))
            self.customPreset_3_Button.enteredWidget.connect(lambda: self.highlightLightsForSnapshotPreset(3))
            self.customPreset_3_Button.leftWidget.connect(lambda: self.highlightLightsForSnapshotPreset(3, True))
            self.customPreset_4_Button.clicked.connect(lambda: recallCustomPreset(4))
            self.customPreset_4_Button.rightclicked.connect(lambda: self.saveCustomPresetDialog(4))
            self.customPreset_4_Button.enteredWidget.connect(lambda: self.highlightLightsForSnapshotPreset(4))
            self.customPreset_4_Button.leftWidget.connect(lambda: self.highlightLightsForSnapshotPreset(4, True))
            self.customPreset_5_Button.clicked.connect(lambda: recallCustomPreset(5))
            self.customPreset_5_Button.rightclicked.connect(lambda: self.saveCustomPresetDialog(5))
            self.customPreset_5_Button.enteredWidget.connect(lambda: self.highlightLightsForSnapshotPreset(5))
            self.customPreset_5_Button.leftWidget.connect(lambda: self.highlightLightsForSnapshotPreset(5, True))
            self.customPreset_6_Button.clicked.connect(lambda: recallCustomPreset(6))
            self.customPreset_6_Button.rightclicked.connect(lambda: self.saveCustomPresetDialog(6))
            self.customPreset_6_Button.enteredWidget.connect(lambda: self.highlightLightsForSnapshotPreset(6))
            self.customPreset_6_Button.leftWidget.connect(lambda: self.highlightLightsForSnapshotPreset(6, True))
            self.customPreset_7_Button.clicked.connect(lambda: recallCustomPreset(7))
            self.customPreset_7_Button.rightclicked.connect(lambda: self.saveCustomPresetDialog(7))
            self.customPreset_7_Button.enteredWidget.connect(lambda: self.highlightLightsForSnapshotPreset(7))
            self.customPreset_7_Button.leftWidget.connect(lambda: self.highlightLightsForSnapshotPreset(7, True))

            self.Slider_CCT_Hue.valueChanged.connect(lambda: self.computeValueCCT(1))
            self.Slider_CCT_Bright.valueChanged.connect(lambda: self.computeValueCCT(2))

            self.Slider_HSI_1_H.valueChanged.connect(lambda: self.computeValueHSI(1))
            self.Slider_HSI_2_S.valueChanged.connect(lambda: self.computeValueHSI(2))
            self.Slider_HSI_3_L.valueChanged.connect(lambda: self.computeValueHSI(3))

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

            # CHECKS TO SEE IF SPECIFIC FIELDS (and the save button) SHOULD BE ENABLED OR DISABLED
            self.customName.clicked.connect(self.checkLightPrefsEnables)
            self.colorTempRange.clicked.connect(self.checkLightPrefsEnables)
            self.saveLightPrefsButton.clicked.connect(self.checkLightPrefs)

            self.resetGlobalPrefsButton.clicked.connect(lambda: self.setupGlobalLightPrefsTab(True))
            self.saveGlobalPrefsButton.clicked.connect(self.saveGlobalPrefs)

            # SHORTCUT KEYS - MAKE THEM HERE, SET THEIR ASSIGNMENTS BELOW WITH self.setupShortcutKeys()
            # IN CASE WE NEED TO CHANGE THEM AFTER CHANGING PREFERENCES
            self.SC_turnOffButton = QShortcut(self)
            self.SC_turnOnButton = QShortcut(self)
            self.SC_scanCommandButton = QShortcut(self)
            self.SC_tryConnectButton = QShortcut(self)
            self.SC_Tab_CCT = QShortcut(self)
            self.SC_Tab_HSI = QShortcut(self)
            self.SC_Tab_SCENE = QShortcut(self)
            self.SC_Tab_PREFS = QShortcut(self)

            # DECREASE/INCREASE BRIGHTNESS REGARDLESS OF WHICH TAB WE'RE ON
            self.SC_Dec_Bri_Small = QShortcut(self)
            self.SC_Inc_Bri_Small = QShortcut(self)
            self.SC_Dec_Bri_Large = QShortcut(self)
            self.SC_Inc_Bri_Large = QShortcut(self)

            # THE SMALL INCREMENTS *DO* NEED A CUSTOM FUNCTION, BUT ONLY IF WE CHANGE THE
            # SHORTCUT ASSIGNMENT TO SOMETHING OTHER THAN THE NORMAL NUMBERS
            # THE LARGE INCREMENTS DON'T NEED A CUSTOM FUNCTION
            self.SC_Dec_1_Small = QShortcut(self)
            self.SC_Inc_1_Small = QShortcut(self)
            self.SC_Dec_2_Small = QShortcut(self)
            self.SC_Inc_2_Small = QShortcut(self)
            self.SC_Dec_3_Small = QShortcut(self)
            self.SC_Inc_3_Small = QShortcut(self)
            self.SC_Dec_1_Large = QShortcut(self)
            self.SC_Inc_1_Large = QShortcut(self)
            self.SC_Dec_2_Large = QShortcut(self)
            self.SC_Inc_2_Large = QShortcut(self)
            self.SC_Dec_3_Large = QShortcut(self)
            self.SC_Inc_3_Large = QShortcut(self)

            self.setupShortcutKeys() # set up the shortcut keys for the first time

            # CONNECT THE KEYS TO THEIR FUNCTIONS
            self.SC_turnOffButton.activated.connect(self.turnLightOff)
            self.SC_turnOnButton.activated.connect(self.turnLightOn)
            self.SC_scanCommandButton.activated.connect(self.startSelfSearch)
            self.SC_tryConnectButton.activated.connect(self.startConnect)
            self.SC_Tab_CCT.activated.connect(lambda: self.switchToTab(0))
            self.SC_Tab_HSI.activated.connect(lambda: self.switchToTab(1))
            self.SC_Tab_SCENE.activated.connect(lambda: self.switchToTab(2))
            self.SC_Tab_PREFS.activated.connect(lambda: self.switchToTab(3))

            # DECREASE/INCREASE BRIGHTNESS REGARDLESS OF WHICH TAB WE'RE ON
            self.SC_Dec_Bri_Small.activated.connect(lambda: self.changeSliderValue(0, -1))
            self.SC_Inc_Bri_Small.activated.connect(lambda: self.changeSliderValue(0, 1))
            self.SC_Dec_Bri_Large.activated.connect(lambda: self.changeSliderValue(0, -5))
            self.SC_Inc_Bri_Large.activated.connect(lambda: self.changeSliderValue(0, 5))

            # THE SMALL INCREMENTS DO NEED A SPECIAL FUNCTION-
            # (see above) - BASICALLY, IF THEY'RE JUST ASSIGNED THE DEFAULT NUMPAD/NUMBER VALUES
            # THESE FUNCTIONS DON'T TRIGGER (THE SAME FUNCTIONS ARE HANDLED BY numberShortcuts(n))
            # BUT IF THEY ARE CUSTOM, *THEN* THESE TRIGGER INSTEAD, AND THIS FUNCTION ^^^^ JUST DOES
            # SCENE SELECTIONS IN SCENE MODE
            self.SC_Dec_1_Small.activated.connect(lambda: self.changeSliderValue(1, -1))
            self.SC_Inc_1_Small.activated.connect(lambda: self.changeSliderValue(1, 1))
            self.SC_Dec_2_Small.activated.connect(lambda: self.changeSliderValue(2, -1))
            self.SC_Inc_2_Small.activated.connect(lambda: self.changeSliderValue(2, 1))
            self.SC_Dec_3_Small.activated.connect(lambda: self.changeSliderValue(3, -1))
            self.SC_Inc_3_Small.activated.connect(lambda: self.changeSliderValue(3, 1))

            # THE LARGE INCREMENTS DON'T NEED A CUSTOM FUNCTION
            self.SC_Dec_1_Large.activated.connect(lambda: self.changeSliderValue(1, -5))
            self.SC_Inc_1_Large.activated.connect(lambda: self.changeSliderValue(1, 5))
            self.SC_Dec_2_Large.activated.connect(lambda: self.changeSliderValue(2, -5))
            self.SC_Inc_2_Large.activated.connect(lambda: self.changeSliderValue(2, 5))
            self.SC_Dec_3_Large.activated.connect(lambda: self.changeSliderValue(3, -5))
            self.SC_Inc_3_Large.activated.connect(lambda: self.changeSliderValue(3, 5))

            # THE NUMPAD SHORTCUTS ARE SET UP REGARDLESS OF WHAT THE CUSTOM INC/DEC SHORTCUTS ARE
            self.SC_Num1 = QShortcut(QKeySequence("1"), self)
            self.SC_Num1.activated.connect(lambda: self.numberShortcuts(1))
            self.SC_Num2 = QShortcut(QKeySequence("2"), self)
            self.SC_Num2.activated.connect(lambda: self.numberShortcuts(2))
            self.SC_Num3 = QShortcut(QKeySequence("3"), self)
            self.SC_Num3.activated.connect(lambda: self.numberShortcuts(3))
            self.SC_Num4 = QShortcut(QKeySequence("4"), self)
            self.SC_Num4.activated.connect(lambda: self.numberShortcuts(4))
            self.SC_Num5 = QShortcut(QKeySequence("5"), self)
            self.SC_Num5.activated.connect(lambda: self.numberShortcuts(5))
            self.SC_Num6 = QShortcut(QKeySequence("6"), self)
            self.SC_Num6.activated.connect(lambda: self.numberShortcuts(6))
            self.SC_Num7 = QShortcut(QKeySequence("7"), self)
            self.SC_Num7.activated.connect(lambda: self.numberShortcuts(7))
            self.SC_Num8 = QShortcut(QKeySequence("8"), self)
            self.SC_Num8.activated.connect(lambda: self.numberShortcuts(8))
            self.SC_Num9 = QShortcut(QKeySequence("9"), self)
            self.SC_Num9.activated.connect(lambda: self.numberShortcuts(9))

        def sortByHeader(self, theHeader):
            global availableLights
            global lastSortingField

            if theHeader < 2: # if we didn't click on the "Linked" or "Status" headers, start processing the sort
                sortingList = [] # a copy of the availableLights array
                checkForCustomNames = False # whether or not to ask to sort by custom names (if there aren't any custom names, then don't allow)

                for a in range(len(availableLights)): # copy the entire availableLights array into a temporary array to process it
                    if theHeader == 0 and availableLights[a][2] != "": # if the current light has a custom name (and we clicked on Name)
                        checkForCustomNames = True # then we need to ask what kind of sorting when we sort

                    sortingList.append([availableLights[a][0], availableLights[a][1], availableLights[a][2], availableLights[a][3], \
                                        availableLights[a][4], availableLights[a][5], availableLights[a][6], availableLights[a][7], \
                                        availableLights[a][0].name, availableLights[a][0].address, availableLights[a][0].rssi])
            else: # we clicked on the "Linked" or "Status" headers, which do not allow sorting
                sortingField = -1

            if theHeader == 0:
                sortDlg = QMessageBox(self)
                sortDlg.setIcon(QMessageBox.Question)
                sortDlg.setWindowTitle("Sort by...")
                sortDlg.setText("Which do you want to sort by?")
                   
                sortDlg.addButton(" RSSI (Signal Level) ", QMessageBox.ButtonRole.AcceptRole)
                sortDlg.addButton(" Type of Light ", QMessageBox.ButtonRole.AcceptRole)

                if checkForCustomNames == True: # if we have custom names available, then add that as an option
                    sortDlg.addButton("Custom Name", QMessageBox.ButtonRole.AcceptRole)    
                    
                sortDlg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                sortDlg.setIcon(QMessageBox.Warning)
                clickedButton = sortDlg.exec_()

                if clickedButton == 0:
                    sortingField = 10 # sort by RSSI
                elif clickedButton == 1:
                    sortingField = 8 # sort by type of light
                elif clickedButton == 2:
                    if checkForCustomNames == True: # if the option was available for custom names, this is "custom name"
                        sortingField = 2 
                    else: # if the option wasn't available, then this is "cancel"
                        sortingField = -1 # cancel out of sorting - write this!
                elif clickedButton == 3: # this option is only available if custom names is accessible - if so, this is "cancel"
                        sortingField = -1 # cancel out of sorting - write this!
            elif theHeader == 1: # sort by MAC Address/GUID
                sortingField = 9

            if sortingField != -1: # we want to sort
                self.lightTable.horizontalHeader().setSortIndicatorShown(True) # show the sorting indicator

                if lastSortingField != sortingField: # if we're doing a different kind of sort than the last one
                    self.lightTable.horizontalHeader().setSortIndicator(theHeader, Qt.SortOrder.AscendingOrder) # force the header to "Ascending" order
                    if sortingField != 10: # if we're not looking at RSSI
                        doReverseSort = False # we need an ascending order search
                    else: # we ARE looking at RSSI
                        doReverseSort = True # if we're looking at RSSI, then the search order is reversed (as the smaller # is actually the higher value)
                else: # if it's the same as before, then take the cue from the last order
                    if self.lightTable.horizontalHeader().sortIndicatorOrder() == Qt.SortOrder.DescendingOrder:
                        if sortingField != 10:
                            doReverseSort = True
                        else:
                            doReverseSort = False
                    elif self.lightTable.horizontalHeader().sortIndicatorOrder() == Qt.SortOrder.AscendingOrder:
                        if sortingField != 10:
                            doReverseSort = False
                        else:
                            doReverseSort = True

                sortedList = sorted(sortingList, key = lambda x: x[sortingField], reverse = doReverseSort) # sort the list
                availableLights.clear() # clear the list of available lights

                for a in range(len(sortedList)): # rebuild the available lights list from the sorted list
                    availableLights.append([sortedList[a][0], sortedList[a][1], sortedList[a][2], sortedList[a][3], \
                                            sortedList[a][4], sortedList[a][5], sortedList[a][6], sortedList[a][7]])
                                        
                self.updateLights(False) # redraw the table with the new light list
                lastSortingField = sortingField # keep track of the last field used for sorting, so we know whether or not to switch to ascending
            else:
                self.lightTable.horizontalHeader().setSortIndicatorShown(False) # hide the sorting indicator

        def switchToTab(self, theTab): # SWITCH TO THE REQUESTED TAB **IF IT IS AVAILABLE**
            if self.ColorModeTabWidget.isTabEnabled(theTab) == True:
                self.ColorModeTabWidget.setCurrentIndex(theTab)

        def numberShortcuts(self, theNumber):
            # THE KEYS (IF THERE AREN'T CUSTOM ONES SET UP):
            # 7 AND 9 ADJUST THE FIRST SLIDER ON A TAB
            # 4 AND 6 ADJUST THE SECOND SLIDER ON A TAB
            # 1 AND 3 ADJUST THE THIRD SLIDER ON A TAB
            # UNLESS WE'RE IN SCENE MODE, THEN THEY JUST SWITCH THE SCENE
            if theNumber == 1:
                if self.ColorModeTabWidget.currentIndex() == 2: # if we're on the SCENE tab, then the number keys correspond to an animation
                    self.computeValueANM(1)
                else: # if we're not, adjust the slider
                    if customKeys[16] == "1":
                        self.changeSliderValue(3, -1) # decrement slider 3
            elif theNumber == 2:
                if self.ColorModeTabWidget.currentIndex() == 2:
                    self.computeValueANM(2)
            elif theNumber == 3:
                if self.ColorModeTabWidget.currentIndex() == 2:
                    self.computeValueANM(3)
                else:
                    if customKeys[17] == "3":
                        self.changeSliderValue(3, 1) # increment slider 3
            elif theNumber == 4:
                if self.ColorModeTabWidget.currentIndex() == 2:
                    self.computeValueANM(4)
                else:
                    if customKeys[14] == "4":
                        self.changeSliderValue(2, -1) # decrement slider 2
            elif theNumber == 5:
                if self.ColorModeTabWidget.currentIndex() == 2:
                    self.computeValueANM(5)
            elif theNumber == 6:
                if self.ColorModeTabWidget.currentIndex() == 2:
                    self.computeValueANM(6)
                else:
                    if customKeys[15] == "6":
                        self.changeSliderValue(2, 1) # increment slider 2
            elif theNumber == 7:
                if self.ColorModeTabWidget.currentIndex() == 2:
                    self.computeValueANM(7)
                else:
                    if customKeys[12] == "7":
                        self.changeSliderValue(1, -1) # decrement slider 1
            elif theNumber == 8:
                if self.ColorModeTabWidget.currentIndex() == 2:
                    self.computeValueANM(8)
            elif theNumber == 9:
                if self.ColorModeTabWidget.currentIndex() == 2:
                    self.computeValueANM(9)
                else:
                    if customKeys[13] == "9":
                        self.changeSliderValue(1, 1) # increment slider 1

        def changeSliderValue(self, sliderToChange, changeAmt):
            if self.ColorModeTabWidget.currentIndex() == 0: # we have 2 sliders in CCT mode
                if sliderToChange == 1:
                    self.Slider_CCT_Hue.setValue(self.Slider_CCT_Hue.value() + changeAmt)
                elif sliderToChange == 2 or sliderToChange == 0:
                    self.Slider_CCT_Bright.setValue(self.Slider_CCT_Bright.value() + changeAmt)
            elif self.ColorModeTabWidget.currentIndex() == 1: # we have 3 sliders in HSI mode
                if sliderToChange == 1:
                    self.Slider_HSI_1_H.setValue(self.Slider_HSI_1_H.value() + changeAmt)
                elif sliderToChange == 2:
                    self.Slider_HSI_2_S.setValue(self.Slider_HSI_2_S.value() + changeAmt)
                elif sliderToChange == 3 or sliderToChange == 0:
                    self.Slider_HSI_3_L.setValue(self.Slider_HSI_3_L.value() + changeAmt)
            elif self.ColorModeTabWidget.currentIndex() == 2:
                if sliderToChange == 0: # the only "slider" in SCENE mode is the brightness
                    self.Slider_ANM_Brightness.setValue(self.Slider_ANM_Brightness.value() + changeAmt)

        def checkLightTab(self, selectedLight = -1):
            if self.ColorModeTabWidget.currentIndex() == 0: # if we're on the CCT tab, do the check
                if selectedLight == -1: # if we don't have a light selected
                    self.setupCCTBounds(3200, 5600) # restore the bounds to their default of 56(00)K
                else: # set up the gradient to show the range of color temperatures available to the currently selected light
                    self.setupCCTBounds(availableLights[selectedLight][4][0], availableLights[selectedLight][4][1])

            elif self.ColorModeTabWidget.currentIndex() == 3: # if we're on the Preferences tab instead
                if selectedLight != -1: # if there is a specific selected light
                    self.setupLightPrefsTab(selectedLight) # update the Prefs tab with the information for that selected light

        def getCCTTempGradient(self, startRange, endRange):
            rangeStep = (endRange - startRange) / 4 # figure out how much in between steps of the gradient
            gradient = QLinearGradient(0, 0, 532, 31) # make a new gradient

            for i in range(5): # fill the gradient with a new set of colors
                rgbValues = convert_K_to_RGB(startRange + (rangeStep * i))                
                gradient.setColorAt((0.25 * i), QColor(rgbValues[0], rgbValues[1], rgbValues[2]))
                # THIS LINE UNDERNEATH IS JUST FOR DEBUGGING THE GRADIENT GENERATOR (it shows the values from the calculations above)
                # print(str(startRange + (rangeStep * i)) + " (" + str(0.25 * i) + "): " + str(rgbValues[0]) + " / " + str(rgbValues[1]) + " / " + str(rgbValues[2]))

            return gradient # return the new gradient to switch the display out with

        def getHSIHueGradient(self, hue):
            gradient = QLinearGradient(0, 0, 532, 31) # make a new gradient

            gradient.setColorAt(0, QColor(255, 255, 255))
            newColor = convert_HSI_to_RGB(hue / 360)
            gradient.setColorAt(1, QColor(newColor[0], newColor[1], newColor[2]))

            return gradient # return the new gradient to switch the display out with

        def setupCCTBounds(self, startRange, endRange):
            self.TFV_CCT_Hue_Min.setText(str(startRange) + "K")
            self.TFV_CCT_Hue_Max.setText(str(endRange) + "K")

            self.Slider_CCT_Hue.setMinimum(startRange / 100) # set the min value of the color temperature slider to the new min bounds
            self.Slider_CCT_Hue.setMaximum(endRange / 100) # set the max value of the color temperature slider to the new max bounds
            
            self.CCT_Temp_Gradient_BG.scene().setBackgroundBrush(self.getCCTTempGradient(startRange, endRange)) # change the gradient to fit the new boundary

        def setupLightPrefsTab(self, selectedLight):
            # SET UP THE CUSTOM NAME TEXT BOX
            if availableLights[selectedLight][2] == "":
                self.customName.setChecked(False)
                self.customNameTF.setEnabled(False)
                self.customNameTF.setText("") # set the "custom name" to nothing
            else:
                self.customName.setChecked(True)
                self.customNameTF.setEnabled(True)
                self.customNameTF.setText(availableLights[selectedLight][2]) # set the "custom name" field to the custom name of this light

            # SET UP THE MINIMUM AND MAXIMUM TEXT BOXES
            defaultRange = getLightSpecs(availableLights[selectedLight][0].name, "temp")

            if availableLights[selectedLight][4] == defaultRange:
                self.colorTempRange.setChecked(False)
                self.colorTempRange_Min_TF.setEnabled(False)
                self.colorTempRange_Max_TF.setEnabled(False)

                self.colorTempRange_Min_TF.setText(str(defaultRange[0]))
                self.colorTempRange_Max_TF.setText(str(defaultRange[1]))
            else:
                self.colorTempRange.setChecked(True)
                self.colorTempRange_Min_TF.setEnabled(True)
                self.colorTempRange_Max_TF.setEnabled(True)
                
                self.colorTempRange_Min_TF.setText(str(availableLights[selectedLight][4][0]))
                self.colorTempRange_Max_TF.setText(str(availableLights[selectedLight][4][1]))
            
            # IF THE OPTION TO SEND ONLY CCT MODE IS ENABLED, THEN ENABLE THAT CHECKBOX
            if availableLights[selectedLight][5] == True:
                self.onlyCCTModeCheck.setChecked(True)
            else:
                self.onlyCCTModeCheck.setChecked(False)

            self.checkLightPrefsEnables() # set up which fields on the panel are enabled

        def checkLightPrefsEnables(self): # enable/disable fields when clicking on checkboxes
            # allow/deny typing in the "custom name" field if the option is clicked
            if self.customName.isChecked():
                self.customNameTF.setEnabled(True)
            else:
                self.customNameTF.setEnabled(False)
                self.customNameTF.setText("")

            # allow/deny typing in the "minmum" and "maximum" fields if the option is clicked
            if self.colorTempRange.isChecked():
                self.colorTempRange_Min_TF.setEnabled(True)
                self.colorTempRange_Max_TF.setEnabled(True)
            else:
                selectedRows = self.selectedLights() # get the list of currently selected lights
                defaultSettings = getLightSpecs(availableLights[selectedRows[0]][0].name, "temp")

                self.colorTempRange_Min_TF.setText(str(defaultSettings[0]))
                self.colorTempRange_Max_TF.setText(str(defaultSettings[1]))

                self.colorTempRange_Min_TF.setEnabled(False)
                self.colorTempRange_Max_TF.setEnabled(False)
            
        def checkLightPrefs(self): # check the new settings and save the custom file
            selectedRows = self.selectedLights() # get the list of currently selected lights

            # CHECK DEFAULT SETTINGS AGAINST THE CURRENT SETTINGS
            defaultSettings = getLightSpecs(availableLights[selectedRows[0]][0].name)

            if self.colorTempRange.isChecked():
                newRange = [testValid("range_min", self.colorTempRange_Min_TF.text(), defaultSettings[1][0], 1000, 5600, True),
                            testValid("range_max", self.colorTempRange_Max_TF.text(), defaultSettings[1][1], 1000, 10000, True)]
            else:
                newRange = defaultSettings[1]

            changedPrefs = 0 # number of how many preferences have changed

            if len(selectedRows) == 1: # if we have 1 selected light - which should never be false, as we can't use Prefs with more than 1
                if self.customName.isChecked(): # if we're set to allow a custom name
                    if availableLights[selectedRows[0]][2] != self.customNameTF.text():
                        availableLights[selectedRows[0]][2] = self.customNameTF.text() # set this light's custom name to the text box
                        changedPrefs += 1 # add one to the preferences changed counter
                else: # we're not supposed to set a custom name (so delete it)
                    if availableLights[selectedRows[0]][2] != "":
                        availableLights[selectedRows[0]][2] = "" # clear the old custom name if we've turned this off
                        changedPrefs += 1 # add one to the preferences changed counter

                # IF A CUSTOM NAME IS SET UP FOR THIS LIGHT, THEN CHANGE THE TABLE TO REFLECT THAT
                if availableLights[selectedRows[0]][2] != "":
                    self.setTheTable([availableLights[selectedRows[0]][2] + " (" + availableLights[selectedRows[0]][0].name + ")" "\n  [ʀssɪ: " + str(availableLights[selectedRows[0]][0].rssi) + " dBm]",
                                    "", "", ""], selectedRows[0])
                else: # if there is no custom name, then reset the table to show that
                    self.setTheTable([availableLights[selectedRows[0]][0].name + "\n  [ʀssɪ: " + str(availableLights[selectedRows[0]][0].rssi) + " dBm]",
                                    "", "", ""], selectedRows[0])

                if self.colorTempRange.isChecked(): # if we've asked to save a custom temperature range for this light
                    if availableLights[selectedRows[0]][4] != newRange: # change the range in the available lights table if they are different
                        if defaultSettings[1] != newRange:
                            availableLights[selectedRows[0]][4][0] = newRange[0]
                            availableLights[selectedRows[0]][4][1] = newRange[1]
                            changedPrefs += 1 # add one to the preferences changed counter
                        else: # the ranges are the same as the default range, so we're not modifying those values
                            printDebugString("You asked for a custom range of color temperatures, but didn't specify a custom range, so not changing!")
                else: # if the custom temp checkbox is not clicked
                    if availableLights[selectedRows[0]][4] != defaultSettings[1]: # and the settings are not the defaults
                        availableLights[selectedRows[0]][4] = defaultSettings[1] # restore them to the defaults
                        changedPrefs += 1 # add one to the preferences changed counter

                if availableLights[selectedRows[0]][5] != self.onlyCCTModeCheck.isChecked():
                    availableLights[selectedRows[0]][5] = self.onlyCCTModeCheck.isChecked() # if the option to send BRI and HUE separately is checked, then turn that on
                    changedPrefs += 1

                if changedPrefs > 0:
                    # IF ALL THE SETTINGS ARE THE SAME AS THE DEFAULT, THEN DELETE THE PREFS FILE (IF IT EXISTS)
                    if defaultSettings[0] == self.customNameTF.text() and \
                    defaultSettings[1] == newRange and \
                    defaultSettings[2] == self.onlyCCTModeCheck.isChecked():
                        printDebugString("All the options that are currently set are the defaults for this light, so the preferences file will be deleted.")
                        saveLightPrefs(selectedRows[0], True) # delete the old prefs file
                    else:
                        saveLightPrefs(selectedRows[0]) # save the light settings to a special file
                else:                    
                    printDebugString("You don't have any new preferences to save, so we aren't saving any!")

        def setupGlobalLightPrefsTab(self, setDefault=False):
            if setDefault == False:
                self.findLightsOnStartup_check.setChecked(findLightsOnStartup)
                self.autoConnectToLights_check.setChecked(autoConnectToLights)
                self.printDebug_check.setChecked(printDebug)
                self.rememberLightsOnExit_check.setChecked(rememberLightsOnExit)
                self.rememberPresetsOnExit_check.setChecked(rememberPresetsOnExit)
                self.maxNumOfAttempts_field.setText(str(maxNumOfAttempts))
                self.acceptable_HTTP_IPs_field.setText("\n".join(acceptable_HTTP_IPs))
                self.whiteListedMACs_field.setText("\n".join(whiteListedMACs))
                self.SC_turnOffButton_field.setKeySequence(customKeys[0])
                self.SC_turnOnButton_field.setKeySequence(customKeys[1])
                self.SC_scanCommandButton_field.setKeySequence(customKeys[2])
                self.SC_tryConnectButton_field.setKeySequence(customKeys[3])
                self.SC_Tab_CCT_field.setKeySequence(customKeys[4])
                self.SC_Tab_HSI_field.setKeySequence(customKeys[5])
                self.SC_Tab_SCENE_field.setKeySequence(customKeys[6])
                self.SC_Tab_PREFS_field.setKeySequence(customKeys[7])
                self.SC_Dec_Bri_Small_field.setKeySequence(customKeys[8])
                self.SC_Inc_Bri_Small_field.setKeySequence(customKeys[9])
                self.SC_Dec_Bri_Large_field.setKeySequence(customKeys[10])
                self.SC_Inc_Bri_Large_field.setKeySequence(customKeys[11])
                self.SC_Dec_1_Small_field.setKeySequence(customKeys[12])
                self.SC_Inc_1_Small_field.setKeySequence(customKeys[13])
                self.SC_Dec_2_Small_field.setKeySequence(customKeys[14])
                self.SC_Inc_2_Small_field.setKeySequence(customKeys[15])
                self.SC_Dec_3_Small_field.setKeySequence(customKeys[16])
                self.SC_Inc_3_Small_field.setKeySequence(customKeys[17])
                self.SC_Dec_1_Large_field.setKeySequence(customKeys[18])
                self.SC_Inc_1_Large_field.setKeySequence(customKeys[19])
                self.SC_Dec_2_Large_field.setKeySequence(customKeys[20])
                self.SC_Inc_2_Large_field.setKeySequence(customKeys[21])
                self.SC_Dec_3_Large_field.setKeySequence(customKeys[22])
                self.SC_Inc_3_Large_field.setKeySequence(customKeys[23])
            else: # if you clicked the RESET button, reset all preference values to their defaults
                self.findLightsOnStartup_check.setChecked(True)
                self.autoConnectToLights_check.setChecked(True)
                self.printDebug_check.setChecked(True)
                self.rememberLightsOnExit_check.setChecked(False)
                self.rememberPresetsOnExit_check.setChecked(True)
                self.maxNumOfAttempts_field.setText("6")
                self.acceptable_HTTP_IPs_field.setText("\n".join(["127.0.0.1", "192.168.", "10."]))
                self.whiteListedMACs_field.setText("")
                self.SC_turnOffButton_field.setKeySequence("Ctrl+PgDown")
                self.SC_turnOnButton_field.setKeySequence("Ctrl+PgUp")
                self.SC_scanCommandButton_field.setKeySequence("Ctrl+Shift+S")
                self.SC_tryConnectButton_field.setKeySequence("Ctrl+Shift+C")
                self.SC_Tab_CCT_field.setKeySequence("Alt+1")
                self.SC_Tab_HSI_field.setKeySequence("Alt+2")
                self.SC_Tab_SCENE_field.setKeySequence("Alt+3")
                self.SC_Tab_PREFS_field.setKeySequence("Alt+4")
                self.SC_Dec_Bri_Small_field.setKeySequence("/")
                self.SC_Inc_Bri_Small_field.setKeySequence("*")
                self.SC_Dec_Bri_Large_field.setKeySequence("Ctrl+/")
                self.SC_Inc_Bri_Large_field.setKeySequence("Ctrl+*")
                self.SC_Dec_1_Small_field.setKeySequence("7")
                self.SC_Inc_1_Small_field.setKeySequence("9")
                self.SC_Dec_2_Small_field.setKeySequence("4")
                self.SC_Inc_2_Small_field.setKeySequence("6")
                self.SC_Dec_3_Small_field.setKeySequence("1")
                self.SC_Inc_3_Small_field.setKeySequence("3")
                self.SC_Dec_1_Large_field.setKeySequence("Ctrl+7")
                self.SC_Inc_1_Large_field.setKeySequence("Ctrl+9")
                self.SC_Dec_2_Large_field.setKeySequence("Ctrl+4")
                self.SC_Inc_2_Large_field.setKeySequence("Ctrl+6")
                self.SC_Dec_3_Large_field.setKeySequence("Ctrl+1")
                self.SC_Inc_3_Large_field.setKeySequence("Ctrl+3")

        def saveGlobalPrefs(self):
            # change these global values to the new values in Prefs
            global customKeys, autoConnectToLights, printDebug, rememberLightsOnExit, rememberPresetsOnExit, maxNumOfAttempts, acceptable_HTTP_IPs, whiteListedMACs

            finalPrefs = [] # list of final prefs to merge together at the end

            if not self.findLightsOnStartup_check.isChecked(): # this option is usually on, so only add on false
                finalPrefs.append("findLightsOnStartup=0")
            
            if not self.autoConnectToLights_check.isChecked(): # this option is usually on, so only add on false
                autoConnectToLights = False
                finalPrefs.append("autoConnectToLights=0")
            else:
                autoConnectToLights = True
            
            if not self.printDebug_check.isChecked(): # this option is usually on, so only add on false
                printDebug = False
                finalPrefs.append("printDebug=0")
            else:
                printDebug = True
            
            if self.rememberLightsOnExit_check.isChecked(): # this option is usually off, so only add on true
                rememberLightsOnExit = True
                finalPrefs.append("rememberLightsOnExit=1")
            else:
                rememberLightsOnExit = False

            if not self.rememberPresetsOnExit_check.isChecked(): # this option is usually on, so only add if false
                rememberPresetsOnExit = False
                finalPrefs.append("rememberPresetsOnExit=0")
            else:
                rememberPresetsOnExit = True
            
            if self.maxNumOfAttempts_field.text() != "6": # the default for this option is 6 attempts
                maxNumOfAttempts = int(self.maxNumOfAttempts_field.text())
                finalPrefs.append("maxNumOfAttempts=" + self.maxNumOfAttempts_field.text())
            else:
                maxNumOfAttempts = 6

            # FIGURE OUT IF THE HTTP IP ADDRESSES HAVE CHANGED
            returnedList_HTTP_IPs = self.acceptable_HTTP_IPs_field.toPlainText().split("\n")
            
            if returnedList_HTTP_IPs != ["127.0.0.1", "192.168.", "10."]: # if the list of HTTP IPs have changed
                acceptable_HTTP_IPs = returnedList_HTTP_IPs # change the global HTTP IPs available
                finalPrefs.append("acceptable_HTTP_IPs=" + ";".join(acceptable_HTTP_IPs)) # add the new ones to the preferences
            else:
                acceptable_HTTP_IPs = ["127.0.0.1", "192.168.", "10."] # if we reset the IPs, then re-reset the parameter

            # ADD WHITELISTED LIGHTS TO PREFERENCES IF THEY EXIST
            returnedList_whiteListedMACs = self.whiteListedMACs_field.toPlainText().replace(" ", "").split("\n") # remove spaces and split on newlines

            if returnedList_whiteListedMACs[0] != "": # if we have any MAC addresses specified
                whiteListedMACs = returnedList_whiteListedMACs # then set the list to the addresses specified
                finalPrefs.append("whiteListedMACs=" + ";".join(whiteListedMACs)) # add the new addresses to the preferences
            else:
                whiteListedMACs = [] # or clear the list
            
            # SET THE NEW KEYBOARD SHORTCUTS TO THE VALUES IN PREFERENCES
            customKeys[0] = self.SC_turnOffButton_field.keySequence().toString()
            customKeys[1] = self.SC_turnOnButton_field.keySequence().toString()
            customKeys[2] = self.SC_scanCommandButton_field.keySequence().toString()
            customKeys[3] = self.SC_tryConnectButton_field.keySequence().toString()
            customKeys[4] = self.SC_Tab_CCT_field.keySequence().toString()
            customKeys[5] = self.SC_Tab_HSI_field.keySequence().toString()
            customKeys[6] = self.SC_Tab_SCENE_field.keySequence().toString()
            customKeys[7] = self.SC_Tab_PREFS_field.keySequence().toString()
            customKeys[8] = self.SC_Dec_Bri_Small_field.keySequence().toString()
            customKeys[9] = self.SC_Inc_Bri_Small_field.keySequence().toString()
            customKeys[10] = self.SC_Dec_Bri_Large_field.keySequence().toString()
            customKeys[11] = self.SC_Inc_Bri_Large_field.keySequence().toString()
            customKeys[12] = self.SC_Dec_1_Small_field.keySequence().toString()
            customKeys[13] = self.SC_Inc_1_Small_field.keySequence().toString()
            customKeys[14] = self.SC_Dec_2_Small_field.keySequence().toString()
            customKeys[15] = self.SC_Inc_2_Small_field.keySequence().toString()
            customKeys[16] = self.SC_Dec_3_Small_field.keySequence().toString()
            customKeys[17] = self.SC_Inc_3_Small_field.keySequence().toString()
            customKeys[18] = self.SC_Dec_1_Large_field.keySequence().toString()
            customKeys[19] = self.SC_Inc_1_Large_field.keySequence().toString()
            customKeys[20] = self.SC_Dec_2_Large_field.keySequence().toString()
            customKeys[21] = self.SC_Inc_2_Large_field.keySequence().toString()
            customKeys[22] = self.SC_Dec_3_Large_field.keySequence().toString()
            customKeys[23] = self.SC_Inc_3_Large_field.keySequence().toString()

            self.setupShortcutKeys() # change shortcut key assignments to the new values in prefs

            if customKeys[0] != "Ctrl+PgDown": 
                finalPrefs.append("SC_turnOffButton=" + customKeys[0])
            
            if customKeys[1] != "Ctrl+PgUp":
                finalPrefs.append("SC_turnOnButton=" + customKeys[1])
            
            if customKeys[2] != "Ctrl+Shift+S":
                finalPrefs.append("SC_scanCommandButton=" + customKeys[2])
            
            if customKeys[3] != "Ctrl+Shift+C":
                finalPrefs.append("SC_tryConnectButton=" + customKeys[3])
            
            if customKeys[4] != "Alt+1":
                finalPrefs.append("SC_Tab_CCT=" + customKeys[4])
            
            if customKeys[5] != "Alt+2":
                finalPrefs.append("SC_Tab_HSI=" + customKeys[5])
            
            if customKeys[6] != "Alt+3":
                finalPrefs.append("SC_Tab_SCENE=" + customKeys[6])
            
            if customKeys[7] != "Alt+4":
                finalPrefs.append("SC_Tab_PREFS=" + customKeys[7])
            
            if customKeys[8] != "/":
                finalPrefs.append("SC_Dec_Bri_Small=" + customKeys[8])
            
            if customKeys[9] != "*":
                finalPrefs.append("SC_Inc_Bri_Small=" + customKeys[9])
            
            if customKeys[10] != "Ctrl+/":
                finalPrefs.append("SC_Dec_Bri_Large=" + customKeys[10])
            
            if customKeys[11] != "Ctrl+*":
                finalPrefs.append("SC_Inc_Bri_Large=" + customKeys[11])
            
            if customKeys[12] != "7":
                finalPrefs.append("SC_Dec_1_Small=" + customKeys[12])
            
            if customKeys[13] != "9":
                finalPrefs.append("SC_Inc_1_Small=" + customKeys[13])
            
            if customKeys[14] != "4":
                finalPrefs.append("SC_Dec_2_Small=" + customKeys[14])
            
            if customKeys[15] != "6":
                finalPrefs.append("SC_Inc_2_Small=" + customKeys[15])
            
            if customKeys[16] != "1":
                finalPrefs.append("SC_Dec_3_Small=" + customKeys[16])
            
            if customKeys[17] != "3":
                finalPrefs.append("SC_Inc_3_Small=" + customKeys[17])
            
            if customKeys[18] != "Ctrl+7":
                finalPrefs.append("SC_Dec_1_Large=" + customKeys[18])
            
            if customKeys[19] != "Ctrl+9":
                finalPrefs.append("SC_Inc_1_Large=" + customKeys[19])
            
            if customKeys[20] != "Ctrl+4":
                finalPrefs.append("SC_Dec_2_Large=" + customKeys[20])
            
            if customKeys[21] != "Ctrl+6":
                finalPrefs.append("SC_Inc_2_Large=" + customKeys[21])
            
            if customKeys[22] != "Ctrl+1":
                finalPrefs.append("SC_Dec_3_Large=" + customKeys[22])
            
            if customKeys[23] != "Ctrl+3":
                finalPrefs.append("SC_Inc_3_Large=" + customKeys[23])

            # CARRY "HIDDEN" DEBUGGING OPTIONS TO PREFERENCES FILE
            if enableTabsOnLaunch == True:
                finalPrefs.append("enableTabsOnLaunch=1")
               
            if len(finalPrefs) > 0: # if we actually have preferences to save...
                with open(globalPrefsFile, mode="w", encoding="utf-8") as prefsFileToWrite:
                    prefsFileToWrite.write(("\n").join(finalPrefs)) # then write them to the prefs file

                # PRINT THIS INFORMATION WHETHER DEBUG OUTPUT IS TURNED ON OR NOT
                print("New global preferences saved in " + globalPrefsFile + " - here is the list:")

                for a in range(len(finalPrefs)):
                    print(" > " + finalPrefs[a]) # iterate through the list of preferences and show the new value(s) you set
            else: # there are no preferences to save, so clean up the file (if it exists)
                print("There are no preferences to save (all preferences are currently set to their default values).")
                
                if os.path.exists(globalPrefsFile): # if a previous preferences file exists
                    print("Since all preferences are set to their defaults, we are deleting the NeewerLite-Python.prefs file.")
                    os.remove(globalPrefsFile) # ...delete it!

        def setupShortcutKeys(self):
            self.SC_turnOffButton.setKey(QKeySequence(customKeys[0]))
            self.SC_turnOnButton.setKey(QKeySequence(customKeys[1]))
            self.SC_scanCommandButton.setKey(QKeySequence(customKeys[2]))
            self.SC_tryConnectButton.setKey(QKeySequence(customKeys[3]))
            self.SC_Tab_CCT.setKey(QKeySequence(customKeys[4]))
            self.SC_Tab_HSI.setKey(QKeySequence(customKeys[5]))
            self.SC_Tab_SCENE.setKey(QKeySequence(customKeys[6]))
            self.SC_Tab_PREFS.setKey(QKeySequence(customKeys[7]))
            self.SC_Dec_Bri_Small.setKey(QKeySequence(customKeys[8]))
            self.SC_Inc_Bri_Small.setKey(QKeySequence(customKeys[9]))
            self.SC_Dec_Bri_Large.setKey(QKeySequence(customKeys[10]))
            self.SC_Inc_Bri_Large.setKey(QKeySequence(customKeys[11]))

            # IF THERE ARE CUSTOM KEYS SET UP FOR THE SMALL INCREMENTS, SET THEM HERE (AS THE NUMPAD KEYS WILL BE TAKEN AWAY IN THAT INSTANCE):
            if customKeys[12] != "7":
                self.SC_Dec_1_Small.setKey(QKeySequence(customKeys[12]))
            else: # if we changed back to default, clear the key assignment if there was one before
                self.SC_Dec_1_Small.setKey("")

            if customKeys[13] != "9":
                self.SC_Inc_1_Small.setKey(QKeySequence(customKeys[13]))
            else:
                self.SC_Inc_1_Small.setKey("")

            if customKeys[14] != "4":
                self.SC_Dec_2_Small.setKey(QKeySequence(customKeys[14]))
            else:
                self.SC_Dec_2_Small.setKey("")
            
            if customKeys[15] != "6":
                self.SC_Inc_2_Small.setKey(QKeySequence(customKeys[15]))
            else:
                self.SC_Inc_2_Small.setKey("")

            if customKeys[16] != "1":
                self.SC_Dec_3_Small.setKey(QKeySequence(customKeys[16]))
            else:
                self.SC_Dec_3_Small.setKey("")

            if customKeys[17] != "3":
                self.SC_Inc_3_Small.setKey(QKeySequence(customKeys[17]))
            else:
                self.SC_Inc_3_Small.setKey("")
                
            self.SC_Dec_1_Large.setKey(QKeySequence(customKeys[18]))
            self.SC_Inc_1_Large.setKey(QKeySequence(customKeys[19]))
            self.SC_Dec_2_Large.setKey(QKeySequence(customKeys[20]))
            self.SC_Inc_2_Large.setKey(QKeySequence(customKeys[21]))
            self.SC_Dec_3_Large.setKey(QKeySequence(customKeys[22]))
            self.SC_Inc_3_Large.setKey(QKeySequence(customKeys[23]))

        # CHECK TO SEE WHETHER OR NOT TO ENABLE/DISABLE THE "Connect" BUTTON OR CHANGE THE PREFS TAB
        def selectionChanged(self):
            selectedRows = self.selectedLights() # get the list of currently selected lights

            if len(selectedRows) > 0: # if we have a selection
                self.tryConnectButton.setEnabled(True) # if we have light(s) selected in the table, then enable the "Connect" button

                if len(selectedRows) == 1: # we have exactly one light selected
                    self.ColorModeTabWidget.setTabEnabled(3, True) # enable the "Preferences" tab for this light

                    # SWITCH THE TURN ON/OFF BUTTONS ON, AND CHANGE TEXT TO SINGLE BUTTON TEXT
                    self.turnOffButton.setText("Turn Light Off")
                    self.turnOffButton.setEnabled(True)
                    self.turnOnButton.setText("Turn Light On")
                    self.turnOnButton.setEnabled(True)

                    self.ColorModeTabWidget.setTabEnabled(0, True)

                    if availableLights[selectedRows[0]][5] == True: # if this light is CCT only, then disable the HSI and ANM tabs
                        self.ColorModeTabWidget.setTabEnabled(1, False) # disable the HSI mode tab
                        self.ColorModeTabWidget.setTabEnabled(2, False) # disable the ANM/SCENE tab
                    else: # we can use HSI and ANM/SCENE modes, so enable those tabs
                        self.ColorModeTabWidget.setTabEnabled(1, True) # enable the HSI mode tab
                        self.ColorModeTabWidget.setTabEnabled(2, True) # enable the ANM/SCENE tab

                    currentlySelectedRow = selectedRows[0] # get the row index of the 1 selected item
                    self.checkLightTab(currentlySelectedRow) # if we're on CCT, check to see if this light can use extended values + on Prefs, update Prefs

                    # RECALL LAST SENT SETTING FOR THIS PARTICULAR LIGHT, IF A SETTING EXISTS
                    if availableLights[currentlySelectedRow][3] != []: # if the last set parameters aren't empty
                        if availableLights[currentlySelectedRow][6] != False: # if the light is listed as being turned ON
                            sendValue = availableLights[currentlySelectedRow][3] # make the current "sendValue" the last set parameter so it doesn't re-send it on re-load

                            if sendValue[1] == 135: # the last parameter was a CCT mode change
                                self.setUpGUI(colorMode="CCT",
                                        brightness=sendValue[3],
                                        temp=sendValue[4])
                            elif sendValue[1] == 134: # the last parameter was a HSI mode change
                                self.setUpGUI(colorMode="HSI",
                                        hue=sendValue[3] + (256 * sendValue[4]),
                                        sat=sendValue[5],
                                        brightness=sendValue[6])
                            elif sendValue[1] == 136: # the last parameter was a ANM/SCENE mode change
                                self.setUpGUI(colorMode="ANM",
                                        brightness=sendValue[3],
                                        scene=sendValue[4])
                        else:
                            self.ColorModeTabWidget.setCurrentIndex(0) # switch to the CCT tab if the light is off and there ARE prior parameters
                    else:
                        self.ColorModeTabWidget.setCurrentIndex(0) # switch to the CCT tab if there are no prior parameters
                else: # we have multiple lights selected
                    # SWITCH THE TURN ON/OFF BUTTONS ON, AND CHANGE TEXT TO MULTIPLE LIGHTS TEXT
                    self.turnOffButton.setText("Turn Light(s) Off")
                    self.turnOffButton.setEnabled(True)
                    self.turnOnButton.setText("Turn Light(s) On")
                    self.turnOnButton.setEnabled(True)

                    self.ColorModeTabWidget.setTabEnabled(0, True)
                    self.ColorModeTabWidget.setTabEnabled(1, True) # enable the "HSI" mode tab
                    self.ColorModeTabWidget.setTabEnabled(2, True) # enable the "ANM/SCENE" mode tab
                    self.ColorModeTabWidget.setTabEnabled(3, False) # disable the "Preferences" tab, as we have multiple lights selected
            else: # the selection has been cleared or there are no lights to select
                currentTab = self.ColorModeTabWidget.currentIndex() # get the currently selected tab (so when we disable the tabs, we stick on the current one)
                self.tryConnectButton.setEnabled(False) # if we have no lights selected, disable the Connect button

                # SWITCH THE TURN ON/OFF BUTTONS OFF, AND CHANGE TEXT TO GENERIC TEXT
                self.turnOffButton.setText("Turn Light(s) Off")
                self.turnOffButton.setEnabled(False)
                self.turnOnButton.setText("Turn Light(s) On")
                self.turnOnButton.setEnabled(False)

                self.ColorModeTabWidget.setTabEnabled(0, False) # disable the "CCT" mode tab
                self.ColorModeTabWidget.setTabEnabled(1, False) # disable the "HSI" mode tab
                self.ColorModeTabWidget.setTabEnabled(2, False) # disable the "ANM/SCENE" mode tab
                self.ColorModeTabWidget.setTabEnabled(3, False) # disable the "Preferences" tab, as we have no lights selected

                if currentTab != 3:
                    self.ColorModeTabWidget.setCurrentIndex(currentTab) # disable the tabs, but don't switch the current one shown
                else:
                    self.ColorModeTabWidget.setCurrentIndex(0) # if we're on Prefs, then switch to the CCT tab

                self.checkLightTab() # check to see if we're on the CCT tab - if we are, then restore order

        # ADD A LIGHT TO THE TABLE VIEW
        def setTheTable(self, infoArray, rowToChange = -1):
            if rowToChange == -1:
                currentRow = self.lightTable.rowCount()
                self.lightTable.insertRow(currentRow) # if rowToChange is not specified, then we'll make a new row at the end
                self.lightTable.setItem(currentRow, 0, QTableWidgetItem())
                self.lightTable.setItem(currentRow, 1, QTableWidgetItem())
                self.lightTable.setItem(currentRow, 2, QTableWidgetItem())
                self.lightTable.setItem(currentRow, 3, QTableWidgetItem())
            else:
                currentRow = rowToChange # change data for the specified row

            # THIS SECTION BELOW LIMITS UPDATING THE TABLE **ONLY** IF THE DATA SUPPLIED IS DIFFERENT THAN IT WAS ORIGINALLY
            if infoArray[0] != "": # the name of the light
                if rowToChange == -1 or (rowToChange != -1 and infoArray[0] != self.returnTableInfo(rowToChange, 0)):
                    self.lightTable.item(currentRow, 0).setText(infoArray[0])
            if infoArray[1] != "": # the MAC address of the light
                if rowToChange == -1 or (rowToChange != -1 and infoArray[1] != self.returnTableInfo(rowToChange, 1)):
                    self.lightTable.item(currentRow, 1).setText(infoArray[1])
            if infoArray[2] != "": # the Linked status of the light
                if rowToChange == -1 or (rowToChange != -1 and infoArray[2] != self.returnTableInfo(rowToChange, 2)):
                    self.lightTable.item(currentRow, 2).setText(infoArray[2])
                    self.lightTable.item(currentRow, 2).setTextAlignment(Qt.AlignCenter) # align the light status info to be center-justified
            if infoArray[3] != "": # the current status message of the light
                if rowToChange == -1 or (rowToChange != -1 and infoArray[2] != self.returnTableInfo(rowToChange, 3)):
                    self.lightTable.item(currentRow, 3).setText(infoArray[3])

            self.lightTable.resizeRowsToContents()

        def returnTableInfo(self, row, column):
            return self.lightTable.item(row, column).text()

        # CLEAR ALL LIGHTS FROM THE TABLE VIEW
        def clearTheTable(self):
            if self.lightTable.rowCount() != 0:
                self.lightTable.clearContents()
                self.lightTable.setRowCount(0)

        def selectRows(self, rowsToSelect):
            self.lightTable.clearSelection()
            indexes = [self.lightTable.model().index(r, 0) for r in rowsToSelect]
            [self.lightTable.selectionModel().select(i, QItemSelectionModel.Select | QItemSelectionModel.Rows) for i in indexes]
            
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
            currentSelection = self.selectedLights() # get the list of currently selected lights

            if i == 0: # we clicked on the CCT tab
                if len(currentSelection) > 0: # if we have something selected
                    if len(currentSelection) == 1: # if we have just one light selected
                        # CHECK THE CURRENT SELECTED LIGHT TO SEE IF IT CAN USE EXTENDED COLOR TEMPERATURES
                        self.checkLightTab(currentSelection[0]) # set up the current light's CCT bounds

                        if availableLights[currentSelection[0]][6] != False: # if the light that's selected is off, then don't update CCT value
                            self.computeValueCCT() # calculate the current CCT value
                    else: # if we have more than one light selected
                        self.checkLightTab() # reset the bounds to the normal values (5600K)
            elif i == 1: # we clicked on the HSI tab
                if len(currentSelection) == 1: # if we have only one thing selected
                    # if the "saturation" gradient isn't drawn yet, do that here
                    if self.HSI_Sat_Gradient_BG.scene().backgroundBrush() == Qt.NoBrush:
                        self.HSI_Sat_Gradient_BG.scene().setBackgroundBrush(self.getHSIHueGradient(self.Slider_HSI_1_H.value())) # change the gradient to fit the new boundary

                    if availableLights[currentSelection[0]][6] != False: # if the light that's selected is off, then don't update HSI value
                        self.computeValueHSI() # calculate the current HSI value
            elif i == 2: # we clicked on the ANM tab
                pass # skip this, we don't want the animation automatically triggering when we go to this page - but keep it for readability
            elif i == 3: # we clicked on the PREFS tab
                if len(currentSelection) == 1: # this tab function ^^ should *ONLY* call if we have just one light selected, but just in *case*
                    self.setupLightPrefsTab(currentSelection[0])
            elif i == 4: # we clicked on the Global PREFS tab
                self.setupGlobalLightPrefsTab()

        # COMPUTE A BYTESTRING FOR THE CCT SECTION
        def computeValueCCT(self, hueOrBrightness = -1):
            global CCTSlider
            CCTSlider = hueOrBrightness # set the global CCT "current slider" to the slider you just... slid

            if CCTSlider == 1: # we dragged the color temperature slider
                self.TFV_CCT_Hue.setText(str(self.Slider_CCT_Hue.value()) + "00K")
            else: # we dragged the brightness slider
                self.TFV_CCT_Bright.setText(str(self.Slider_CCT_Bright.value()) + "%")

            calculateByteString(colorMode="CCT",\
                                temp=str(int(self.Slider_CCT_Hue.value())),\
                                brightness=str(int(self.Slider_CCT_Bright.value())))

            self.statusBar.showMessage("Current value (CCT Mode): " + updateStatus())
            self.startSend()

        # COMPUTE A BYTESTRING FOR THE HSI SECTION
        def computeValueHSI(self, slidSlider = -1):
            calculateByteString(colorMode="HSI",\
                                HSI_H=str(int(self.Slider_HSI_1_H.value())),\
                                HSI_S=str(int(self.Slider_HSI_2_S.value())),\
                                HSI_I=str(int(self.Slider_HSI_3_L.value())))

            if slidSlider == 1: # we dragged the hue slider
                self.TFV_HSI_1_H.setText(str(int(self.Slider_HSI_1_H.value())) + "º")
                self.HSI_Sat_Gradient_BG.scene().setBackgroundBrush(self.getHSIHueGradient(self.Slider_HSI_1_H.value())) # change the gradient to fit the new boundary
                # BUILD THE GRADIENT HERE
            elif slidSlider == 2: # we dragged the saturation slider
                self.TFV_HSI_2_S.setText(str(int(self.Slider_HSI_2_S.value())) + "%")
            elif slidSlider == 3: # we dragged the intensity slider
                self.TFV_HSI_3_L.setText(str(int(self.Slider_HSI_3_L.value())) + "%")
            
            self.statusBar.showMessage("Current value (HSI Mode): " + updateStatus())
            self.startSend()

        # COMPUTE A BYTESTRING FOR THE ANIM SECTION
        def computeValueANM(self, buttonPressed):
            global lastAnimButtonPressed

            if buttonPressed == 0:
                buttonPressed = lastAnimButtonPressed
                self.TFV_ANM_Brightness.setText(str(int(self.Slider_ANM_Brightness.value())) + "%")
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
            setPowerBytestring("ON")
            self.statusBar.showMessage("Turning light on")
            self.startSend()

        def turnLightOff(self):
            setPowerBytestring("OFF")
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

                for a in range(len(currentSelection)):
                    selectionList.append(currentSelection[a].row()) # add the row index of the nth selected light to the selectionList array

            return selectionList # return the row IDs that are currently selected, or an empty array ([]) otherwise

        # UPDATE THE TABLE WITH THE CURRENT INFORMATION FROM availableLights
        def updateLights(self, updateTaskbar = True):
            self.clearTheTable()

            if updateTaskbar == True: # if we're scanning for lights, then update the taskbar - if we're just sorting, then don't
                if len(availableLights) != 0: # if we found lights on the last scan
                    if self.scanCommandButton.text() == "Scan":
                        self.scanCommandButton.setText("Re-scan") # change the "Scan" button to "Re-scan"

                    if len(availableLights) == 1: # we found 1 light
                        self.statusBar.showMessage("We located 1 Neewer light on the last search")
                    elif len(availableLights) > 1: # we found more than 1 light
                        self.statusBar.showMessage("We located " + str(len(availableLights)) + " Neewer lights on the last search")
                else: # if we didn't find any (additional) lights on the last scan
                    self.statusBar.showMessage("We didn't locate any Neewer lights on the last search")

            for a in range(len(availableLights)):
                if availableLights[a][1] == "": # the light does not currently have a Bleak object connected to it
                    if availableLights[a][2] != "": # the light has a custom name, so add the custom name to the light
                        self.setTheTable([availableLights[a][2] + " (" + availableLights[a][0].name + ")" + "\n  [ʀssɪ: " + str(availableLights[a][0].rssi) + " dBm]", availableLights[a][0].address, "Waiting", "Waiting to connect..."])
                    else: # the light does not have a custom name, so just use the model # of the light
                        self.setTheTable([availableLights[a][0].name + "\n  [ʀssɪ: " + str(availableLights[a][0].rssi) + " dBm]", availableLights[a][0].address, "Waiting", "Waiting to connect..."])
                else: # the light does have a Bleak object connected to it
                    if availableLights[a][2] != "": # the light has a custom name, so add the custom name to the light
                        if availableLights[a][1].is_connected: # we have a connection to the light
                            self.setTheTable([availableLights[a][2] + " (" + availableLights[a][0].name + ")" + "\n  [ʀssɪ: " + str(availableLights[a][0].rssi) + " dBm]", availableLights[a][0].address, "LINKED", "Waiting to send..."])
                        else: # we're still trying to connect, or haven't started trying yet
                            self.setTheTable([availableLights[a][2] + " (" + availableLights[a][0].name + ")" + "\n  [ʀssɪ: " + str(availableLights[a][0].rssi) + " dBm]", availableLights[a][0].address, "Waiting", "Waiting to connect..."])
                    else: # the light does not have a custom name, so just use the model # of the light
                        if availableLights[a][1].is_connected:
                            self.setTheTable([availableLights[a][0].name + "\n  [ʀssɪ: " + str(availableLights[a][0].rssi) + " dBm]", availableLights[a][0].address, "LINKED", "Waiting to send..."])
                        else:
                            self.setTheTable([availableLights[a][0].name + "\n  [ʀssɪ: " + str(availableLights[a][0].rssi) + " dBm]", availableLights[a][0].address, "Waiting", "Waiting to connect..."])

        # THE FINAL FUNCTION TO UNLINK ALL LIGHTS WHEN QUITTING THE PROGRAM
        def closeEvent(self, event):
            global threadAction

            # WAIT UNTIL THE BACKGROUND THREAD SETS THE threadAction FLAG TO finished SO WE CAN UNLINK THE LIGHTS
            while threadAction != "finished": # wait until the background thread has a chance to terminate
                printDebugString("Waiting for the background thread to terminate...")
                threadAction = "quit" # make sure to tell the thread to quit again (if it missed it the first time)
                time.sleep(2)

            if rememberPresetsOnExit == True:
                printDebugString("You asked NeewerLite-Python to save the custom parameters on exit, so we will do that now...")
                customPresetsToWrite = [] # the list of custom presets to write to file

                # CHECK EVERY SINGLE CUSTOM PRESET AGAINST THE "DEFAULT" LIST, AND IF IT'S DIFFERENT, THEN LOG THAT ONE
                if customLightPresets[0] != defaultLightPresets[0]:
                    customPresetsToWrite.append(customPresetToString(0))
                if customLightPresets[1] != defaultLightPresets[1]:
                    customPresetsToWrite.append(customPresetToString(1))
                if customLightPresets[2] != defaultLightPresets[2]:
                    customPresetsToWrite.append(customPresetToString(2))
                if customLightPresets[3] != defaultLightPresets[3]:
                    customPresetsToWrite.append(customPresetToString(3))
                if customLightPresets[4] != defaultLightPresets[4]:
                    customPresetsToWrite.append(customPresetToString(4))
                if customLightPresets[5] != defaultLightPresets[5]:
                    customPresetsToWrite.append(customPresetToString(5))
                if customLightPresets[6] != defaultLightPresets[6]:
                    customPresetsToWrite.append(customPresetToString(6))
                if customLightPresets[7] != defaultLightPresets[7]:
                    customPresetsToWrite.append(customPresetToString(7))

                if customPresetsToWrite != []: # if there are any altered presets, then write them to the custom presets file
                    createLightPrefsFolder() # create the light_prefs folder if it doesn't exist

                    # WRITE THE PREFERENCES FILE
                    with open(customLightPresetsFile, mode="w", encoding="utf-8") as prefsFileToWrite:
                        prefsFileToWrite.write("\n".join(customPresetsToWrite))

                    printDebugString("Exported custom presets to " + customLightPresetsFile)
                else:
                    if os.path.exists(customLightPresetsFile):
                        printDebugString("There were no changed custom presets, so we're deleting the custom presets file!")
                        os.remove(customLightPresetsFile) # if there are no presets to save, then delete the custom presets file
                      
            # Keep in mind, this is broken into 2 separate "for" loops, so we save all the light params FIRST, then try to unlink from them
            if rememberLightsOnExit == True:
                printDebugString("You asked NeewerLite-Python to save the last used light parameters on exit, so we will do that now...")

                for a in range(len(availableLights)):
                    printDebugString("Saving last used parameters for light #" + str(a + 1) + " (" + str(a + 1) + " of " + str(len(availableLights)) + ")")
                    saveLightPrefs(a)

            # THE THREAD HAS TERMINATED, NOW CONTINUE...
            printDebugString("We will now attempt to unlink from the lights...")
            self.statusBar.showMessage("Quitting program - unlinking from lights...")
            QApplication.processEvents() # force the status bar to update

            asyncioEventLoop.run_until_complete(parallelAction("disconnect", [-1])) # disconnect from all lights in parallel

            printDebugString("Closing the program NOW")

        def saveCustomPresetDialog(self, numOfPreset):
            if (QApplication.keyboardModifiers() & Qt.AltModifier) == Qt.AltModifier: # if you have the ALT key held down
                customLightPresets[numOfPreset] = defaultLightPresets[numOfPreset] # then restore the default for this preset

                # And change the button display back to "PRESET GLOBAL"
                if numOfPreset == 0:
                    self.customPreset_0_Button.markCustom(0, -1)
                if numOfPreset == 1:
                    self.customPreset_1_Button.markCustom(1, -1)
                if numOfPreset == 2:
                    self.customPreset_2_Button.markCustom(2, -1)
                if numOfPreset == 3:
                    self.customPreset_3_Button.markCustom(3, -1)
                if numOfPreset == 4:
                    self.customPreset_4_Button.markCustom(4, -1)
                if numOfPreset == 5:
                    self.customPreset_5_Button.markCustom(5, -1)
                if numOfPreset == 6:
                    self.customPreset_6_Button.markCustom(6, -1)
                if numOfPreset == 7:
                    self.customPreset_7_Button.markCustom(7, -1)
            else:
                if len(availableLights) == 0: # if we don't have lights, then we can't save a preset!
                    errDlg = QMessageBox(self)
                    errDlg.setWindowTitle("Can't Save Preset!")
                    errDlg.setText("You can't save a custom preset at the moment because you don't have any lights set up yet.  To save a custom preset, connect a light to NeewerLite-Python first.")
                    errDlg.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
                    errDlg.setIcon(QMessageBox.Warning)
                    errDlg.exec_()
                else: # we have lights, we can do it!
                    selectedLights = self.selectedLights() # get the currently selected lights

                    saveDlg = QMessageBox(self)
                    saveDlg.setWindowTitle("Save a Custom Preset")
                    saveDlg.setTextFormat(Qt.TextFormat.RichText)
                    saveDlg.setText("Would you like to save a <em>Global</em> or <em>Snapshot</em> preset for preset " + str(numOfPreset + 1) + "?" + "<hr>"
                                    "A <em>Global Preset</em> saves only the currently set global parameters (mode, hue, color temperature, brightness, etc.) and applies that global preset to all the lights that are currently selected.<br><br>"
                                    "A <em>Snapshot Preset</em> saves the currently set parameters for each light individually, allowing you to recall more complex lighting setups.  You can also either set a <em>snapshot preset</em> for a series of selected lights (you have to select 1 or more lights for this option), or all the currently available lights.  If you save a <em>snapshot preset</em> of a series of selected lights, it will only apply the settings for those specific lights.")
                    saveDlg.addButton(" Global Preset ", QMessageBox.ButtonRole.YesRole)
                    saveDlg.addButton(" Snapshot Preset - All Lights ", QMessageBox.ButtonRole.YesRole)

                    selectedLightsQuestion = 0

                    if selectedLights != []:
                        saveDlg.addButton(" Snapshot Preset - Selected Lights ", QMessageBox.ButtonRole.YesRole)
                        selectedLightsQuestion = 1
                    
                    saveDlg.addButton(" Cancel ", QMessageBox.ButtonRole.RejectRole)           
                    saveDlg.setIcon(QMessageBox.Question)

                    clickedButton = saveDlg.exec_()
                    
                    if clickedButton == 0: # save a "Global" preset
                        saveCustomPreset("global", numOfPreset)
                    elif clickedButton == 1: # save a "Snapshot" preset with all lights
                        saveCustomPreset("snapshot", numOfPreset)
                    elif clickedButton == 2: # save a "Snapshot" preset with only the selected lights
                        saveCustomPreset("snapshot", numOfPreset, selectedLights)
                        
                    if clickedButton != (2 + selectedLightsQuestion): # if we didn't cancel out, then mark that button as being "custom"
                        if numOfPreset == 0:
                                self.customPreset_0_Button.markCustom(0, clickedButton)
                        if numOfPreset == 1:
                                self.customPreset_1_Button.markCustom(1, clickedButton)
                        if numOfPreset == 2:
                                self.customPreset_2_Button.markCustom(2, clickedButton)
                        if numOfPreset == 3:
                                self.customPreset_3_Button.markCustom(3, clickedButton)
                        if numOfPreset == 4:
                                self.customPreset_4_Button.markCustom(4, clickedButton)
                        if numOfPreset == 5:
                                self.customPreset_5_Button.markCustom(5, clickedButton)
                        if numOfPreset == 6:
                                self.customPreset_6_Button.markCustom(6, clickedButton)
                        if numOfPreset == 7:
                                self.customPreset_7_Button.markCustom(7, clickedButton)

        def highlightLightsForSnapshotPreset(self, numOfPreset, exited = False):
            global lastSelection

            if exited == False: # if we're entering a snapshot preset, then highlight the affected lights in green
                toolTip = customPresetInfoBuilder(numOfPreset)

                # LOAD A NEWLY GENERATED TOOLTIP FOR EVERY HOVER
                if numOfPreset == 0:
                    self.customPreset_0_Button.setToolTip(toolTip)
                elif numOfPreset == 1:
                    self.customPreset_1_Button.setToolTip(toolTip)
                elif numOfPreset == 2:
                    self.customPreset_2_Button.setToolTip(toolTip)
                elif numOfPreset == 3:
                    self.customPreset_3_Button.setToolTip(toolTip)
                elif numOfPreset == 4:
                    self.customPreset_4_Button.setToolTip(toolTip)
                elif numOfPreset == 5:
                    self.customPreset_5_Button.setToolTip(toolTip)
                elif numOfPreset == 6:
                    self.customPreset_6_Button.setToolTip(toolTip)
                elif numOfPreset == 7:
                    self.customPreset_7_Button.setToolTip(toolTip)

                lightsToHighlight = self.checkForSnapshotPreset(numOfPreset)
                
                if lightsToHighlight != []:
                    lastSelection = self.selectedLights() # store the current selection to restore it when leaving the control
                    self.lightTable.clearSelection() # clear the current selection to allow the preset to shine

                    for a in range(len(lightsToHighlight)):
                        for b in range(4):
                            self.lightTable.item(lightsToHighlight[a], b).setBackground(QColor(113, 233, 147)) # set the affected rows the same color as the snapshot button
            else: # if we're exiting a snapshot preset, then reset the color of the affected lights back to white
                lightsToHighlight = self.checkForSnapshotPreset(numOfPreset)
                
                if lightsToHighlight != []:
                    self.selectRows(lastSelection) # re-highlight the last selected lights on exit

                    for a in range(len(lightsToHighlight)):
                        for b in range(4):
                            self.lightTable.item(lightsToHighlight[a], b).setBackground(Qt.white) # clear formatting on the previously selected rows

        def checkForSnapshotPreset(self, numOfPreset):
            if customLightPresets[numOfPreset][0][0] != -1: # if the value is not -1, then we most likely have a snapshot preset
                lightsToHighlight = []
                
                for a in range(len(customLightPresets[numOfPreset])): # check each entry in the preset for matching lights
                    currentLight = returnLightIndexesFromMacAddress(customLightPresets[numOfPreset][a][0])

                    if currentLight != []: # if we have a match, add it to the list of lights to highlight
                        lightsToHighlight.append(currentLight[0])

                return lightsToHighlight
            else:
                return [] # if we don't have a snapshot preset, then just return an empty list (no lights directly affected)

        # SET UP THE GUI BASED ON COMMAND LINE ARGUMENTS
        def setUpGUI(self, **modeArgs):
            if modeArgs["colorMode"] == "CCT":
                self.ColorModeTabWidget.setCurrentIndex(0)

                self.Slider_CCT_Hue.setValue(modeArgs["temp"])
                self.Slider_CCT_Bright.setValue(modeArgs["brightness"])

                self.computeValueCCT()
            elif modeArgs["colorMode"] == "HSI":
                self.ColorModeTabWidget.setCurrentIndex(1)

                self.Slider_HSI_1_H.setValue(modeArgs["hue"])
                self.Slider_HSI_2_S.setValue(modeArgs["sat"])
                self.Slider_HSI_3_L.setValue(modeArgs["brightness"])

                self.computeValueHSI()
            elif modeArgs["colorMode"] == "ANM":
                self.ColorModeTabWidget.setCurrentIndex(2)

                self.Slider_ANM_Brightness.setValue(modeArgs["brightness"])
                self.computeValueANM(modeArgs["scene"])
except NameError:
    pass # could not load the GUI, but we have already logged an error message

def setUpAsyncio():
    global asyncioEventLoop

    try:
        asyncioEventLoop = asyncio.get_running_loop()
    except RuntimeError:
        asyncioEventLoop = asyncio.new_event_loop()

    asyncio.set_event_loop(asyncioEventLoop)

# CALCULATE THE RGB VALUE OF COLOR TEMPERATURE
def convert_K_to_RGB(Ktemp):
    # Based on this script: https://gist.github.com/petrklus/b1f427accdf7438606a6
    # from @petrklus on GitHub (his source was from http://www.tannerhelland.com/4435/convert-temperature-rgb-algorithm-code/)

    tmp_internal = Ktemp / 100.0
    
    # red 
    if tmp_internal <= 66:
        red = 255
    else:
        tmp_red = 329.698727446 * math.pow(tmp_internal - 60, -0.1332047592)

        if tmp_red < 0:
            red = 0
        elif tmp_red > 255:
            red = 255
        else:
            red = tmp_red
    
    # green
    if tmp_internal <= 66:
        tmp_green = 99.4708025861 * math.log(tmp_internal) - 161.1195681661

        if tmp_green < 0:
            green = 0
        elif tmp_green > 255:
            green = 255
        else:
            green = tmp_green
    else:
        tmp_green = 288.1221695283 * math.pow(tmp_internal - 60, -0.0755148492)

        if tmp_green < 0:
            green = 0
        elif tmp_green > 255:
            green = 255
        else:
            green = tmp_green
    
    # blue
    if tmp_internal >= 66:
        blue = 255
    elif tmp_internal <= 19:
        blue = 0
    else:
        tmp_blue = 138.5177312231 * math.log(tmp_internal - 10) - 305.0447927307
        if tmp_blue < 0:
            blue = 0
        elif tmp_blue > 255:
            blue = 255
        else:
            blue = tmp_blue
    
    return int(red), int(green), int(blue) # return the integer value for each part of the RGB values for this step

def convert_HSI_to_RGB(h, s = 1, v = 1):
    # Taken from this StackOverflow page, which is an articulation of the colorsys code to
    # convert HSV values (not HSI, but close, as I'm keeping S and V locked to 1) to RGB:
    # https://stackoverflow.com/posts/26856771/revisions

    if s == 0.0: v*=255; return (v, v, v)
    i = int(h*6.) # XXX assume int() truncates!
    f = (h*6.)-i; p,q,t = int(255*(v*(1.-s))), int(255*(v*(1.-s*f))), int(255*(v*(1.-s*(1.-f)))); v*=255; i%=6
    if i == 0: return (v, t, p)
    if i == 1: return (q, v, p)
    if i == 2: return (p, v, t)
    if i == 3: return (p, q, v)
    if i == 4: return (t, p, v)
    if i == 5: return (v, p, q)

def saveLightPrefs(lightID, deleteFile = False): # save a sidecar file with the preferences for a specific light
    createLightPrefsFolder() # create the light_prefs folder if it doesn't exist

    # GET THE CUSTOM FILENAME FOR THIS FILE, NOTED FROM THE MAC ADDRESS OF THE CURRENT LIGHT
    exportFileName = availableLights[lightID][0].address.split(":") # take the colons out of the MAC address
    exportFileName = os.path.dirname(os.path.abspath(sys.argv[0])) + os.sep + "light_prefs" + os.sep + "".join(exportFileName)

    if deleteFile == True:
        if os.path.exists(exportFileName):
            os.remove(exportFileName) # delete the old preferences file (if it exists)
    else:
        customName = availableLights[lightID][2] # the custom name for this light
        defaultSettings = getLightSpecs(availableLights[lightID][0].name)

        if defaultSettings[1] != availableLights[lightID][4]:
            customTempRange = str(availableLights[lightID][4][0]) + "," + str(availableLights[lightID][4][1]) # the color temperature range available
        else:
            customTempRange = "" # if the range is the same as the default range, then just leave this entry blank

        if defaultSettings[2] != availableLights[lightID][5]:
            onlyCCTMode = str(availableLights[lightID][5]) # whether or not the light can only use CCT mode
        else:
            onlyCCTMode = "" # if the CCT mode enable is the same as the default value, then just leave this entry blank

        exportString = customName + "|" + customTempRange + "|" + onlyCCTMode # the exported string, minus the light last set parameters

        if rememberLightsOnExit == True: # if we're supposed to remember the last settings, then add that to the Prefs file
            if len(availableLights[lightID][3]) > 0: # if we actually have a value stored for this light
                lastSettingsString = ",".join(map(str, availableLights[lightID][3])) # combine all the elements of the last set params
                exportString += "|" + lastSettingsString # add it to the exported string
            else: # if we don't have a value stored for this light (nothing has changed yet)
                exportString += "|" + "120,135,2,100,56,157" # then just give the default (CCT, 5600K, 100%) params

        # WRITE THE PREFERENCES FILE
        with open(exportFileName, mode="w", encoding="utf-8") as prefsFileToWrite:
            prefsFileToWrite.write(exportString)

        if customName != "":
            printDebugString("Exported preferences for " + customName + " [" + availableLights[lightID][0].name + "] to " + exportFileName)
        else:
            printDebugString("Exported preferences for [" + availableLights[lightID][0].name + "] to " + exportFileName)

# WORKING WITH CUSTOM PRESETS
def customPresetInfoBuilder(numOfPreset, formatForHTTP = False):
    toolTipBuilder = [] # constructor for the tooltip
    numOfLights = len(customLightPresets[numOfPreset]) # the number of lights in this specific preset

    if numOfLights == 1 and customLightPresets[numOfPreset][0][0] == -1: # we're looking at a global preset
        if formatForHTTP == False:
            toolTipBuilder.append("[GLOBAL PRESET]")
        else:
            toolTipBuilder.append("<STRONG>[GLOBAL PRESET]</STRONG>")
    else: # we're looking at a snapshot preset
        if formatForHTTP == False:
            toolTipBuilder.append("[SNAPSHOT PRESET]")
        else:
            toolTipBuilder.append("<STRONG>[SNAPSHOT PRESET]</STRONG>")

    toolTipBuilder.append("")

    for a in range(numOfLights): # write out a little description of each part of this preset
        if customLightPresets[numOfPreset][a][0] == -1:
            if formatForHTTP == False:
                toolTipBuilder.append(" FOR: ALL SELECTED LIGHTS") # this is a global preset, and it affects all *selected* lights
            else:
                toolTipBuilder.append(" FOR: ALL LIGHTS AVAILABLE") # this is a global preset, and it affects all lights
        else:
            currentLight = returnLightIndexesFromMacAddress(customLightPresets[numOfPreset][a][0]) # find the light in the current list

            if currentLight != []: # if we have a match, add it to the list of lights to highlight
                if availableLights[currentLight[0]][2] != "": # if the custom name is filled in
                    toolTipBuilder.append(" FOR: " + availableLights[currentLight[0]][2] + " [" + availableLights[currentLight[0]][0].name + "]")
                else:
                    toolTipBuilder.append(" FOR: " + availableLights[currentLight[0]][0].name)
            else:
                toolTipBuilder.append("FOR: ---LIGHT NOT AVAILABLE AT THE MOMENT---") # if the light is not found (yet), display that

            toolTipBuilder.append(" " + customLightPresets[numOfPreset][a][0] + "") # this is a snapshot preset, and this specific preset controls this light
                    
        if customLightPresets[numOfPreset][a][1][0] == 5:
            if formatForHTTP == False:
                toolTipBuilder.append(" > MODE: CCT / TEMP: " + str(customLightPresets[numOfPreset][a][1][2]) + "00K / BRIGHTNESS: " + str(customLightPresets[numOfPreset][a][1][1]) + "% < ")
            else:
                toolTipBuilder.append(" &gt; MODE: CCT / TEMP: " + str(customLightPresets[numOfPreset][a][1][2]) + "00K / BRIGHTNESS: " + str(customLightPresets[numOfPreset][a][1][1]) + "% &lt; ")
        elif customLightPresets[numOfPreset][a][1][0] == 4:
            if formatForHTTP == False:
                toolTipBuilder.append(" > MODE: HSI / H: " + str(customLightPresets[numOfPreset][a][1][2]) + "º / S: " + str(customLightPresets[numOfPreset][a][1][3]) + "% / I: " + str(customLightPresets[numOfPreset][a][1][1]) + "% < ")
            else: # if we're sending this string back for the HTTP server, then replace the degree with the HTML version
                toolTipBuilder.append(" &gt; MODE: HSI / H: " + str(customLightPresets[numOfPreset][a][1][2]) + "&#176; / S: " + str(customLightPresets[numOfPreset][a][1][3]) + "% / I: " + str(customLightPresets[numOfPreset][a][1][1]) + "% &lt; ")
        elif customLightPresets[numOfPreset][a][1][0] == 6:
            if formatForHTTP == False:
                toolTipBuilder.append(" > MODE: SCENE / ANIMATION: " + str(customLightPresets[numOfPreset][a][1][2]) + " / BRIGHTNESS: " + str(customLightPresets[numOfPreset][a][1][1]) + "% < ")
            else:
                toolTipBuilder.append(" &gt; MODE: SCENE / ANIMATION: " + str(customLightPresets[numOfPreset][a][1][2]) + " / BRIGHTNESS: " + str(customLightPresets[numOfPreset][a][1][1]) + "% &lt; ")
        else: # if we're set to turn the light off, show that here
            if formatForHTTP == False:
                toolTipBuilder.append(" > TURN THIS LIGHT OFF < ")
            else:
                toolTipBuilder.append(" &gt; TURN THIS LIGHT OFF &lt; ")

        if numOfLights > 1 and a < (numOfLights - 1): # if we have any more lights, then separate each one
            if formatForHTTP == False:
                toolTipBuilder.append("----------------------------")
            else:
                toolTipBuilder.append("")
            
    if formatForHTTP == False:
        return "\n".join(toolTipBuilder)
    else:
        return "<BR>".join(toolTipBuilder)

def recallCustomPreset(numOfPreset, updateGUI=True, loop=None):
    global availableLights
    global lastSelection

    changedLights = [] # if a snapshot preset exists in this setting, log the lights that are to be changed here

    for a in range(len(customLightPresets[numOfPreset])): # check all the entries stored in this preset
        if customLightPresets[numOfPreset][0][0] == -1: # we're looking at a global preset, so set the light(s) up accordingly
            
            if updateGUI == True: # if we are in the GUI
                if mainWindow.selectedLights() == []: # and no lights are selected in the light selector
                    mainWindow.lightTable.selectAll() # select all of the lights available
                    time.sleep(0.2)
            
            if customLightPresets[numOfPreset][0][1][0] == 5: # the preset is in CCT mode
                p_colorMode = "CCT"
                p_brightness = customLightPresets[numOfPreset][0][1][1]
                p_temp = customLightPresets[numOfPreset][0][1][2]

                if updateGUI == True:
                    mainWindow.setUpGUI(colorMode=p_colorMode, brightness=p_brightness, temp=p_temp)
                else:
                    computedValue = calculateByteString(True, colorMode=p_colorMode, brightness=p_brightness, temp=p_temp)
            elif customLightPresets[numOfPreset][0][1][0] == 4: # the preset is in HSI mode
                p_colorMode = "HSI"
                # Due to the way the custom presets store information (brightness is always first),
                # this section is broken up into H, S and I portions for readability
                p_hue = customLightPresets[numOfPreset][0][1][2]
                p_sat = customLightPresets[numOfPreset][0][1][3]
                p_int = customLightPresets[numOfPreset][0][1][1]

                if updateGUI == True:
                    mainWindow.setUpGUI(colorMode=p_colorMode, hue=p_hue, sat=p_sat, brightness=p_int)
                else:
                    computedValue = calculateByteString(True, colorMode=p_colorMode, HSI_H=p_hue, HSI_S=p_sat, HSI_I=p_int)
            elif customLightPresets[numOfPreset][0][1][0] == 6: # the preset is in ANM/SCENE mode
                p_colorMode = "ANM"
                p_brightness = customLightPresets[numOfPreset][0][1][1]
                p_scene = customLightPresets[numOfPreset][0][1][2]

                if updateGUI == True:
                    mainWindow.setUpGUI(colorMode=p_colorMode, brightness=p_brightness, scene=p_scene)
                else:
                    computedValue = calculateByteString(True, colorMode=p_colorMode, brightness=p_brightness, scene=p_scene)

            if updateGUI == False:
                for b in range(len(availableLights)):
                    changedLights.append(b) # add each light to changedLights
                    availableLights[b][3] = computedValue # set each light's "last" parameter to the computed value above

        else: # we're looking at a snapshot preset, so see if any of those lights are available to change
            currentLight = returnLightIndexesFromMacAddress(customLightPresets[numOfPreset][a][0])

            if currentLight != []: # if we have a match
                # always refer to the light it found as currentLight[0]
                if customLightPresets[numOfPreset][a][1][0] == 5 or customLightPresets[numOfPreset][a][1][0] == 8: # the preset is in CCT mode
                    availableLights[currentLight[0]][3] = calculateByteString(True, colorMode="CCT",\
                                                            brightness=customLightPresets[numOfPreset][a][1][1],\
                                                            temp=customLightPresets[numOfPreset][a][1][2])

                    if customLightPresets[numOfPreset][a][1][0] == 8: # if we want to turn the light off, let the send system know this
                        availableLights[currentLight[0]][3][0] = 0
                elif customLightPresets[numOfPreset][a][1][0] == 4 or customLightPresets[numOfPreset][a][1][0] == 7: # the preset is in HSI mode
                    availableLights[currentLight[0]][3] = calculateByteString(True, colorMode="HSI",\
                                                            HSI_I=customLightPresets[numOfPreset][a][1][1],\
                                                            HSI_H=customLightPresets[numOfPreset][a][1][2],\
                                                            HSI_S=customLightPresets[numOfPreset][a][1][3])

                    if customLightPresets[numOfPreset][a][1][0] == 7: # if we want to turn the light off, let the send system know this
                        availableLights[currentLight[0]][3][0] = 0
                elif customLightPresets[numOfPreset][a][1][0] == 6 or customLightPresets[numOfPreset][a][1][0] == 9: # the preset is in ANM/SCENE mode
                    availableLights[currentLight[0]][3] = calculateByteString(True, colorMode="ANM",\
                                                            brightness=customLightPresets[numOfPreset][a][1][1],\
                                                            animation=customLightPresets[numOfPreset][a][1][2])
                    
                    if customLightPresets[numOfPreset][a][1][0] == 9: # if we want to turn the light off, let the send system know this
                        availableLights[currentLight[0]][3][0] = 0
                
                changedLights.append(currentLight[0])

    if changedLights != []:
        if updateGUI == True:
            lastSelection = [] # clear the last selection if you've clicked on a snapshot preset (which, if we're here, you did)

            mainWindow.lightTable.setFocus() # set the focus to the light table, in order to show which rows are selected
            mainWindow.selectRows(changedLights) # select those rows affected by the lights above

            global threadAction
            threadAction = "send|" + "|".join(map(str, changedLights)) # set the thread to write to all of the affected lights
        else:
            processMultipleSends(loop, "send|" + "|".join(map(str, changedLights)), updateGUI)

def saveCustomPreset(presetType, numOfPreset, selectedLights = []):
    global customLightPresets

    if presetType == "global":
        customLightPresets[numOfPreset] = [listBuilder(-1)]
    elif presetType == "snapshot":
        listConstructor = []
        
        if selectedLights == []: # add all the lights to the snapshot preset
            for a in range(len(availableLights)): 
                listConstructor.append(listBuilder(a))
        else: # add only the selected lights to the snapshot preset
            for a in range(len(selectedLights)):
                listConstructor.append(listBuilder(selectedLights[a]))

        customLightPresets[numOfPreset] = listConstructor

def listBuilder(selectedLight):
    paramsListBuilder = [] # the cut-down list of parameters to return to the main preset constructor

    if selectedLight == -1: # then we get the value from sendValue
        lightMACAddress = -1 # this is a global preset
        listToWorkWith = sendValue # we're using the last sent parameter on any light for this
    else: # we're recalling the params for a specific light
        lightMACAddress = availableLights[selectedLight][0].address # this is a snapshot preset
        listToWorkWith = availableLights[selectedLight][3] # we're specificially using the last parameter for the specified light for this

    if listToWorkWith != []: # if we have elements in this list, then sort them out
        if availableLights[selectedLight][6] == False:
            paramsListBuilder.append(listToWorkWith[1] - 127) # the first value is the mode, but -127 to simplify it (and mark it as being OFF)
        else:
            paramsListBuilder.append(listToWorkWith[1] - 130) # the first value is the mode, but -130 to simplify it (and mark it as being ON)

        if listToWorkWith[1] == 135: # we're in CCT mode
            paramsListBuilder.append(listToWorkWith[3]) # the brightness
            paramsListBuilder.append(listToWorkWith[4]) # the color temperature
        elif listToWorkWith[1] == 134: # we're in HSI mode
            paramsListBuilder.append(listToWorkWith[6]) # the brightness
            paramsListBuilder.append(listToWorkWith[3] + (256 * listToWorkWith[4])) # the hue
            paramsListBuilder.append(listToWorkWith[5]) # the saturation
        elif listToWorkWith[1] == 136: # we're in ANM/SCENE
            paramsListBuilder.append(listToWorkWith[3]) # the brightness
            paramsListBuilder.append(listToWorkWith[4]) # the scene

    return [lightMACAddress, paramsListBuilder]

def customPresetToString(numOfPreset):
    returnedString = "customPreset" + str(numOfPreset) + "=" # the string to return back to the saving mechanism
    numOfLights = len(customLightPresets[numOfPreset]) # how many lights this custom preset holds values for

    for a in range(numOfLights): # get all of the lights stored in this preset (or 1 if it's a global)
        returnedString += str(customLightPresets[numOfPreset][a][0]) # get the MAC address/UUID of the nth light
        returnedString += "|" + "|".join(map(str,customLightPresets[numOfPreset][a][1])) # get a string for the rest of this current array
      
        if numOfLights > 1 and a < (numOfLights - 1): # if there are more lights left, then add a semicolon to differentiate that
            returnedString += ";"

    return returnedString

def stringToCustomPreset(presetString, numOfPreset):   
    if presetString != "|": # if the string is a valid string, then process it
        lightsToWorkWith = presetString.split(";") # split the current string into individual lights
        presetToReturn = [] # a list containing all of the preset information

        for a in range(len(lightsToWorkWith)):
            presetList = lightsToWorkWith[a].split("|") # split the current light list into its individual items
            presetPayload = [] # the actual preset list
            
            for b in range(1, len(presetList)):
                presetPayload.append(int(presetList[b]))

            if presetList[0] == "-1":
                presetToReturn.append([-1, presetPayload]) # if the light ID is -1, keep that value as an integer
            else:
                presetToReturn.append([presetList[0], presetPayload]) # if it isn't, then the MAC address is a string, so keep it that way

        return presetToReturn
    else: # if it isn't, then just return the default parameters for this preset
        return defaultLightPresets[numOfPreset]

def loadCustomPresets():
    global customLightPresets

    # READ THE PREFERENCES FILE INTO A LIST
    with open(customLightPresetsFile, mode="r", encoding="utf-8") as fileToOpen:
        customPresets = fileToOpen.read().split("\n")

    acceptable_arguments = ["customPreset0", "customPreset1", "customPreset2", "customPreset3", \
                            "customPreset4", "customPreset5", "customPreset6", "customPreset7"]

    for a in range(len(customPresets) - 1, -1, -1):
            if not any(x in customPresets[a] for x in acceptable_arguments): # if the current argument is invalid
                customPresets.pop(a) # delete the invalid argument from the list

    # NOW THAT ANY STRAGGLERS ARE OUT, ADD DASHES TO WHAT REMAINS TO PROPERLY PARSE IN THE PARSER
    for a in range(len(customPresets)):
        customPresets[a] = "--" + customPresets[a]

    customPresetParser = argparse.ArgumentParser()

    customPresetParser.add_argument("--customPreset0", default=-1)
    customPresetParser.add_argument("--customPreset1", default=-1)
    customPresetParser.add_argument("--customPreset2", default=-1)
    customPresetParser.add_argument("--customPreset3", default=-1)
    customPresetParser.add_argument("--customPreset4", default=-1)
    customPresetParser.add_argument("--customPreset5", default=-1)
    customPresetParser.add_argument("--customPreset6", default=-1)
    customPresetParser.add_argument("--customPreset7", default=-1)

    customPresets = customPresetParser.parse_args(customPresets)

    if customPresets.customPreset0 != -1:
        customLightPresets[0] = stringToCustomPreset(customPresets.customPreset0, 0)
    if customPresets.customPreset1 != -1:
        customLightPresets[1] = stringToCustomPreset(customPresets.customPreset1, 1)
    if customPresets.customPreset2 != -1:
        customLightPresets[2] = stringToCustomPreset(customPresets.customPreset2, 2)
    if customPresets.customPreset3 != -1:
        customLightPresets[3] = stringToCustomPreset(customPresets.customPreset3, 3)
    if customPresets.customPreset4 != -1:
        customLightPresets[4] = stringToCustomPreset(customPresets.customPreset4, 4)
    if customPresets.customPreset5 != -1:
        customLightPresets[5] = stringToCustomPreset(customPresets.customPreset5, 5)
    if customPresets.customPreset6 != -1:
        customLightPresets[6] = stringToCustomPreset(customPresets.customPreset6, 6)
    if customPresets.customPreset7 != -1:
        customLightPresets[7] = stringToCustomPreset(customPresets.customPreset7, 7)
    
# RETURN THE CORRECT NAME FOR THE IDENTIFIER OF THE LIGHT (FOR DEBUG STRINGS)
def returnMACname():
    if platform.system() == "Darwin":
        return "UUID:"
    else:
        return "MAC Address:"

# TEST TO MAKE SURE THE VALUE GIVEN TO THE FUNCTION IS VALID OR IN BOUNDS
def testValid(theParam, theValue, defaultValue, startBounds, endBounds, returnDefault = False):
    if theParam == "temp":
        if len(theValue) > 1: # if the temp has at least 2 characters in it
            theValue = theValue[:2] # take the first 2 characters of the string to convert into int
        else: # it either doesn't have enough characters, or isn't a number
            printDebugString(" >> error with --temp specified (not enough digits or not a number), so falling back to default value of " + str(defaultValue))
            theValue = defaultValue # default to 56(00)K for color temperature

    try: # try converting the string into an integer and processing the bounds
        theValue = int(theValue) # the value is assumed to be within the bounds, so we check it...

        if theValue < startBounds or theValue > endBounds: # the value is not within bounds, so there's an error
            if returnDefault == False: # if the value is too high or low, but we aren't set to return the defaults, make it the lowest/highest boundary
                if theValue < startBounds: # if the value specified is below the starting boundary, make it the starting boundary
                    printDebugString(" >> --" + theParam + " (" + str(theValue) + ") isn't between the bounds of " + str(startBounds) + " and " + str(endBounds) + ", so falling back to closest boundary of " + str(startBounds))
                    theValue = startBounds
                elif theValue > endBounds: # if the value specified is above the ending boundary, make it the ending boundary
                    printDebugString(" >> --" + theParam + " (" + str(theValue) + ") isn't between the bounds of " + str(startBounds) + " and " + str(endBounds) + ", so falling back to closest boundary of " + str(endBounds))
                    theValue = endBounds
            else: # if the value is too high or low, but we're set to return the default, do that here
                printDebugString(" >> --" + theParam + " (" + str(theValue) + ") isn't between the bounds of " + str(startBounds) + " and " + str(endBounds) + ", so falling back to the default value of " + str(defaultValue))
                theValue = defaultValue

        return theValue # return the within-bounds value
    except ValueError: # if the string can not be converted, then return the defaultValue
        printDebugString(" >> --" + theParam + " specified is not a number - falling back to default value of " + str(defaultValue))
        return defaultValue # return the default value

# PRINT A DEBUG STRING TO THE CONSOLE, ALONG WITH THE CURRENT TIME
def printDebugString(theString):
    if printDebug == True:
        now = datetime.now()
        currentTime = now.strftime("%H:%M:%S")

        print("[" + currentTime + "] - " + theString)

# CALCULATE THE BYTESTRING TO SEND TO THE LIGHT
def calculateByteString(returnValue = False, **modeArgs):
    if modeArgs["colorMode"] == "CCT":
        # We're in CCT (color balance) mode
        computedValue = [120, 135, 2, 0, 0, 0]

        computedValue[3] = int(modeArgs["brightness"]) # the brightness value
        computedValue[4] = int(modeArgs["temp"]) # the color temp value, ranging from 32(00K) to 85(00)K - some lights (like the SL-80) can go as high as 8500K
        computedValue[5] = calculateChecksum(computedValue) # compute the checksum
    elif modeArgs["colorMode"] == "HSI":
        # We're in HSI (any color of the spectrum) mode
        computedValue = [120, 134, 4, 0, 0, 0, 0, 0]

        computedValue[3] = int(modeArgs["HSI_H"]) & 255 # hue value, up to 255
        computedValue[4] = (int(modeArgs["HSI_H"]) & 65280) >> 8 # offset value, computed from above value
        computedValue[5] = int(modeArgs["HSI_S"]) # saturation value
        computedValue[6] = int(modeArgs["HSI_I"]) # intensity value
        computedValue[7] = calculateChecksum(computedValue) # compute the checksum
    elif modeArgs["colorMode"] == "ANM":
        # We're in ANM (animation) mode
        computedValue = [120, 136, 2, 0, 0, 0]

        computedValue[3] = int(modeArgs["brightness"]) # brightness value
        computedValue[4] = int(modeArgs["animation"]) # the number of animation you're going to run (check comments above)
        computedValue[5] = calculateChecksum(computedValue) # compute the checksum
    else:
        computedValue = [0]

    if returnValue == False: # if we aren't supposed to return a value, then just set sendValue to the value returned from computedValue
        global sendValue
        sendValue = computedValue
    else:
        return computedValue # return the computed value

# RECALCULATE THE BYTESTRING FOR CCT-ONLY NEEWER LIGHTS INTO HUE AND BRIGHTNESS SEPARATELY
def calculateSeparateBytestrings(sendValue):
    # CALCULATE BRIGHTNESS ONLY PARAMETER FROM MAIN PARAMETER
    newValueBRI = [120, 130, 1, sendValue[3], 0]
    newValueBRI[4] = calculateChecksum(newValueBRI)

    # CALCULATE HUE ONLY PARAMETER FROM MAIN PARAMETER
    newValueHUE = [120, 131, 1, sendValue[4], 0]
    newValueHUE[4] = calculateChecksum(newValueHUE)

    if CCTSlider == -1: # return both newly computed values
        return [newValueBRI, newValueHUE]
    elif CCTSlider == 1: # return only the color temperature value
        return newValueHUE
    elif CCTSlider == 2: # return only the brightness value
        return newValueBRI
        

def setPowerBytestring(onOrOff):
    global sendValue

    if onOrOff == "ON":
        sendValue = [120, 129, 1, 1, 251] # return the "turn on" bytestring
    else:
        sendValue = [120, 129, 1, 2, 252] # return the "turn off" bytestring

# MAKE CURRENT BYTESTRING INTO A STRING OF HEX CHARACTERS TO SHOW THE CURRENT VALUE BEING GENERATED BY THE PROGRAM
def updateStatus(splitString = False, customValue=False):
        currentHexString = ""

        if customValue == False:
            customValue = sendValue

        if splitString == False: # False is for the status bar (shows the bytestring computed as one long line)
            for a in range(len(customValue)):
                currentHexString = currentHexString + " " + str(hex(customValue[a]))
        else: # True is for the table view, this view no longer shows bytestring, but readable status of current mode (temp/bri/hue, etc.)
            currentHexString = ""

            if customValue[1] == 134:
                currentHexString = "(HSI MODE):\n"
                currentHexString = currentHexString + "  H: " + str(customValue[3] + (256 * customValue[4])) + u'\N{DEGREE SIGN}' + " / S: " + str(customValue[5]) + " / I: " + str(customValue[6])
            elif customValue[1] == 135:
                currentHexString = "(CCT MODE):\n"
                currentHexString = currentHexString + "  TEMP: " + str(customValue[4]) + "00K / BRI: " + str(customValue[3])
            elif customValue[1] == 136:
                currentHexString = "(ANM/SCENE MODE):\n"
                currentHexString = currentHexString + "  SCENE: " + str(customValue[4]) + " / BRI: " + str(customValue[3])

        return currentHexString

# CALCULATE THE CHECKSUM FROM THE BYTESTRING
def calculateChecksum(sendValue):
    checkSum = 0

    for a in range(len(sendValue) - 1):
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
        if d.address in whiteListedMACs: # if the MAC address is in the list of whitelisted addresses, add this device
            printDebugString("Matching whitelisted address found - " + returnMACname() + " " + d.address + ", adding to the list")
            currentScan.append(d)
        else: # if this device is not whitelisted, check to see if it's valid (contains "NEEWER" in the name)
            if d.name != None and "NEEWER" in d.name: # if Bleak returned a proper string, and the string has "NEEWER" in the name
                currentScan.append(d) # add this light to this session's available lights            

    for a in range(len(currentScan)): # scan the newly found NEEWER devices
        newLight = True # initially mark this light as a "new light"

        # check the "new light" against the global list
        for b in range(len(availableLights)):
            if currentScan[a].address == availableLights[b][0].address: # if the new light's MAC address matches one already in the global list
                printDebugString("Light found! [" + currentScan[a].name + "] " + returnMACname() + " " + currentScan[a].address + " but it's already in the list.  It may have disconnected, so relinking might be necessary.")
                newLight = False # then don't add another instance of it

                # if we found the light *again*, it's most likely the light disconnected, so we need to link it again
                availableLights[b][0].rssi = currentScan[a].rssi # update the RSSI information
                availableLights[b][1] = "" # clear the Bleak connection (as it's changed) to force the light to need re-linking

                break # stop checking if we've found a negative result

        if newLight == True: # if this light was not found in the global list, then we need to add it
            printDebugString("Found new light! [" + currentScan[a].name + "] " + returnMACname() + " " + currentScan[a].address + " RSSI: " + str(currentScan[a].rssi) + " dBm")
            customPrefs = getCustomLightPrefs(currentScan[a].address, currentScan[a].name)

            if len(customPrefs) == 3: # we need to rename the light and set up CCT and color temp range
                availableLights.append([currentScan[a], "", customPrefs[0], [120, 135, 2, 20, 56, 157], customPrefs[1], customPrefs[2], True, ["---", "---"]]) # add it to the global list
            elif len(customPrefs) == 4: # same as above, but we have previously stored parameters, so add them in as well
                availableLights.append([currentScan[a], "", customPrefs[0], customPrefs[3], customPrefs[1], customPrefs[2], True, ["---", "---"]]) # add it to the global list

    if threadAction != "quit":
        return "" # once the device scan is over, set the threadAction to nothing
    else: # if we're requesting that we quit, then just quit
        return "quit"

def getCustomLightPrefs(MACAddress, lightName = ""):
    customPrefsPath = MACAddress.split(":")
    customPrefsPath = os.path.dirname(os.path.abspath(sys.argv[0])) + os.sep + "light_prefs" + os.sep + "".join(customPrefsPath)

    if os.path.exists(customPrefsPath):
        printDebugString("A custom preferences file was found for " + MACAddress + "!")

        # READ THE PREFERENCES FILE INTO A LIST
        with open(customPrefsPath, mode="r", encoding="utf-8") as fileToOpen:
            customPrefs = fileToOpen.read().split("|")

        if customPrefs[1] == "True": # original "wider" preference set expands color temps to 3200-8500K
            customPrefs[1] = [3200, 8500]
        elif customPrefs[1] == "False": # original "non wider" preference set color temps to 3200-5600K
            customPrefs[1] = [3200, 5600]
        elif customPrefs[1] == "": # no entry means we need to get the default value for color temps
            customPrefs[1] = getLightSpecs(lightName, "temp")
        else: # we have a new version of preferences that directly specify the color temperatures
            testPrefs = getLightSpecs(lightName, "temp")
            colorTemps = customPrefs[1].replace(" ", "").split(",")

            # TEST TO MAKE SURE VALUES RETURNED FROM colorTemps ARE VALID INTEGER VALUES
            if len(colorTemps) == 2: # we NEED to have 2 values in the list, or it's not a correct declaration (min,max)
                customPrefs[1] = [testValid("custom_preset_range_min", colorTemps[0], testPrefs[0], 1000, 5600, True),
                                  testValid("custom_preset_range_max", colorTemps[1], testPrefs[1], 1000, 10000, True)]
            else: # so if we have a different number of elements, we're wrong - revert to defaults
                printDebugString("Custom color range defined in preferences is incorrect - falling back to default values!")
                customPrefs[1] = testPrefs

        if customPrefs[2] == "True":
            customPrefs[2] = True # convert "True" as a string to an actual boolean value of True
        elif customPrefs[2] == "False":
            customPrefs[2] = False # convert "False" as a string to an actual boolean value of False
        else: # if we have no value, then get the default value for CCT enabling
            customPrefs[2] = getLightSpecs(lightName, "CCT")

        if len(customPrefs) == 4: # if we have a 4th element (the last used parameters), then load them here
            customPrefs[3] = customPrefs[3].replace(" ", "").split(",") # split the last params into a list

            for a in range(len(customPrefs[3])): # convert the string values to ints
                customPrefs[3][a] = int(customPrefs[3][a])

        return customPrefs
    else: # if there is no custom preferences file, still check the name against a list of per-light parameters
        return getLightSpecs(lightName) # get the factory default settings for this light

# RETURN THE DEFAULT FACTORY SPECIFICATIONS FOR LIGHTS
def getLightSpecs(lightName, returnParam = "all"):
    # the first section of lights here are LED only (can't use HSI), and the 2nd section are HSI-capable lights
    # listed with their name, the max and min color temps available to use in CCT mode, and HSI only (True) or not (False)
    masterNeewerLightList = [
        ["Apollo", 5600, 5600, True], ["GL1", 2900, 7000, True], ["NL140", 3200, 5600, True],
        ["SNL1320", 3200, 5600, True], ["SNL1920", 3200, 5600, True], ["SNL480", 3200, 5600, True],
        ["SNL530", 3200, 5600, True], ["SNL660", 3200, 5600, True], ["SNL960", 3200, 5600, True],
        ["SRP16", 3200, 5600, True], ["SRP18", 3200, 5600, True], ["WRP18", 3200, 5600, True],
        ["ZRP16", 3200, 5600, True],
        ["BH30S", 2500, 10000, False], ["CB60", 2500, 6500, False], ["CL124", 2500, 10000, False],
        ["RGB C80", 2500, 10000, False], ["RGB CB60", 2500, 10000, False], ["RGB1000", 2500, 10000, False],
        ["RGB1200", 2500, 10000, False], ["RGB140", 2500, 10000, False], ["RGB168", 2500, 8500, False],
        ["RGB176 A1", 2500, 10000, False], ["RGB512", 2500, 10000, False], ["RGB800", 2500, 10000, False],
        ["SL-90", 2500, 10000, False], ["RGB1", 3200, 5600, False], ["RGB176", 3200, 5600, False],
        ["RGB18", 3200, 5600, False], ["RGB190", 3200, 5600, False], ["RGB450", 3200, 5600, False],
        ["RGB480", 3200, 5600, False], ["RGB530PRO", 3200, 5600, False], ["RGB530", 3200, 5600, False],
        ["RGB650", 3200, 5600, False], ["RGB660PRO", 3200, 5600, False], ["RGB660", 3200, 5600, False],
        ["RGB960", 3200, 5600, False], ["RGB-P200", 3200, 5600, False], ["RGB-P280", 3200, 5600, False],
        ["SL70", 3200, 8500, False], ["SL80", 3200, 8500, False], ["ZK-RY", 5600, 5600, False]
    ]
    
    for a in range(len(masterNeewerLightList)): # scan the list of preset specs above to find the current light in them
        # the default list of preferences - no custom name, a color temp range from 3200-5600K, and RGB not restricted (False)
        # if we don't find the name of the light in the master list, we just return these default parameters
        customPrefs = ["", [3200, 5600], False]

        # check the master list to see if the current light is found - if it is, then change the prefs to reflect the light's spec
        if masterNeewerLightList[a][0] in lightName.replace(" ", ""):
            # customPrefs[0] = masterNeewerLightList[a][0] # the name of the light (for testing purposes)
            customPrefs[1] = [masterNeewerLightList[a][1], masterNeewerLightList[a][2]] # the HSI color temp range
            customPrefs[2] = masterNeewerLightList[a][3] # whether or not to allow RGB commands
            break # stop looking for the light!

    if returnParam == "all": # we want to return all information (the default)
        return customPrefs
    elif returnParam == "temp": # we only want to return color temp ranges for this light
        return customPrefs[1]
    elif returnParam == "CCT": # we only want to return CCT-only status for this light
        return customPrefs[2]

# CONNECT (LINK) TO A LIGHT
async def connectToLight(selectedLight, updateGUI=True):
    global availableLights
    isConnected = False # whether or not the light is connected
    returnValue = "" # the value to return to the thread (in GUI mode, a string) or True/False (in CLI mode, a boolean value)

    lightName = availableLights[selectedLight][0].name # the Name of the light (for status updates)
    lightMAC = availableLights[selectedLight][0].address # the MAC address of the light (to keep track of the light even if the index number changes)

    # FILL THE [1] ELEMENT OF THE availableLights ARRAY WITH THE BLEAK CONNECTION
    if availableLights[returnLightIndexesFromMacAddress(lightMAC)[0]][1] == "":
        availableLights[returnLightIndexesFromMacAddress(lightMAC)[0]][1] = BleakClient(availableLights[returnLightIndexesFromMacAddress(lightMAC)[0]][0])
        await asyncio.sleep(0.25) # wait just a short time before trying to connect

    # TRY TO CONNECT TO THE LIGHT SEVERAL TIMES BEFORE GIVING UP THE LINK
    currentAttempt = 1

    while isConnected == False and currentAttempt <= maxNumOfAttempts:
        if threadAction != "quit":
            try:
                if not availableLights[returnLightIndexesFromMacAddress(lightMAC)[0]][1].is_connected: # if the current device isn't linked to Bluetooth
                    printDebugString("Attempting to link to light [" + lightName + "] " + returnMACname() + " " + lightMAC + " (Attempt " + str(currentAttempt) + " of " + str(maxNumOfAttempts) + ")")
                    isConnected = await availableLights[returnLightIndexesFromMacAddress(lightMAC)[0]][1].connect() # try connecting it (and return the connection status)
                else:
                    isConnected = True # the light is already connected, so mark it as being connected
            except Exception as e:
                printDebugString("Error linking to light [" + lightName + "] " + returnMACname() + " " + lightMAC)
              
                if updateGUI == True:
                    if currentAttempt < maxNumOfAttempts:
                        mainWindow.setTheTable(["", "", "NOT\nLINKED", "There was an error connecting to the light, trying again (Attempt " + str(currentAttempt + 1) + " of " + str(maxNumOfAttempts) + ")..."], returnLightIndexesFromMacAddress(lightMAC)[0]) # there was an issue connecting this specific light to Bluetooth, so show that
                else:
                    returnValue = False # if we're in CLI mode, and there is an error connecting to the light, return False

                currentAttempt = currentAttempt + 1
                await asyncio.sleep(4) # wait a few seconds before trying to link to the light again
        else:
            return "quit"

    if threadAction == "quit":
        return "quit"
    else:
        if isConnected == True:
            printDebugString("Successful link on light [" + lightName + "] " + returnMACname() + " " + lightMAC)

            if updateGUI == True:
                mainWindow.setTheTable(["", "", "LINKED", "Waiting to send..."], returnLightIndexesFromMacAddress(lightMAC)[0]) # if it's successful, show that in the table
            else:
                returnValue = True  # if we're in CLI mode, and there is no error connecting to the light, return True
        else:
            if updateGUI == True:
                mainWindow.setTheTable(["", "", "NOT\nLINKED", "There was an error connecting to the light"], returnLightIndexesFromMacAddress(lightMAC)[0]) # there was an issue connecting this specific light to Bluetooh, so show that

            returnValue = False # the light is not connected

    return returnValue # once the connection is over, then return either True or False (for CLI) or nothing (for GUI)

async def readNotifyCharacteristic(selectedLight, diagCommand, typeOfData):
    # clear the global variable before asking the light for info
    global receivedData
    receivedData = ""

    try:
        await availableLights[selectedLight][1].start_notify(notifyLightUUID, notifyCallback) # start reading notifications from the light
    except Exception as e:
        try: # if we've resorted the list, there is a possibility of a hanging callback, so this will raise an exception
            await availableLights[selectedLight][1].stop_notify(notifyLightUUID) # so we need to try disconnecting first
            await asyncio.sleep(0.5) # wait a little bit of time before re-connecting to the callback
            await availableLights[selectedLight][1].start_notify(notifyLightUUID, notifyCallback) # try again to start reading notifications from the light
        except Exception as e: # if we truly can't connect to the callback, return a blank string
            return "" # if there is an error starting the characteristic scan, just quit out of this routine

    for a in range(maxNumOfAttempts): # attempt maxNumOfAttempts times to read the characteristics
        try:
            await availableLights[selectedLight][1].write_gatt_char(setLightUUID, bytearray(diagCommand))
        except Exception as e:
            return "" # if there is an error checking the characteristic, just quit out of this routine

        if receivedData != "": # if the recieved data is populated
            if len(receivedData) > 1: # if we have enough elements to get a status from
                if receivedData[1] == typeOfData: # if the data returned is the correct *kind* of data
                    break # stop scanning for data
            else: # if we have a list, but it doesn't have a payload in it (the light didn't supply enough data)
                receivedData = "---" # then just re-set recievedData to the default string
                break # stop scanning for data
        else:
            await asyncio.sleep(0.25) # wait a little bit of time before checking again
    try:
        await availableLights[selectedLight][1].stop_notify(notifyLightUUID) # stop reading notifications from the light
    except Exception as e:
        pass # we will return whatever data remains from the scan, so if we can't stop the scan (light disconnected), just return what we have

    return receivedData

async def getLightChannelandPower(selectedLight):
    global availableLights
    returnInfo = ["---", "---"] # the information to return to the light

    powerInfo = await readNotifyCharacteristic(selectedLight, [120, 133, 0, 253], 2)

    try:
        if powerInfo != "":
            if powerInfo[3] == 1:
                returnInfo[0] = "ON"
            elif powerInfo[3] == 2:
                returnInfo[0] = "STBY"
        
            # IF THE LIGHT IS ON, THEN ATTEMPT TO READ THE CURRENT CHANNEL
            chanInfo = await readNotifyCharacteristic(selectedLight, [120, 132, 0, 252], 1)

            if chanInfo != "": # if we got a result from the query
                try:
                    returnInfo[1] = chanInfo[3] # set the current channel to the returned result
                except IndexError:
                    pass # if we have an index error (the above value doesn't exist), then just return -1
    except IndexError:
        # if we have an IndexError (the information returned isn't blank, but also isn't enough to descipher the status)
        # then just error out, but print the information that *was* returned for debugging purposes
        printDebugString("We don't have enough information from light [" + availableLights[selectedLight][0].name + "] to get the status.")
        print(powerInfo)

    availableLights[selectedLight][7][0] = returnInfo[0]

    if availableLights[selectedLight][1] != "---" and returnInfo[1] != "---":
        availableLights[selectedLight][7][1] = returnInfo[1]

def notifyCallback(sender, data):
    global receivedData
    receivedData = data

# DISCONNECT FROM A LIGHT
async def disconnectFromLight(selectedLight, updateGUI=True):
    returnValue = "" # same as above, string for GUI mode and boolean for CLI mode, default to blank string

    if availableLights[selectedLight][1] != "": # if there is a Bleak object attached to the light, try to disconnect
        try:
            if availableLights[selectedLight][1].is_connected: # if the current light is connected
                await availableLights[selectedLight][1].disconnect() # disconnect the selected light
        except Exception as e:
            returnValue = False # if we're in CLI mode, then return False if there is an error disconnecting

            printDebugString("Error unlinking from light " + str(selectedLight + 1) + " [" + availableLights[selectedLight][0].name + "] " + returnMACname() + " " + availableLights[selectedLight][0].address)
            print(e)

        try:
            if not availableLights[selectedLight][1].is_connected: # if the current light is NOT connected, then we're good
                if updateGUI == True: # if we're using the GUI, update the display (if we're waiting)
                    mainWindow.setTheTable(["", "", "NOT\nLINKED", "Light disconnected!"], selectedLight) # show the new status in the table
                else: # if we're not, then indicate that we're good
                    returnValue = True # if we're in CLI mode, then return False if there is an error disconnecting

                printDebugString("Successfully unlinked from light " + str(selectedLight + 1) + " [" + availableLights[selectedLight][0].name + "] " + returnMACname() + " " + availableLights[selectedLight][0].address)
        except AttributeError:
            printDebugString("Light " + str(selectedLight + 1) + " has no Bleak object attached to it, so not attempting to disconnect from it")

    return returnValue

# WRITE TO A LIGHT - optional arguments for the CLI version (GUI version doesn't use either of these)
async def writeToLight(selectedLights=0, updateGUI=True, useGlobalValue=True):
    global availableLights
    returnValue = "" # same as above, return value "" for GUI, or boolean for CLI

    startTimer = time.time() # the start of the triggering
    printDebugString("Going into send mode")

    try:
        if updateGUI == True:
            if selectedLights == 0:
                selectedLights = mainWindow.selectedLights() # get the list of currently selected lights from the GUI table
        else:
            if type(selectedLights) is int: # if we specify an integer-based index
                selectedLights = [selectedLights] # convert asked-for light to list

        currentSendValue = [] # initialize the value check

        # if there are lights selected (otherwise just dump out), and the delay timer is less than it's maximum, then try to send to the lights selected
        while (len(selectedLights) > 0 and time.time() - startTimer < 0.4) :
            if currentSendValue != sendValue: # if the current value is different than what was last sent to the light, then send a new one
                currentSendValue = sendValue # get this value before sending to multiple lights, to ensure the same value is sent to each one

                for a in range(len(selectedLights)): # try to write each light in turn, and show the current data being sent to them in the table
                    # THIS SECTION IS FOR LOADING SNAPSHOT PRESET POWER STATES
                    if useGlobalValue == False: # if we're forcing the lights to use their stored parameters, then load that in here
                        if availableLights[selectedLights[a]][3][0] == 0: # we want to turn the light off
                            availableLights[selectedLights[a]][3][0] = 120 # reset the light's value to the normal value
                            currentSendValue = [120, 129, 1, 2, 252] # set the send value to turn the light off downstream
                        else: # we want to turn the light on and run a snapshot preset
                            await availableLights[int(selectedLights[a])][1].write_gatt_char(setLightUUID, bytearray([120, 129, 1, 1, 251]), False) # force this light to turn on
                            availableLights[int(selectedLights[a])][6] = True # set the ON flag of this light to True
                            await asyncio.sleep(0.05)

                            currentSendValue = availableLights[selectedLights[a]][3] # set the send value to set the preset downstream

                    if availableLights[selectedLights[a]][1] != "": # if a Bleak connection is there
                        try:
                            if availableLights[(int(selectedLights[a]))][5] == True: # if we're using the old style of light
                                if currentSendValue[1] == 135: # if we're on CCT mode
                                    if CCTSlider == -1: # and we need to write both HUE and BRI to the light
                                        splitCommands = calculateSeparateBytestrings(currentSendValue) # get both commands from the converter

                                        # WRITE BOTH LUMINANCE AND HUE VALUES TOGETHER, BUT SEPARATELY
                                        await availableLights[int(selectedLights[a])][1].write_gatt_char(setLightUUID, bytearray(splitCommands[0]), False)
                                        await asyncio.sleep(0.05) # wait 1/20th of a second to give the Bluetooth bus a little time to recover
                                        await availableLights[int(selectedLights[a])][1].write_gatt_char(setLightUUID, bytearray(splitCommands[1]), False)
                                    else: # we're only writing either HUE or BRI independently
                                        await availableLights[int(selectedLights[a])][1].write_gatt_char(setLightUUID, bytearray(calculateSeparateBytestrings(currentSendValue)), False)
                                elif currentSendValue[1] == 129: # we're using an old light, but we're either turning the light on or off
                                    await availableLights[int(selectedLights[a])][1].write_gatt_char(setLightUUID, bytearray(currentSendValue), False)
                                elif currentSendValue[1] == 134: # we can't use HSI mode with this light, so show that
                                    if updateGUI == True:
                                        mainWindow.setTheTable(["", "", "", "This light can not use HSI mode"], int(selectedLights[a]))
                                    else:
                                        returnValue = True # we successfully wrote to the light (or tried to at least)
                                elif currentSendValue[1] == 136: # we can't use ANM/SCENE mode with this light, so show that
                                    if updateGUI == True:
                                        mainWindow.setTheTable(["", "", "", "This light can not use ANM/SCENE mode"], int(selectedLights[a]))
                                    else:
                                        returnValue = True # we successfully wrote to the light (or tried to at least)
                            else: # we're using a "newer" Neewer light, so just send the original calculated value
                                await availableLights[int(selectedLights[a])][1].write_gatt_char(setLightUUID, bytearray(currentSendValue), False)

                            if updateGUI == True:
                                # if we're not looking at an old light, or if we are, we're not in either HSI or ANM modes, then update the status of that light
                                if not (availableLights[(int(selectedLights[a]))][5] == True and (currentSendValue[1] == 134 or currentSendValue[1] == 136)):
                                    if currentSendValue[1] != 129: # if we're not turning the light on or off
                                        mainWindow.setTheTable(["", "", "", updateStatus(True, currentSendValue)], int(selectedLights[a]))
                                    else: # we ARE turning the light on or off
                                        if currentSendValue[3] == 1: # we turned the light on
                                            availableLights[int(selectedLights[a])][6] = True # toggle the "light on" parameter of this light to ON

                                            changeStatus = mainWindow.returnTableInfo(selectedLights[a], 2).replace("STBY", "ON")
                                            mainWindow.setTheTable(["", "", changeStatus, "Light turned on"], int(selectedLights[a]))

                                        else: # we turned the light off
                                            availableLights[int(selectedLights[a])][6] = False # toggle the "light on" parameter of this light to OFF

                                            changeStatus = mainWindow.returnTableInfo(selectedLights[a], 2).replace("ON", "STBY")
                                            mainWindow.setTheTable(["", "", changeStatus, "Light turned off\nA long period of inactivity may require a re-link to the light"], int(selectedLights[a]))
                            else:
                                returnValue = True # we successfully wrote to the light

                            if currentSendValue[1] != 129: # if we didn't just send a command to turn the light on/off
                                availableLights[selectedLights[a]][3] = currentSendValue # store the currenly sent value to recall later
                        except Exception as e:
                            if updateGUI == True:
                                mainWindow.setTheTable(["", "", "", "Error Sending to light!"], int(selectedLights[a]))
                    else: # if there is no Bleak object associated with this light (otherwise, it's been found, but not linked)
                        if updateGUI == True:
                            mainWindow.setTheTable(["", "", "", "Light isn't linked yet, can't send to it"], int(selectedLights[a]))
                        else:
                            returnValue = 0 # the light is not linked, even though it *should* be if it gets to this point, so this is an odd error

                if useGlobalValue == True:
                    startTimer = time.time() # if we sent a value, then reset the timer
                else:
                    break # don't do the loop again (as we just want to send the commands once instead of look for newly selected lights)

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

# USE THIS FUNCTION TO CONNECT TO ONE LIGHT (for CLI mode) AND RETRIEVE ANY CUSTOM PREFS (necessary for lights like the SNL-660)
async def connectToOneLight(MACAddress):
    global availableLights

    try:
        currentLightToAdd = await BleakScanner.find_device_by_address(MACAddress)
        customLightPrefs = getCustomLightPrefs(currentLightToAdd.address, currentLightToAdd.name)
        availableLights = [[currentLightToAdd, "", customLightPrefs[0], [], customLightPrefs[1], customLightPrefs[2], True]]
    except Exception as e:
        printDebugString("Error finding the Neewer light with MAC address " + MACAddress)
        print(e)

# THE BACKGROUND WORKER THREAD
def workerThread(_loop):
    global threadAction

    # A LIST OF LIGHTS THAT DON'T SEND POWER/CHANNEL STATUS
    lightsToNotCheckPower = ["NEEWER-RGB176"]

    if findLightsOnStartup == True: # if we're set to find lights at startup, then automatically set the thread to discovery mode
        threadAction = "discover"

    delayTicks = 1 # count a few ticks before checking light information

    while True:
        if delayTicks < 12:
            delayTicks += 1
        elif delayTicks == 12:
            delayTicks = 1
            printDebugString("Background Thread Running")

            # CHECK EACH LIGHT AGAINST THE TABLE TO SEE IF THERE ARE CONNECTION ISSUES
            for a in range(len(availableLights)):
                if threadAction == "": # if we're not sending, then update the light info... (check this before scanning each light)
                    if availableLights[a][1] != "": # if there is a Bleak object, then check to see if it's connected
                        if not availableLights[a][1].is_connected: # the light is disconnected, but we're reporting it isn't
                            mainWindow.setTheTable(["", "", "NOT\nLINKED", "Light disconnected!"], a) # show the new status in the table
                            availableLights[a][1] = "" # clear the Bleak object
                        else:
                            if not availableLights[a][0].name in lightsToNotCheckPower: # if the name of the current light is not in the list to skip checking
                                _loop.run_until_complete(getLightChannelandPower(a)) # then check the power and light status of that light
                                mainWindow.setTheTable(["", "", "LINKED\n" + availableLights[a][7][0] + " / ᴄʜ. " + str(availableLights[a][7][1]), ""], a)
                            else: # if the light we're scanning doesn't supply power or channel status, then just show "LINKED"
                                mainWindow.setTheTable(["", "", "LINKED", ""], a)

        if threadAction == "quit":
            printDebugString("Stopping the background thread")
            threadAction = "finished"
            break # stop the background thread before quitting the program
        elif threadAction == "discover":
            threadAction = _loop.run_until_complete(findDevices()) # add new lights to the main array

            if threadAction != "quit":
                mainWindow.updateLights() # tell the GUI to update its list of available lights

                if autoConnectToLights == True: # if we're set to automatically link to the lights on startup, then do it here
                    #for a in range(len(availableLights)):
                    if threadAction != "quit": # if we're not supposed to quit, then try to connect to the light(s)
                        _loop.run_until_complete(parallelAction("connect", [-1])) # connect to each available light in parallel

                threadAction = ""
        elif threadAction == "connect":
            selectedLights = mainWindow.selectedLights() # get the list of currently selected lights

            if threadAction != "quit": # if we're not supposed to quit, then try to connect to the light(s)
                _loop.run_until_complete(parallelAction("connect", selectedLights)) # connect to each *selected* light in parallel

            threadAction = ""                
        elif threadAction == "send":
            threadAction = _loop.run_until_complete(writeToLight()) # write a value to the light(s) - the selectedLights() section is in the write loop itself for responsiveness
        elif threadAction != "":
            threadAction = processMultipleSends(_loop, threadAction)
        
        time.sleep(0.25)

def processMultipleSends(_loop, threadAction, updateGUI = True):
    currentThreadAction = threadAction.split("|")

    if currentThreadAction[0] == "send": # this will come from loading a custom snapshot preset
        lightsToSendTo = [] # the current lights to affect

        for a in range (1, len(currentThreadAction)): # find the lights that need to be refreshed
            lightsToSendTo.append(int(currentThreadAction[a]))

        threadAction = _loop.run_until_complete(writeToLight(lightsToSendTo, updateGUI, False)) # write the value stored in the lights to the light(s)
        return threadAction

async def parallelAction(theAction, theLights, updateGUI = True):
    # SUBMIT A SERIES OF PARALLEL ASYNCIO FUNCTIONS TO RUN ALL IN PARALLEL
    parallelFuncs = []

    if theLights[0] == -1: # if we have no specific lights set, then operate on the entire availableLights range
        theLights = [] # clear the selected light list

        for a in range(len(availableLights)):
            theLights.append(a) # add all of availableLights to the list

    for a in range(len(theLights)):
        if theAction == "connect": # connect to a series of lights
            parallelFuncs.append(connectToLight(theLights[a], updateGUI))
        elif theAction == "disconnect": # disconnect from a series of lights
            parallelFuncs.append(disconnectFromLight(theLights[a], updateGUI))
        
    await asyncio.gather(*parallelFuncs) # run the functions in parallel

def processCommands(listToProcess=[]):
    inStartupMode = False # if we're in startup mode (so report that to the log), start as False initially to be set to True below

    # SET THE CURRENT LIST TO THE sys.argv SYSTEM PARAMETERS LIST IF A LIST ISN'T SPECIFIED
    # SO WE CAN USE THIS SAME FUNCTION TO PARSE HTML ARGUMENTS USING THE HTTP SERVER AND COMMAND-LINE ARGUMENTS
    if len(listToProcess) == 0: # if there aren't any elements in the list, then check against sys.argv
        listToProcess = sys.argv[1:] # the list to parse is the system args minus the first one
        inStartupMode = True

    # ADD DASHES TO ANY PARAMETERS THAT DON'T CURRENTLY HAVE THEM AS WELL AS
    # CONVERT ALL ARGUMENTS INTO lower case (to allow ALL CAPS arguments to parse correctly)
    for a in range(len(listToProcess)):
        if listToProcess[a] != "-h" and listToProcess[a][:2] != "--": # if the dashes aren't in the current item (and it's not the -h flag)
            if listToProcess[a][:1] == "-": # if the current parameter only has one dash (typed wrongly)
                listToProcess[a] = "--" + listToProcess[a][1:].lower() # then remove that, and add the double dash and switch to lowercase
            else: # the parameter has no dashes at all, so add them
                if listToProcess[a][:11] == "custom_name": # if we're setting a custom name for the light, DON'T LOWERCASE THE RESULT
                    listToProcess[a] = "--" + listToProcess[a] # add the dashes (but don't make it lowercase)
                else:
                    listToProcess[a] = "--" + listToProcess[a].lower() # add the dashes + switch to lowercase to properly parse as arguments below                  
        else: # if the dashes are already in the current item
            listToProcess[a] = listToProcess[a].lower() # we don't need to add dashes, so just switch to lowercase

    # ARGUMENTS EACH MODE HAS ACCESS TO
    acceptable_arguments = ["--light", "--mode", "--temp", "--hue", "--sat", "--bri", "--intensity",
                            "--scene", "--animation", "--list", "--on", "--off", "--force_instance"]

    # MODE-SPECIFIC ARGUMENTS
    if inStartupMode == True: # if we're using the GUI or CLI, then add these arguments to the list
        acceptable_arguments.extend(["--http", "--cli", "--silent", "--help"])
    else: # if we're using the HTTP server, then add these arguments to the list
        acceptable_arguments.extend(["--custom_name", "--discover", "--nopage", "--link", "--use_preset", "--save_preset"])

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
    for a in range(len(listToProcess)):
        if listToProcess[a].find("--silent") != -1:
            listToProcess[a] = "--silent"
        elif listToProcess[a].find("--cli") != -1:
            listToProcess[a] = "--cli"
        elif listToProcess[a].find("--html") != -1:
            listToProcess[a] = "--html"
        elif listToProcess[a].find("--discover") != -1:
            listToProcess[a] = "--discover"
        elif listToProcess[a].find("--off") != -1:
            listToProcess[a] = "--off"
        elif listToProcess[a].find("--on") != -1:
            listToProcess[a] = "--on"
        elif listToProcess[a] == "--link":
            listToProcess[a] = "--link=-1"
        elif listToProcess[a] == "--custom_name":
            listToProcess[a] = "--custom_name=-1"
        elif listToProcess[a] == "--use_preset":
            listToProcess[a] = "--use_preset=-1"
        elif listToProcess[a] == "--save_preset":
            listToProcess[a] = "--save_preset=-1"

    # PARSE THE ARGUMENT LIST FOR CUSTOM PARAMETERS
    parser = argparse.ArgumentParser()

    parser.add_argument("--list", action="store_true", help="Scan for nearby Neewer lights and list them on the CLI") # list the currently available lights
    parser.add_argument("--http", action="store_true", help="Use an HTTP server to send commands to Neewer lights using a web browser")
    parser.add_argument("--silent", action="store_false", help="Don't show any debug information in the console")
    parser.add_argument("--cli", action="store_false", help="Don't show the GUI at all, just send command to one light and quit")
    parser.add_argument("--force_instance", action="store_false", help="Force a new instance of NeewerLite-Python if another one is already running")

    # HTML SERVER SPECIFIC PARAMETERS
    if inStartupMode == False:
        parser.add_argument("--custom_name", default=-1) # a new custom name for the light
        parser.add_argument("--discover", action="store_true") # tell the HTTP server to search for newly added lights
        parser.add_argument("--link", default=-1) # link a specific light to NeewerLite-Python
        parser.add_argument("--nopage", action="store_false") # don't render an HTML page
        parser.add_argument("--use_preset", default=-1) # number of custom preset to use via the HTTP interface
        parser.add_argument("--save_preset", default=-1) # option to save a custom snapshot preset via the HTTP interface

    parser.add_argument("--on", action="store_true", help="Turn the light on")
    parser.add_argument("--off", action="store_true", help="Turn the light off")
    parser.add_argument("--light", default="", help="The MAC Address (XX:XX:XX:XX:XX:XX) of the light you want to send a command to or ALL to find and control all lights (only valid when also using --cli switch)")
    parser.add_argument("--mode", default="CCT", help="[DEFAULT: CCT] The current control mode - options are HSI, CCT and either ANM or SCENE")
    parser.add_argument("--temp", "--temperature", default="56", help="[DEFAULT: 56(00)K] (CCT mode) - the color temperature (3200K+) to set the light to")
    parser.add_argument("--hue", default="240", help="[DEFAULT: 240] (HSI mode) - the hue (0-360 degrees) to set the light to")
    parser.add_argument("--sat", "--saturation", default="100", help="[DEFAULT: 100] (HSI mode) The saturation (how vibrant the color is) to set the light to")
    parser.add_argument("--bri", "--brightness", "--intensity", default="100", help="[DEFAULT: 100] (CCT/HSI/ANM mode) The brightness (intensity) to set the light to")
    parser.add_argument("--scene", "--animation", default="1", help="[DEFAULT: 1] (ANM or SCENE mode) The animation (1-9) to use in Scene mode")

    args = parser.parse_args(listToProcess)

    if args.force_instance == False: # if this value is True, then don't do anything
        global anotherInstance
        anotherInstance = False # change the global to False to allow new instances

    if args.silent == True:
        if inStartupMode == True:
            if args.list != True: # if we're not looking for lights using --list, then print line
                printDebugString("Starting program with command-line arguments")
        else:
            printDebugString("Processing HTTP arguments")
            args.cli = False # we're running the CLI, so don't initialize the GUI
            args.silent = printDebug # we're not changing the silent flag, pass on the current printDebug setting

    if args.http == True:
        return ["HTTP", args.silent] # special mode - don't do any other mode/color/etc. processing, just jump into running the HTML server

    if inStartupMode == False:
        # HTTP specific parameter returns!
        if args.custom_name != -1:
            return [None, args.nopage, args.custom_name, "custom_name"] # rename one of the lights with a new name (| delimited)

        if args.discover == True:
            return[None, args.nopage, None, "discover"] # discover new lights

        if args.link != -1:
            return[None, args.nopage, args.link, "link"] # return the value defined by the parameter

        if args.list == True:
            return [None, args.nopage, None, "list"]

        if args.use_preset != -1:
            return[None, args.nopage, testValid("use_preset", int(args.use_preset), 1, 1, 8), "use_preset"]
    else:
        # If we request "LIST" from the CLI, then return a CLI list of lights available
        if args.list == True:
            return["LIST", False]

    # CHECK TO SEE IF THE LIGHT SHOULD BE TURNED OFF
    if args.on == True: # we want to turn the light on
        return [args.cli, args.silent, args.light, "ON"]
    elif args.off == True: # we want to turn the light off
        return [args.cli, args.silent, args.light, "OFF"]

    # IF THE LIGHT ISN'T BEING TURNED OFF, CHECK TO SEE IF MODES ARE BEING SET
    if args.mode.lower() == "hsi":
        return [args.cli, args.silent, args.light, "HSI",
                testValid("hue", args.hue, 240, 0, 360),
                testValid("sat", args.sat, 100, 0, 100),
                testValid("bri", args.bri, 100, 0, 100)]
    elif args.mode.lower() in ("anm", "scene"):
        return [args.cli, args.silent, args.light, "ANM",
                testValid("scene", args.scene, 1, 1, 9),
                testValid("bri", args.bri, 100, 0, 100)]
    else: # we've either asked for CCT mode, or gave an invalid mode name
        if args.mode.lower() != "cct": # if we're not actually asking for CCT mode, display error message
            printDebugString(" >> Improper mode selected with --mode command - valid entries are")
            printDebugString(" >> CCT, HSI or either ANM or SCENE, so rolling back to CCT mode.")

        # RETURN CCT MODE PARAMETERS IN CCT/ALL OTHER CASES
        return [args.cli, args.silent, args.light, "CCT",
                testValid("temp", args.temp, 56, 32, 85),
                testValid("bri", args.bri, 100, 0, 100)]

def processHTMLCommands(paramsList, loop):
    global threadAction

    if threadAction == "": # if we're not already processing info in another thread
        threadAction = "HTTP"

        if len(paramsList) != 0:
            if paramsList[3] == "discover": # we asked to discover new lights
                asyncioEventLoop.run_until_complete(findDevices()) # find the lights available to control

                # try to connect to each light
                if autoConnectToLights == True:
                    asyncioEventLoop.run_until_complete(parallelAction("connect", [-1], False)) # try to connect to *all* lights in parallel
            elif paramsList[3] == "link": # we asked to connect to a specific light
                selectedLights = returnLightIndexesFromMacAddress(paramsList[2])

                if len(selectedLights) > 0:
                    asyncioEventLoop.run_until_complete(parallelAction("connect", selectedLights, False)) # try to connect to all *selected* lights in parallel
            elif paramsList[3] == "use_preset":
                recallCustomPreset(paramsList[2] - 1, False, loop)
            elif paramsList[3] == "save_preset":
                pass
            elif paramsList[3] == "custom_name":
                if paramsList[2] != "-1": # if we haven't returned a negative value, process it
                    nameInfo = paramsList[2].split("|") # split the command into 2 parts
                
                    if len(nameInfo) > 1: # if we have more than 1 parameter (correct), process it
                        nameInfo[0] = int(nameInfo[0]) # make sure the first element is an integer
                        nameInfo[1] = urllib.parse.unquote(nameInfo[1]) # decode URL string for new light name
                        
                        availableLights[nameInfo[0]][2] = nameInfo[1] # change the custom name in the list
                        saveLightPrefs(nameInfo[0]) # save the new custom name to the prefs file

            else: # we want to write a value to a specific light
                if paramsList[3] == "CCT": # calculate CCT bytestring
                    calculateByteString(colorMode=paramsList[3], temp=paramsList[4], brightness=paramsList[5])
                elif paramsList[3] == "HSI": # calculate HSI bytestring
                    calculateByteString(colorMode=paramsList[3], HSI_H=paramsList[4], HSI_S=paramsList[5], HSI_I=paramsList[6])
                elif paramsList[3] == "ANM": # calculate ANM/SCENE bytestring
                    calculateByteString(colorMode=paramsList[3], animation=paramsList[4], brightness=paramsList[5])
                elif paramsList[3] == "ON": # turn the light(s) on
                    setPowerBytestring("ON")
                elif paramsList[3] == "OFF": # turn the light(s) off
                    setPowerBytestring("OFF")

                selectedLights = returnLightIndexesFromMacAddress(paramsList[2])

                if len(selectedLights) > 0:
                    asyncioEventLoop.run_until_complete(writeToLight(selectedLights, False))

            threadAction = "" # clear the thread variable
    else:
        printDebugString("The HTTP Server requested an action, but we're already working on one.  Please wait...")

def returnLightIndexesFromMacAddress(addresses):
    foundIndexes = [] # the list of indexes for the lights you specified

    if addresses == "*": # if we ask for every light available, then return that
        for a in range(len(availableLights)):
            foundIndexes.append(a)
    else: # break down what we're asking for into indexes
        addressesToCheck = addresses.split(";")

        for a in range(len(addressesToCheck)):
            try: # if the specified light is just an index, then return the light you asked for
                currentLight = int(addressesToCheck[a]) - 1 # check to see if the current light can be converted to an integer

                # if the above succeeds, make sure that the index returned is a valid light index
                if currentLight < 0 or currentLight > len(availableLights):
                    currentLight = -1 # if the index is less than 0, or higher than the last available light, then... nada
            except ValueError: # we're most likely asking for a MAC address instead of an integer index
                currentLight = -1

                for b in range(len(availableLights)):
                    if addressesToCheck[a].upper() == availableLights[b][0].address.upper(): # if the MAC address specified matches the current light
                        currentLight = b
                        break

            if currentLight != -1: # the found light index is valid
                foundIndexes.append(currentLight) # add the found index to the list of indexes

    return foundIndexes

class NLPythonServer(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/favicon.ico": # if favicon.ico is specified, then send a 404 error and stop processing
            try:
                self.send_error(404)
            except ConnectionAbortedError:
                printDebugString("Could not serve the error page, the HTTP server is already busy with another request.")

            return
        else:
            # CHECK THE LENGTH OF THE URL REQUEST AND SEE IF IT'S TOO LONG
            if len(self.path) > 159: # INCREASED LENGTH DUE TO ADDITION OF doAction IN THE URL
                # THE LAST REQUEST WAS WAY TOO LONG, SO QUICKLY RENDER AN ERROR PAGE AND RETURN FROM THE HTTP RENDERER
                writeHTMLSections(self, "httpheaders")
                writeHTMLSections(self, "htmlheaders")
                writeHTMLSections(self, "quicklinks")
                writeHTMLSections(self, "errorHelp", "The last request you provided was too long!  The NeewerLite-Python HTTP server can only accept URL commands less than 132 characters long after /NeewerLite-Python/doAction?")
                writeHTMLSections(self, "quicklinks")
                writeHTMLSections(self, "htmlendheaders")

                return

            # CHECK TO SEE IF THE IP REQUESTING ACCESS IS IN THE LIST OF "acceptable_HTTP_IPs"
            clientIP = self.client_address[0] # the IP address of the machine making the request
            acceptedIP = False

            for check in range(len(acceptable_HTTP_IPs)): # check all the "accepted" IP addresses against the current requesting IP
                if acceptedIP != True: # if we haven't found the IP in the accepted list, then keep checking
                    if acceptable_HTTP_IPs[check] in clientIP:
                        acceptedIP = True # if we're good to go, then we can just move on

            # IF THE IP MAKING THE REQUEST IS NOT IN THE LIST OF APPROVED ADDRESSES, THEN RETURN A "FORBIDDEN" ERROR
            if acceptedIP == False:
                self.send_error(403, "The IP of the device you're making the request from (" + clientIP + ") has to be in the list of accepted IP addresses in order to use the NeewerLite-Python HTTP Server, any outside addresses will generate this Forbidden error.  To use this device with NeewerLite-Python, add its IP address (or range of IP addresses) to the list of acceptable IPs")
                return

            acceptableURL = "/NeewerLite-Python/doAction?"

            if not acceptableURL in self.path: # if we ask for something that's not the main directory, then redirect to the main error page
                self.send_response(302)
                self.send_header('Location', acceptableURL)
                self.end_headers()

                return
            else: # if the URL contains "/NeewerLite-Python/doAction?" then it's a valid URL
                writeHTMLSections(self, "httpheaders")

                # BREAK THE URL INTO USABLE PARAMTERS
                paramsList = self.path.replace(acceptableURL, "").split("&") # split the included params into a list
                paramsList = processCommands(paramsList) # process the commands returned from the HTTP parameters

                if len(paramsList) == 0: # we have no valid parameters, so show the error page
                    writeHTMLSections(self, "htmlheaders")
                    writeHTMLSections(self, "quicklinks")
                    writeHTMLSections(self, "errorHelp", "You didn't provide any valid parameters in the last URL.  To send multiple parameters to NeewerLite-Python, separate each one with a & character.")
                    writeHTMLSections(self, "quicklinks")
                    writeHTMLSections(self, "htmlendheaders")
                    return
                else:
                    if paramsList[1] == True:
                        writeHTMLSections(self, "htmlheaders") # write the HTML header section
                        writeHTMLSections(self, "quicklinks")

                        self.wfile.write(bytes("<H1>Request Successful!</H1>\n", "utf-8"))
                        self.wfile.write(bytes("Last Request: <EM>" + self.path + "</EM><BR>\n", "utf-8"))
                        self.wfile.write(bytes("From IP: <EM>" + clientIP + "</EM><BR><BR>\n", "utf-8"))

                    if paramsList[3] != "list":
                        if paramsList[1] == True:
                            self.wfile.write(bytes("Provided Parameters:<BR>\n", "utf-8"))

                            if len(paramsList) <= 2:
                                for a in range(len(paramsList)):
                                    self.wfile.write(bytes("&nbsp;&nbsp;" + str(paramsList[a]) + "<BR>\n", "utf-8"))
                            else:
                                if paramsList[3] == "use_preset":
                                    self.wfile.write(bytes("&nbsp;&nbsp;Preset to Use: " + str(paramsList[2]) + "<BR>\n", "utf-8"))
                                elif paramsList[3] == "save_preset":
                                    pass # TODO: implement saving presets!
                                else:
                                    self.wfile.write(bytes("&nbsp;&nbsp;Parameters: " + str(paramsList[2]) + "<BR>\n", "utf-8"))

                                self.wfile.write(bytes("&nbsp;&nbsp;Mode: " + str(paramsList[3]) + "<BR>\n", "utf-8"))

                                if paramsList[3] == "CCT":
                                    self.wfile.write(bytes("&nbsp;&nbsp;Color Temperature: " + str(paramsList[4]) + "00K<BR>\n", "utf-8"))
                                    self.wfile.write(bytes("&nbsp;&nbsp;Brightness: " + str(paramsList[5]) + "<BR>\n", "utf-8"))
                                elif paramsList[3] == "HSI":
                                    self.wfile.write(bytes("&nbsp;&nbsp;Hue: " + str(paramsList[4]) + "<BR>\n", "utf-8"))
                                    self.wfile.write(bytes("&nbsp;&nbsp;Saturation: " + str(paramsList[5]) + "<BR>\n", "utf-8"))
                                    self.wfile.write(bytes("&nbsp;&nbsp;Brightness: " + str(paramsList[6]) + "<BR>\n", "utf-8"))
                                elif paramsList[3] == "ANM" or paramsList[3] == "SCENE":
                                    self.wfile.write(bytes("&nbsp;&nbsp;Animation Scene: " + str(paramsList[4]) + "<BR>\n", "utf-8"))
                                    self.wfile.write(bytes("&nbsp;&nbsp;Brightness: " + str(paramsList[5]) + "<BR>\n", "utf-8"))
                            
                            self.wfile.write(bytes("<BR><HR><BR>\n", "utf-8"))

                        # PROCESS THE HTML COMMANDS IN ANOTHER THREAD
                        htmlProcessThread = threading.Thread(target=processHTMLCommands, args=(paramsList, asyncioEventLoop), name="htmlProcessThread")
                        htmlProcessThread.start()

                    if paramsList[1] == True: # if we've been asked to list the currently available lights, do that now
                        totalLights = len(availableLights)

                        if totalLights == 0: # there are no lights available to you at the moment!
                            self.wfile.write(bytes("NeewerLite-Python is not currently set up with any Neewer lights.  To discover new lights, <A HREF='doAction?discover'>click here</a>.<BR>\n", "utf-8"))
                        else:
                            # JAVASCRIPT CODE TO CHANGE LIGHT NAMES
                            self.wfile.write(bytes("\n<!-- JAVASCRIPT CODE TO CHANGE LIGHT NAMES -->\n", "utf-8"))
                            self.wfile.write(bytes("<script>\n", "utf-8"))
                            self.wfile.write(bytes("  function editLight(lightNum, lightType, previousName) {\n", "utf-8"))
                            self.wfile.write(bytes("     let newName = prompt('What do you want to call light ' + (lightNum+1) + ' (' + lightType + ')?', previousName);\n\n", "utf-8"))
                            self.wfile.write(bytes("     if (!(newName == null || newName == '' || newName == previousName)) {\n", "utf-8"))
                            self.wfile.write(bytes("          window.location.href = 'doAction?custom_name=' + lightNum + '|' + newName + '';\n", "utf-8"))
                            self.wfile.write(bytes("     }\n", "utf-8"))
                            self.wfile.write(bytes("  }\n", "utf-8"))
                            self.wfile.write(bytes("</script>\n\n", "utf-8"))

                            self.wfile.write(bytes("List of available Neewer lights:<BR><BR>\n", "utf-8"))
                            self.wfile.write(bytes("<TABLE WIDTH='98%' BORDER='1'>\n", "utf-8"))
                            self.wfile.write(bytes("  <TR>\n", "utf-8"))
                            self.wfile.write(bytes("     <TH STYLE='width:2%; text-align:left'>ID #\n", "utf-8"))
                            self.wfile.write(bytes("     <TH STYLE='width:18%; text-align:left'>Custom Name</TH>\n", "utf-8"))
                            self.wfile.write(bytes("     <TH STYLE='width:18%; text-align:left'>Light Type</TH>\n", "utf-8"))
                            self.wfile.write(bytes("     <TH STYLE='width:30%; text-align:left'>MAC Address/GUID</TH>\n", "utf-8"))
                            self.wfile.write(bytes("     <TH STYLE='width:5%; text-align:left'>RSSI</TH>\n", "utf-8"))
                            self.wfile.write(bytes("     <TH STYLE='width:5%; text-align:left'>Linked</TH>\n", "utf-8"))
                            self.wfile.write(bytes("     <TH STYLE='width:22%; text-align:left'>Last Sent Value</TH>\n", "utf-8"))
                            self.wfile.write(bytes("  </TR>\n", "utf-8"))

                            for a in range(totalLights):
                                self.wfile.write(bytes("  <TR>\n", "utf-8"))
                                self.wfile.write(bytes("     <TD STYLE='background-color:rgb(173,255,47)'>" + str(a + 1) + "</TD>\n", "utf-8")) # light ID #
                                self.wfile.write(bytes("     <TD STYLE='background-color:rgb(240,248,255)'><button onclick='editLight(" + str(a) + ", \"" + availableLights[a][0].name + "\", \"" + availableLights[a][2] + "\")'>Edit</button>&nbsp;&nbsp;" + availableLights[a][2] + "</TD>\n", "utf-8")) # light custom name
                                self.wfile.write(bytes("     <TD STYLE='background-color:rgb(240,248,255)'>" + availableLights[a][0].name + "</TD>\n", "utf-8")) # light type
                                self.wfile.write(bytes("     <TD STYLE='background-color:rgb(240,248,255)'>" + availableLights[a][0].address + "</TD>\n", "utf-8")) # light MAC address
                                self.wfile.write(bytes("     <TD STYLE='background-color:rgb(240,248,255)'>" + str(availableLights[a][0].rssi) + " dbM</TD>\n", "utf-8")) # light RSSI (signal quality)

                                try:
                                    if availableLights[a][1].is_connected:
                                        self.wfile.write(bytes("     <TD STYLE='background-color:rgb(240,248,255)'>" + "Yes" + "</TD>\n", "utf-8")) # is the light linked?
                                    else:
                                        self.wfile.write(bytes("     <TD STYLE='background-color:rgb(240,248,255)'>" + "<A HREF='doAction?link=" + str(a + 1) + "'>No</A></TD>\n", "utf-8")) # is the light linked?
                                except Exception as e:
                                    self.wfile.write(bytes("     <TD STYLE='background-color:rgb(240,248,255)'>" + "<A HREF='doAction?link=" + str(a + 1) + "'>No</A></TD>\n", "utf-8")) # is the light linked?

                                self.wfile.write(bytes("     <TD STYLE='background-color:rgb(240,248,255)'>" + updateStatus(False, availableLights[a][3]) + "</TD>\n", "utf-8")) # the last sent value to the light
                                self.wfile.write(bytes("  </TR>\n", "utf-8"))

                            self.wfile.write(bytes("</TABLE>\n", "utf-8"))

                        self.wfile.write(bytes("<BR><HR><BR>\n", "utf-8"))
                        self.wfile.write(bytes("<A ID='presets'>List of available custom presets to use:</A><BR><BR>\n", "utf-8"))
                        self.wfile.write(bytes("<TABLE WIDTH='98%' BORDER='1'>\n", "utf-8"))
                        self.wfile.write(bytes("  <TR>\n", "utf-8"))
                        self.wfile.write(bytes("     <TH STYLE='width:4%; text-align:left'>Preset\n", "utf-8"))
                        self.wfile.write(bytes("     <TH STYLE='width:46%; text-align:left'>Preset Parameters</TH>\n", "utf-8"))
                        self.wfile.write(bytes("     <TH STYLE='width:4%; text-align:left'>Preset\n", "utf-8"))
                        self.wfile.write(bytes("     <TH STYLE='width:46%; text-align:left'>Preset Parameters</TH>\n", "utf-8"))
                        self.wfile.write(bytes("  </TR>\n", "utf-8"))
                        
                        for a in range(4): # build the list itself, showing 2 presets next to each other
                            currentPreset = (2 * a)
                            self.wfile.write(bytes("  <TR>\n", "utf-8"))
                            self.wfile.write(bytes("     <TD ALIGN='CENTER' STYLE='background-color:rgb(173,255,47)'><FONT SIZE='+2'><A HREF='doAction?use_preset=" + str(currentPreset + 1) + "#presets'>" + str(currentPreset + 1) + "</A></FONT></TD>\n", "utf-8"))
                            self.wfile.write(bytes("     <TD VALIGN='TOP' STYLE='background-color:rgb(240,248,255)'>" + customPresetInfoBuilder(currentPreset, True) + "</TD>\n", "utf-8"))
                            self.wfile.write(bytes("     <TD ALIGN='CENTER' STYLE='background-color:rgb(173,255,47)'><FONT SIZE='+2'><A HREF='doAction?use_preset=" + str(currentPreset + 2) + "#presets'>" + str(currentPreset + 2) + "</A></FONT></TD>\n", "utf-8"))
                            self.wfile.write(bytes("     <TD VALIGN='TOP' STYLE='background-color:rgb(240,248,255)'>" + customPresetInfoBuilder(currentPreset + 1, True) + "</TD>\n", "utf-8"))
                            self.wfile.write(bytes("  </TR>\n", "utf-8"))
                        
                        self.wfile.write(bytes("</TABLE>\n", "utf-8"))
            
            if paramsList[1] == True:
                writeHTMLSections(self, "quicklinks") # add the footer to the bottom of the page
                writeHTMLSections(self, "htmlendheaders") # add the ending section to the very bottom

def writeHTMLSections(self, theSection, errorMsg = ""):
    if theSection == "httpheaders":
        self.send_response(200)
        self._send_cors_headers()
        self.send_header("Content-type", "text/html")
        self.end_headers()
    elif theSection == "htmlheaders":
        self.wfile.write(bytes("<!DOCTYPE html>\n", "utf-8"))
        self.wfile.write(bytes("<HTML>\n<HEAD>\n", "utf-8"))
        self.wfile.write(bytes("<META HTTP-EQUIV='Content-Type' CONTENT='text/html;charset=UTF-8'>\n", "utf-8"))
        self.wfile.write(bytes("<TITLE>NeewerLite-Python 0.12 HTTP Server by Zach Glenwright</TITLE>\n</HEAD>\n", "utf-8"))
        self.wfile.write(bytes("<BODY>\n", "utf-8"))
    elif theSection == "errorHelp":
        self.wfile.write(bytes("<H1>Invalid request!</H1>\n", "utf-8"))
        self.wfile.write(bytes("Last Request: <EM>" + self.path + "</EM><BR>\n", "utf-8"))
        self.wfile.write(bytes(errorMsg + "<BR><BR>\n", "utf-8"))
        self.wfile.write(bytes("Valid parameters to use -<BR>\n", "utf-8"))
        self.wfile.write(bytes("<STRONG>list</STRONG> - list the current lights NeewerLite-Python has available to it and the custom presets it can use<BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <EM>http://(server address)/NeewerLite-Python/doAction?list</EM><BR>\n", "utf-8"))
        self.wfile.write(bytes("<STRONG>discover</STRONG> - tell NeewerLite-Python to scan for new lights<BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <EM>http://(server address)/NeewerLite-Python/doAction?discover</EM><BR>\n", "utf-8"))
        self.wfile.write(bytes("<STRONG>nopage</STRONG> - send a command to the HTTP server, but don't render the webpage showing the results (<EM>useful, for example, on a headless Raspberry Pi where you don't necessarily want to see the results page</EM>)<BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <EM>http://(server address)/NeewerLite-Python/doAction?nopage</EM><BR>\n", "utf-8"))
        self.wfile.write(bytes("<STRONG>link=</STRONG> - (value: <EM>index of light to link to</EM>) manually link to a specific light - you can specify multiple lights with semicolons (so link=1;2 would try to link to both lights 1 and 2)<BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <EM>http://(server address)/NeewerLite-Python/doAction?link=1</EM><BR>\n", "utf-8"))
        self.wfile.write(bytes("<STRONG>light=</STRONG> - the MAC address (or current index of the light) you want to send a command to - you can specify multiple lights with semicolons (so light=1;2 would send a command to both lights 1 and 2)<BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <EM>http://(server address)/NeewerLite-Python/doAction?light=11:22:33:44:55:66</EM><BR>\n", "utf-8"))
        self.wfile.write(bytes("<STRONG>mode=</STRONG> - the mode (value: <EM>HSI, CCT, and either ANM or SCENE</EM>) - the color mode to switch the light to<BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <EM>http://(server address)/NeewerLite-Python/doAction?mode=CCT</EM><BR>\n", "utf-8"))
        self.wfile.write(bytes("<STRONG>use_preset=</STRONG> - (value: <EM>1-8</EM>) - use a custom global or snapshot preset<BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <EM>http://(server address)/NeewerLite-Python/doAction?use_preset=2</EM><BR>\n", "utf-8"))
        self.wfile.write(bytes("(CCT mode only) <STRONG>temp=</STRONG> or <STRONG>temperature=</STRONG> - (value: <EM>3200 to 8500</EM>) the color temperature in CCT mode to set the light to<BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <EM>http://(server address)/NeewerLite-Python/doAction?temp=5200</EM><BR>\n", "utf-8"))
        self.wfile.write(bytes("(HSI mode only) <STRONG>hue=</STRONG> - (value: <EM>0 to 360</EM>) the hue value in HSI mode to set the light to<BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <EM>http://(server address)/NeewerLite-Python/doAction?hue=240</EM><BR>\n", "utf-8"))
        self.wfile.write(bytes("(HSI mode only) <STRONG>sat=</STRONG> or <STRONG>saturation=</STRONG> - (value: <EM>0 to 100</EM>) the color saturation value in HSI mode to set the light to<BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <EM>http://(server address)/NeewerLite-Python/doAction?sat=65</EM><BR>\n", "utf-8"))
        self.wfile.write(bytes("(ANM/SCENE mode only) <STRONG>scene=</STRONG> - (value: <EM>1 to 9</EM>) which animation (scene) to switch the light to<BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <EM>http://(server address)/NeewerLite-Python/doAction?scene=3</EM><BR>\n", "utf-8"))
        self.wfile.write(bytes("(CCT/HSI/ANM modes) <STRONG>bri=</STRONG>, <STRONG>brightness=</STRONG> or <STRONG>intensity=</STRONG> - (value: <EM>0 to 100</EM>) how bright you want the light<BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <EM>http://(server address)/NeewerLite-Python/doAction?brightness=80</EM><BR>\n", "utf-8"))
        self.wfile.write(bytes("<BR><BR>More examples -<BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;Set the light with MAC address <EM>11:22:33:44:55:66</EM> to <EM>CCT</EM> mode, with a color temperature of <EM>5200</EM> and brightness of <EM>40</EM><BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;<EM>http://(server address)/NeewerLite-Python/doAction?light=11:22:33:44:55:66&mode=CCT&temp=5200&bri=40</EM><BR><BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;Set the light with MAC address <EM>11:22:33:44:55:66</EM> to <EM>HSI</EM> mode, with a hue of <EM>70</EM>, saturation of <EM>50</EM> and brightness of <EM>10</EM><BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;<EM>http://(server address)/NeewerLite-Python/doAction?light=11:22:33:44:55:66&mode=HSI&hue=70&sat=50&bri=10</EM><BR><BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;Set the first light available to <EM>SCENE</EM> mode, using the <EM>first</EM> animation and brightness of <EM>55</EM><BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;<EM>http://(server address)/NeewerLite-Python/doAction?light=1&mode=SCENE&scene=1&bri=55</EM><BR><BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;Use the 2nd custom preset, but don't render the webpage showing the results<BR>\n", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;<EM>http://(server address)/NeewerLite-Python/doAction?use_preset=2&nopage</EM><BR>\n", "utf-8"))
    elif theSection == "quicklinks":
        footerLinks = "Shortcut links: "
        footerLinks = footerLinks + "<A HREF='doAction?discover'>Scan for New Lights</A> | "
        footerLinks = footerLinks + "<A HREF='doAction?list'>List Currently Available Lights and Custom Presets</A>"
        self.wfile.write(bytes("<HR>" + footerLinks + "<HR>\n", "utf-8"))
    elif theSection == "htmlendheaders":
        self.wfile.write(bytes("<CENTER><A HREF='https://github.com/taburineagle/NeewerLite-Python/'>NeewerLite-Python 0.12</A> / HTTP Server / by Zach Glenwright<BR></CENTER>\n", "utf-8"))
        self.wfile.write(bytes("</BODY>\n</HTML>", "utf-8"))

def formatStringForConsole(theString, maxLength):
    if theString == "-": # return a header divider if the string is "="
        return "-" * maxLength
    else:
        if len(theString) == maxLength: # if the string is the max length, then just return the string
            return theString
        if len(theString) < maxLength: # if the string fits in the max length, then add spaces to pad it out
            return theString + " " * (maxLength - len(theString))
        else: # truncate the string, it's too long
            return theString[0:maxLength - 4] + " ..."

def createLightPrefsFolder():
    #CREATE THE light_prefs FOLDER IF IT DOESN'T EXIST
    try:
        os.mkdir(os.path.dirname(os.path.abspath(sys.argv[0])) + os.sep + "light_prefs")
    except FileExistsError:
        pass # the folder already exists, so we don't need to create it

def loadPrefsFile(globalPrefsFile = ""):
    global findLightsOnStartup, autoConnectToLights, printDebug, maxNumOfAttempts, \
           rememberLightsOnExit, acceptable_HTTP_IPs, customKeys, enableTabsOnLaunch, \
           whiteListedMACs, rememberPresetsOnExit

    if globalPrefsFile != "":
        printDebugString("Loading global preferences from file...")

        with open(globalPrefsFile, mode="r", encoding="utf-8") as fileToOpen:
            mainPrefs = fileToOpen.read().splitlines()

        acceptable_arguments = ["findLightsOnStartup", "autoConnectToLights", "printDebug", "maxNumOfAttempts", "rememberLightsOnExit", "acceptableIPs", \
            "SC_turnOffButton", "SC_turnOnButton", "SC_scanCommandButton", "SC_tryConnectButton", "SC_Tab_CCT", "SC_Tab_HSI", "SC_Tab_SCENE", "SC_Tab_PREFS", \
            "SC_Dec_Bri_Small", "SC_Inc_Bri_Small", "SC_Dec_Bri_Large", "SC_Inc_Bri_Large", \
            "SC_Dec_1_Small", "SC_Inc_1_Small", "SC_Dec_2_Small", "SC_Inc_2_Small", "SC_Dec_3_Small", "SC_Inc_3_Small", \
            "SC_Dec_1_Large", "SC_Inc_1_Large", "SC_Dec_2_Large", "SC_Inc_2_Large", "SC_Dec_3_Large", "SC_Inc_3_Large", \
            "enableTabsOnLaunch", "whiteListedMACs", "rememberPresetsOnExit"]

        # KICK OUT ANY PARAMETERS THAT AREN'T IN THE "ACCEPTABLE ARGUMENTS" LIST ABOVE
        # THIS SECTION OF CODE IS *SLIGHTLY* DIFFERENT THAN THE CLI KICK OUT CODE
        # THIS WAY, WE CAN HAVE COMMENTS IN THE PREFS FILE IF DESIRED
        for a in range(len(mainPrefs) - 1, -1, -1):
            if not any(x in mainPrefs[a] for x in acceptable_arguments): # if the current argument is invalid
                mainPrefs.pop(a) # delete the invalid argument from the list

        # NOW THAT ANY STRAGGLERS ARE OUT, ADD DASHES TO WHAT REMAINS TO PROPERLY PARSE IN THE PARSER
        for a in range(len(mainPrefs)):
            mainPrefs[a] = "--" + mainPrefs[a]
    else:
        mainPrefs = [] # submit an empty list to return the default values for everything

    prefsParser = argparse.ArgumentParser() # parser for preference arguments

    # SET PROGRAM DEFAULTS
    prefsParser.add_argument("--findLightsOnStartup", default=1)
    prefsParser.add_argument("--autoConnectToLights", default=1)
    prefsParser.add_argument("--printDebug", default=1)
    prefsParser.add_argument("--maxNumOfAttempts", default=6)
    prefsParser.add_argument("--rememberLightsOnExit", default=0)
    prefsParser.add_argument("--acceptableIPs", default=["127.0.0.1", "192.168.", "10."])
    prefsParser.add_argument("--whiteListedMACs" , default=[])
    prefsParser.add_argument("--rememberPresetsOnExit", default=1)

    # SHORTCUT KEY CUSTOMIZATIONS
    prefsParser.add_argument("--SC_turnOffButton", default="Ctrl+PgDown") # 0
    prefsParser.add_argument("--SC_turnOnButton", default="Ctrl+PgUp") # 1
    prefsParser.add_argument("--SC_scanCommandButton", default="Ctrl+Shift+S") # 2
    prefsParser.add_argument("--SC_tryConnectButton", default="Ctrl+Shift+C") # 3
    prefsParser.add_argument("--SC_Tab_CCT", default="Alt+1") # 4
    prefsParser.add_argument("--SC_Tab_HSI", default="Alt+2") # 5
    prefsParser.add_argument("--SC_Tab_SCENE", default="Alt+3") # 6
    prefsParser.add_argument("--SC_Tab_PREFS", default="Alt+4") # 7
    prefsParser.add_argument("--SC_Dec_Bri_Small", default="/") # 8
    prefsParser.add_argument("--SC_Inc_Bri_Small", default="*") # 9
    prefsParser.add_argument("--SC_Dec_Bri_Large", default="Ctrl+/") # 10
    prefsParser.add_argument("--SC_Inc_Bri_Large", default="Ctrl+*") # 11
    prefsParser.add_argument("--SC_Dec_1_Small", default="7") # 12
    prefsParser.add_argument("--SC_Inc_1_Small", default="9") # 13
    prefsParser.add_argument("--SC_Dec_2_Small", default="4") # 14
    prefsParser.add_argument("--SC_Inc_2_Small", default="6") # 15
    prefsParser.add_argument("--SC_Dec_3_Small", default="1") # 16
    prefsParser.add_argument("--SC_Inc_3_Small", default="3") # 17
    prefsParser.add_argument("--SC_Dec_1_Large", default="Ctrl+7") # 18
    prefsParser.add_argument("--SC_Inc_1_Large", default="Ctrl+9") # 19
    prefsParser.add_argument("--SC_Dec_2_Large", default="Ctrl+4") # 20
    prefsParser.add_argument("--SC_Inc_2_Large", default="Ctrl+6") # 21
    prefsParser.add_argument("--SC_Dec_3_Large", default="Ctrl+1") # 22
    prefsParser.add_argument("--SC_Inc_3_Large", default="Ctrl+3") # 23

    # "HIDDEN" DEBUG OPTIONS - oooooh!
    # THESE ARE OPTIONS THAT HELP DEBUG THINGS, BUT AREN'T REALLY USEFUL FOR NORMAL OPERATION
    # enableTabsOnLaunch SHOWS ALL TABS ACTIVE (INSTEAD OF DISABLING THEM) ON LAUNCH SO EVEN WITHOUT A LIGHT, A BYTESTRING CAN BE CALCULATED
    prefsParser.add_argument("--enableTabsOnLaunch", default=0)

    mainPrefs = prefsParser.parse_args(mainPrefs)

    # SET GLOBAL VALUES BASED ON PREFERENCES
    findLightsOnStartup = bool(int(mainPrefs.findLightsOnStartup)) # whether or not to scan for lights on launch
    autoConnectToLights = bool(int(mainPrefs.autoConnectToLights)) # whether or not to connect to lights when found
    printDebug = bool(int(mainPrefs.printDebug)) # whether or not to display debug messages in the console
    maxNumOfAttempts = int(mainPrefs.maxNumOfAttempts) # maximum number of attempts before failing out
    rememberLightsOnExit = bool(int(mainPrefs.rememberLightsOnExit)) # whether or not to remember light mode/settings when quitting out
    rememberPresetsOnExit = bool(int(mainPrefs.rememberPresetsOnExit)) # whether or not to remember the custom presets when quitting out

    if type(mainPrefs.acceptableIPs) is not list: # we have a string in the return, so we need to post-process it
        acceptable_HTTP_IPs = mainPrefs.acceptableIPs.replace(" ", "").split(";") # split the IP addresses into a list for acceptable IPs
    else: # the return is already a list (the default list), so return it
        acceptable_HTTP_IPs = mainPrefs.acceptableIPs

    if type(mainPrefs.whiteListedMACs) is not list: # if we've specified MAC addresses to whitelist, add them to the global list
        whiteListedMACs = mainPrefs.whiteListedMACs.replace(" ", "").split(";")

    # RETURN THE CUSTOM KEYBOARD MAPPINGS
    customKeys = [mainPrefs.SC_turnOffButton, mainPrefs.SC_turnOnButton, mainPrefs.SC_scanCommandButton, mainPrefs.SC_tryConnectButton, \
                  mainPrefs.SC_Tab_CCT, mainPrefs.SC_Tab_HSI, mainPrefs.SC_Tab_SCENE, mainPrefs.SC_Tab_PREFS, \
                  mainPrefs.SC_Dec_Bri_Small, mainPrefs.SC_Inc_Bri_Small, mainPrefs.SC_Dec_Bri_Large, mainPrefs.SC_Inc_Bri_Large, \
                  mainPrefs.SC_Dec_1_Small, \
                  mainPrefs.SC_Inc_1_Small, \
                  mainPrefs.SC_Dec_2_Small, \
                  mainPrefs.SC_Inc_2_Small, \
                  mainPrefs.SC_Dec_3_Small, \
                  mainPrefs.SC_Inc_3_Small, \
                  mainPrefs.SC_Dec_1_Large, \
                  mainPrefs.SC_Inc_1_Large, \
                  mainPrefs.SC_Dec_2_Large, \
                  mainPrefs.SC_Inc_2_Large, \
                  mainPrefs.SC_Dec_3_Large, \
                  mainPrefs.SC_Inc_3_Large]
                
    enableTabsOnLaunch = bool(int(mainPrefs.enableTabsOnLaunch))

if __name__ == '__main__':
    # Display the version of NeewerLite-Python we're using
    print("---------------------------------------------------------")
    print("             NeewerLite-Python ver. 0.12")
    print("                 by Zach Glenwright")
    print("  > https://github.com/taburineagle/NeewerLite-Python <")
    print("---------------------------------------------------------")

    singleInstanceLock() # make a lockfile if one doesn't exist yet, and quit out if one does

    if os.path.exists(globalPrefsFile):
        loadPrefsFile(globalPrefsFile) # if a preferences file exists, process it and load the preferences
    else:
        loadPrefsFile() # if it doesn't, then just load the defaults

    if os.path.exists(customLightPresetsFile):
        loadCustomPresets() # if there's a custom mapping for presets, then load that into memory

    setUpAsyncio() # set up the asyncio loop
    cmdReturn = [True] # initially set to show the GUI interface over the CLI interface

    if len(sys.argv) > 1: # if we have more than 1 argument on the command line (the script itself is argument 1), then process switches
        cmdReturn = processCommands()
        printDebug = cmdReturn[1] # if we use the --quiet option, then don't show debug strings in the console

        if cmdReturn[0] == False: # if we're trying to load the CLI, make sure we aren't already running another version of it
            doAnotherInstanceCheck() # check to see if another instance is running, and if it is, then error out and quit

        # START HTTP SERVER HERE AND SIT IN THIS LOOP UNTIL THE END
        if cmdReturn[0] == "HTTP":
            doAnotherInstanceCheck() # check to see if another instance is running, and if it is, then error out and quit
                
            webServer = ThreadingHTTPServer(("", 8080), NLPythonServer)

            try:
                printDebugString("Starting the HTTP Server on Port 8080...")
                printDebugString("-------------------------------------------------------------------------------------")

                # start the HTTP server and wait for requests
                webServer.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                printDebugString("Stopping the HTTP Server...")
                webServer.server_close()

                # DISCONNECT FROM EACH LIGHT BEFORE FINISHING THE PROGRAM
                printDebugString("Attempting to unlink from lights...")
                asyncioEventLoop.run_until_complete(parallelAction("disconnect", [-1], False)) # disconnect from all lights in parallel
           
            printDebugString("Closing the program NOW")
            singleInstanceUnlockandQuit(0) # delete the lock file and quit out

        if cmdReturn[0] == "LIST":
            doAnotherInstanceCheck() # check to see if another instance is running, and if it is, then error out and quit

            print("NeewerLite-Python 0.12 by Zach Glenwright")
            print("Searching for nearby Neewer lights...")
            asyncioEventLoop.run_until_complete(findDevices())

            if len(availableLights) > 0:
                print()

                if len(availableLights) == 1: # we only found one
                    print("We found 1 Neewer light on the last search.")
                else: # we found more than one
                    print("We found " + str(len(availableLights)) + " Neewer lights on the last search.")

                print()

                if platform.system() == "Darwin": # if we're on MacOS, then we display the GUID instead of the MAC address
                    addressCharsAllowed = 36 # GUID addresses are 36 characters long
                    addressString = "GUID (MacOS)"
                else:
                    addressCharsAllowed = 17 # MAC addresses are 17 characters long
                    addressString = "MAC Address"

                nameCharsAllowed = 79 - addressCharsAllowed # the remaining space is to display the light name

                # PRINT THE HEADERS
                print(formatStringForConsole("Custom Name (Light Type)", nameCharsAllowed) + \
                      " " + \
                      formatStringForConsole(addressString, addressCharsAllowed))

                # PRINT THE SEPARATORS
                print(formatStringForConsole("-", nameCharsAllowed) + " " + formatStringForConsole("-", addressCharsAllowed))

                # PRINT THE LIGHTS
                for a in range(len(availableLights)):
                    lightName = availableLights[a][2] + "(" + availableLights[a][0].name + ")"

                    print(formatStringForConsole(lightName, nameCharsAllowed) + " " + \
                          formatStringForConsole(availableLights[a][0].address, addressCharsAllowed))

                    print(formatStringForConsole(" > RSSI: " + str(availableLights[a][0].rssi) + "dBm", nameCharsAllowed))
            else:
                print("We did not find any Neewer lights on the last search.")

            singleInstanceUnlockandQuit(0) # delete the lock file and quit out

        printDebugString(" > Launch GUI: " + str(cmdReturn[0]))
        printDebugString(" > Show Debug Strings on Console: " + str(cmdReturn[1]))

        printDebugString(" > Mode: " + cmdReturn[3])

        if cmdReturn[3] == "CCT":
            printDebugString(" > Color Temperature: " + str(cmdReturn[4]) + "00K")
            printDebugString(" > Brightness: " + str(cmdReturn[5]))
        elif cmdReturn[3] == "HSI":
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

                asyncioEventLoop.run_until_complete(connectToOneLight(cmdReturn[2])) # get Bleak object linking to this specific light and getting custom prefs
            else:
                printDebugString("-------------------------------------------------------------------------------------")
                printDebugString(" > CLI >> You did not specify a light to send the command to - use the --light switch")
                printDebugString(" > CLI >> and write either a MAC Address (XX:XX:XX:XX:XX:XX) to a Neewer light or")
                printDebugString(" > CLI >> ALL to send to all available Neewer lights found by Bluetooth")
                printDebugString("-------------------------------------------------------------------------------------")

    if cmdReturn[0] == True: # launch the GUI with the command-line arguments
        if importError == 0:
            try: # try to load the GUI
                app = QApplication(sys.argv)
                
                if anotherInstance == True: # different than the CLI handling, the GUI needs to show a dialog box asking to quit or launch
                    errDlg = QMessageBox()
                    errDlg.setWindowTitle("Another Instance Running!")
                    errDlg.setTextFormat(Qt.TextFormat.RichText)
                    errDlg.setText("There is another instance of NeewerLite-Python already running.&nbsp;Please close out of that instance first before trying to launch a new instance of the program.<br><br>If you are positive that you don't have any other instances running and you want to launch a new one anyway,&nbsp;click <em>Launch New Instance</em> below.&nbsp;Otherwise click <em>Quit</em> to quit out.")
                    errDlg.addButton("Launch New Instance", QMessageBox.ButtonRole.YesRole)
                    errDlg.addButton("Quit", QMessageBox.ButtonRole.NoRole)
                    errDlg.setDefaultButton(QMessageBox.No)
                    errDlg.setIcon(QMessageBox.Warning)

                    button = errDlg.exec_()

                    if button == 1: # if we clicked the Quit button, then quit out
                        sys.exit(1)

                mainWindow = MainWindow()

                # SET UP GUI BASED ON COMMAND LINE ARGUMENTS
                if len(cmdReturn) > 1:
                    if cmdReturn[3] == "CCT": # set up the GUI in CCT mode with specified parameters (or default, if none)
                        mainWindow.setUpGUI(colorMode=cmdReturn[3], temp=cmdReturn[4], brightness=cmdReturn[5])
                    elif cmdReturn[3] == "HSI": # set up the GUI in HSI mode with specified parameters (or default, if none)
                        mainWindow.setUpGUI(colorMode=cmdReturn[3], hue=cmdReturn[4], sat=cmdReturn[5], brightness=cmdReturn[6])
                    elif cmdReturn[3] == "ANM": # set up the GUI in ANM mode with specified parameters (or default, if none)
                        mainWindow.setUpGUI(colorMode=cmdReturn[3], scene=cmdReturn[4], brightness=cmdReturn[5])

                mainWindow.show()

                # START THE BACKGROUND THREAD
                workerThread = threading.Thread(target=workerThread, args=(asyncioEventLoop,), name="workerThread")
                workerThread.start()

                ret = app.exec_()
                singleInstanceUnlockandQuit(ret) # delete the lock file and quit out
            except NameError:
                pass # same as above - we could not load the GUI, but we have already sorted error messages
        else:
            if importError == 1: # we can't load PySide2
                print(" ===== CAN NOT FIND PYSIDE2 LIBRARY =====")
                print(" You don't have the PySide2 Python library installed.  If you're only running NeewerLite-Python from")
                print(" a command-line (from a Raspberry Pi CLI for instance), or using the HTTP server, you don't need this package.")
                print(" If you want to launch NeewerLite-Python with the GUI, you need to install the PySide2 package.")
                print()
                print(" To install PySide2, run either pip or pip3 from the command line:")
                print("    pip install PySide2")
                print("    pip3 install PySide2")
                print()
                print(" Or visit this website for more information:")
                print("    https://pypi.org/project/PySide2/")
            elif importError == 2: # we have PySide2, but can't load the GUI file itself for some reason
                print(" ===== COULD NOT LOAD/FIND GUI FILE =====")
                print(" If you don't need to use the GUI, you are fine going without the PySide2 pacakge.")
                print(" but using NeewerLite-Python with the GUI requires the PySide2 library.")
                print()
                print(" If you have already installed the PySide2 library but are still getting this error message,")
                print(" Make sure you have the ui_NeewerLightUI.py script in the same directory as NeewerLite-Python.py")
                print(" If you don't know where that file is, redownload the NeewerLite-Python package from Github here:")
                print("    https://github.com/taburineagle/NeewerLite-Python/")

                sys.exit(1) # quit out, we can't run the program without PySide2 or the GUI (for the GUI version, at least)
    else: # don't launch the GUI, send command to a light/lights and quit out
        if len(cmdReturn) > 1:
            if cmdReturn[3] == "CCT": # calculate CCT bytestring
                calculateByteString(colorMode=cmdReturn[3], temp=cmdReturn[4], brightness=cmdReturn[5])
            elif cmdReturn[3] == "HSI": # calculate HSI bytestring
                calculateByteString(colorMode=cmdReturn[3], HSI_H=cmdReturn[4], HSI_S=cmdReturn[5], HSI_I=cmdReturn[6])
            elif cmdReturn[3] == "ANM": # calculate ANM/SCENE bytestring
                calculateByteString(colorMode=cmdReturn[3], animation=cmdReturn[4], brightness=cmdReturn[5])
            elif cmdReturn[3] == "ON": # turn the light on
                setPowerBytestring("ON")
            elif cmdReturn[3] == "OFF": # turn the light off
                setPowerBytestring("OFF")

        if availableLights != []:
            printDebugString(" > CLI >> Bytestring to send to light:" + updateStatus())

            # CONNECT TO THE LIGHT AND SEND INFORMATION TO IT
            isFinished = False
            numOfAttempts = 1

            while isFinished == False:
                printDebugString("-------------------------------------------------------------------------------------")
                printDebugString(" > CLI >> Attempting to connect to light (attempt " + str(numOfAttempts) + " of " + str(maxNumOfAttempts) + ")")
                printDebugString("-------------------------------------------------------------------------------------")
                isFinished = asyncioEventLoop.run_until_complete(connectToLight(0, False))

                if numOfAttempts < maxNumOfAttempts:
                    numOfAttempts = numOfAttempts + 1
                else:
                    printDebugString("Error connecting to light " + str(maxNumOfAttempts) + " times - quitting out")
                    singleInstanceUnlockandQuit(1) # delete the lock file and quit out

            isFinished = False
            numOfAttempts = 1

            while isFinished == False:
                printDebugString("-------------------------------------------------------------------------------------")
                printDebugString(" > CLI >> Attempting to write to light (attempt " + str(numOfAttempts) + " of " + str(maxNumOfAttempts) + ")")
                printDebugString("-------------------------------------------------------------------------------------")
                isFinished = asyncioEventLoop.run_until_complete(writeToLight(0, False))

                if numOfAttempts < maxNumOfAttempts:
                    numOfAttempts = numOfAttempts + 1
                else:
                    printDebugString("Error writing to light " + str(maxNumOfAttempts) + " times - quitting out")
                    singleInstanceUnlockandQuit(1) # delete the lock file and quit out

            isFinished = False
            numOfAttempts = 1

            while isFinished == False:
                printDebugString("-------------------------------------------------------------------------------------")
                printDebugString(" > CLI >> Attempting to disconnect from light (attempt " + str(numOfAttempts) + " of " + str(maxNumOfAttempts) + ")")
                printDebugString("-------------------------------------------------------------------------------------")
                isFinished = asyncioEventLoop.run_until_complete(disconnectFromLight(0))

                if numOfAttempts < maxNumOfAttempts:
                    numOfAttempts = numOfAttempts + 1
                else:
                    printDebugString("Error disconnecting from light " + str(maxNumOfAttempts) + " times - quitting out")
                    singleInstanceUnlockandQuit(1) # delete the lock file and quit out
        else:
            printDebugString("-------------------------------------------------------------------------------------")
            printDebugString(" > CLI >> Calculated bytestring:" + updateStatus())

        singleInstanceUnlockandQuit(0) # delete the lock file and quit out