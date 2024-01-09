#!/usr/bin/python3
#############################################################
## NeewerLite-Python ver. 0.15-RC-010924
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

''' 
NOTE! NOTE! NOTE! NOTE! NOTE! THIS BRANCH IS A WIP (work-in-progress) BRANCH - 
THAT MEANS IT'S NOT 100% PRODUCTION READY, SO USE AT YOUR OWN RISK.  YOU HAVE
BEEN WARRRRRRRRRRRNNNEEDD... NOW:

Things to do!
    - Sort out all of the LEMURs in the script
    - Re-write all of the "turn on/off" logic to work with Infinity lights
'''

import os
import sys
import tempfile
import argparse
import asyncio
import threading
import time

import platform # used to determine which OS we're using for MAC address/GUID listing
from importlib import metadata as ilm # used to determine which version of Bleak we have running
from subprocess import run, PIPE # used to get MacOS Mac address

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
sendValue = [120, 135, 2, 50, 56, 50] # an array to hold the values to be sent to the light
lastSelection = [] # the current light selection (this is for snapshot preset entering/leaving buttons)
lastSortingField = -1 # the last field used for sorting purposes

availableLights = [] # the list of Neewer lights currently available to control
# List Subitems (for ^^^^^^):
# [0] - UpdatedBLEInformation object (replaces Bleak object, but retains information) Object (can use .name / .realname / .address / .rssi / .HWMACaddr to get specifics)
# [1] - Bleak Connection (the actual Bluetooth connection to the light itself)
# [2] - Custom Name for Light (string)
# [3] - Last Used Parameters (list)
# [4] - The range of color temperatures to use in CCT mode (list, min, max) <- changed in 0.12
# [5] - Whether or not to send Brightness and Hue independently for old lights (boolean)
# [6] - Whether or not this light has been manually turned ON/OFF (boolean)
# [7] - The Power and Channel data returned for this light (list)
# [8] - Whether or not this light uses the new Infinity light protocol (boolean)

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

customLightPresets = [] # the list of custom light presets
# The list of **default** light presets for restoring and checking against
defaultLightPresets = [
    [[-1, [120, 135, 2, 20, 56, 50]]],
    [[-1, [120, 135, 2, 20, 32, 50]]],
    [[-1, [120, 135, 2, 0, 56, 50]]],
    [[-1, [120, 134, 4, 0, 0, 120, 20]]],
    [[-1, [120, 134, 4, 240, 0, 100, 20]]],
    [[-1, [120, 134, 4, 120, 0, 100, 20]]],
    [[-1, [120, 134, 4, 44, 1, 100, 20]]],
    [[-1, [120, 134, 4, 160, 0, 100, 20]]]
    ]

