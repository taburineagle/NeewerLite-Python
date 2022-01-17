#############################################################
## NeewerLite-Python
## by Zach Glenwright
#############################################################
##   > https://github.com/taburineagle/NeewerLite-Python/ <
#############################################################
## A cross-platform Python script using the bleak and
## PySide2 libraries to control Neewer brand lights via
## Bluetooth on multiple platforms -
##          Windows, Linux/Ubuntu, MacOS and RPi
#############################################################
## Based on the NeewerLight project by @keefo (Xu Lian)
##   > https://github.com/keefo/NeewerLite <
#############################################################

import os
import sys
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
    from PySide2.QtCore import Qt
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
except Exception as e:
    pass # if there are any HTTP errors, don't do anything yet

CCTSlider = -1 # the current slider moved in the CCT window - 1 - Brightness / 2 - Hue / -1 - Both Brightness and Hue
sendValue = [] # an array to hold the values to be sent to the light
lastAnimButtonPressed = 1 # which animation button you clicked last - if none, then it defaults to 1 (the police sirens)

availableLights = [] # the list of Neewer lights currently available to control - format:
                     #  0                  1                 2            3            4                 5                           6             7
                     # [Bleak Scan Object, Bleak Connection, Custom Name, Last Params, Extend CCT Range, Send BRI/HUE independently, Light On/Off, Power/CH Data Returned]

threadAction = "" # the current action to take from the thread

setLightUUID = "69400002-B5A3-F393-E0A9-E50E24DCCA99" # the UUID to send information to the light
notifyLightUUID = "69400003-B5A3-F393-E0A9-E50E24DCCA99" # the UUID for notify callbacks from the light

receivedData = "" # the data received from the Notify characteristic

# SET FROM THE PREFERENCES FILE ON LAUNCH
findLightsOnStartup = True # whether or not to look for lights when the program starts
autoConnectToLights = True # whether or not to auto-connect to lights after finding them
printDebug = True # show debug messages in the console for all of the program's events
maxNumOfAttempts = 6 # the maximum attempts the program will attempt an action before erroring out
rememberLightsOnExit = False # whether or not to save the currently set light settings (mode/hue/brightness/etc.) when quitting out
acceptable_HTTP_IPs = [] # the acceptable IPs for the HTTP server, set on launch by prefs file
customKeys = [] # custom keymappings for keyboard shortcuts, set on launch by the prefs file
enableTabsOnLaunch = False # whether or not to enable tabs on startup (even with no lights connected)

