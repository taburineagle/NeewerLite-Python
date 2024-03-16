from PySide2.QtCore import QRect, Signal, Qt
from PySide2.QtGui import QFont, QLinearGradient, QColor, QKeySequence
from PySide2.QtWidgets import QFormLayout, QGridLayout, QKeySequenceEdit, QWidget, QPushButton, QTableWidget, QTableWidgetItem, QAbstractScrollArea, QAbstractItemView, \
                              QTabWidget, QGraphicsScene, QGraphicsView, QFrame, QSlider, QLabel, QLineEdit, QCheckBox, QStatusBar, QScrollArea, QTextEdit, \
                              QComboBox

import math # for gradient generation
import platform # for selecting specific fonts for specific systems

mainFont = QFont()
mainFont.setBold(True)
mainFont.setWeight(75)

def combinePySide2Values(theValues):
    # ADDED THIS TO FIX PySide2 VERSIONS < 5.15 
    # AND THE "can not interpret as integer" 
    # ERROR WHEN COMBINING ALIGNMENT FLAGS
    returnValue = int(theValues[0])

    for a in range(1, len(theValues)):
        returnValue = returnValue + int(theValues[a])

    return returnValue

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        # ============ FONTS, GRADIENTS AND OTHER WINDOW SPECIFICS ============
        MainWindow.setFixedSize(590, 670) # the main window should be this size at launch, and no bigger
        MainWindow.setWindowTitle("NeewerLite-Python [2024-03-16-BETA] by Zach Glenwright")

        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")

        # ============ THE TOP-MOST BUTTONS ============
        self.turnOffButton = QPushButton(self.centralwidget)
        self.turnOffButton.setGeometry(QRect(10, 4, 150, 22))
        self.turnOffButton.setText("Turn Light(s) Off")

        self.turnOnButton = QPushButton(self.centralwidget)
        self.turnOnButton.setGeometry(QRect(165, 4, 150, 22))
        self.turnOnButton.setText("Turn Light(s) On")

        self.scanCommandButton = QPushButton(self.centralwidget)
        self.scanCommandButton.setGeometry(QRect(416, 4, 81, 22))
        self.scanCommandButton.setText("Scan")

        self.tryConnectButton = QPushButton(self.centralwidget)
        self.tryConnectButton.setGeometry(QRect(500, 4, 81, 22))
        self.tryConnectButton.setText("Connect")

        self.turnOffButton.setEnabled(False)
        self.turnOnButton.setEnabled(False)
        self.tryConnectButton.setEnabled(False)

        # ============ THE LIGHT TABLE ============
        self.lightTable = QTableWidget(self.centralwidget)

        self.lightTable.setColumnCount(4)
        self.lightTable.setColumnWidth(0, 120)
        self.lightTable.setColumnWidth(1, 150)
        self.lightTable.setColumnWidth(2, 94)
        self.lightTable.setColumnWidth(3, 190)

        __QT0 = QTableWidgetItem()
        __QT0.setText("Light Name")
        self.lightTable.setHorizontalHeaderItem(0, __QT0)

        __QT1 = QTableWidgetItem()
        __QT1.setText("MAC Address")
        self.lightTable.setHorizontalHeaderItem(1, __QT1)

        __QT2 = QTableWidgetItem()
        __QT2.setText("Linked")
        self.lightTable.setHorizontalHeaderItem(2, __QT2)

        __QT3 = QTableWidgetItem()
        __QT3.setText("Status")
        self.lightTable.setHorizontalHeaderItem(3, __QT3)

        self.lightTable.setGeometry(QRect(10, 32, 571, 261))
        self.lightTable.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.lightTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.lightTable.setAlternatingRowColors(True)
        self.lightTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.lightTable.verticalHeader().setStretchLastSection(False)

        # ============ THE CUSTOM PRESET BUTTONS ============

        self.customPresetButtonsCW = QWidget(self.centralwidget)
        self.customPresetButtonsCW.setGeometry(QRect(10, 300, 571, 68))
        self.customPresetButtonsLay = QGridLayout(self.customPresetButtonsCW)
        self.customPresetButtonsLay.setContentsMargins(0, 0, 0, 0) # ensure this widget spans from the left to the right edge of the light table

        self.customPreset_0_Button = customPresetButton(self.centralwidget, text="<strong><font size=+2>1</font></strong><br>PRESET<br>GLOBAL")
        self.customPresetButtonsLay.addWidget(self.customPreset_0_Button, 1, 1)
        self.customPreset_1_Button = customPresetButton(self.centralwidget, text="<strong><font size=+2>2</font></strong><br>PRESET<br>GLOBAL")
        self.customPresetButtonsLay.addWidget(self.customPreset_1_Button, 1, 2)
        self.customPreset_2_Button = customPresetButton(self.centralwidget, text="<strong><font size=+2>3</font></strong><br>PRESET<br>GLOBAL")
        self.customPresetButtonsLay.addWidget(self.customPreset_2_Button, 1, 3)
        self.customPreset_3_Button = customPresetButton(self.centralwidget, text="<strong><font size=+2>4</font></strong><br>PRESET<br>GLOBAL")
        self.customPresetButtonsLay.addWidget(self.customPreset_3_Button, 1, 4)
        self.customPreset_4_Button = customPresetButton(self.centralwidget, text="<strong><font size=+2>5</font></strong><br>PRESET<br>GLOBAL")
        self.customPresetButtonsLay.addWidget(self.customPreset_4_Button, 1, 5)
        self.customPreset_5_Button = customPresetButton(self.centralwidget, text="<strong><font size=+2>6</font></strong><br>PRESET<br>GLOBAL")
        self.customPresetButtonsLay.addWidget(self.customPreset_5_Button, 1, 6)
        self.customPreset_6_Button = customPresetButton(self.centralwidget, text="<strong><font size=+2>7</font></strong><br>PRESET<br>GLOBAL")
        self.customPresetButtonsLay.addWidget(self.customPreset_6_Button, 1, 7)
        self.customPreset_7_Button = customPresetButton(self.centralwidget, text="<strong><font size=+2>8</font></strong><br>PRESET<br>GLOBAL")
        self.customPresetButtonsLay.addWidget(self.customPreset_7_Button, 1, 8)

        # ============ THE MODE TABS ============
        self.ColorModeTabWidget = QTabWidget(self.centralwidget)
        self.ColorModeTabWidget.setGeometry(QRect(10, 385, 571, 254))

        # === >> MAIN TAB WIDGETS << ===
        self.CCT = QWidget()
        self.HSI = QWidget()
        self.ANM = QWidget()
        
        # ============ SINGLE SLIDER WIDGET DEFINITIONS ============

        self.colorTempSlider = parameterWidget(title="Color Temperature", gradient="TEMP", 
                                               sliderMin=32, sliderMax=72, sliderVal=56, prefix="00K")
        self.brightSlider = parameterWidget(title="Brightness", gradient="BRI")
        self.GMSlider = parameterWidget(title="GM Compensation", gradient="GM", sliderOffset=-50, sliderVal=50, prefix="")
        
        self.RGBSlider = parameterWidget(title="Hue", gradient="RGB", sliderMin=0, sliderMax=360, sliderVal=180, prefix="º")
        self.colorSatSlider = parameterWidget(title="Saturation", gradient="SAT", sliderVal=100)

        # change the saturation gradient when the RGB slider changes
        self.RGBSlider.valueChanged.connect(self.colorSatSlider.adjustSatGradient)
        
        self.speedSlider = parameterWidget(title="Speed", gradient="SPEED", sliderMin=0, sliderMax=10, sliderVal=5, prefix="")
        self.sparksSlider = parameterWidget(title="Sparks", gradient="SPARKS", sliderMin=0, sliderMax=10, sliderVal=5, prefix="")

        # ============ DOUBLE SLIDER WIDGET DEFINITIONS ============

        self.brightDoubleSlider = doubleSlider(sliderType="BRI")
        self.RGBDoubleSlider = doubleSlider(sliderType="RGB")
        self.colorTempDoubleSlider = doubleSlider(sliderType="TEMP")
        
        # ============ FX CHOOSER DEFINITIONS ============

        self.effectChooser_Title = QLabel(self.ANM, text="Choose an effect:")
        self.effectChooser_Title.setGeometry(QRect(8, 6, 120, 20))
        self.effectChooser_Title.setFont(mainFont)

        self.effectChooser = QComboBox(self.ANM)
        self.effectChooser.setGeometry(QRect(125, 6, 430, 22))

        # ============ FX CHOOSER DEFINITIONS ============

        self.specialOptionsSection = QWidget(self.ANM)

        self.specialOptions_Title = QLabel(self.specialOptionsSection, text="Choose a color option:")
        self.specialOptions_Title.setFont(mainFont)
        self.specialOptions_Title.setGeometry(0, 0, 250, 20)

        self.specialOptionsChooser = QComboBox(self.specialOptionsSection)
        self.specialOptionsChooser.setGeometry(QRect(0, 20, self.ColorModeTabWidget.width() - 16, 22))

        self.specialOptionsSection.hide()

        # self.specialOptionsChooser.addItems(["Red", "Blue", "Red and Blue", "White and Blue", "Red, Blue and White"])
        # self.specialOptionsChooser.setCurrentIndex(2)

        # self.specialOptionsSetion.setParent(self.CCT)
        # self.specialOptionsSetion.move(8, 20)

        # =============================================================================

        # === >> THE LIGHT PREFS TAB << ===
        self.lightPrefs = QWidget()

        # CUSTOM NAME FIELD FOR THIS LIGHT
        self.customName = QCheckBox(self.lightPrefs)
        self.customName.setGeometry(QRect(10, 14, 541, 16))
        self.customName.setText("Custom Name for this light:")
        self.customName.setFont(mainFont)

        self.customNameTF = QLineEdit(self.lightPrefs)
        self.customNameTF.setGeometry(QRect(10, 34, 541, 20))
        self.customNameTF.setMaxLength(80)

        # CUSTOM HSI COLOR TEMPERATURE RANGES FOR THIS LIGHT
        self.colorTempRange = QCheckBox(self.lightPrefs)
        self.colorTempRange.setGeometry(QRect(10, 82, 541, 16))
        self.colorTempRange.setText("Use Custom Color Temperature Range for CCT mode:")
        self.colorTempRange.setFont(mainFont)

        self.colorTempRange_Min_TF = QLineEdit(self.lightPrefs)
        self.colorTempRange_Min_TF.setGeometry(QRect(10, 102, 120, 20))
        self.colorTempRange_Min_TF.setMaxLength(80)

        self.colorTempRange_Max_TF = QLineEdit(self.lightPrefs)
        self.colorTempRange_Max_TF.setGeometry(QRect(160, 102, 120, 20))
        self.colorTempRange_Max_TF.setMaxLength(80)
        
        self.colorTempRange_Min_Description = QLabel(self.lightPrefs)
        self.colorTempRange_Min_Description.setGeometry(QRect(10, 124, 120, 16))
        self.colorTempRange_Min_Description.setAlignment(Qt.AlignCenter)
        self.colorTempRange_Min_Description.setText("Minimum")
        self.colorTempRange_Min_Description.setFont(mainFont)
        
        self.colorTempRange_Max_Description = QLabel(self.lightPrefs)
        self.colorTempRange_Max_Description.setGeometry(QRect(160, 124, 120, 16))
        self.colorTempRange_Max_Description.setAlignment(Qt.AlignCenter)
        self.colorTempRange_Max_Description.setText("Maximum")
        self.colorTempRange_Max_Description.setFont(mainFont)
        
        # WHETHER OR NOT TO ONLY ALLOW CCT MODE FOR THIS LIGHT
        self.onlyCCTModeCheck = QCheckBox(self.lightPrefs)
        self.onlyCCTModeCheck.setGeometry(QRect(10, 160, 401, 31))
        self.onlyCCTModeCheck.setText("This light can only use CCT mode\n(for Neewer lights without HSI mode)")
        self.onlyCCTModeCheck.setFont(mainFont)

        # SAVE IIITTTTTT!
        self.saveLightPrefsButton = QPushButton(self.lightPrefs)
        self.saveLightPrefsButton.setGeometry(QRect(416, 170, 141, 23))
        self.saveLightPrefsButton.setText("Save Preferences")

        # === >> THE GLOBAL PREFS TAB << ===
        self.globalPrefs = QScrollArea()
        self.globalPrefsCW = QWidget()

        self.globalPrefsCW.setMaximumWidth(550) # make sure to resize all contents to fit in the horizontal space of the scrollbar widget

        self.globalPrefsLay = QFormLayout(self.globalPrefsCW)
        self.globalPrefsLay.setLabelAlignment(Qt.AlignLeft)

        self.globalPrefs.setWidget(self.globalPrefsCW)
        self.globalPrefs.setWidgetResizable(True)

        # MAIN PROGRAM PREFERENCES
        self.findLightsOnStartup_check = QCheckBox("Scan for Neewer lights on program launch")
        self.autoConnectToLights_check = QCheckBox("Automatically try to link to newly found lights")
        self.printDebug_check = QCheckBox("Print debug information to the console")
        self.rememberLightsOnExit_check = QCheckBox("Remember the last mode parameters set for lights on exit")
        self.rememberPresetsOnExit_check = QCheckBox("Save configuration of custom presets on exit")
        self.maxNumOfAttempts_field = QLineEdit()
        self.maxNumOfAttempts_field.setFixedWidth(35)
        self.acceptable_HTTP_IPs_field = QTextEdit()
        self.acceptable_HTTP_IPs_field.setFixedHeight(70)
        self.whiteListedMACs_field = QTextEdit()
        self.whiteListedMACs_field.setFixedHeight(70)

        self.resetGlobalPrefsButton = QPushButton("Reset Preferences to Defaults")
        self.saveGlobalPrefsButton = QPushButton("Save Global Preferences")

        # THE FIRST SECTION OF KEYBOARD MAPPING SECTION
        self.windowButtonsCW = QWidget()
        self.windowButtonsLay = QGridLayout(self.windowButtonsCW)

        self.SC_turnOffButton_field = singleKeySequenceEditCancel("Ctrl+PgDown")
        self.windowButtonsLay.addWidget(QLabel("<strong>Window Top</strong><br>Turn Light(s) Off", alignment=Qt.AlignCenter), 1, 1)
        self.windowButtonsLay.addWidget(self.SC_turnOffButton_field, 2, 1)
        self.SC_turnOnButton_field = singleKeySequenceEditCancel("Ctrl+PgUp")
        self.windowButtonsLay.addWidget(QLabel("<strong>Window Top</strong><br>Turn Light(s) On", alignment=Qt.AlignCenter), 1, 2)
        self.windowButtonsLay.addWidget(self.SC_turnOnButton_field, 2, 2)
        self.SC_scanCommandButton_field = singleKeySequenceEditCancel("Ctrl+Shift+S")
        self.windowButtonsLay.addWidget(QLabel("<strong>Window Top</strong><br>Scan/Re-Scan", alignment=Qt.AlignCenter), 1, 3)
        self.windowButtonsLay.addWidget(self.SC_scanCommandButton_field, 2, 3)
        self.SC_tryConnectButton_field = singleKeySequenceEditCancel("Ctrl+Shift+C")
        self.windowButtonsLay.addWidget(QLabel("<strong>Window Top</strong><br>Connect", alignment=Qt.AlignCenter), 1, 4)
        self.windowButtonsLay.addWidget(self.SC_tryConnectButton_field, 2, 4)

        # SWITCHING BETWEEN TABS KEYBOARD MAPPING SECTION
        self.tabSwitchCW = QWidget()
        self.tabSwitchLay = QGridLayout(self.tabSwitchCW)

        self.SC_Tab_CCT_field = singleKeySequenceEditCancel("Alt+1")
        self.tabSwitchLay.addWidget(QLabel("<strong>Switching Tabs</strong><br>To CCT", alignment=Qt.AlignCenter), 1, 1)
        self.tabSwitchLay.addWidget(self.SC_Tab_CCT_field, 2, 1)
        self.SC_Tab_HSI_field = singleKeySequenceEditCancel("Alt+2")
        self.tabSwitchLay.addWidget(QLabel("<strong>Switching Tabs</strong><br>To HSI", alignment=Qt.AlignCenter), 1, 2)
        self.tabSwitchLay.addWidget(self.SC_Tab_HSI_field, 2, 2)
        self.SC_Tab_SCENE_field = singleKeySequenceEditCancel("Alt+3")
        self.tabSwitchLay.addWidget(QLabel("<strong>Switching Tabs</strong><br>To SCENE", alignment=Qt.AlignCenter), 1, 3)
        self.tabSwitchLay.addWidget(self.SC_Tab_SCENE_field, 2, 3)
        self.SC_Tab_PREFS_field = singleKeySequenceEditCancel("Alt+4")
        self.tabSwitchLay.addWidget(QLabel("<strong>Switching Tabs</strong><br>To Light Prefs", alignment=Qt.AlignCenter), 1, 4)
        self.tabSwitchLay.addWidget(self.SC_Tab_PREFS_field, 2, 4)

        # BRIGHTNESS ADJUSTMENT KEYBOARD MAPPING SECTION
        self.brightnessCW = QWidget()
        self.brightnessLay = QGridLayout(self.brightnessCW)

        self.SC_Dec_Bri_Small_field = singleKeySequenceEditCancel("/")
        self.brightnessLay.addWidget(QLabel("<strong>Brightness</strong><br>Small Decrease", alignment=Qt.AlignCenter), 1, 1)
        self.brightnessLay.addWidget(self.SC_Dec_Bri_Small_field, 2, 1)
        self.SC_Dec_Bri_Large_field = singleKeySequenceEditCancel("Ctrl+/")
        self.brightnessLay.addWidget(QLabel("<strong>Brightness</strong><br>Large Decrease", alignment=Qt.AlignCenter), 1, 2)
        self.brightnessLay.addWidget(self.SC_Dec_Bri_Large_field, 2, 2)
        self.SC_Inc_Bri_Small_field = singleKeySequenceEditCancel("*")
        self.brightnessLay.addWidget(QLabel("<strong>Brightness</strong><br>Small Increase", alignment=Qt.AlignCenter), 1, 3)
        self.brightnessLay.addWidget(self.SC_Inc_Bri_Small_field, 2, 3)
        self.SC_Inc_Bri_Large_field = singleKeySequenceEditCancel("Ctrl+*")
        self.brightnessLay.addWidget(QLabel("<strong>Brightness</strong><br>Large Increase", alignment=Qt.AlignCenter), 1, 4)
        self.brightnessLay.addWidget(self.SC_Inc_Bri_Large_field, 2, 4)

        # SLIDER ADJUSTMENT KEYBOARD MAPPING SECTIONS
        self.sliderAdjustmentCW = QWidget()
        self.sliderAdjustmentLay = QGridLayout(self.sliderAdjustmentCW)

        self.SC_Dec_1_Small_field = singleKeySequenceEditCancel("7")
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 1</strong><br>Small Decrease", alignment=Qt.AlignCenter), 1, 1)
        self.sliderAdjustmentLay.addWidget(self.SC_Dec_1_Small_field, 2, 1)
        self.SC_Dec_1_Large_field = singleKeySequenceEditCancel("Ctrl+7")
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 1</strong><br>Large Decrease", alignment=Qt.AlignCenter), 1, 2)
        self.sliderAdjustmentLay.addWidget(self.SC_Dec_1_Large_field, 2, 2)
        self.SC_Inc_1_Small_field = singleKeySequenceEditCancel("9")
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 1</strong><br>Small Increase", alignment=Qt.AlignCenter), 1, 3)
        self.sliderAdjustmentLay.addWidget(self.SC_Inc_1_Small_field, 2, 3)
        self.SC_Inc_1_Large_field = singleKeySequenceEditCancel("Ctrl+9")
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 1</strong><br>Large Increase", alignment=Qt.AlignCenter), 1, 4)
        self.sliderAdjustmentLay.addWidget(self.SC_Inc_1_Large_field, 2, 4)

        self.SC_Dec_2_Small_field = singleKeySequenceEditCancel("4")
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 2</strong><br>Small Decrease", alignment=Qt.AlignCenter), 3, 1)
        self.sliderAdjustmentLay.addWidget(self.SC_Dec_2_Small_field, 4, 1)
        self.SC_Dec_2_Large_field = singleKeySequenceEditCancel("Ctrl+4")
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 2</strong><br>Large Decrease", alignment=Qt.AlignCenter), 3, 2)
        self.sliderAdjustmentLay.addWidget(self.SC_Dec_2_Large_field, 4, 2)
        self.SC_Inc_2_Small_field = singleKeySequenceEditCancel("6")
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 2</strong><br>Small Increase", alignment=Qt.AlignCenter), 3, 3)
        self.sliderAdjustmentLay.addWidget(self.SC_Inc_2_Small_field, 4, 3)
        self.SC_Inc_2_Large_field = singleKeySequenceEditCancel("Ctrl+6")
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 2</strong><br>Large Increase", alignment=Qt.AlignCenter), 3, 4)
        self.sliderAdjustmentLay.addWidget(self.SC_Inc_2_Large_field, 4, 4)

        self.SC_Dec_3_Small_field = singleKeySequenceEditCancel("1")
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 3</strong><br>Small Decrease", alignment=Qt.AlignCenter), 5, 1)
        self.sliderAdjustmentLay.addWidget(self.SC_Dec_3_Small_field, 6, 1)
        self.SC_Dec_3_Large_field = singleKeySequenceEditCancel("Ctrl+1")
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 3</strong><br>Large Decrease", alignment=Qt.AlignCenter), 5, 2)
        self.sliderAdjustmentLay.addWidget(self.SC_Dec_3_Large_field, 6, 2)
        self.SC_Inc_3_Small_field = singleKeySequenceEditCancel("3")
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 3</strong><br>Small Increase", alignment=Qt.AlignCenter), 5, 3)
        self.sliderAdjustmentLay.addWidget(self.SC_Inc_3_Small_field, 6, 3)
        self.SC_Inc_3_Large_field = singleKeySequenceEditCancel("Ctrl+3")
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 3</strong><br>Large Increase", alignment=Qt.AlignCenter), 5, 4)
        self.sliderAdjustmentLay.addWidget(self.SC_Inc_3_Large_field, 6, 4)

        # BOTTOM BUTTONS
        self.bottomButtonsCW = QWidget()
        self.bottomButtonsLay = QGridLayout(self.bottomButtonsCW)

        self.bottomButtonsLay.addWidget(self.resetGlobalPrefsButton, 1, 1)
        self.bottomButtonsLay.addWidget(self.saveGlobalPrefsButton, 1, 2)

        # FINALLY, IT'S TIME TO BUILD THE PREFERENCES PANE ITSELF
        self.globalPrefsLay.addRow(QLabel("<strong><u>Main Program Options</strong></u>", alignment=Qt.AlignCenter))
        self.globalPrefsLay.addRow(self.findLightsOnStartup_check)
        self.globalPrefsLay.addRow(self.autoConnectToLights_check)
        self.globalPrefsLay.addRow(self.printDebug_check)
        self.globalPrefsLay.addRow(self.rememberLightsOnExit_check)
        self.globalPrefsLay.addRow(self.rememberPresetsOnExit_check)
        self.globalPrefsLay.addRow("Maximum Number of retries:", self.maxNumOfAttempts_field)
        self.globalPrefsLay.addRow(QLabel("<hr><strong><u>Acceptable IPs to use for the HTTP Server:</strong></u><br><em>Each line below is an IP allows access to NeewerLite-Python's HTTP server.<br>Wildcards for IP addresses can be entered by just leaving that section blank.<br><u>For example:</u><br><strong>192.168.*.*</strong> would be entered as just <strong>192.168.</strong><br><strong>10.0.1.*</strong> is <strong>10.0.1.</strong>", alignment=Qt.AlignCenter))
        self.globalPrefsLay.addRow(self.acceptable_HTTP_IPs_field)
        self.globalPrefsLay.addRow(QLabel("<hr><strong><u>Whitelisted MAC Addresses/GUIDs</u></strong><br><em>Devices with whitelisted MAC Addresses/GUIDs are added to the<br>list of lights even if their name doesn't contain <strong>Neewer</strong> in it.<br><br>This preference is really only useful if you have compatible lights<br>that don't show up properly due to name mismatches.</em>", alignment=Qt.AlignCenter))
        self.globalPrefsLay.addRow(self.whiteListedMACs_field)
        self.globalPrefsLay.addRow(QLabel("<hr><strong><u>Custom GUI Keyboard Shortcut Mapping - GUI Buttons</strong></u><br><em>To switch a keyboard shortcut, click on the old shortcut and type a new one in.<br>To reset a shortcut to default, click the X button next to it.</em><br><br>These 4 keyboard shortcuts control the buttons on the top of the window.", alignment=Qt.AlignCenter))
        self.globalPrefsLay.addRow(self.windowButtonsCW)
        self.globalPrefsLay.addRow(QLabel("<hr><strong><u>Custom GUI Keyboard Shortcut Mapping - Switching Mode Tabs</strong></u><br><em>To switch a keyboard shortcut, click on the old shortcut and type a new one in.<br>To reset a shortcut to default, click the X button next to it.</em><br><br>These 4 keyboard shortcuts switch between<br>the CCT, HSI, SCENE and LIGHT PREFS tabs.", alignment=Qt.AlignCenter))
        self.globalPrefsLay.addRow(self.tabSwitchCW)
        self.globalPrefsLay.addRow(QLabel("<hr><strong><u>Custom GUI Keyboard Shortcut Mapping - Increase/Decrease Brightness</strong></u><br><em>To switch a keyboard shortcut, click on the old shortcut and type a new one in.<br>To reset a shortcut to default, click the X button next to it.</em><br><br>These 4 keyboard shortcuts adjust the brightness of the selected light(s).", alignment=Qt.AlignCenter))
        self.globalPrefsLay.addRow(self.brightnessCW)
        self.globalPrefsLay.addRow(QLabel("<hr><strong><u>Custom GUI Keyboard Shortcut Mapping - Slider Adjustments</strong></u><br><em>To switch a keyboard shortcut, click on the old shortcut and type a new one in.<br>To reset a shortcut to default, click the X button next to it.</em><br><br>These 12 keyboard shortcuts adjust <em>up to 3 sliders</em> on the currently active tab.", alignment=Qt.AlignCenter))
        self.globalPrefsLay.addRow(self.sliderAdjustmentCW)
        self.globalPrefsLay.addRow(QLabel("<hr>"))
        self.globalPrefsLay.addRow(self.bottomButtonsCW)

        # === >> ADD THE TABS TO THE TAB WIDGET << ===
        self.ColorModeTabWidget.addTab(self.CCT, "CCT Mode")
        self.ColorModeTabWidget.addTab(self.HSI, "HSI Mode")
        self.ColorModeTabWidget.addTab(self.ANM, "Scene Mode")
        self.ColorModeTabWidget.addTab(self.lightPrefs, "Light Preferences")
        self.ColorModeTabWidget.addTab(self.globalPrefs, "Global Preferences")

        self.ColorModeTabWidget.setCurrentIndex(0) # make the CCT tab the main tab shown on launch

        # ============ THE STATUS BAR AND WINDOW ASSIGNS ============
        MainWindow.setCentralWidget(self.centralwidget)
        self.statusBar = QStatusBar(MainWindow)
        MainWindow.setStatusBar(self.statusBar)