# Initially fill the custom presets with the default preset parameters - custom file will overwrite these, if it exists
for a in range(len(defaultLightPresets)):
    customLightPresets.append(defaultLightPresets[a])

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
            self.effectChooser.currentIndexChanged.connect(self.effectChanged)

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

            # Connect the sliders to the computation function
            self.colorTempSlider.valueChanged.connect(lambda: self.computeValues())
            self.brightSlider.valueChanged.connect(lambda: self.computeValues())
            self.GMSlider.valueChanged.connect(lambda: self.computeValues())
            self.RGBSlider.valueChanged.connect(lambda: self.computeValues())
            self.colorSatSlider.valueChanged.connect(lambda: self.computeValues())
            self.brightDoubleSlider.valueChanged.connect(lambda: self.computeValues())
            self.RGBDoubleSlider.valueChanged.connect(lambda: self.computeValues())
            self.colorTempDoubleSlider.valueChanged.connect(lambda: self.computeValues())
            self.speedSlider.valueChanged.connect(lambda: self.computeValues())
            self.sparksSlider.valueChanged.connect(lambda: self.computeValues())
            self.specialOptionsChooser.currentIndexChanged.connect(lambda: self.computeValues())

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
                                        availableLights[a][0].name, availableLights[a][0].address, availableLights[a][0].rssi, \
                                        availableLights[a][8]])
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
                                            sortedList[a][4], sortedList[a][5], sortedList[a][6], sortedList[a][7], \
                                            sortedList[a][11]])
                                        
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
            if theNumber == 1:
                if customKeys[16] == "1":
                    self.changeSliderValue(3, -1) # decrement slider 3
            elif theNumber == 2:
                pass
            elif theNumber == 3:
                if customKeys[17] == "3":
                        self.changeSliderValue(3, 1) # increment slider 3
            elif theNumber == 4:
                if customKeys[14] == "4":
                        self.changeSliderValue(2, -1) # decrement slider 2
            elif theNumber == 5:
                pass
            elif theNumber == 6:
                if customKeys[15] == "6":
                        self.changeSliderValue(2, 1) # increment slider 2
            elif theNumber == 7:
                if customKeys[12] == "7":
                        self.changeSliderValue(1, -1) # decrement slider 1
            elif theNumber == 8:
                pass
            elif theNumber == 9:
                if customKeys[13] == "9":
                        self.changeSliderValue(1, 1) # increment slider 1

        def changeSliderValue(self, sliderToChange, changeAmt):
            if self.ColorModeTabWidget.currentIndex() == 0: # we have 2 sliders in CCT mode
                if sliderToChange == 1:
                    self.colorTempSlider.setValue(self.colorTempSlider.value() + changeAmt)
                elif sliderToChange == 2 or sliderToChange == 0:
                    self.brightSlider.setValue(self.brightSlider.value() + changeAmt)
                elif sliderToChange == 3:
                    self.GMSlider.setValue(self.GMSlider.value() + changeAmt)
            elif self.ColorModeTabWidget.currentIndex() == 1: # we have 3 sliders in HSI mode
                if sliderToChange == 1:
                    self.RGBSlider.setValue(self.RGBSlider.value() + changeAmt)
                elif sliderToChange == 2:
                    self.colorSatSlider.setValue(self.colorSatSlider.value() + changeAmt)
                elif sliderToChange == 3 or sliderToChange == 0:
                    self.brightSlider.setValue(self.brightSlider.value() + changeAmt)
            elif self.ColorModeTabWidget.currentIndex() == 2:
                if sliderToChange == 0: # the only "slider" in SCENE mode is the brightness
                    self.Slider_ANM_Brightness.setValue(self.Slider_ANM_Brightness.value() + changeAmt)

        def checkLightTab(self, selectedLight = -1):
            currentIdx = self.ColorModeTabWidget.currentIndex()

            if currentIdx == 0 or currentIdx == 2: # if we're on the CCT or ANM tabs, do the check
                if selectedLight == -1: # if we don't have a light selected
                    self.setupCCTBounds(3200, 5600) # restore the bounds to their default of 56(00)K
                else: # set up the gradient to show the range of color temperatures available to the currently selected light
                    self.setupCCTBounds(availableLights[selectedLight][4][0], availableLights[selectedLight][4][1])
            elif currentIdx == 3: # if we're on the Preferences tab instead
                if selectedLight != -1: # if there is a specific selected light
                    self.setupLightPrefsTab(selectedLight) # update the Prefs tab with the information for that selected light

        def setupCCTBounds(self, startRange, endRange):
            startRange = int(startRange / 100)
            endRange = int(endRange / 100)

            self.colorTempSlider.changeSliderRange([startRange, endRange])
            self.colorTempDoubleSlider.changeSliderRange([startRange, endRange])

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
            global customKeys, autoConnectToLights, printDebug, rememberLightsOnExit, \
                   rememberPresetsOnExit, maxNumOfAttempts, acceptable_HTTP_IPs, whiteListedMACs

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
            selectedRows = self.selectedLights(True) # get the list of currently selected lights

            if len(selectedRows[0]) > 0: # if we have a selection
                self.tryConnectButton.setEnabled(True) # if we have light(s) selected in the table, then enable the "Connect" button

                if len(selectedRows[0]) == 1: # we have exactly one light selected
                    self.ColorModeTabWidget.setTabEnabled(3, True) # enable the "Preferences" tab for this light

                    # SWITCH THE TURN ON/OFF BUTTONS ON, AND CHANGE TEXT TO SINGLE BUTTON TEXT
                    self.turnOffButton.setText("Turn Light Off")
                    self.turnOffButton.setEnabled(True)
                    self.turnOnButton.setText("Turn Light On")
                    self.turnOnButton.setEnabled(True)

                    self.ColorModeTabWidget.setTabEnabled(0, True)

                    if availableLights[selectedRows[0][0]][5] == True: # if this light is CCT only, then disable the HSI and ANM tabs
                        self.ColorModeTabWidget.setTabEnabled(1, False) # disable the HSI mode tab
                        self.ColorModeTabWidget.setTabEnabled(2, False) # disable the ANM/SCENE tab
                    else: # we can use HSI and ANM/SCENE modes, so enable those tabs
                        self.ColorModeTabWidget.setTabEnabled(1, True) # enable the HSI mode tab
                        self.ColorModeTabWidget.setTabEnabled(2, True) # enable the ANM/SCENE tab

                    if selectedRows[1] == True:
                        self.GMSlider.setVisible(True)
                    else:
                        self.GMSlider.setVisible(False)

                    currentlySelectedRow = selectedRows[0][0] # get the row index of the 1 selected item
                    self.checkLightTab(currentlySelectedRow) # if we're on CCT, check to see if this light can use extended values + on Prefs, update Prefs

                    # RECALL LAST SENT SETTING FOR THIS PARTICULAR LIGHT, IF A SETTING EXISTS
                    if availableLights[currentlySelectedRow][3] != []: # if the last set parameters aren't empty
                        if availableLights[currentlySelectedRow][6] != False: # if the light is listed as being turned ON
                            sendValue = translateByteString(availableLights[currentlySelectedRow][3]) # make the current "sendValue" the last set parameter so it doesn't re-send it on re-load
                            self.setUpGUI(**sendValue)
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

                    # ENABLE ALL OF THE TABS BELOW
                    self.ColorModeTabWidget.setTabEnabled(0, True)
                    self.ColorModeTabWidget.setTabEnabled(1, True) # enable the "HSI" mode tab
                    self.ColorModeTabWidget.setTabEnabled(2, True) # enable the "ANM/SCENE" mode tab
                    self.ColorModeTabWidget.setTabEnabled(3, False) # disable the "Preferences" tab, as we have multiple lights selected

                    if selectedRows[1] == True:
                        self.GMSlider.setVisible(True)
                    else:
                        self.GMSlider.setVisible(False)
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
                self.ColorModeTabWidget.setTabEnabled(3, False) # disable the "Light Preferences" tab, as we have no lights selected

                if currentTab < 2:
                    self.ColorModeTabWidget.setCurrentIndex(currentTab) # disable the tabs, but don't switch (unless ANM or Preferences)
                else:
                    self.ColorModeTabWidget.setCurrentIndex(0) # if we're on Prefs, then switch to the CCT tab

                self.checkLightTab() # check to see if we're on the CCT tab - if we are, then restore order

        # SET UP THE GUI FOR USING INFINITY MODE/SWITCHING EFFECTS LIST
        def setInfinityMode(self, infinityMode = False):
            countOfCurrentEffects = self.effectChooser.count()

            if infinityMode == False:
                if countOfCurrentEffects == 0 or countOfCurrentEffects == 18:
                    self.effectChooser.clear()
                    self.effectChooser.addItems(["1 - Cop Car", "2 - Ambulance", "3 - Fire Engine",
                                             "4 - Fireworks", "5 - Party", "6 - Candlelight",
                                             "7 - Lightning", "8 - Paparazzi", "9 - TV Screen"])
            else:
                if countOfCurrentEffects == 0 or countOfCurrentEffects == 9:
                    self.effectChooser.clear()
                    self.effectChooser.addItems(["1 Lightning", "2 Paparazzi", "3 Defective Bulb",
                                             "4 Explosion", "5 Welding", "6 CCT Flash",
                                             "7 Hue Flash", "8 CCT Pulse", "9 Hue Pulse",
                                             "10 Cop Car", "11 Candlelight", "12 Hue Loop",
                                             "13 CCT Loop", "14 INT Loop (CCT)", "14 INT Loop (HSI)",
                                             "15 TV Screen", "16 Fireworks", "17 Party"])

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

        # CLEAR THE SCENE TABS OF ALL SLIDERS
        def cleanSlate(self):
            self.colorTempSlider.hide()
            self.brightSlider.hide()
            self.GMSlider.hide()
            self.RGBSlider.hide()
            self.colorSatSlider.hide()
            self.brightDoubleSlider.hide()
            self.RGBDoubleSlider.hide()
            self.colorTempDoubleSlider.hide()
            self.speedSlider.hide()
            self.sparksSlider.hide()
            self.specialOptionsSection.hide()

        # CHANGING FX TYPES ON THE SCENE TAB
        def effectChanged(self, effectID):
            self.cleanSlate() # delete every slider off of the current tab
            
            wX = [8, 290] # X positions for widgets - [0], left half  [1], right half
            wY = [30, 95, 160] # Y positions for widgets - [0], first [1], 2nd [2], 3rd
            
            if self.effectChooser.itemText(0) == "1 Lightning": # Infinity mode
                if effectID == 0: # Light(n)ing
                    self.brightSlider.presentMe(self.ANM, wX[0], wY[0])
                    self.colorTempSlider.presentMe(self.ANM, wX[0], wY[1])
                    self.speedSlider.presentMe(self.ANM, wX[0], wY[2])
                elif effectID == 1 or effectID == 2: # Paparazzi or Defective Bulb
                    self.brightSlider.presentMe(self.ANM, wX[0], wY[0])
                    self.colorTempSlider.presentMe(self.ANM, wX[0], wY[1])
                    self.GMSlider.presentMe(self.ANM, wX[0], wY[2], True)
                    self.speedSlider.presentMe(self.ANM, wX[1], wY[2], True)
                elif effectID == 3: # Explosion
                    self.brightSlider.presentMe(self.ANM, wX[0], wY[0])
                    self.colorTempSlider.presentMe(self.ANM, wX[0], wY[1], True)
                    self.GMSlider.presentMe(self.ANM, wX[1], wY[1], True)
                    self.speedSlider.presentMe(self.ANM, wX[0], wY[2], True)
                    self.sparksSlider.presentMe(self.ANM, wX[1], wY[2], True)
                elif effectID == 4: # Welding
                    self.brightDoubleSlider.presentMe(self.ANM, wX[0], wY[0])
                    self.colorTempSlider.presentMe(self.ANM, wX[0], wY[1])
                    self.GMSlider.presentMe(self.ANM, wX[0], wY[2], True)
                    self.speedSlider.presentMe(self.ANM, wX[1], wY[2], True)
                elif effectID == 5: # CCT Flash
                    self.brightSlider.presentMe(self.ANM, wX[0], wY[0])
                    self.colorTempSlider.presentMe(self.ANM, wX[0], wY[1])
                    self.GMSlider.presentMe(self.ANM, wX[0], wY[2], True)
                    self.speedSlider.presentMe(self.ANM, wX[1], wY[2], True)
                elif effectID == 6: # Hue Flash
                    self.brightSlider.presentMe(self.ANM, wX[0], wY[0])
                    self.RGBSlider.presentMe(self.ANM, wX[0], wY[1])
                    self.colorSatSlider.presentMe(self.ANM, wX[0], wY[2], True)
                    self.speedSlider.presentMe(self.ANM, wX[1], wY[2], True)
                elif effectID == 7: # CCT Pulse
                    self.brightSlider.presentMe(self.ANM, wX[0], wY[0])
                    self.colorTempSlider.presentMe(self.ANM, wX[0], wY[1])
                    self.GMSlider.presentMe(self.ANM, wX[0], wY[2], True)
                    self.speedSlider.presentMe(self.ANM, wX[1], wY[2], True)
                elif effectID == 8: # Hue Pulse
                    self.brightSlider.presentMe(self.ANM, wX[0], wY[0])
                    self.RGBSlider.presentMe(self.ANM, wX[0], wY[1])
                    self.colorSatSlider.presentMe(self.ANM, wX[0], wY[2], True)
                    self.speedSlider.presentMe(self.ANM, wX[1], wY[2], True)
                elif effectID == 9: # Cop Car
                    self.brightSlider.presentMe(self.ANM, wX[0], wY[0])
                    self.setUpColorOptions(effectID, 2, wX[0], wY[1] + 5)
                    self.speedSlider.presentMe(self.ANM, wX[0], wY[2])
                elif effectID == 10: # Candlelight
                    self.brightDoubleSlider.presentMe(self.ANM, wX[0], wY[0])
                    self.colorTempSlider.presentMe(self.ANM, wX[0], wY[1], True)
                    self.GMSlider.presentMe(self.ANM, wX[1], wY[1], True)
                    self.speedSlider.presentMe(self.ANM, wX[0], wY[2], True)
                    self.sparksSlider.presentMe(self.ANM, wX[1], wY[2], True)
                elif effectID == 11: # Hue Loop
                    self.brightSlider.presentMe(self.ANM, wX[0], wY[0])
                    self.RGBDoubleSlider.presentMe(self.ANM, wX[0], wY[1])
                    self.speedSlider.presentMe(self.ANM, wX[0], wY[2])
                elif effectID == 12: # CCT Loop
                    self.brightSlider.presentMe(self.ANM, wX[0], wY[0])
                    self.colorTempDoubleSlider.presentMe(self.ANM, wX[0], wY[1])
                    self.speedSlider.presentMe(self.ANM, wX[0], wY[2])
                elif effectID == 13: # INT Loop (CCT)
                    self.brightDoubleSlider.presentMe(self.ANM, wX[0], wY[0])
                    self.colorTempSlider.presentMe(self.ANM, wX[0], wY[1])
                    self.speedSlider.presentMe(self.ANM, wX[0], wY[2])
                elif effectID == 14: # INT Loop (HSI)
                    self.brightDoubleSlider.presentMe(self.ANM, wX[0], wY[0])
                    self.RGBSlider.presentMe(self.ANM, wX[0], wY[1])
                    self.speedSlider.presentMe(self.ANM, wX[0], wY[2])
                elif effectID == 15: # TV Screen
                    self.brightDoubleSlider.presentMe(self.ANM, wX[0], wY[0])
                    self.colorTempSlider.presentMe(self.ANM, wX[0], wY[1])
                    self.GMSlider.presentMe(self.ANM, wX[0], wY[2], True)
                    self.speedSlider.presentMe(self.ANM, wX[1], wY[2], True)
                elif effectID == 16: # Fireworks
                    self.brightSlider.presentMe(self.ANM, wX[0], wY[0])
                    self.setUpColorOptions(effectID, 1, wX[0], wY[1] + 5)
                    self.speedSlider.presentMe(self.ANM, wX[0], wY[2], True)
                    self.sparksSlider.presentMe(self.ANM, wX[1], wY[2], True)
                elif effectID == 17: # Party!
                    self.brightSlider.presentMe(self.ANM, wX[0], wY[0])
                    self.setUpColorOptions(effectID, 1, wX[0], wY[1] + 5)
                    self.speedSlider.presentMe(self.ANM, wX[0], wY[2])
            else: # we're using an older style Neewer light, so we don't need all the custom parameters
                self.brightSlider.presentMe(self.ANM, wX[0], wY[0])

        def setUpColorOptions(self, theTab, defaultEffect, posX, posY):
            self.specialOptionsChooser.clear()

            if theTab == 9: # Cop Car effect colors
                self.specialOptionsChooser.addItems(["Red", "Blue", "Red and Blue", "White and Blue", "Red, Blue and White"])
            else: # Fireworks and Party colors
                self.specialOptionsChooser.addItems(["Single Color", "Multiple Colors", "Combined"])

            self.specialOptionsChooser.setCurrentIndex(defaultEffect)
            self.specialOptionsSection.move(posX, posY)
            self.specialOptionsSection.show()

        # IF YOU CLICK ON ONE OF THE TABS, THIS WILL SWITCH THE VIEW/SEND A NEW SIGNAL FROM THAT SPECIFIC TAB
        def tabChanged(self, i):
            currentSelection = self.selectedLights(True) # get the list of currently selected lights
            
            if i == 0:
                self.colorTempSlider.presentMe(self.CCT, 8, 10)
                self.brightSlider.presentMe(self.CCT, 8, 80)
                self.GMSlider.presentMe(self.CCT, 8, 150)

                if currentSelection[1] == True:
                    self.GMSlider.setVisible(True)
                else:
                    self.GMSlider.setVisible(False)
            elif i == 1:
                self.RGBSlider.presentMe(self.HSI, 8, 10)
                self.colorSatSlider.presentMe(self.HSI, 8, 80)
                self.brightSlider.presentMe(self.HSI, 8, 150)
            elif i == 2:
                self.setInfinityMode(currentSelection[1])
                self.effectChanged(self.effectChooser.currentIndex())
            elif i == 3: # we clicked on the PREFS tab
                if len(currentSelection[0]) == 1:
                    self.setupLightPrefsTab(currentSelection[0][0])
            elif i == 4: # we clicked on the Global PREFS tab
                self.setupGlobalLightPrefsTab()
                
        def computeValues(self):
            currentTab = self.ColorModeTabWidget.currentIndex() # get the current tab that's active

            if currentTab == 0:
                calculateByteString(colorMode="CCT",\
                                    temp=self.colorTempSlider.value(),\
                                    brightness=self.brightSlider.value(),\
                                    GM=self.GMSlider.value())
            elif currentTab == 1:
                calculateByteString(colorMode="HSI",\
                                    hue=self.RGBSlider.value(),\
                                    saturation=self.colorSatSlider.value(),\
                                    brightness=self.brightSlider.value())
            elif currentTab == 2:
                currentEffect = self.effectChooser.currentIndex() + 1

                if self.effectChooser.itemText(0) == "1 Lightning": # Infinity mode
                    if currentEffect == 1:
                        calculateByteString(colorMode="ANM",\
                                            effect=currentEffect,\
                                            brightness=self.brightSlider.value(),\
                                            temp=self.colorTempSlider.value(),\
                                            speed=self.speedSlider.value())
                    elif currentEffect == 2 or currentEffect == 3 or \
                        currentEffect == 6 or currentEffect == 8:
                        calculateByteString(colorMode="ANM",\
                                            effect=currentEffect,\
                                            brightness=self.brightSlider.value(),\
                                            temp=self.colorTempSlider.value(),\
                                            GM=self.GMSlider.value(),\
                                            speed=self.speedSlider.value())
                    elif currentEffect == 4:
                        calculateByteString(colorMode="ANM",\
                                            effect=currentEffect,\
                                            brightness=self.brightSlider.value(),\
                                            temp=self.colorTempSlider.value(),\
                                            GM=self.GMSlider.value(),\
                                            speed=self.speedSlider.value(),\
                                            sparks=self.sparksSlider.value())
                    elif currentEffect == 5:
                        brightRange = self.brightDoubleSlider.value()

                        calculateByteString(colorMode="ANM",\
                                            effect=currentEffect,\
                                            bright_min=brightRange[0],\
                                            bright_max=brightRange[1],\
                                            temp=self.colorTempSlider.value(),\
                                            GM=self.GMSlider.value(),\
                                            speed=self.speedSlider.value())
                    elif currentEffect == 7 or currentEffect == 9:
                        calculateByteString(colorMode="ANM",
                                            effect=currentEffect,\
                                            brightness=self.brightSlider.value(),\
                                            hue=self.RGBSlider.value(),\
                                            saturation=self.colorSatSlider.value(),\
                                            speed=self.speedSlider.value())
                    elif currentEffect == 10:
                        calculateByteString(colorMode="ANM",\
                                            effect=currentEffect,\
                                            brightness=self.brightSlider.value(),\
                                            specialOptions=self.specialOptionsChooser.currentIndex(),\
                                            speed=self.speedSlider.value())
                    elif currentEffect == 11:
                        brightRange = self.brightDoubleSlider.value()

                        calculateByteString(colorMode="ANM",\
                                            effect=currentEffect,\
                                            bright_min=brightRange[0],\
                                            bright_max=brightRange[1],\
                                            temp=self.colorTempSlider.value(),\
                                            GM=self.GMSlider.value(),\
                                            speed=self.speedSlider.value(),
                                            sparks=self.sparksSlider.value())
                    elif currentEffect == 12:
                        hueRange = self.RGBDoubleSlider.value()

                        calculateByteString(colorMode="ANM",
                                            effect=currentEffect,\
                                            brightness=self.brightSlider.value(),\
                                            hue_min=hueRange[0],\
                                            hue_max=hueRange[1],\
                                            speed=self.speedSlider.value())
                    elif currentEffect == 13:
                        tempRange = self.colorTempDoubleSlider.value()

                        calculateByteString(colorMode="ANM",\
                                            effect=currentEffect,\
                                            brightness=self.brightSlider.value(),\
                                            temp_min=tempRange[0],\
                                            temp_max=tempRange[1],\
                                            speed=self.speedSlider.value())
                    elif currentEffect == 14:
                        brightRange = self.brightDoubleSlider.value()

                        calculateByteString(colorMode="ANM",\
                                            effect=currentEffect,\
                                            bright_min=brightRange[0],\
                                            bright_max=brightRange[1],\
                                            temp=self.colorTempSlider.value(),\
                                            speed=self.speedSlider.value())
                    elif currentEffect == 15:
                        brightRange = self.brightDoubleSlider.value()

                        calculateByteString(colorMode="ANM",\
                                            effect=currentEffect,\
                                            bright_min=brightRange[0],\
                                            bright_max=brightRange[1],\
                                            hue=self.RGBSlider.value(),\
                                            speed=self.speedSlider.value())
                    elif currentEffect == 16:
                        brightRange = self.brightDoubleSlider.value()

                        calculateByteString(colorMode="ANM",\
                                            effect=currentEffect,\
                                            bright_min=brightRange[0],\
                                            bright_max=brightRange[1],\
                                            temp=self.colorTempSlider.value(),\
                                            GM=self.GMSlider.value(),\
                                            speed=self.speedSlider.value())
                    elif currentEffect == 17:
                        calculateByteString(colorMode="ANM",\
                                            effect=currentEffect,\
                                            brightness=self.brightSlider.value(),\
                                            specialOptions=self.specialOptionsChooser.currentIndex(),\
                                            speed=self.speedSlider.value(),\
                                            sparks=self.sparksSlider.value())
                    elif currentEffect == 18:
                        calculateByteString(colorMode="ANM",\
                                            effect=currentEffect,\
                                            brightness=self.brightSlider.value(),\
                                            specialOptions=self.specialOptionsChooser.currentIndex(),\
                                            speed=self.speedSlider.value())
                else:
                    calculateByteString(colorMode="ANM",\
                                        effect=(currentEffect + 20),\
                                        brightness=self.brightSlider.value())

            self.statusBar.showMessage("Current value: " + updateStatus())                                        
            self.startSend()

        # LEMUR! Check out the turn on value for the Infinity lights
        def turnLightOn(self):
            setPowerBytestring("ON")
            self.statusBar.showMessage("Turning light on")
            self.startSend()

        # LEMUR! Check out the turn off value for the Infinity lights
        def turnLightOff(self):
            setPowerBytestring("OFF")
            self.statusBar.showMessage("Turning light off")
            self.startSend()

        # ==============================================================
        # FUNCTIONS TO RETURN / MODIFY VALUES RUNNING IN THE GUI
        # ==============================================================

        # RETURN THE ROW INDEXES THAT ARE CURRENTLY HIGHLIGHTED IN THE TABLE VIEW
        def selectedLights(self, returnExtraInformation = False):
            selectionList = []
            infinityStatus = False
            tempBounds = [3200, 5600] # the boundaries of color temps this selection can accomplish

            if threadAction != "quit":
                currentSelection = self.lightTable.selectionModel().selectedRows()

                for a in range(len(currentSelection)):
                    selectionList.append(currentSelection[a].row()) # add the row index of the nth selected light to the selectionList array

                if returnExtraInformation == True:
                    # check to see if any lights in the selection are Infinity control lights
                    for a in range(len(selectionList)):
                        if availableLights[selectionList[a]][8] == True:
                            infinityStatus = True
                            break
                    
                    # get the min and max CCT bounds for the current selection
                    for a in range(len(selectionList)):
                        currentBounds = availableLights[selectionList[a]][4]
                        
                        if currentBounds[0] < tempBounds[0]:
                            tempBounds[0] = currentBounds[0]

                        if currentBounds[1] > tempBounds[1]:
                            tempBounds[1] = currentBounds[1]

                    tempBounds[0] = int(tempBounds[0] / 100)
                    tempBounds[1] = int(tempBounds[1] / 100)

            if returnExtraInformation == False:
                return selectionList # return the row IDs that are currently selected, or an empty array ([]) otherwise
            else:
                return [selectionList, infinityStatus, tempBounds] # return the row IDs, and a flag whether or not an Infinity light is selected

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
                    # lastSelection = self.selectedLights() # store the current selection to restore it when leaving the control
                    # self.lightTable.clearSelection() # clear the current selection to allow the preset to shine

                    for a in range(len(lightsToHighlight)):
                        for b in range(4):
                            self.lightTable.item(lightsToHighlight[a], b).setBackground(QColor(113, 233, 147)) # set the affected rows the same color as the snapshot button
            else: # if we're exiting a snapshot preset, then reset the color of the affected lights back to white
                lightsToHighlight = self.checkForSnapshotPreset(numOfPreset)
                
                if lightsToHighlight != []:
                    # self.selectRows(lastSelection) # re-highlight the last selected lights on exit

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
                if "GM" in modeArgs:
                    GM = int(modeArgs["GM"])
                else:
                    GM = 50

                self.ColorModeTabWidget.setCurrentIndex(0)

                self.colorTempSlider.setValue(modeArgs["temp"])
                self.brightSlider.setValue(modeArgs["brightness"])
                self.GMSlider.setValue(GM)

                self.computeValues()
            elif modeArgs["colorMode"] == "HSI":
                self.ColorModeTabWidget.setCurrentIndex(1)

                self.RGBSlider.setValue(modeArgs["hue"])
                self.colorSatSlider.setValue(modeArgs["saturation"])
                self.brightSlider.setValue(modeArgs["brightness"])

                self.computeValues()
            elif modeArgs["colorMode"] == "ANM":
                self.ColorModeTabWidget.setCurrentIndex(2)
                FX = modeArgs["effect"]

                if FX < 20:
                    self.setInfinityMode(True)
                    self.effectChooser.setCurrentIndex(modeArgs["effect"] - 1)
                else:
                    self.setInfinityMode(False)
                    self.effectChooser.setCurrentIndex(modeArgs["effect"] - 21)
                
                if "brightness" in modeArgs:
                    self.brightSlider.setValue(modeArgs["brightness"])
                if "bright_min" in modeArgs:
                    self.brightDoubleSlider.setValue("left", modeArgs["bright_min"])
                if "bright_max" in modeArgs:
                    self.brightDoubleSlider.setValue("right", modeArgs["bright_max"])                
                if "temp" in modeArgs:
                    self.colorTempSlider.setValue(modeArgs["temp"])
                if "temp_min" in modeArgs:
                    self.colorTempDoubleSlider.setValue("left", modeArgs["temp_min"])
                if "temp_max" in modeArgs:
                    self.colorTempDoubleSlider.setValue("right", modeArgs["temp_max"])
                if "GM" in modeArgs:
                    self.GMSlider.setValue(modeArgs["GM"])
                if "hue" in modeArgs:
                    self.RGBSlider.setValue(modeArgs["hue"])
                if "hue_min" in modeArgs:
                    self.RGBDoubleSlider.setValue("left", modeArgs["hue_min"])
                if "hue_max" in modeArgs:
                    self.RGBDoubleSlider.setValue("right", modeArgs["hue_max"])
                if "saturation" in modeArgs:
                    self.colorSatSlider.setValue(modeArgs["saturation"])
                if "speed" in modeArgs:
                    self.speedSlider.setValue(modeArgs["speed"])
                if "sparks" in modeArgs:
                    self.sparksSlider.setValue(modeArgs["sparks"])
                if "specialOptions" in modeArgs:
                    self.specialOptionsChooser.setCurrentIndex(modeArgs["specialOptions"])

                self.effectChanged(FX)