lockFile = tempfile.gettempdir() + os.sep + "NeewerLite-Python.lock"
anotherInstance = False # whether or not we're using a new instance (for the Singleton check)
globalPrefsFile = os.path.dirname(os.path.abspath(sys.argv[0])) + os.sep + "NeewerLite-Python.prefs" # the global preferences file for saving/loading

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

            self.show

        def connectMe(self):
            self.turnOffButton.clicked.connect(self.turnLightOff)
            self.turnOnButton.clicked.connect(self.turnLightOn)

            self.scanCommandButton.clicked.connect(self.startSelfSearch)
            self.tryConnectButton.clicked.connect(self.startConnect)

            self.ColorModeTabWidget.currentChanged.connect(self.tabChanged)
            self.lightTable.itemSelectionChanged.connect(self.selectionChanged)

            self.Slider_CCT_Hue.valueChanged.connect(lambda: self.computeValueCCT(2))
            self.Slider_CCT_Bright.valueChanged.connect(lambda: self.computeValueCCT(1))

            self.Slider_HSI_1_H.valueChanged.connect(self.computeValueHSI)
            self.Slider_HSI_2_S.valueChanged.connect(self.computeValueHSI)
            self.Slider_HSI_3_L.valueChanged.connect(self.computeValueHSI)

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
                    self.setupLightPrefsTab(selectedLight) # update the Prefs tab with the information for that selected light

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

        def setupLightPrefsTab(self, selectedLight):
            self.customNameTF.setText(availableLights[selectedLight][2]) # set the "custom name" field to the custom name of this light

            # IF THE OPTION TO ALLOW WIDER COLOR TEMPERATURES IS ENABLED, THEN ENABLE THAT CHECKBOX
            if availableLights[selectedLight][4] == True:
                self.widerRangeCheck.setChecked(True)
            else:
                self.widerRangeCheck.setChecked(False)

            # IF THE OPTION TO SEND ONLY CCT MODE IS ENABLED, THEN ENABLE THAT CHECKBOX
            if availableLights[selectedLight][5] == True:
                self.onlyCCTModeCheck.setChecked(True)
            else:
                self.onlyCCTModeCheck.setChecked(False)

        def setupGlobalLightPrefsTab(self, setDefault=False):
            if setDefault == False:
                self.findLightsOnStartup_check.setChecked(findLightsOnStartup)
                self.autoConnectToLights_check.setChecked(autoConnectToLights)
                self.printDebug_check.setChecked(printDebug)
                self.rememberLightsOnExit_check.setChecked(rememberLightsOnExit)
                self.maxNumOfAttempts_field.setText(str(maxNumOfAttempts))
                self.acceptable_HTTP_IPs_field.setText("\n".join(acceptable_HTTP_IPs))
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
                self.maxNumOfAttempts_field.setText("6")
                self.acceptable_HTTP_IPs_field.setText("\n".join(["127.0.0.1", "192.168", "10.0.0"]))
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
            global customKeys, autoConnectToLights, printDebug, rememberLightsOnExit, maxNumOfAttempts, acceptable_HTTP_IPs

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
            
            if self.maxNumOfAttempts_field.text() != "6": # the default for this option is 6 attempts
                maxNumOfAttempts = int(self.maxNumOfAttempts_field.text())
                finalPrefs.append("maxNumOfAttempts=" + self.maxNumOfAttempts_field.text())
            else:
                maxNumOfAttempts = 6

            # FIGURE OUT IF THE HTTP IP ADDRESSES HAVE CHANGED
            returnedList_HTTP_IPs = self.acceptable_HTTP_IPs_field.toPlainText().split("\n")
            
            if returnedList_HTTP_IPs != ["127.0.0.1", "192.168", "10.0.0"]: # if the list of HTTP IPs have changed
                acceptable_HTTP_IPs = returnedList_HTTP_IPs # change the global HTTP IPs available
                finalPrefs.append("acceptable_HTTP_IPs=" + ";".join(acceptable_HTTP_IPs)) # add the new ones to the preferences
            else:
                acceptable_HTTP_IPs = ["127.0.0.1", "192.168", "10.0.0"] # if we reset the IPs, then re-reset the parameter
            
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
      
            # WRITE THE GLOBAL PREFERENCES FILE
            with open(globalPrefsFile, "w") as prefsFileToWrite:
                prefsFileToWrite.write(("\n").join(finalPrefs))

            if len(finalPrefs) > 0:
                # PRINT THIS INFORMATION WHETHER DEBUG OUTPUT IS TURNED ON OR NOT
                print("New global preferences saved in " + globalPrefsFile + " - here is the list:")

                for a in range(len(finalPrefs)):
                    print(" > " + finalPrefs[a])
            else:
                print("There are no new preferences to save (all preferences are set to their default values).")
                print("The NeewerLite-Python.prefs file has been cleared out - you can delete the file if you'd like to.")

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

        def checkLightPrefs(self): # check the new settings and save the custom file
            selectedRows = self.selectedLights() # get the list of currently selected lights

            if len(selectedRows) == 1: # if we have 1 selected light - which should never be false, as we can't use Prefs with more than 1
                availableLights[selectedRows[0]][2] = self.customNameTF.text() # set this light's custom name to the text box
                availableLights[selectedRows[0]][4] = self.widerRangeCheck.isChecked() # if the "wider range" box is checked, then allow wider ranges
                availableLights[selectedRows[0]][5] = self.onlyCCTModeCheck.isChecked() # if the option to send BRI and HUE separately is checked, then turn that on

                # IF A CUSTOM NAME IS SET UP FOR THIS LIGHT, THEN CHANGE THE TABLE TO REFLECT THAT
                if availableLights[selectedRows[0]][2] != "":
                    self.setTheTable([availableLights[selectedRows[0]][2] + " (" + availableLights[selectedRows[0]][0].name + ")" "\n  [ʀssɪ: " + str(availableLights[selectedRows[0]][0].rssi) + " dBm]",
                                    "", "", ""], selectedRows[0])

                self.saveLightPrefs(selectedRows[0]) # save the light settings to a special file

        def saveLightPrefs(self, lightID): # save a sidecar file with the preferences for a specific light
            #CREATE THE light_prefs FOLDER IF IT DOESN'T EXIST
            try:
                os.mkdir(os.path.dirname(os.path.abspath(sys.argv[0])) + os.sep + "light_prefs")
            except FileExistsError:
                pass # the folder already exists, so we don't need to create it

            # GET THE CUSTOM FILENAME FOR THIS FILE, NOTED FROM THE MAC ADDRESS OF THE CURRENT LIGHT
            exportFileName = availableLights[lightID][0].address.split(":") # take the colons out of the MAC address
            exportFileName = os.path.dirname(os.path.abspath(sys.argv[0])) + os.sep + "light_prefs" + os.sep + "".join(exportFileName)

            customName = availableLights[lightID][2] # the custom name for this light
            widerRange = str(availableLights[lightID][4]) # whether or not the light can use extended CCT ranges
            onlyCCTMode = str(availableLights[lightID][5]) # whether or not the light can only use CCT mode

            exportString = customName + "|" + widerRange + "|" + onlyCCTMode # the exported string, minus the light last set parameters

            if rememberLightsOnExit == True: # if we're supposed to remember the last settings, then add that to the Prefs file
                if len(availableLights[lightID][3]) > 0: # if we actually have a value stored for this light
                    lastSettingsString = ",".join(map(str, availableLights[lightID][3])) # combine all the elements of the last set params
                    exportString += "|" + lastSettingsString # add it to the exported string
                else: # if we don't have a value stored for this light (nothing has changed yet)
                    exportString += "|" + "120,135,2,100,56,157" # then just give the default (CCT, 5600K, 100%) params

            # WRITE THE PREFERENCES FILE
            with open(exportFileName, "w") as prefsFileToWrite:
                prefsFileToWrite.write(exportString)

            if customName != "":
                printDebugString("Exported preferences for " + customName + " [" + availableLights[lightID][0].name + "] to " + exportFileName)
            else:
                printDebugString("Exported preferences for [" + availableLights[lightID][0].name + "] to " + exportFileName)

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
                self.lightTable.item(currentRow, 2).setTextAlignment(Qt.AlignCenter) # align the light status info to be center-justified
            if infoArray[3] != "": # the current status message of the light
                self.lightTable.setItem(currentRow, 3, QTableWidgetItem(infoArray[3]))

            self.lightTable.resizeRowsToContents()

        def returnTableInfo(self, row, column):
            return self.lightTable.item(row, column).text()

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
            # CCTSlider = -1 # force this value to -1 to send both hue and brightness at the same time on SNL-660
            CCTSlider = hueOrBrightness # set the global CCT "current slider" to the slider you just... slid

            self.TFV_CCT_Hue.setText(str(self.Slider_CCT_Hue.value()) + "00K")

            calculateByteString(colorMode="CCT",\
                                temp=str(int(self.Slider_CCT_Hue.value())),\
                                brightness=str(int(self.Slider_CCT_Bright.value())))

            self.statusBar.showMessage("Current value (CCT Mode): " + updateStatus())
            self.startSend()

        # COMPUTE A BYTESTRING FOR THE HSI SECTION
        def computeValueHSI(self):
            calculateByteString(colorMode="HSI",\
                                HSI_H=str(int(self.Slider_HSI_1_H.value())),\
                                HSI_S=str(int(self.Slider_HSI_2_S.value())),\
                                HSI_I=str(int(self.Slider_HSI_3_L.value())))

            self.statusBar.showMessage("Current value (HSI Mode): " + updateStatus())
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

            for a in range(len(availableLights)):
                if availableLights[a][1] == "": # the light is not currently linked, so put "waiting to connect" as status
                    if availableLights[a][2] != "": # the light has a custom name, so add the custom name to the light
                        self.setTheTable([availableLights[a][2] + " (" + availableLights[a][0].name + ")" + "\n  [ʀssɪ: " + str(availableLights[a][0].rssi) + " dBm]", availableLights[a][0].address, "Waiting", "Waiting to connect..."])
                    else: # the light does not have a custom name, so just use the model # of the light
                        self.setTheTable([availableLights[a][0].name + "\n  [ʀssɪ: " + str(availableLights[a][0].rssi) + " dBm]", availableLights[a][0].address, "Waiting", "Waiting to connect..."])
                else: # we have previously tried to connect, so we have a Bleak object - so put "waiting to send" as status
                    if availableLights[a][2] != "": # the light has a custom name, so add the custom name to the light
                        self.setTheTable([availableLights[a][2] + " (" + availableLights[a][0].name + ")" + "\n  [ʀssɪ: " + str(availableLights[a][0].rssi) + " dBm]", availableLights[a][0].address, "LINKED", "Waiting to send..."])
                    else: # the light does not have a custom name, so just use the model # of the light
                        self.setTheTable([availableLights[a][0].name + "\n  [ʀssɪ: " + str(availableLights[a][0].rssi) + " dBm]", availableLights[a][0].address, "LINKED", "Waiting to send..."])

        # THE FINAL FUNCTION TO UNLINK ALL LIGHTS WHEN QUITTING THE PROGRAM
        def closeEvent(self, event):
            global threadAction

            # WAIT UNTIL THE BACKGROUND THREAD SETS THE threadAction FLAG TO finished SO WE CAN UNLINK THE LIGHTS
            while threadAction != "finished": # wait until the background thread has a chance to terminate
                printDebugString("Waiting for the background thread to terminate...")
                threadAction = "quit" # make sure to tell the thread to quit again (if it missed it the first time)
                time.sleep(2)

            # Keep in mind, this is broken into 2 separate "for" loops, so we save all the light params FIRST, then try to unlink from them
            if rememberLightsOnExit == True:
                printDebugString("You asked NeewerLite-Python to save the last used light parameters on exit, so we will do that now...")

                for a in range(len(availableLights)):
                    printDebugString("Saving last used parameters for light #" + str(a + 1) + " (" + str(a + 1) + " of " + str(len(availableLights)) + ")")
                    self.saveLightPrefs(a)

            # THE THREAD HAS TERMINATED, NOW CONTINUE...
            printDebugString("We will now attempt to unlink from the lights...")
            self.statusBar.showMessage("Quitting program - unlinking from lights...")
            QApplication.processEvents() # force the status bar to update

            loop = asyncio.get_event_loop()
            loop.run_until_complete(parallelAction("disconnect", [-1])) # disconnect from all lights in parallel

            printDebugString("Closing the program NOW")

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