class parameterWidget(QWidget):
    valueChanged = Signal(int) # return the value that's been changed

    def __init__(self, **kwargs):
        super(parameterWidget, self).__init__()

        if 'prefix' in kwargs:
            self.thePrefix = kwargs['prefix']
        else:
            self.thePrefix = "%"
        
        self.widgetTitle = QLabel(self)
        self.widgetTitle.setFont(mainFont)
        self.widgetTitle.setGeometry(0, 0, 440, 17)

        if 'title' in kwargs:
            self.widgetTitle.setText(kwargs['title'])    
        
        self.bgGradient = QGraphicsView(QGraphicsScene(self), self)
        self.bgGradient.setGeometry(0, 20, 552, 24)
        self.bgGradient.setFrameShape(QFrame.NoFrame)
        self.bgGradient.setFrameShadow(QFrame.Sunken)
        self.bgGradient.setAlignment(Qt.Alignment(combinePySide2Values([Qt.AlignLeft, Qt.AlignTop])))

        self.slider = QSlider(self)
        self.slider.setGeometry(0, 25, 552, 16)
        self.slider.setStyleSheet("QSlider::groove:horizontal" 
                                  "{"
                                  "border: 2px solid transparent;"
                                  "height: 12px;"
                                  "background: transparent;"
                                  "margin: 2px 0;"
                                  "}"
                                  "QSlider::handle:horizontal {"
                                  "background-color: rgba(255, 255, 255, 0.75);"
                                  "opacity:0.3;"
                                  "border: 2px solid #5c5c5c;"
                                  "width: 12px;"
                                  "margin: -2px 0;"
                                  "border-radius: 3px;"
                                  "}")
        
        if 'sliderOffset' in kwargs:
            self.sliderOffset = kwargs['sliderOffset']
        else:
            self.sliderOffset = 0

        if 'sliderMin' in kwargs:
            self.slider.setMinimum(kwargs['sliderMin'])
        else:
            self.slider.setMinimum(0)

        if 'sliderMax' in kwargs:
            self.slider.setMaximum(kwargs['sliderMax'])
        else:
            self.slider.setMaximum(100)

        if 'sliderVal' in kwargs:
            self.slider.setValue(kwargs['sliderVal'])
        else:
            self.slider.setValue(50)

        if 'gradient' in kwargs:
            self.gradient = kwargs['gradient']
            self.bgGradient.setBackgroundBrush(self.renderGradient(self.gradient)) 

        self.slider.setOrientation(Qt.Horizontal)
        self.slider.valueChanged.connect(self.sliderValueChanged)

        self.minTF = QLabel(self, text=str(self.slider.minimum() + self.sliderOffset) + self.thePrefix)
        self.minTF.setGeometry(0, 46, 184, 20)
        self.minTF.setAlignment(Qt.AlignLeft)

        self.valueTF = QLabel(self, text=str(self.slider.value() + self.sliderOffset) + self.thePrefix)
        self.valueTF.setFont(mainFont)
        self.valueTF.setGeometry(185, 42, 184, 20)
        self.valueTF.setAlignment(Qt.AlignCenter)

        self.maxTF = QLabel(self, text=str(self.slider.maximum() + self.sliderOffset) + self.thePrefix)
        self.maxTF.setGeometry(370, 46, 184, 20)
        self.maxTF.setAlignment(Qt.AlignRight)
    
    def value(self):
        return self.slider.value()

    def setValue(self, theValue):
        self.slider.setValue(int(theValue))

    def setRangeText(self, min, max):
        self.widgetTitle.setText("Range: " + str(min) + self.thePrefix + "-" + str(max) + self.thePrefix)

    def changeSliderRange(self, newRange):
        self.slider.setMinimum(newRange[0])
        self.slider.setMaximum(newRange[1])
        self.minTF.setText(str(newRange[0]) + self.thePrefix)
        self.maxTF.setText(str(newRange[1]) + self.thePrefix)

        if self.gradient == "TEMP":
            self.bgGradient.setBackgroundBrush(self.renderGradient(self.gradient))

    def sliderValueChanged(self, changeValue):
        self.valueTF.setText(str(changeValue  + self.sliderOffset) + self.thePrefix)
        self.valueChanged.emit(changeValue)

    def adjustSatGradient(self, hue):
        self.bgGradient.setBackgroundBrush(self.renderGradient("SAT", hue))

    def presentMe(self, parent, posX, posY, halfSize = False):
        self.setParent(parent) # move the control to a different tab parent

        if halfSize == False: # check all the sizes to make sure they're correct
            if self.widgetTitle.geometry() != QRect(0, 0, 440, 17):
                self.widgetTitle.setGeometry(0, 0, 440, 17)
            if self.bgGradient.geometry() != QRect(0, 20, 552, 24):
                self.bgGradient.setGeometry(0, 20, 552, 24)
            if self.slider.geometry() != QRect(0, 25, 552, 16):
                self.slider.setGeometry(0, 25, 552, 16)
            if self.minTF.geometry() != QRect(0, 46, 184, 20):
                self.minTF.setGeometry(0, 46, 184, 20)
            if self.valueTF.geometry() != QRect(185, 42, 184, 20):
                self.valueTF.setGeometry(185, 42, 184, 20)
            if self.maxTF.geometry() != QRect(370, 46, 184, 20):
                self.maxTF.setGeometry(370, 46, 184, 20)
        else:
            if self.widgetTitle.geometry() != QRect(0, 0, 216, 17):
                self.widgetTitle.setGeometry(0, 0, 216, 17)
            if self.bgGradient.geometry() != QRect(0, 20, 272, 24):
                self.bgGradient.setGeometry(0, 20, 272, 24)
            if self.slider.geometry() != QRect(0, 25, 272, 16):
                self.slider.setGeometry(0, 25, 272, 16)
            if self.minTF.geometry() != QRect(0, 46, 90, 20):
                self.minTF.setGeometry(0, 46, 90, 20)
            if self.valueTF.geometry() != QRect(90, 42, 90, 20):
                self.valueTF.setGeometry(90, 42, 90, 20)
            if self.maxTF.geometry() != QRect(180, 46, 90, 20):
                self.maxTF.setGeometry(180, 46, 90, 20)

        # finally move the entire control to a position and display it
        self.move(posX, posY)
        self.show()

    def renderGradient(self, gradientType, hue=180):
        returnGradient = QLinearGradient(0, 0, 1, 0)
        returnGradient.setCoordinateMode(returnGradient.ObjectMode)

        if gradientType == "TEMP": # color temperature gradient (calculate new gradient with new bounds)
            min = self.slider.minimum() * 100
            max = self.slider.maximum() * 100

            rangeStep = (max - min) / 4 # figure out how much in between steps of the gradient

            for i in range(5): # fill the gradient with a new set of colors
                rgbValues = self.convert_K_to_RGB(min + (rangeStep * i))                
                returnGradient.setColorAt((0.25 * i), QColor(rgbValues[0], rgbValues[1], rgbValues[2]))
        elif gradientType == "BRI": # brightness gradient
            returnGradient.setColorAt(0.0, QColor(0, 0, 0, 255)) # Dark
            returnGradient.setColorAt(1.0, QColor(255, 255, 255, 255)) # Light
        elif gradientType == "GM": # GM adjustment gradient
            returnGradient.setColorAt(0.0, QColor(255, 0, 255, 255)) # Full Magenta
            returnGradient.setColorAt(0.5, QColor(255, 255, 255, 255)) # White
            returnGradient.setColorAt(1.0, QColor(0, 255, 0, 255)) # Full Green
        elif gradientType == "RGB": # RGB 360º gradient
            returnGradient.setColorAt(0.0, QColor(255, 0, 0, 255))
            returnGradient.setColorAt(0.16, QColor(255, 255, 0, 255))
            returnGradient.setColorAt(0.33, QColor(0, 255, 0, 255))
            returnGradient.setColorAt(0.49, QColor(0, 255, 255, 255))
            returnGradient.setColorAt(0.66, QColor(0, 0, 255, 255))
            returnGradient.setColorAt(0.83, QColor(255, 0, 255, 255))
            returnGradient.setColorAt(1.0, QColor(255, 0, 0, 255))
        elif gradientType == "SAT": # color saturation gradient (calculate new gradient with base hue)
            returnGradient.setColorAt(0, QColor(255, 255, 255))
            newColor = self.convert_HSI_to_RGB(hue / 360)
            returnGradient.setColorAt(1, QColor(newColor[0], newColor[1], newColor[2]))
        elif gradientType == "SPEED": # speed setting gradient
            returnGradient.setColorAt(0.0, QColor(255, 255, 255, 255))
            returnGradient.setColorAt(1.0, QColor(0, 0, 255, 255))
        elif gradientType == "SPARKS": # sparks setting gradient
            returnGradient.setColorAt(0.0, QColor(255, 255, 255, 255))
            returnGradient.setColorAt(1.0, QColor(255, 0, 0, 255))

        return returnGradient
    
    # CALCULATE THE RGB VALUE OF COLOR TEMPERATURE
    def convert_K_to_RGB(self, Ktemp):
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

    def convert_HSI_to_RGB(self, h, s = 1, v = 1):
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