except NameError:
    pass # could not load the GUI, but we have already logged an error message

def setUpAsyncio():
    global asyncioEventLoop

    try:
        asyncioEventLoop = asyncio.get_running_loop()
    except RuntimeError:
        asyncioEventLoop = asyncio.new_event_loop()

    asyncio.set_event_loop(asyncioEventLoop)

def saveLightPrefs(lightID, deleteFile = False): # save a sidecar file with the preferences for a specific light
    createLightPrefsFolder() # create the light_prefs folder if it doesn't exist

    # GET THE CUSTOM FILENAME FOR THIS FILE, NOTED FROM THE MAC ADDRESS OF THE CURRENT LIGHT
    exportFileName = splitMACAddress(availableLights[lightID][0].address) # take the colons out of the MAC address
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
                    
        toolTipBuilder.append(updateStatus(customValue=customLightPresets[numOfPreset][a][1]))

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

            sendValue = translateByteString(customLightPresets[numOfPreset][0][1])
            
            if updateGUI == True:
                mainWindow.setUpGUI(**sendValue)
            else:
                computedValue = calculateByteString(True, **sendValue)
            
            if updateGUI == False:
                for b in range(len(availableLights)):
                    changedLights.append(b) # add each light to changedLights
                    availableLights[b][3] = computedValue # set each light's "last" parameter to the computed value above

        else: # we're looking at a snapshot preset, so see if any of those lights are available to change
            currentLight = returnLightIndexesFromMacAddress(customLightPresets[numOfPreset][a][0])

            if currentLight != []: # if we have a match
                # the original snapshot presets had options turning the lights off by having a mode ID# 3 higher than the
                # normal mode number - take this into consideration - maybe a 2nd array element? [numOfPreset][a][2] ?
                # or store the "120" as "121" ?

                availableLights[currentLight[0]][3] = customLightPresets[numOfPreset][a][1]
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
        customLightPresets[numOfPreset] = [[-1, sendValue]]
    elif presetType == "snapshot":
        listConstructor = []
        
        if selectedLights == []: # add all the lights to the snapshot preset
            for a in range(len(availableLights)): 
                listConstructor.append([availableLights[a][0].address, availableLights[a][3]])
        else: # add only the selected lights to the snapshot preset
            for a in range(len(selectedLights)):
                listConstructor.append([availableLights[selectedLights[a]][0].address, availableLights[selectedLights[a]][3]])
        
        print(listConstructor)

        customLightPresets[numOfPreset] = listConstructor