def returnMACname():
    # RETURN THE CORRECT NAME FOR THE IDENTIFIER OF THE LIGHT (FOR DEBUG STRINGS)
    if platform.system() == "Darwin":
        return "UUID:"
    else:
        return "MAC Address:"

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
    elif modeArgs["colorMode"] == "HSI":
        # We're in HSI (any color of the spectrum) mode
        sendValue = [120, 134, 4, 0, 0, 0, 0, 0]

        sendValue[3] = int(modeArgs["HSI_H"]) & 255 # hue value, up to 255
        sendValue[4] = (int(modeArgs["HSI_H"]) & 65280) >> 8 # offset value, computed from above value
        sendValue[5] = int(modeArgs["HSI_S"]) # saturation value
        sendValue[6] = int(modeArgs["HSI_I"]) # intensity value
        sendValue[7] = calculateChecksum(sendValue) # compute the checksum
    elif modeArgs["colorMode"] == "ANM":
        # We're in ANM (animation) mode
        sendValue = [120, 136, 2, 0, 0, 0]

        sendValue[3] = int(modeArgs["brightness"]) # brightness value
        sendValue[4] = int(modeArgs["animation"]) # the number of animation you're going to run (check comments above)
        sendValue[5] = calculateChecksum(sendValue) # compute the checksum
    else:
        sendValue = [0]

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
    elif CCTSlider == 1: # return only the brightness value
        return newValueBRI
    elif CCTSlider == 2: # return only the hue value
        return newValueHUE

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
        try:
            d.name.index("NEEWER") # try to see if the current device has the name "NEEWER" in it
        except ValueError:
            pass # if the current device doesn't ^^^^, then this error is thrown
        else:
            currentScan.append(d) # and if it finds the phrase, add it to this session's available lights

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
                availableLights.append([currentScan[a], "", customPrefs[0], [], customPrefs[1], customPrefs[2], True, ["---", "---"]]) # add it to the global list
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
        fileToOpen = open(customPrefsPath)
        customPrefs = fileToOpen.read().split("|")
        fileToOpen.close()

        # CHANGE STRING "Booleans" INTO ACTUAL BOOLEANS
        for b in range(1,3):
            if customPrefs[b] == "True":
                customPrefs[b] = True
            else:
                customPrefs[b] = False

        if len(customPrefs) == 4: # if we have a 4th element (the last used parameters), then load them here
            customPrefs[3] = customPrefs[3].replace(" ", "").split(",") # split the last params into a list

            for a in range(len(customPrefs[3])): # convert the string values to ints
                customPrefs[3][a] = int(customPrefs[3][a])
    else: # if there is no custom preferences file, still check the name against a list of per-light parameters
        if lightName == "NEEWER-SL80": # we can use extended ranges with the SL80
            customPrefs = ["", True, False]
        elif lightName == "NEEWER-SNL660": # we can ONLY use CCT mode with the SNL-660
            customPrefs = ["", False, True]
        else: # return a blank slate
             customPrefs = ["", False, False]

    return customPrefs