class doubleSlider(QWidget):
    valueChanged = Signal(int, int) # return left value, right value

    def __init__(self, **kwargs):
        super(doubleSlider, self).__init__()

        if 'sliderType' in kwargs:
            self.sliderType = kwargs['sliderType']
        else:
            self.sliderType = "RGB"

        if self.sliderType == "RGB":
            self.leftSlider = parameterWidget(title="Hue Limits", gradient="RGB", sliderMin=0, sliderVal=0, sliderMax=360, prefix="º")
            self.rightSlider = parameterWidget(title="Range: 0º-360º", gradient="RGB", sliderMin=0, sliderVal=360, sliderMax=360, prefix="º")
        elif self.sliderType == "BRI":
            self.leftSlider = parameterWidget(title="Brightness Limits", gradient="BRI", sliderMin=0, sliderVal=0, sliderMax=100, prefix="%")
            self.rightSlider = parameterWidget(title="Range: 0%-100%", gradient="BRI", sliderMin=0, sliderVal=100, sliderMax=100, prefix="%")
        elif self.sliderType == "TEMP":
            self.leftSlider = parameterWidget(title="Color Temperature Limits", gradient="TEMP", sliderMin=32, sliderVal=32, sliderMax=72, prefix="00K")
            self.rightSlider = parameterWidget(title="Range: 3200K-5600K", gradient="TEMP", sliderMin=32, sliderVal=72, sliderMax=72, prefix="00K")
    
        self.leftSlider.valueChanged.connect(self.doubleSliderValueChanged)
        self.rightSlider.valueChanged.connect(self.doubleSliderValueChanged)

        self.leftSlider.presentMe(self, 0, 0, True)
        self.rightSlider.presentMe(self, 282, 0, True)

    def doubleSliderValueChanged(self):
        leftSliderValue = self.leftSlider.value()
        rightSliderValue = self.rightSlider.value()

        if leftSliderValue > rightSliderValue:
            self.rightSlider.setValue(leftSliderValue)
        if rightSliderValue < leftSliderValue:
            self.leftSlider.setValue(rightSliderValue)

        self.rightSlider.setRangeText(leftSliderValue, rightSliderValue)
        self.valueChanged.emit(leftSliderValue, rightSliderValue)

    def changeSliderRange(self, newRange):
        self.leftSlider.changeSliderRange(newRange)
        self.rightSlider.changeSliderRange(newRange)

    def value(self):
        return([self.leftSlider.value(), self.rightSlider.value()])
    
    def setValue(self, theSlider, theValue):
        if theSlider == "left":
            self.leftSlider.setValue(theValue)
        elif theSlider == "right":
            self.rightSlider.setValue(theValue)

    def presentMe(self, parent, posX, posY):
        self.setParent(parent)
        self.move(posX, posY)
        self.show()