def customPresetToString(numOfPreset):
    returnedString = "customPreset" + str(numOfPreset) + "=" # the string to return back to the saving mechanism
    numOfLights = len(customLightPresets[numOfPreset]) # how many lights this custom preset holds values for

    for a in range(numOfLights): # get all of the lights stored in this preset (or 1 if it's a global)
        returnedString += str(customLightPresets[numOfPreset][a][0]) # get the MAC address/UUID of the nth light
        returnedString += "|" + "|".join(map(str,customLightPresets[numOfPreset][a][1])) # get a string for the rest of this current array
      
        if numOfLights > 1 and a < (numOfLights - 1): # if there are more lights left, then add a semicolon to differentiate that
            returnedString += ";"

    return returnedString

def loadCustomPresets():
    global customLightPresets

    # READ THE PREFERENCES FILE INTO A LIST
    with open(customLightPresetsFile, mode="r", encoding="utf-8") as fileToOpen:
        customPresets = fileToOpen.read().split("\n")

    for a in range(0, len(customPresets)):
        currentLine = customPresets[a][14:].split(";")
        paramsList = []
        
        for b in range(len(currentLine)):
            currentParams = currentLine[b].split("|")

            # convert all values after the MAC address to integer values
            for c in range(1, len(currentParams)):
                currentParams[c] = int(currentParams[c])

            # add all of the current light's parameters to the parameters list
            paramsList.append([currentParams[0], currentParams[1:]])

        # add the params list to the appropriate button
        if "customPreset0=" in customPresets[a]:
            customLightPresets[0] = paramsList
        elif "customPreset1=" in customPresets[a]:
            customLightPresets[1] = paramsList
        elif "customPreset2=" in customPresets[a]:
            customLightPresets[2] = paramsList
        elif "customPreset3=" in customPresets[a]:
            customLightPresets[3] = paramsList
        elif "customPreset4=" in customPresets[a]:
            customLightPresets[4] = paramsList
        elif "customPreset5=" in customPresets[a]:
            customLightPresets[5] = paramsList
        elif "customPreset6=" in customPresets[a]:
            customLightPresets[6] = paramsList
        elif "customPreset7=" in customPresets[a]:
            customLightPresets[7] = paramsList
            
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

def splitMACAddress(MACAddress, returnInt = False):
    MACAddress = MACAddress.split(":")

    if returnInt == False:
        return MACAddress # return the MAC address as a list
    else: # return the integer values of each part of the MAC address
        MACReturn = []

        if len(MACAddress) == 6:
            for part in MACAddress:
                MACReturn.append(int(part, 16))
        else:
            pass # if the MAC address doesn't correctly split, we need to deal with that here

        return MACReturn

# CALCULATE THE BYTESTRING TO SEND TO THE LIGHT
def calculateByteString(returnValue = False, **modeArgs):
    if modeArgs["colorMode"] == "CCT":
        # We're in CCT (color balance) mode
        computedValue = [120, 135, 2]

        computedValue.append(int(modeArgs["brightness"])) # the brightness value
        computedValue.append(int(modeArgs["temp"])) # the color temp value, ranging from 32(00K) to 85(00)K - some lights (like the SL-80) can go as high as 8500K
        computedValue.append(int(modeArgs["GM"])) # the GM compensation value, from -50 to 50
    elif modeArgs["colorMode"] == "HSI":
        # We're in HSI (any color of the spectrum) mode
        computedValue = [120, 134, 4]

        computedValue.append(int(modeArgs["hue"]) & 255) # hue value, up to 255
        computedValue.append((int(modeArgs["hue"]) & 65280) >> 8) # offset value, computed from above value
        computedValue.append(int(modeArgs["saturation"])) # saturation value
        computedValue.append(int(modeArgs["brightness"])) # intensity value
    elif modeArgs["colorMode"] == "ANM":
        # We're in ANM (animation) mode
        computedValue = [120, 136, 2]

        if "effect" in modeArgs:
            effect = int(modeArgs["effect"])
        if "brightness" in modeArgs:
            brightness = int(modeArgs["brightness"])
        if "bright_min" in modeArgs:
            bright_min = int(modeArgs["bright_min"])
        if "bright_max" in modeArgs:
            bright_max = int(modeArgs["bright_max"])
        if "temp" in modeArgs:
            temp = int(modeArgs["temp"])
        if "temp_min" in modeArgs:
            temp_min = int(modeArgs["temp_min"])
        if "temp_max" in modeArgs:
            temp_max = int(modeArgs["temp_max"])
        if "GM" in modeArgs:
            GM = int(modeArgs["GM"])
        if "hue" in modeArgs:
            hue = int(modeArgs["hue"])
            hue = [hue & 255, (hue & 65280) >> 8]
        if "hue_min" in modeArgs:
            hue_min = int(modeArgs["hue_min"])
            hue_min = [hue_min & 255, (hue_min & 65280) >> 8]
        if "hue_max" in modeArgs:
            hue_max = int(modeArgs["hue_max"])
            hue_max = [hue_max & 255, (hue_max & 65280) >> 8]
        if "saturation" in modeArgs:
            saturation = int(modeArgs["saturation"])
        if "speed" in modeArgs:
            speed = int(modeArgs["speed"])
        if "sparks" in modeArgs:
            sparks = int(modeArgs["sparks"])
        if "specialOptions" in modeArgs:
            specialOptions = int(modeArgs["specialOptions"])

        if effect == 1: # Lightning
            computedValue.extend([effect, brightness, temp, speed])
        elif effect == 2 or effect == 3 or effect == 6 or effect == 8: # Paparazzi, Defective Bulb, CCT Flash or CCT Pulse
            computedValue.extend([effect, brightness, temp, GM, speed])
        elif effect == 4: # Explosion
            computedValue.extend([effect, brightness, temp, GM, speed, sparks])
        elif effect == 5: # Welding
            computedValue.extend([effect, bright_min, bright_max, temp, GM, speed])
        elif effect == 7 or effect == 9: # Hue Flash or Hue Pulse
            computedValue.extend([effect, brightness, hue[0], hue[1], saturation, speed])
        elif effect == 10: # Cop Car
            computedValue.extend([effect, brightness, specialOptions, speed])
        elif effect == 11: # Candlelight
            computedValue.extend([effect, bright_min, bright_max, temp, GM, speed, sparks])
        elif effect == 12: # Hue Loop
            computedValue.extend([effect, brightness, hue_min[0], hue_min[1], hue_max[0], hue_max[1], speed])
        elif effect == 13: # CCT Loop
            computedValue.extend([effect, brightness, temp_min, temp_max, speed])
        elif effect == 14: # INT Loop (CCT)
            computedValue.extend([14, 0, bright_min, bright_max, 0, 0, temp, speed])
        elif effect == 15: # INT Loop (HSI)
            computedValue.extend([14, 1, bright_min, bright_max, hue[0], hue[1], 0, speed])
        elif effect == 16: # TV Screen (effect is #15)
            computedValue.extend([15, bright_min, bright_max, temp, GM, speed])
        elif effect == 17: # Fireworks (effect is #16)
            computedValue.extend([16, brightness, specialOptions, speed, sparks])
        elif effect == 18: # Party (effect is #17)
            computedValue.extend([17, brightness, specialOptions, speed])

        # OLD EFFECT PARAMETERS RETROFITTED WITH INFINITY COMMANDS
        elif effect == 21: # OLD EFFECT: Cop Car
            computedValue.extend([effect, brightness, 3, 5])
        elif effect == 22: # OLD EFFECT: Ambulance
            computedValue.extend([effect, brightness, 3, 5]) # find matching Infinity preset that looks like old style FX
        elif effect == 23: # OLD EFFECT: Fire Engine
            computedValue.extend([effect, brightness, 3, 5]) # find matching Infinity preset that looks like old style FX
        elif effect == 24: # OLD EFFECT: Fireworks
            computedValue.extend([effect, brightness, 2, 5, 5])
        elif effect == 25: # OLD EFFECT: Party
            computedValue.extend([effect, brightness, 2, 5])
        elif effect == 26: # OLD EFFECT: Candlelight
            computedValue.extend([effect, 10, brightness, 56, 50, 5, 5])
        elif effect == 27: # OLD EFFECT: Lightning
            computedValue.extend([effect, brightness, 32, 5])
        elif effect == 28: # OLD EFFECT: Paparazzi
            computedValue.extend([effect, brightness, 32, 50, 5])
        elif effect == 29: # OLD EFFECT: TV Screen
            computedValue.extend([effect, 10, brightness, 32, 50, 5])
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
    newValueBRI = [120, 130, 1, sendValue[3]]
    
    # CALCULATE HUE ONLY PARAMETER FROM MAIN PARAMETER
    newValueHUE = [120, 131, 1, sendValue[4]]
    
    if CCTSlider == -1: # return both newly computed values
        return [newValueBRI, newValueHUE]
    elif CCTSlider == 1: # return only the color temperature value
        return newValueHUE
    elif CCTSlider == 2: # return only the brightness value
        return newValueBRI