# CONNECT (LINK) TO A LIGHT
async def connectToLight(selectedLight, updateGUI=True):
    global availableLights
    isConnected = False # whether or not the light is connected
    returnValue = "" # the value to return to the thread (in GUI mode, a string) or True/False (in CLI mode, a boolean value)

    # FILL THE [1] ELEMENT OF THE availableLights ARRAY WITH THE BLEAK CONNECTION
    if availableLights[selectedLight][1] == "":
        availableLights[selectedLight][1] = BleakClient(availableLights[selectedLight][0])
        await asyncio.sleep(0.25) # wait just a short time before trying to connect

    # TRY TO CONNECT TO THE LIGHT SEVERAL TIMES BEFORE GIVING UP THE LINK
    currentAttempt = 1

    while isConnected == False and currentAttempt <= maxNumOfAttempts:
        if threadAction != "quit":
            printDebugString("Attempting to link to light " + str(selectedLight + 1) + " [" + availableLights[selectedLight][0].name + "] " + returnMACname() + " " + availableLights[selectedLight][0].address + " (Attempt " + str(currentAttempt) + " of " + str(maxNumOfAttempts) + ")")

            try:
                if not availableLights[selectedLight][1].is_connected: # if the current device isn't linked to Bluetooth
                    isConnected = await availableLights[selectedLight][1].connect() # try connecting it (and return the connection status)
                else:
                    isConnected = True # the light is already connected, so mark it as being connected
            except Exception as e:
                printDebugString("Error linking to light " + str(selectedLight + 1) + " [" + availableLights[selectedLight][0].name + "] " + returnMACname() + " " + availableLights[selectedLight][0].address)
              
                if updateGUI == True:
                    mainWindow.setTheTable(["", "", "NOT\nLINKED", "There was an error connecting to the light, trying again (Attempt " + str(currentAttempt + 1) + " of " + str(maxNumOfAttempts) + ")..."], selectedLight) # there was an issue connecting this specific light to Bluetooh, so show that
                else:
                    returnValue = False # if we're in CLI mode, and there is an error connecting to the light, return False

                currentAttempt = currentAttempt + 1
                await asyncio.sleep(3) # wait a few seconds before trying again
        else:
            return "quit"

    if threadAction == "quit":
        return "quit"
    else:
        if isConnected == True:
            printDebugString("Successfully linked to light " + str(selectedLight + 1) + " [" + availableLights[selectedLight][0].name + "] " + returnMACname() + " " + availableLights[selectedLight][0].address)

            if updateGUI == True:
                mainWindow.setTheTable(["", "", "LINKED\n --- / ᴄʜ. ---", "Waiting to send..."], selectedLight) # if it's successful, show that in the table
            else:
                returnValue = True  # if we're in CLI mode, and there is no error connecting to the light, return True
        else:
            if updateGUI == True:
                mainWindow.setTheTable(["", "", "NOT\nLINKED", "There was an error connecting to the light"], selectedLight) # there was an issue connecting this specific light to Bluetooh, so show that

            returnValue = False # the light is not connected

    return returnValue # once the connection is over, then return either True or False (for CLI) or nothing (for GUI)