class customPresetButton(QLabel):
    clicked = Signal() # signal sent when you click on the button
    rightclicked = Signal() # signal sent when you right-click on the button
    enteredWidget = Signal() # signal sent when the mouse enters the button
    leftWidget = Signal() # signal sent when the mouse leaves the button

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if platform.system() == "Windows": # Windows font
            customPresetFont = QFont("Calibri")
            customPresetFont.setPointSize(10.5)
            self.setFont(customPresetFont)
        elif platform.system() == "Linux": # Linux (Ubuntu) font
            customPresetFont = QFont()
            customPresetFont.setPointSize(10.5)
            self.setFont(customPresetFont)
        else: # fallback font
            customPresetFont = QFont()
            customPresetFont.setPointSize(12)
            self.setFont(customPresetFont)

        self.setAlignment(Qt.AlignCenter)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setText(kwargs['text'])

        self.setStyleSheet("customPresetButton"
                           "{"
                           "border: 1px solid grey; background-color: #a5cbf7;"
                           "}"
                           "customPresetButton::hover"
                           "{"
                           "background-color: #a5e3f7;"
                           "}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        elif event.button() == Qt.RightButton:
            self.rightclicked.emit()

    def enterEvent(self, event):
        self.enteredWidget.emit()

    def leaveEvent(self, event):
        self.leftWidget.emit()

    def markCustom(self, presetNum, isSnap = 0):
        if isSnap == 0: # we're using a global preset
            self.setText("<strong><font size=+2>" + str(presetNum + 1) + "</font></strong><br>CUSTOM<br>GLOBAL")

            self.setStyleSheet("customPresetButton"
                           "{"
                           "border: 1px solid grey; background-color: #7188ff;"
                           "}"
                           "customPresetButton::hover"
                           "{"
                           "background-color: #70b0ff;"
                           "}")
        elif isSnap >= 1: # we're using a snapshot preset
            self.setText("<strong><font size=+2>" + str(presetNum + 1) + "</font></strong><br>CUSTOM<br>SNAP")

            self.setStyleSheet("customPresetButton"
                           "{"
                           "border: 1px solid grey; background-color: #71e993;"
                           "}"
                           "customPresetButton::hover"
                           "{"
                           "background-color: #abe9ab;"
                           "}")
        else: # we're resetting back to a default preset
            self.setText("<strong><font size=+2>" + str(presetNum + 1) + "</font></strong><br>PRESET<br>GLOBAL")

            self.setStyleSheet("customPresetButton"
                           "{"
                           "border: 1px solid grey; background-color: #a5cbf7;"
                           "}"
                           "customPresetButton::hover"
                           "{"
                           "background-color: #a5e3f7;"
                           "}")

class singleKeySequenceEditCancel(QWidget):
    def __init__(self, defaultValue):
        super(singleKeySequenceEditCancel, self).__init__()
        self.defaultValue = defaultValue # the default keyboard shortcut for this field

        customLayout = QGridLayout()
        customLayout.setContentsMargins(0, 0, 0, 0) # don't use any extra padding for this control

        # THE KEYBOARD SHORTCUT FIELD
        self.keyPressField = singleKeySequenceEdit()
        # self.keyPressField.setToolTip("Click on this field and type in a new keyboard shortcut to register it")

        # THE RESET BUTTON
        self.resetButton = QLabel("X", alignment=Qt.AlignCenter)
        self.resetButton.setFixedWidth(24)
        self.resetButton.setStyleSheet("QLabel"
                                       "{"
                                       "border: 1px solid black; background-color: light grey;"
                                       "}"
                                       "QLabel::hover"
                                       "{"
                                       "background-color: salmon;"
                                       "}")
        # self.resetButton.setToolTip("Click on this button to reset the current keyboard shortcut to it's default value")
        self.resetButton.mousePressEvent = self.resetValue

        customLayout.addWidget(self.keyPressField, 1, 1)
        customLayout.addWidget(self.resetButton, 1, 2)

        self.setMaximumWidth(135) # make sure the entire control is no longer than 135 pixels wide
        self.setLayout(customLayout)

    def keySequence(self):
        return self.keyPressField.keySequence()

    def setKeySequence(self, keySequence):
        self.keyPressField.setKeySequence(keySequence)

    def resetValue(self, event):
        self.keyPressField.setKeySequence(self.defaultValue)

class singleKeySequenceEdit(QKeySequenceEdit):
    # CUSTOM VERSION OF QKeySequenceEdit THAT ONLY ACCEPTS ONE COMBINATION BEFORE RETURNING
    def keyPressEvent(self, event):
        super(singleKeySequenceEdit, self).keyPressEvent(event)

        theString = self.keySequence().toString(QKeySequence.NativeText)

        if theString:
            lastSequence = theString.split(",")[-1].strip()
            self.setKeySequence(lastSequence)