# CALCULATE THE CHECKSUM FROM A BYTESTRING AND ADD IT TO THE END OF THE LIST
def tagChecksum(sendValue):
    returnArray = []
    checkSum = 0
    
    for a in range(len(sendValue)):
        if sendValue[a] < 0:
            checkSum = checkSum + int(sendValue[a] + 256)
        else:
            checkSum = checkSum + int(sendValue[a])

        returnArray.append(sendValue[a])

    checkSum = checkSum & 255
    returnArray.append(checkSum)
    return returnArray

def setPowerBytestring(onOrOff):
    global sendValue

    if onOrOff == "ON":
        sendValue = [120, 129, 1, 1, 251] # return the "turn on" bytestring
    else:
        sendValue = [120, 129, 1, 2, 252] # return the "turn off" bytestring

def translateByteString(customValue = None):
    if customValue == None:
        customValue = sendValue

    translatedByteString = {}

    if customValue[1] == 134:
        translatedByteString["colorMode"] = "HSI"
        translatedByteString["hue"] = customValue[3] + (256 * customValue[4])
        translatedByteString["saturation"] = customValue[5]
        translatedByteString["brightness"] = customValue[6]
    elif customValue[1] == 135:
        translatedByteString["colorMode"] = "CCT"
        translatedByteString["brightness"] = customValue[3]
        translatedByteString["temp"] = customValue[4]
        translatedByteString["GM"] = customValue[5]
    elif customValue[1] == 136:
        FX = customValue[3]

        translatedByteString["colorMode"] = "ANM"
        translatedByteString["effect"] = FX

        if FX == 1:
            translatedByteString["brightness"] = customValue[4]
            translatedByteString["temp"] = customValue[5]
            translatedByteString["speed"] = customValue[6]
        elif FX == 2 or FX == 3 or FX == 6 or FX == 8:
            translatedByteString["brightness"] = customValue[4]
            translatedByteString["temp"] = customValue[5]
            translatedByteString["GM"] = customValue[6]
            translatedByteString["speed"] = customValue[7]
        elif FX == 4:
            translatedByteString["brightness"] = customValue[4]
            translatedByteString["temp"] = customValue[5]
            translatedByteString["speed"] = customValue[6]
        elif FX == 5:
            translatedByteString["bright_min"] = customValue[4]
            translatedByteString["bright_max"] = customValue[5]
            translatedByteString["temp"] = customValue[6]
            translatedByteString["GM"] = customValue[7]
            translatedByteString["speed"] = customValue[8]
        elif FX == 7 or FX == 9:
            translatedByteString["brightness"] = customValue[4]
            translatedByteString["hue"] = customValue[5] + (256 * customValue[6])
            translatedByteString["saturation"] = customValue[7]
            translatedByteString["speed"] = customValue[8]
        elif FX == 10:
            translatedByteString["brightness"] = customValue[4]
            translatedByteString["specialOptions"] = customValue[5]
            translatedByteString["speed"] = customValue[6]
        elif FX == 11:
            translatedByteString["bright_min"] = customValue[4]
            translatedByteString["bright_max"] = customValue[5]
            translatedByteString["temp"] = customValue[6]
            translatedByteString["GM"] = customValue[7]
            translatedByteString["speed"] = customValue[8]
            translatedByteString["sparks"] = customValue[9]
        elif FX == 12:
            translatedByteString["brightness"] = customValue[4]
            translatedByteString["hue_min"] = customValue[5] + (256 * customValue[6])
            translatedByteString["hue_max"] = customValue[7] + (256 * customValue[8])
            translatedByteString["speed"] = customValue[9]
        elif FX == 13:
            translatedByteString["brightness"] = customValue[4]
            translatedByteString["temp_min"] = customValue[5]
            translatedByteString["temp_max"] = customValue[6]
            translatedByteString["speed"] = customValue[7]
        elif FX == 14:
            print(customValue)
            loopMode = customValue[4] # get whether we're in CCT or HSI mode with loopMode

            translatedByteString["bright_min"] = customValue[5]
            translatedByteString["bright_max"] = customValue[6]
    
            if loopMode == 0: # if we're in CCT mode
                translatedByteString["effect"] = 14
                translatedByteString["temp"] = customValue[9]
            else: # we're in HSI mode
                translatedByteString["effect"] = 15
                translatedByteString["hue"] = customValue[7] + (256 * customValue[8]) # convert this from 2 values

            translatedByteString["speed"] = customValue[10]
        elif FX == 15:
            translatedByteString["effect"] = 16
            translatedByteString["bright_min"] = customValue[4]
            translatedByteString["bright_max"] = customValue[5]
            translatedByteString["temp"] = customValue[6]
            translatedByteString["GM"] = customValue[7]
            translatedByteString["speed"] = customValue[8]
        elif FX == 16:
            translatedByteString["effect"] = 17
            translatedByteString["brightness"] = customValue[4]
            translatedByteString["specialOptions"] = customValue[5]
            translatedByteString["speed"] = customValue[6]
            translatedByteString["sparks"] = customValue[7]
        elif FX == 17:
            translatedByteString["effect"] = 18
            translatedByteString["brightness"] = customValue[4]
            translatedByteString["specialOptions"] = customValue[5]
            translatedByteString["speed"] = customValue[6]
        else:
            if FX == 26 or FX == 29:
                translatedByteString["brightness"] = customValue[5]
            else:
                translatedByteString["brightness"] = customValue[4]

    return translatedByteString
    
# MAKE CURRENT BYTESTRING INTO A STRING OF HEX CHARACTERS TO SHOW THE CURRENT VALUE BEING GENERATED BY THE PROGRAM
def updateStatus(splitString = "", customValue = None):
    if customValue == None:
        statusInfo = translateByteString(sendValue)
    else:
        statusInfo = translateByteString(customValue)

    if splitString != "":
        splitString = "\n"

    returnStatus = "(" + statusInfo["colorMode"] + " Mode):" + splitString

    if statusInfo["colorMode"] == "HSI":
        returnStatus += "  H: " + str(statusInfo["hue"]) + u'\N{DEGREE SIGN}'
        returnStatus += " / S: " + str(statusInfo["saturation"])
        returnStatus += " / I: " + str(statusInfo["brightness"])
    elif statusInfo["colorMode"] == "CCT":
        returnStatus += "  TEMP: " + str(statusInfo["temp"]) + "00K"
        returnStatus += " / BRI: " + str(statusInfo["brightness"])
        returnStatus += " / GM: " + str(statusInfo["GM"] - 50)
    elif statusInfo["colorMode"] == "ANM":
        returnStatus += "  FX: " + str(statusInfo["effect"])
        # returnStatus += " / BRI:" + str(statusInfo["brightness"])

    return returnStatus

# Use this class to store information in a format that plays nicer with Bleak > 0.19
class UpdatedBLEInformation:
    def __init__(self, name, address, rssi, HWMACaddr = None):
        self.name = name # the corrected name of this device (SL90 Pro)
        self.realname = name # the real name of this device (NW-2342520000FFF, etc.)
        self.address = address # the MAC address (or in the case of MacOS, the GUID)
        self.rssi = rssi # the signal level of this device
        self.HWMACaddr = HWMACaddr # the exact MAC address (needed for MacOS) of this device
        
# FIND NEW LIGHTS
async def findDevices():
    global availableLights
    printDebugString("Searching for new lights")
    currentScan = [] # add all the current scan's lights detected to a standby array (to check against the main one)

    bleak_ver = ilm.version('bleak').split(".") # the version of Bleak that we're using
    devices = [] # master list of found devices (changed for getting MacOS MAC addresses)

    # after Bleak 0.19, RSSI information is stored in an Advertisement variable 
    # instead of the BLEDevice itself, so it needs to be obtained differently!
    if int(bleak_ver[0]) == 0 and int(bleak_ver[1]) < 19:
        device_scan = await BleakScanner.discover() # scan all available Bluetooth devices nearby

        for d in device_scan:
            devices.append(UpdatedBLEInformation(d.name, d.address, d.rssi))
    else: 
        
        device_scan = await BleakScanner.discover(return_adv=True) # scan all available Bluetooth devices nearby and return Advertisement data

        for device, adv_data in device_scan.values():
            devices.append(UpdatedBLEInformation(device.name, device.address, adv_data.rssi))
        
    for d in devices: # go through all of the devices Bleak just found
        if d.address in whiteListedMACs: # if the MAC address is in the list of whitelisted addresses, add this device
            printDebugString("Matching whitelisted address found - " + returnMACname() + " " + d.address + ", adding to the list")
            currentScan.append(d)
        else: # if this device is not whitelisted, check to see if it's valid (contains "NEEWER" in the name)
            if d.name != None:
                acceptedPrefixes = ["NEEWER", "NW-", "SL", "NWR"]

                for a in range(len(acceptedPrefixes)):
                    if acceptedPrefixes[a] in d.name:
                        d.name = getCorrectedName(d.name) # fix the "newer" light names, like NW-20220057 with their correct names, like SL90 Pro
                        currentScan.append(d)
                        break

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

            if len(customPrefs) == 4: # we need to rename the light and set up CCT and color temp range
                availableLights.append([currentScan[a], "", customPrefs[0], [120, 135, 2, 50, 56, 50], customPrefs[1], customPrefs[2], True, ["---", "---"], customPrefs[3]]) # add it to the global list
            elif len(customPrefs) == 5: # same as above, but we have previously stored parameters, so add them in as well
                availableLights.append([currentScan[a], "", customPrefs[0], customPrefs[3], customPrefs[1], customPrefs[2], True, ["---", "---"], customPrefs[4]]) # add it to the global list

    if threadAction != "quit":
        return "" # once the device scan is over, set the threadAction to nothing
    else: # if we're requesting that we quit, then just quit
        return "quit"