async def readNotifyCharacteristic(selectedLight, diagCommand, typeOfData):
    # clear the global variable before asking the light for info
    global receivedData
    receivedData = ""

    try:
        await availableLights[selectedLight][1].start_notify(notifyLightUUID, notifyCallback) # start reading notifications from the light
    except Exception as e:
        return "" # if there is an error starting the characteristic scan, just quit out of this routine

    for a in range(maxNumOfAttempts): # attempt maxNumOfAttempts times to read the characteristics
        try:
            await availableLights[selectedLight][1].write_gatt_char(setLightUUID, bytearray(diagCommand))
        except Exception as e:
            return "" # if there is an error checking the characteristic, just quit out of this routine

        if receivedData != "" and len(receivedData) > 1 and receivedData[1] == typeOfData: # if we've received data, and the data returned is the right *kind* of data, then return it
            break # we found data, so we can stop checking
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
                if updateGUI == False:
                    returnValue = True # if we're in CLI mode, then return False if there is an error disconnecting
                    mainWindow.setTheTable(["", "", "NOT\nLINKED", "Light disconnected!"], selectedLight) # show the new status in the table

                printDebugString("Successfully unlinked from light " + str(selectedLight + 1) + " [" + availableLights[selectedLight][0].name + "] " + returnMACname() + " " + availableLights[selectedLight][0].address)
        except AttributeError:
            printDebugString("Light " + str(selectedLight + 1) + " has no Bleak object attached to it, so not attempting to disconnect from it")

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
            if type(selectedLights) is int: # if we specify an integer-based index
                selectedLights = [selectedLights] # convert asked-for light to list

        currentSendValue = [] # initialize the value check

        # if there are lights selected (otherwise just dump out), and the delay timer is less than it's maximum, then try to send to the lights selected
        while (len(selectedLights) > 0 and time.time() - startTimer < 0.4) :
            if currentSendValue != sendValue: # if the current value is different than what was last sent to the light, then send a new one
                currentSendValue = sendValue # get this value before sending to multiple lights, to ensure the same value is sent to each one

                for a in range(len(selectedLights)): # try to write each light in turn, and show the current data being sent to them in the table
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
                                        mainWindow.setTheTable(["", "", "", updateStatus(True)], int(selectedLights[a]))
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
                            _loop.run_until_complete(getLightChannelandPower(a))
                            mainWindow.setTheTable(["", "", "LINKED\n" + availableLights[a][7][0] + " / ᴄʜ. " + str(availableLights[a][7][1]), ""], a)

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

        time.sleep(0.25)

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
                listToProcess[a] = "--" + listToProcess[a].lower() # add the dashes + switch to lowercase to properly parse as arguments below
        else: # if the dashes are already in the current item
            listToProcess[a] = listToProcess[a].lower() # we don't need to add dashes, so just switch to lowercase

    # DELETE ANY INVALID ARGUMENTS FROM THE COMMAND LINE BEFORE RUNNING THE ARGUMENT PARSER
    # TO CLEAN UP THE ARGUMENT LIST AND ENSURE THE PARSER CAN STILL RUN WHEN INVALID ARGUMENTS ARE PRESENT
    if inStartupMode == True:
        acceptable_arguments = ["--http", "--cli", "--silent", "--light", "--mode", "--temp", "--hue",
        "--sat", "--bri", "--intensity", "--scene", "--animation", "--help", "--off", "--on", "--list", "--force_instance"]
    else: # if we're doing HTTP processing, we don't need the http, cli, silent and help flags, so toss 'em
        acceptable_arguments = ["--light", "--mode", "--temp", "--hue", "--sat", "--bri", "--intensity",
        "--scene", "--animation", "--list", "--discover", "--link", "--off", "--on"]

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
        elif listToProcess[a].find("--list") != -1:
            listToProcess[a] = "--list"
        elif listToProcess[a].find("--discover") != -1:
            listToProcess[a] = "--discover"
        elif listToProcess[a].find("--off") != -1:
            listToProcess[a] = "--off"
        elif listToProcess[a].find("--on") != -1:
            listToProcess[a] = "--on"
        elif listToProcess[a] == "--link":
            listToProcess[a] = "--link=-1"

    # PARSE THE ARGUMENT LIST FOR CUSTOM PARAMETERS
    parser = argparse.ArgumentParser()

    parser.add_argument("--list", action="store_true", help="Scan for nearby Neewer lights and list them on the CLI") # list the currently available lights
    parser.add_argument("--http", action="store_true", help="Use an HTTP server to send commands to Neewer lights using a web browser")
    parser.add_argument("--silent", action="store_false", help="Don't show any debug information in the console")
    parser.add_argument("--cli", action="store_false", help="Don't show the GUI at all, just send command to one light and quit")
    parser.add_argument("--force_instance", action="store_false", help="Force a new instance of NeewerLite-Python if another one is already running")

    # HTML SERVER SPECIFIC PARAMETERS
    if inStartupMode == False:
        parser.add_argument("--discover", action="store_true") # tell the HTTP server to search for newly added lights
        parser.add_argument("--link", default=-1) # link a specific light to NeewerPython-Lite


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
        if args.list == True:
            return["list"] # list the currently available lights

        if args.discover == True:
            return["discover"] # discover new lights

        if args.link != -1:
            return["link", args.link] # return the value defined by the parameter
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
            if paramsList[0] == "discover": # we asked to discover new lights
                loop.run_until_complete(findDevices()) # find the lights available to control

                # try to connect to each light
                if autoConnectToLights == True:
                    loop.run_until_complete(parallelAction("connect", [-1], False)) # try to connect to *all* lights in parallel
            elif paramsList[0] == "link": # we asked to connect to a specific light
                selectedLights = returnLightIndexesFromMacAddress(paramsList[1])

                if len(selectedLights) > 0:
                    loop.run_until_complete(parallelAction("connect", selectedLights, False)) # try to connect to all *selected* lights in parallel
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
                    loop.run_until_complete(writeToLight(selectedLights, False))

            threadAction = "" # clear the thread variable
    else:
        printDebugString("The HTTP Server requested an action, but we're already working on one.  Please wait...")

def returnLightIndexesFromMacAddress(addresses):
    addressesToCheck = addresses.split(";")
    foundIndexes = [] # the list of indexes for the lights you specified

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
    loop = asyncio.get_event_loop()

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
                writeHTMLSections(self, "header")
                writeHTMLSections(self, "errorHelp", "The last request you provided was too long!  The NeewerLite-Python HTTP server can only accept URL commands less than 132 characters long after /NeewerLite-Python/doAction?.")
                writeHTMLSections(self, "footer")

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
                writeHTMLSections(self, "header")

                # BREAK THE URL INTO USABLE PARAMTERS
                paramsList = self.path.replace(acceptableURL, "").split("&") # split the included params into a list
                paramsList = processCommands(paramsList) # process the commands returned from the HTTP parameters

            if len(paramsList) == 0: # if we have no valid parameters, then say that in the error report
                writeHTMLSections(self, "errorHelp", "You didn't provide any valid parameters in the last URL.  To send multiple parameters to NeewerLite-Python, separate each one with a & character.")
            else:
                self.wfile.write(bytes("<h1>Request Successful!</h1>", "utf-8"))
                self.wfile.write(bytes("Last Request: <em>" + self.path + "</em><br>", "utf-8"))
                self.wfile.write(bytes("From IP: <em>" + clientIP + "</em><br><br>", "utf-8"))

                if paramsList[0] != "list":
                    self.wfile.write(bytes("Provided Parameters:<br>", "utf-8"))

                    if len(paramsList) <= 2:
                        for a in range(len(paramsList)):
                            self.wfile.write(bytes("&nbsp;&nbsp;" + str(paramsList[a]) + "<br>", "utf-8"))
                    else:
                        self.wfile.write(bytes("&nbsp;&nbsp;Light(s) to connect to: " + str(paramsList[2]) + "<br>", "utf-8"))
                        self.wfile.write(bytes("&nbsp;&nbsp;Mode: " + str(paramsList[3]) + "<br>", "utf-8"))

                        if paramsList[3] == "CCT":
                            self.wfile.write(bytes("&nbsp;&nbsp;Color Temperature: " + str(paramsList[4]) + "00K<br>", "utf-8"))
                            self.wfile.write(bytes("&nbsp;&nbsp;Brightness: " + str(paramsList[5]) + "<br>", "utf-8"))
                        elif paramsList[3] == "HSI":
                            self.wfile.write(bytes("&nbsp;&nbsp;Hue: " + str(paramsList[4]) + "<br>", "utf-8"))
                            self.wfile.write(bytes("&nbsp;&nbsp;Saturation: " + str(paramsList[5]) + "<br>", "utf-8"))
                            self.wfile.write(bytes("&nbsp;&nbsp;Brightness: " + str(paramsList[6]) + "<br>", "utf-8"))
                        elif paramsList[3] == "ANM" or paramsList[3] == "SCENE":
                            self.wfile.write(bytes("&nbsp;&nbsp;Animation Scene: " + str(paramsList[4]) + "<br>", "utf-8"))
                            self.wfile.write(bytes("&nbsp;&nbsp;Brightness: " + str(paramsList[5]) + "<br>", "utf-8"))

                    # PROCESS THE HTML COMMANDS IN ANOTHER THREAD
                    htmlProcessThread = threading.Thread(target=processHTMLCommands, args=(paramsList, loop), name="htmlProcessThread")
                    htmlProcessThread.start()
                else: # build the list of lights to display in the browser
                    totalLights = len(availableLights)

                    if totalLights == 0: # there are no lights available to you at the moment!
                        self.wfile.write(bytes("NeewerLite-Python is not currently set up with any Neewer lights.  To discover new lights, <a href=""doAction?discover"">click here</a>.<br>", "utf-8"))
                    else:
                        self.wfile.write(bytes("List of available Neewer lights:<HR>", "utf-8"))
                        self.wfile.write(bytes("<TABLE WIDTH=""98%"" BORDER=""1"">", "utf-8"))
                        self.wfile.write(bytes("<TR>", "utf-8"))
                        self.wfile.write(bytes("<TH STYLE=""width:2%;text-align:left"">ID #", "utf-8"))
                        self.wfile.write(bytes("<TH STYLE=""width:20%;text-align:left"">Custom Name</TH>", "utf-8"))
                        self.wfile.write(bytes("<TH STYLE=""width:20%;text-align:left"">Light Type</TH>", "utf-8"))
                        self.wfile.write(bytes("<TH STYLE=""width:15%;text-align:left"">MAC Address/GUID</TH>", "utf-8"))
                        self.wfile.write(bytes("<TH STYLE=""width:5%;text-align:left"">RSSI</TH>", "utf-8"))
                        self.wfile.write(bytes("<TH STYLE=""width:5%;text-align:left"">Linked</TH>", "utf-8"))
                        self.wfile.write(bytes("<TH STYLE=""width:33%;text-align:left"">Last Sent Value</TH>", "utf-8"))
                        self.wfile.write(bytes("</TR>", "utf-8"))

                        for a in range(totalLights):
                            self.wfile.write(bytes("<TR>", "utf-8"))
                            self.wfile.write(bytes("<TD>" + str(a + 1) + "</TD>", "utf-8")) # light ID #
                            self.wfile.write(bytes("<TD>" + availableLights[a][2] + "</TD>", "utf-8")) # light custom name
                            self.wfile.write(bytes("<TD>" + availableLights[a][0].name + "</TD>", "utf-8")) # light type
                            self.wfile.write(bytes("<TD>" + availableLights[a][0].address + "</TD>", "utf-8")) # light MAC address
                            self.wfile.write(bytes("<TD>" + str(availableLights[a][0].rssi) + " dbM</TD>", "utf-8")) # light RSSI (signal quality)

                            try:
                                if availableLights[a][1].is_connected:
                                    self.wfile.write(bytes("<TD>" + "Yes" + "</TD>", "utf-8")) # is the light linked?
                                else:
                                    self.wfile.write(bytes("<TD>" + "<A HREF=link=" + str(a + 1) + ">No</A></TD>", "utf-8")) # is the light linked?
                            except Exception as e:
                                self.wfile.write(bytes("<TD>" + "<A HREF=link=" + str(a + 1) + ">Nope!</A></TD>", "utf-8")) # is the light linked?

                            self.wfile.write(bytes("<TD>" + updateStatus(False, availableLights[a][3]) + "</TD>", "utf-8")) # the last sent value to the light
                            self.wfile.write(bytes("</TR>", "utf-8"))

                        self.wfile.write(bytes("</TABLE>", "utf-8"))

            writeHTMLSections(self, "footer") # add the footer to the bottom of the page