def getCustomLightPrefs(MACAddress, lightName = ""):
    customPrefsPath = splitMACAddress(MACAddress)
    customPrefsPath = os.path.dirname(os.path.abspath(sys.argv[0])) + os.sep + "light_prefs" + os.sep + "".join(customPrefsPath)

    defaultPrefs = getLightSpecs(lightName)

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
            customPrefs[1] = defaultPrefs[1]
        else: # we have a new version of preferences that directly specify the color temperatures            
            colorTemps = customPrefs[1].replace(" ", "").split(",")

            # TEST TO MAKE SURE VALUES RETURNED FROM colorTemps ARE VALID INTEGER VALUES
            if len(colorTemps) == 2: # we NEED to have 2 values in the list, or it's not a correct declaration (min,max)
                customPrefs[1] = [testValid("custom_preset_range_min", colorTemps[0], defaultPrefs[0], 1000, 5600, True),
                                  testValid("custom_preset_range_max", colorTemps[1], defaultPrefs[1], 1000, 10000, True)]
            else: # so if we have a different number of elements, we're wrong - revert to defaults
                printDebugString("Custom color range defined in preferences is incorrect - falling back to default values!")
                customPrefs[1] = defaultPrefs[1]

        if customPrefs[2] == "True":
            customPrefs[2] = True # convert "True" as a string to an actual boolean value of True
        elif customPrefs[2] == "False":
            customPrefs[2] = False # convert "False" as a string to an actual boolean value of False
        else: # if we have no value, then get the default value for CCT enabling
            customPrefs[2] = defaultPrefs[2]

        if len(customPrefs) == 4: # if we have a 4th element (the last used parameters), then load them here
            customPrefs[3] = customPrefs[3].replace(" ", "").split(",") # split the last params into a list

            for a in range(len(customPrefs[3])): # convert the string values to ints
                customPrefs[3][a] = int(customPrefs[3][a])

        customPrefs.append(defaultPrefs[3]) # append the Infinity flag to the custom prefs list

        return customPrefs
    else: # if there is no custom preferences file, still check the name against a list of per-light parameters
        return getLightSpecs(lightName) # get the factory default settings for this light

# GET A MORE CORRECT VERSION OF THE NEWER LIGHT NAMES
def getCorrectedName(lightName):
    newLightNames = [
        ["20200015", "RGB1"], ["20200037", "SL90"], ["20200049", "RGB1200"], ["20210006", "Apollo 150D"],
        ["20210007", "RGB C80"], ["20210012", "CB60 RGB"], ["20210018", "BH-30S RGB"], ["20210034", "MS60B"],
        ["20210035", "MS60C"], ["20210036", "TL60 RGB"], ["20210037", "CB200B"], ["20220014", "CB60B"],
        ["20220016", "PL60C"], ["20220035", "MS150B"], ["20220041", "AS600B"], ["20220043", "FS150B"],
        ["20220046", "RP19C"],  ["20220051", "CB100C"],  ["20220055", "CB300B"], ["20220057", "SL90 Pro"],
        ["20230021", "BH-30S RGB"], ["20230022", "HS60B"], ["20230025", "RGB1200"], ["20230031", "TL120C"],
        ["20230050", "FS230 5600K"], ["20230051", "FS230B"], ["20230052", "FS150 5600K"], ["20230064", "TL60 RGB"],
        ["20230080", "MS60C"], ["20230092", "RGB1200"]
    ]

    for a in range(len(newLightNames)):
        if newLightNames[a][0] in lightName:
            lightName = newLightNames[a][1]
            break

    return lightName

# RETURN THE DEFAULT FACTORY SPECIFICATIONS FOR LIGHTS
def getLightSpecs(lightName, returnParam = "all"):
    # the first section of lights here are LED only (can't use HSI), and the 2nd section are HSI-capable lights
    # listed with their name, the max and min color temps available to use in CCT mode, HSI only (True) or not (False)
    # and Infinity mode command structure needed (most False, use this for the newest series of lights)
    masterNeewerLightList = [
        ["Apollo", 5600, 5600, True, False], ["GL1", 2900, 7000, True, False], ["NL140", 3200, 5600, True, False],
        ["SNL1320", 3200, 5600, True, False], ["SNL1920", 3200, 5600, True, False], ["SNL480", 3200, 5600, True, False],
        ["SNL530", 3200, 5600, True, False], ["SNL660", 3200, 5600, True, False], ["SNL960", 3200, 5600, True, False],
        ["SRP16", 3200, 5600, True, False], ["SRP18", 3200, 5600, True, False], ["WRP18", 3200, 5600, True, False],
        ["ZRP16", 3200, 5600, True, False], 
        ["MS60B", 2700, 6500, True, True],
        ["BH-30S RGB", 2500, 10000, False, True], ["CB60 RGB", 2500, 6500, False, True], ["CL124", 2500, 10000, False, False],
        ["RGB C80", 2500, 10000, False, True], ["RGB CB60", 2500, 10000, False, True], ["RGB1000", 2500, 10000, False, True],
        ["RGB1200", 2500, 10000, False, True], ["RGB140", 2500, 10000, False, True], ["RGB168", 2500, 8500, False, False],
        ["RGB176 A1", 2500, 10000, False, False], ["RGB512", 2500, 10000, False, True], ["RGB800", 2500, 10000, False, True],
        ["SL90", 2500, 10000, False, True], ["SL90 Pro", 2500, 10000, False, True], ["RGB1", 3200, 5600, False, True],
        ["RGB176", 3200, 5600, False, False], ["RGB18", 3200, 5600, False, False], ["RGB190", 3200, 5600, False, False], 
        ["RGB450", 3200, 5600, False, False], ["RGB480", 3200, 5600, False, False], ["RGB530PRO", 3200, 5600, False, False], 
        ["RGB530", 3200, 5600, False, False], ["RGB650", 3200, 5600, False, False], ["RGB660PRO", 3200, 5600, False, False], 
        ["RGB660", 3200, 5600, False, False], ["RGB960", 3200, 5600, False, False], ["RGB-P200", 3200, 5600, False, False], 
        ["RGB-P280", 3200, 5600, False, False], ["SL70", 3200, 8500, False, False], ["SL80", 3200, 8500, False, False], 
        ["ZK-RY", 5600, 5600, False, False]
    ]
    
    for a in range(len(masterNeewerLightList)): # scan the list of preset specs above to find the current light in them
        # the default list of preferences - no custom name, a color temp range from 3200-5600K, and RGB not restricted (False)
        # if we don't find the name of the light in the master list, we just return these default parameters
        customPrefs = ["", [3200, 5600], False, False]

        # check the master list to see if the current light is found - if it is, then change the prefs to reflect the light's spec
        if masterNeewerLightList[a][0] in lightName:
            # customPrefs[0] = masterNeewerLightList[a][0] # the name of the light (for testing purposes)
            customPrefs[1] = [masterNeewerLightList[a][1], masterNeewerLightList[a][2]] # the HSI color temp range
            customPrefs[2] = masterNeewerLightList[a][3] # whether or not to allow RGB commands
            customPrefs[3] = masterNeewerLightList[a][4] # whether or not this light uses Infinity mode
            break # stop looking for the light!

    if returnParam == "all": # we want to return all information (the default)
        return customPrefs
    elif returnParam == "temp": # we only want to return color temp ranges for this light
        return customPrefs[1]
    elif returnParam == "CCT": # we only want to return CCT-only status for this light
        return customPrefs[2]
    elif returnParam == "Infinity": # we only want to return the Infinity mode for this light
        return customPrefs[3]