def writeHTMLSections(self, theSection, errorMsg = ""):
    if theSection == "header":
        self.send_response(200)
        self._send_cors_headers()
        self.send_header("Content-type", "text/html")
        self.end_headers()

        self.wfile.write(bytes("<html><head><title>NeewerLite-Python HTTP Server</title></head>", "utf-8"))
        self.wfile.write(bytes("<body>", "utf-8"))
    elif theSection == "errorHelp":
        self.wfile.write(bytes("<h1>Invalid request!</h1>", "utf-8"))
        self.wfile.write(bytes("Last Request: <em>" + self.path + "</em><br>", "utf-8"))
        self.wfile.write(bytes(errorMsg + "<br><br>", "utf-8"))
        self.wfile.write(bytes("Valid parameters to use -<br>", "utf-8"))
        self.wfile.write(bytes("<strong>list</strong> - list the current lights NeewerPython-Lite has available to it<br>", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/doAction?list</em><br>", "utf-8"))
        self.wfile.write(bytes("<strong>discover</strong> - tell NeewerLite-Python to scan for new lights<br>", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/doAction?discover</em><br>", "utf-8"))
        self.wfile.write(bytes("<strong>link=</strong> - (value: <em>index of light to link to</em>) manually link to a specific light - you can specify multiple lights with semicolons (so link=1;2 would try to link to both lights 1 and 2)<br>", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/doAction?link=1</em><br>", "utf-8"))
        self.wfile.write(bytes("<strong>light=</strong> - the MAC address (or current index of the light) you want to send a command to - you can specify multiple lights with semicolons (so light=1;2 would send a command to both lights 1 and 2)<br>", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/doAction?light=11:22:33:44:55:66</em><br>", "utf-8"))
        self.wfile.write(bytes("<strong>mode=</strong> - the mode (value: <em>HSI, CCT, and either ANM or SCENE</em>) - the color mode to switch the light to<br>", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/doAction?mode=CCT</em><br>", "utf-8"))
        self.wfile.write(bytes("(CCT mode only) <strong>temp=</strong> or <strong>temperature=</strong> - (value: <em>3200 to 8500</em>) the color temperature in CCT mode to set the light to<br>", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/doAction?temp=5200</em><br>", "utf-8"))
        self.wfile.write(bytes("(HSI mode only) <strong>hue=</strong> - (value: <em>0 to 360</em>) the hue value in HSI mode to set the light to<br>", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/doAction?hue=240</em><br>", "utf-8"))
        self.wfile.write(bytes("(HSI mode only) <strong>sat=</strong> or <strong>saturation=</strong> - (value: <em>0 to 100</em>) the color saturation value in HSI mode to set the light to<br>", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/doAction?sat=65</em><br>", "utf-8"))
        self.wfile.write(bytes("(ANM/SCENE mode only) <strong>scene=</strong> - (value: <em>1 to 9</em>) which animation (scene) to switch the light to<br>", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/doAction?scene=3</em><br>", "utf-8"))
        self.wfile.write(bytes("(CCT/HSI/ANM modes) <strong>bri=</strong>, <strong>brightness=</strong> or <strong>intensity=</strong> - (value: <em>0 to 100</em>) how bright you want the light<br>", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;Example: <em>http://(server address)/NeewerLite-Python/doAction?brightness=80</em><br>", "utf-8"))
        self.wfile.write(bytes("<br><br>More examples -<br>", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;Set the light with MAC address <em>11:22:33:44:55:66</em> to <em>CCT</em> mode, with a color temperature of <em>5200</em> and brightness of <em>40</em><br>", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;<em>http://(server address)/NeewerLite-Python/doAction?light=11:22:33:44:55:66&mode=CCT&temp=5200&bri=40</em><br><br>", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;Set the light with MAC address <em>11:22:33:44:55:66</em> to <em>HSI</em> mode, with a hue of <em>70</em>, saturation of <em>50</em> and brightness of <em>10</em><br>", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;<em>http://(server address)/NeewerLite-Python/doAction?light=11:22:33:44:55:66&mode=HSI&hue=70&sat=50&bri=10</em><br><br>", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;Set the first light available to <em>SCENE</em> mode, using the <em>first</em> animation and brightness of <em>55</em><br>", "utf-8"))
        self.wfile.write(bytes("&nbsp;&nbsp;&nbsp;&nbsp;<em>http://(server address)/NeewerLite-Python/doAction?light=1&mode=SCENE&scene=1&bri=55</em><br>", "utf-8"))
    elif theSection == "footer":
        footerLinks = "Shortcut links: "
        footerLinks = footerLinks + "<A HREF=""doAction?discover"">Scan for New Lights</A> | "
        footerLinks = footerLinks + "<A HREF=""doAction?list"">List Currently Available Lights</A>"

        self.wfile.write(bytes("<HR>" + footerLinks + "<br>", "utf-8"))
        self.wfile.write(bytes("<A HREF=""https://github.com/taburineagle/NeewerLite-Python/"">NeewerLite-Python 0.8</A> by Zach Glenwright<br>", "utf-8"))
        self.wfile.write(bytes("</body></html>", "utf-8"))

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

def loadPrefsFile(globalPrefsFile = ""):
    global findLightsOnStartup, autoConnectToLights, printDebug, maxNumOfAttempts, \
           rememberLightsOnExit, acceptable_HTTP_IPs, customKeys, enableTabsOnLaunch

    if globalPrefsFile != "":
        printDebugString("Loading global preferences from file...")

        fileToOpen = open(globalPrefsFile)
        mainPrefs = fileToOpen.read().splitlines()
        fileToOpen.close()

        acceptable_arguments = ["findLightsOnStartup", "autoConnectToLights", "printDebug", "maxNumOfAttempts", "rememberLightsOnExit", "acceptableIPs", \
            "SC_turnOffButton", "SC_turnOnButton", "SC_scanCommandButton", "SC_tryConnectButton", "SC_Tab_CCT", "SC_Tab_HSI", "SC_Tab_SCENE", "SC_Tab_PREFS", \
            "SC_Dec_Bri_Small", "SC_Inc_Bri_Small", "SC_Dec_Bri_Large", "SC_Inc_Bri_Large", \
            "SC_Dec_1_Small", "SC_Inc_1_Small", "SC_Dec_2_Small", "SC_Inc_2_Small", "SC_Dec_3_Small", "SC_Inc_3_Small", \
            "SC_Dec_1_Large", "SC_Inc_1_Large", "SC_Dec_2_Large", "SC_Inc_2_Large", "SC_Dec_3_Large", "SC_Inc_3_Large", \
            "enableTabsOnLaunch"]

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
    prefsParser.add_argument("--acceptableIPs", default=["127.0.0.1", "192.168", "10.0.0"])

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

    if type(mainPrefs.acceptableIPs) is not list: # we have a string in the return, so we need to post-process it
        acceptable_HTTP_IPs = mainPrefs.acceptableIPs.replace(" ", "").split(";") # split the IP addresses into a list for acceptable IPs
    else: # the return is already a list (the default list), so return it
        acceptable_HTTP_IPs = mainPrefs.acceptableIPs

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
    singleInstanceLock() # make a lockfile if one doesn't exist yet, and quit out if one does

    if os.path.exists(globalPrefsFile):
        loadPrefsFile(globalPrefsFile) # if a preferences file exists, process it and load the preferences
    else:
        loadPrefsFile() # if it doesn't, then just load the defaults

    loop = asyncio.get_event_loop() # get the current asyncio loop
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
                loop.run_until_complete(parallelAction("disconnect", [-1], False)) # disconnect from all lights in parallel
           
            printDebugString("Closing the program NOW")
            singleInstanceUnlockandQuit(0) # delete the lock file and quit out

        if cmdReturn[0] == "LIST":
            doAnotherInstanceCheck() # check to see if another instance is running, and if it is, then error out and quit

            print("NeewerLite-Python 0.8 by Zach Glenwright")
            print("Searching for nearby Neewer lights...")
            loop.run_until_complete(findDevices())

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

            sys.exit(0) # we shouldn't need to do anything with the lock file here, so just quit out

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

                loop.run_until_complete(connectToOneLight(cmdReturn[2])) # get Bleak object linking to this specific light and getting custom prefs
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
                workerThread = threading.Thread(target=workerThread, args=(loop,), name="workerThread")
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
                isFinished = loop.run_until_complete(connectToLight(0, False))

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
                isFinished = loop.run_until_complete(writeToLight(0, False))

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
                isFinished = loop.run_until_complete(disconnectFromLight(0))

                if numOfAttempts < maxNumOfAttempts:
                    numOfAttempts = numOfAttempts + 1
                else:
                    printDebugString("Error disconnecting from light " + str(maxNumOfAttempts) + " times - quitting out")
                    singleInstanceUnlockandQuit(1) # delete the lock file and quit out
        else:
            printDebugString("-------------------------------------------------------------------------------------")
            printDebugString(" > CLI >> Calculated bytestring:" + updateStatus())

        singleInstanceUnlockandQuit(0) # delete the lock file and quit out