# CONNECT (LINK) TO A LIGHT
async def connectToLight(selectedLight, updateGUI=True):
    global availableLights
    isConnected = False # whether or not the light is connected
    returnValue = "" # the value to return to the thread (in GUI mode, a string) or True/False (in CLI mode, a boolean value)

    lightName = availableLights[selectedLight][0].name # the Name of the light (for status updates)
    lightMAC = availableLights[selectedLight][0].address # the MAC address of the light (to keep track of the light even if the index number changes)

    lightIdx = returnLightIndexesFromMacAddress(lightMAC)[0]
    createNewBleakInstance = False

    # CHECK TO SEE IF A BLEAK OBJECT EXISTS
    if availableLights[lightIdx][1] == "":
        createNewBleakInstance = True
    else: # if the object exists, but nothing is connected to it, then make a new instance
        if not availableLights[lightIdx][1].is_connected:
            createNewBleakInstance = True

    if createNewBleakInstance == True: # FILL THE [1] ELEMENT OF THE availableLights ARRAY WITH A NEW BLEAK CONNECTION OBJECT
        availableLights[lightIdx][1] = BleakClient(availableLights[lightIdx][0].address)
        await asyncio.sleep(0.25) # wait just a short time before trying to connect

    # TRY TO CONNECT TO THE LIGHT SEVERAL TIMES BEFORE GIVING UP THE LINK
    currentAttempt = 1

    while isConnected == False and currentAttempt <= maxNumOfAttempts:
        if threadAction != "quit":
            try:
                if not availableLights[lightIdx][1].is_connected: # if the current device isn't linked to Bluetooth
                    printDebugString("Attempting to link to light [" + lightName + "] " + returnMACname() + " " + lightMAC + " (Attempt " + str(currentAttempt) + " of " + str(maxNumOfAttempts) + ")")
                    isConnected = await availableLights[lightIdx][1].connect() # try connecting it (and return the connection status)
                else:
                    isConnected = True # the light is already connected, so mark it as being connected
            except Exception as e:
                printDebugString("Error linking to light [" + lightName + "] " + returnMACname() + " " + lightMAC)
              
                if updateGUI == True:
                    if currentAttempt < maxNumOfAttempts:
                        mainWindow.setTheTable(["", "", "NOT\nLINKED", "There was an error connecting to the light, trying again (Attempt " + str(currentAttempt + 1) + " of " + str(maxNumOfAttempts) + ")..."], lightIdx) # there was an issue connecting this specific light to Bluetooth, so show that
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

            if availableLights[selectedLight][8] == True: # we're an Infnity light, we need the physical MAC address
                printDebugString("Checking for Hardware MAC address on Infinity light [" + lightName + "] " + returnMACname() + " " + lightMAC)

                if platform.system() == "Darwin": # we're on MacOS, so this needs a little finesse...
                    # run the System Profiler and get the Bluetooth specific devices
                    command = ["system_profiler", "SPBluetoothDataType"]
                    output = run(command, stdout=PIPE, universal_newlines=True)
                    # get the location in the above output dealing with the specific light we're working with
                    light_offset = output.stdout.find(availableLights[selectedLight][0].realname)
                    # find the address adjacent from the above location
                    address_offset = output.stdout.find("Address: ", light_offset)
                    # clip out the MAC address itself
                    output_parse = output.stdout[address_offset + 9:address_offset + 26]

                    availableLights[selectedLight][0].HWMACaddr = output_parse
                else: # we're on a system that uses MAC addresses, so just duplicate the information
                    availableLights[selectedLight][0].HWMACaddr = availableLights[selectedLight][0].address
                
                printDebugString("Found Hardware MAC address: " + availableLights[selectedLight][0].HWMACaddr)

            if updateGUI == True:
                mainWindow.setTheTable(["", "", "LINKED", "Waiting to send..."], lightIdx) # if it's successful, show that in the table
            else:
                returnValue = True  # if we're in CLI mode, and there is no error connecting to the light, return True
        else:
            if updateGUI == True:
                mainWindow.setTheTable(["", "", "NOT\nLINKED", "There was an error connecting to the light"], lightIdx) # there was an issue connecting this specific light to Bluetooh, so show that

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
                    currentLightIdx = int(selectedLights[a])

                    # THIS SECTION IS FOR LOADING SNAPSHOT PRESET POWER STATES
                    if useGlobalValue == False: # if we're forcing the lights to use their stored parameters, then load that in here
                        # LEMUR! This is the code that before turned lights on or off during snapshot presets - take a look at this!
                        '''
                        if availableLights[currentLightIdx][3][0] == 0: # we want to turn the light off
                            availableLights[currentLightIdx][3][0] = 120 # reset the light's value to the normal value
                            currentSendValue = [120, 129, 1, 2, 252] # set the send value to turn the light off downstream
                        else: # we want to turn the light on and run a snapshot preset
                            await availableLights[currentLightIdx][1].write_gatt_char(setLightUUID, bytearray([120, 129, 1, 1, 251]), False) # force this light to turn on
                            availableLights[currentLightIdx][6] = True # set the ON flag of this light to True
                            await asyncio.sleep(0.05)
                        '''
                        currentSendValue = availableLights[currentLightIdx][3] # set the send value to set the preset downstream
                       
                    print(f'Current Send Value: {currentLightIdx} / {currentSendValue}')
                    
                    if availableLights[currentLightIdx][1] != "": # if a Bleak connection is there
                        try:
                            if availableLights[currentLightIdx][5] == True: # if we're using the old style of light
                                if currentSendValue[1] == 135: # if we're on CCT mode
                                    if CCTSlider == -1: # and we need to write both HUE and BRI to the light
                                        splitCommands = calculateSeparateBytestrings(currentSendValue) # get both commands from the converter

                                        # WRITE BOTH LUMINANCE AND HUE VALUES TOGETHER, BUT SEPARATELY
                                        await availableLights[currentLightIdx][1].write_gatt_char(setLightUUID, bytearray(tagChecksum(splitCommands[0])), False)
                                        await asyncio.sleep(0.05) # wait 1/20th of a second to give the Bluetooth bus a little time to recover
                                        await availableLights[currentLightIdx][1].write_gatt_char(setLightUUID, bytearray(tagChecksum(splitCommands[1])), False)
                                    else: # we're only writing either HUE or BRI independently
                                        await availableLights[currentLightIdx][1].write_gatt_char(setLightUUID, bytearray(tagChecksum(calculateSeparateBytestrings(currentSendValue))), False)
                                elif currentSendValue[1] == 129: # we're using an old light, but we're either turning the light on or off
                                    await availableLights[currentLightIdx][1].write_gatt_char(setLightUUID, bytearray(tagChecksum(currentSendValue)), False)
                                elif currentSendValue[1] == 134: # we can't use HSI mode with this light, so show that
                                    if updateGUI == True:
                                        mainWindow.setTheTable(["", "", "", "This light can not use HSI mode"], currentLightIdx)
                                    else:
                                        returnValue = True # we successfully wrote to the light (or tried to at least)
                                elif currentSendValue[1] == 136: # we can't use ANM/SCENE mode with this light, so show that
                                    if updateGUI == True:
                                        mainWindow.setTheTable(["", "", "", "This light can not use ANM/SCENE mode"], currentLightIdx)
                                    else:
                                        returnValue = True # we successfully wrote to the light (or tried to at least)
                            else: # we're using a "newer" Neewer light
                                if availableLights[currentLightIdx][8] == True: # we're using the newest kind of light, so we need to tweak the send value
                                    if currentSendValue[1]  == 135: # we're in CCT mode
                                        infinitySendValue = [120, 144, 11]
                                    elif currentSendValue[1] == 134: # we're in HSI mode
                                        infinitySendValue = [120, 143, 11]
                                    elif currentSendValue[1] == 136: # we're in SCENE/FX mode
                                        infinitySendValue = [120, 145, 6 + (len(currentSendValue) - 2)]

                                    infinitySendValue.extend(splitMACAddress(availableLights[currentLightIdx][0].HWMACaddr, True))

                                    # THE LAST 2 VALUES FOR CCT MODE ARE:
                                    # G/M COMPENSATION (WIP)
                                    # ...........4.  NOT REALLY SURE **WHY** IT'S 4, BUT... IT'S 4.
                                    if currentSendValue[1]  == 135: # CCT mode
                                        infinitySendValue.extend([currentSendValue[1],
                                                                currentSendValue[3],
                                                                currentSendValue[4],
                                                                currentSendValue[5],
                                                                4])
                                    elif currentSendValue[1] == 134: # HSI mode
                                        infinitySendValue.extend([currentSendValue[1],
                                                                currentSendValue[3],
                                                                currentSendValue[4],
                                                                currentSendValue[5],
                                                                currentSendValue[6]])
                                    elif currentSendValue[1] == 136: # SCENE/FX mode
                                        infinitySendValue.append(139)
                                        effectNum = currentSendValue[3]

                                        # if the effect we're recalling is an old light effect, then correct the # here
                                        if effectNum > 20:
                                            if effectNum == 21:
                                                infinitySendValue.append(10)
                                            elif effectNum == 22:
                                                infinitySendValue.append(10) # find matching Infinity preset that looks like old style FX
                                            elif effectNum == 23:
                                                infinitySendValue.append(10) # find matching Infinity preset that looks like old style FX
                                            elif effectNum == 24:
                                                infinitySendValue.append(16)
                                            elif effectNum == 25:
                                                infinitySendValue.append(17)
                                            elif effectNum == 26:
                                                infinitySendValue.append(11)
                                            elif effectNum == 27:
                                                infinitySendValue.append(1)
                                            elif effectNum == 28:
                                                infinitySendValue.append(2)
                                            elif effectNum == 29:
                                                infinitySendValue.append(15)
                                        else:
                                            infinitySendValue.append(effectNum)

                                        for i in range(4, len(currentSendValue)):
                                            infinitySendValue.append(currentSendValue[i])
                                    
                                    await availableLights[currentLightIdx][1].write_gatt_char(setLightUUID, bytearray(tagChecksum(infinitySendValue)), False)
                                else:
                                    if currentSendValue[1] == 135: # if we're in CCT mode (and using a normal light), don't take the GM value
                                        await availableLights[currentLightIdx][1].write_gatt_char(setLightUUID, bytearray(tagChecksum(currentSendValue[0:5])), False)
                                    if currentSendValue[1] == 136: # if we're in ANM/scene mode, we need to convert the Infinity command back to a normal command
                                        normalSceneCommand = currentSendValue[0:5]
                                        
                                        # SWITCH THE 2 ELEMENTS TO THE CORRECT ORDER FOR OLDER LIGHTS
                                        currentEffect = normalSceneCommand[3]
                                        normalSceneCommand[3] = normalSceneCommand[4]
                                        normalSceneCommand[4] = currentEffect
                                        
                                        # if the effect we're recalling is an Infinity light preset, then fix the effect # for old lights
                                        if normalSceneCommand[4] < 20:
                                            if normalSceneCommand[4] == 10:
                                                normalSceneCommand[4] = 1
                                            elif normalSceneCommand[4] == 16:
                                                normalSceneCommand[4] = 4
                                            elif normalSceneCommand[4] == 17:
                                                normalSceneCommand[4] = 5
                                            elif normalSceneCommand[4] == 11:
                                                normalSceneCommand[4] = 6
                                            elif normalSceneCommand[4] == 1:
                                                normalSceneCommand[4] = 7
                                            elif normalSceneCommand[4] == 2:
                                                normalSceneCommand[4] = 8
                                            elif normalSceneCommand[4] == 15:
                                                normalSceneCommand[4] = 9
                                            else: # we're in Ambulance or Fire Engine mode
                                                normalSceneCommand[4] = 10 # find matching Infinity preset that looks like old style FX
                                        else: # we're recalling a light preset designed for older lights
                                            normalSceneCommand[4] = normalSceneCommand[4] - 20 # subtract 20 from the effect to get the correct old effect #

                                        await availableLights[currentLightIdx][1].write_gatt_char(setLightUUID, bytearray(tagChecksum(normalSceneCommand)), False)
                                    else:
                                        await availableLights[currentLightIdx][1].write_gatt_char(setLightUUID, bytearray(tagChecksum(currentSendValue)), False)

                            if updateGUI == True:
                                # if we're not looking at an old light, or if we are, we're not in either HSI or ANM modes, then update the status of that light
                                if not (availableLights[currentLightIdx][5] == True and (currentSendValue[1] == 134 or currentSendValue[1] == 136)):
                                    if currentSendValue[1] != 129: # if we're not turning the light on or off
                                        mainWindow.setTheTable(["", "", "", updateStatus(True, currentSendValue)], currentLightIdx)
                                    else: # we ARE turning the light on or off
                                        if currentSendValue[3] == 1: # we turned the light on
                                            availableLights[currentLightIdx][6] = True # toggle the "light on" parameter of this light to ON

                                            changeStatus = mainWindow.returnTableInfo(currentLightIdx, 2).replace("STBY", "ON")
                                            mainWindow.setTheTable(["", "", changeStatus, "Light turned on"], currentLightIdx)

                                        else: # we turned the light off
                                            availableLights[currentLightIdx][6] = False # toggle the "light on" parameter of this light to OFF

                                            changeStatus = mainWindow.returnTableInfo(currentLightIdx, 2).replace("ON", "STBY")
                                            mainWindow.setTheTable(["", "", changeStatus, "Light turned off\nA long period of inactivity may require a re-link to the light"], currentLightIdx)
                            else:
                                returnValue = True # we successfully wrote to the light

                            if currentSendValue[1] != 129: # if we didn't just send a command to turn the light on/off
                                availableLights[currentLightIdx][3] = currentSendValue # store the currenly sent value to recall later
                        except Exception as e:
                            if updateGUI == True:
                                mainWindow.setTheTable(["", "", "", "Error Sending to light!"], currentLightIdx)
                    else: # if there is no Bleak object associated with this light (otherwise, it's been found, but not linked)
                        if updateGUI == True:
                            mainWindow.setTheTable(["", "", "", "Light isn't linked yet, can't send to it"], currentLightIdx)
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
        printDebugString("There was an error communicating with light " + str(currentLightIdx + 1) + " [" + availableLights[currentLightIdx][0].name + "] " + returnMACname() + " " + availableLights[currentLightIdx][0].address)
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
        currentLightToAdd.name = getCorrectedName(currentLightToAdd.name)
        customLightPrefs = getCustomLightPrefs(currentLightToAdd.address, currentLightToAdd.name)

        availableLights = [[currentLightToAdd, "", customLightPrefs[0], [], customLightPrefs[1], customLightPrefs[2], True, [], customLightPrefs[len(customLightPrefs) - 1]]]
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
                    calculateByteString(colorMode=paramsList[3], hue=paramsList[4], saturation=paramsList[5], brightness=paramsList[6])
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
                        writeHTMLSections(self, "quicklinks-timer") # put the quicklinks (with timer) at the top of the page

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

                        # JAVASCRIPT CODE TO CHANGE LIGHT NAMES
                        self.wfile.write(bytes("\n<!-- JAVASCRIPT CODE TO REFRESH PAGE / CHANGE LIGHT NAMES -->\n", "utf-8"))
                        self.wfile.write(bytes("<script language='JavaScript'>\n", "utf-8"))
                        self.wfile.write(bytes("  class webTimer{\n", "utf-8"))
                        self.wfile.write(bytes("    constructor(timeOut) {\n", "utf-8"))
                        self.wfile.write(bytes("      this.isRunning = true; // set to 'running' status on creation\n", "utf-8"))
                        self.wfile.write(bytes("      this.startTime = Date.now(); // the time the timer was first created\n", "utf-8"))
                        self.wfile.write(bytes("      this.timeOut = timeOut; // how long to time down from\n", "utf-8"))
                        self.wfile.write(bytes("    }\n\n", "utf-8"))
                        self.wfile.write(bytes("    stop() { // stop running the timer\n", "utf-8"))
                        self.wfile.write(bytes("      this.isRunning = false;\n", "utf-8"))
                        self.wfile.write(bytes("    }\n\n", "utf-8"))
                        self.wfile.write(bytes("    restart() { // re-start the countdown timer\n", "utf-8"))
                        self.wfile.write(bytes("      this.isRunning = true;\n", "utf-8"))
                        self.wfile.write(bytes("      this.startTime = Date.now(); // re-initialize the counter from the current time\n", "utf-8"))
                        self.wfile.write(bytes("    }\n\n", "utf-8"))
                        self.wfile.write(bytes("    getTime() {\n", "utf-8"))
                        self.wfile.write(bytes("      if (this.isRunning) { // return the amount of time that's left until the timeout\n", "utf-8"))
                        self.wfile.write(bytes("        return Math.round(this.timeOut - (Date.now() - this.startTime) / 1000);\n", "utf-8"))
                        self.wfile.write(bytes("      }\n\n", "utf-8"))
                        self.wfile.write(bytes("      return 42; // we're paused, so return a... decent answer\n", "utf-8"))
                        self.wfile.write(bytes("    }\n", "utf-8"))
                        self.wfile.write(bytes("  }\n\n", "utf-8"))
                        self.wfile.write(bytes("  function checkPageReload(ctElapsed) {\n", "utf-8"))
                        self.wfile.write(bytes("    if (ctElapsed > 0) {\n", "utf-8"))
                        self.wfile.write(bytes("      if (ctElapsed > 1) {\n", "utf-8"))
                        self.wfile.write(bytes("        document.getElementById('refreshDisplay').innerText = 'This page will auto-refresh in ' + ctElapsed + ' seconds';\n", "utf-8"))
                        self.wfile.write(bytes("      } else {\n", "utf-8"))
                        self.wfile.write(bytes("        document.getElementById('refreshDisplay').innerText = 'This page will auto-refresh in 1 second';\n", "utf-8"))
                        self.wfile.write(bytes("      }\n", "utf-8"))
                        self.wfile.write(bytes("    } else {\n", "utf-8"))
                        self.wfile.write(bytes("      location.assign('/NeewerLite-Python/doAction?list');\n", "utf-8"))
                        self.wfile.write(bytes("    }\n", "utf-8"))
                        self.wfile.write(bytes("  }\n\n", "utf-8"))
                        self.wfile.write(bytes("  function editLight(lightNum, lightType, previousName) {\n", "utf-8"))
                        self.wfile.write(bytes("    WT.stop(); // stop the refresh timer\n\n", "utf-8"))
                        self.wfile.write(bytes("    document.getElementById('refreshDisplay').innerText = 'You clicked on an Edit button, so the refresh timer has been stopped.';\n", "utf-8"))
                        self.wfile.write(bytes("    let newName = prompt('What do you want to call light ' + (lightNum+1) + ' (' + lightType + ')?', previousName);\n\n", "utf-8"))
                        self.wfile.write(bytes("    if (!(newName == null || newName == '' || newName == previousName)) {\n", "utf-8"))
                        self.wfile.write(bytes("      window.location.href = 'doAction?custom_name=' + lightNum + '|' + newName + '';\n", "utf-8"))
                        self.wfile.write(bytes("    } else {\n", "utf-8"))
                        self.wfile.write(bytes("      WT.restart(); // restart the countdown timer for refreshing the page\n", "utf-8"))
                        self.wfile.write(bytes("    }\n", "utf-8"))
                        self.wfile.write(bytes("  }\n\n", "utf-8"))
                        self.wfile.write(bytes("  const timeOut = 8; // the delay in seconds before the page reloads\n", "utf-8"))
                        self.wfile.write(bytes("  const WT = new webTimer(timeOut); // the timer to track the above\n\n", "utf-8"))
                        self.wfile.write(bytes("  // The check to see whether or not to refresh the page\n", "utf-8"))
                        self.wfile.write(bytes("  setInterval(() => {\n", "utf-8"))
                        self.wfile.write(bytes("    const ctElapsed = WT.getTime();\n", "utf-8"))
                        self.wfile.write(bytes("    checkPageReload(ctElapsed);\n", "utf-8"))
                        self.wfile.write(bytes("  }, 250)\n", "utf-8"))
                        self.wfile.write(bytes("</script>\n\n", "utf-8"))

                        if totalLights == 0: # there are no lights available to you at the moment!
                            self.wfile.write(bytes("NeewerLite-Python is not currently set up with any Neewer lights.  To discover new lights, <A HREF='doAction?discover'>click here</a>.<BR>\n", "utf-8"))
                        else:
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
                            self.wfile.write(bytes("     <TD ALIGN='CENTER' STYLE='background-color:rgb(173,255,47)'><FONT SIZE='+2'><A HREF='doAction?use_preset=" + str(currentPreset + 1) + "'>" + str(currentPreset + 1) + "</A></FONT></TD>\n", "utf-8"))
                            self.wfile.write(bytes("     <TD VALIGN='TOP' STYLE='background-color:rgb(240,248,255)'>" + customPresetInfoBuilder(currentPreset, True) + "</TD>\n", "utf-8"))
                            self.wfile.write(bytes("     <TD ALIGN='CENTER' STYLE='background-color:rgb(173,255,47)'><FONT SIZE='+2'><A HREF='doAction?use_preset=" + str(currentPreset + 2) + "'>" + str(currentPreset + 2) + "</A></FONT></TD>\n", "utf-8"))
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
        self.send_header("Content-Type", "text/html;charset=UTF-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
    elif theSection == "htmlheaders":
        self.wfile.write(bytes("<!DOCTYPE html>\n", "utf-8"))
        self.wfile.write(bytes("<HTML>\n<HEAD>\n", "utf-8"))
        self.wfile.write(bytes("<TITLE>NeewerLite-Python 0.15-RC-010924 HTTP Server by Zach Glenwright</TITLE>\n</HEAD>\n", "utf-8"))
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
    elif theSection == "quicklinks" or theSection == "quicklinks-timer":
        footerLinks = "Shortcut links: "
        footerLinks = footerLinks + "<A HREF='doAction?discover'>Scan for New Lights</A> | "
        footerLinks = footerLinks + "<A HREF='doAction?list'>List Currently Available Lights and Custom Presets</A>"
        self.wfile.write(bytes("<CENTER><HR>" + footerLinks + "<HR></CENTER>\n", "utf-8"))

        if theSection == "quicklinks-timer": # write the "This page will refresh..." timer
            self.wfile.write(bytes("<CENTER><strong><em><span id='refreshDisplay'><BR></span></em></strong></CENTER><HR>\n", "utf-8"))
    elif theSection == "htmlendheaders":
        self.wfile.write(bytes("<CENTER><A HREF='https://github.com/taburineagle/NeewerLite-Python/'>NeewerLite-Python 0.15-RC-010924</A> / HTTP Server / by Zach Glenwright<BR></CENTER>\n", "utf-8"))
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
    print("             NeewerLite-Python ver. 0.15-RC-010924")
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

            print("NeewerLite-Python 0.15-RC-010924 by Zach Glenwright")
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
                    # LEMUR! Check out how setUpGUI() needs modeArgs here
                    if cmdReturn[3] == "CCT": # set up the GUI in CCT mode with specified parameters (or default, if none)
                        mainWindow.setUpGUI(colorMode=cmdReturn[3], temp=cmdReturn[4], brightness=cmdReturn[5])
                    elif cmdReturn[3] == "HSI": # set up the GUI in HSI mode with specified parameters (or default, if none)
                        mainWindow.setUpGUI(colorMode=cmdReturn[3], hue=cmdReturn[4], saturation=cmdReturn[5], brightness=cmdReturn[6])
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
                calculateByteString(colorMode=cmdReturn[3], hue=cmdReturn[4], saturation=cmdReturn[5], brightness=cmdReturn[6])
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
                isFinished = asyncioEventLoop.run_until_complete(disconnectFromLight(0, updateGUI = False))

                if numOfAttempts < maxNumOfAttempts:
                    numOfAttempts = numOfAttempts + 1
                else:
                    printDebugString("Error disconnecting from light " + str(maxNumOfAttempts) + " times - quitting out")
                    singleInstanceUnlockandQuit(1) # delete the lock file and quit out
        else:
            printDebugString("-------------------------------------------------------------------------------------")
            printDebugString(" > CLI >> Calculated bytestring:" + updateStatus())

        singleInstanceUnlockandQuit(0) # delete the lock file and quit out