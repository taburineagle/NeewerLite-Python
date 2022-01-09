from PySide2.QtCore import QRect
from PySide2.QtGui import QFont, QLinearGradient, QColor, Qt, QKeySequence
from PySide2.QtWidgets import QFormLayout, QGridLayout, QKeySequenceEdit, QWidget, QPushButton, QTableWidget, QTableWidgetItem, QAbstractScrollArea, QAbstractItemView, \
                              QTabWidget, QGraphicsScene, QGraphicsView, QFrame, QSlider, QLabel, QLineEdit, QCheckBox, QStatusBar, QScrollArea, QTextEdit

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        # ============ FONTS AND OTHER WINDOW SPECIFICS ============
        mainFont = QFont()
        mainFont.setBold(True)
        mainFont.setWeight(75)

        MainWindow.setFixedSize(590, 521) # the main window should be this size at launch, and no bigger
        MainWindow.setWindowTitle("NeewerLite-Python 0.7 by Zach Glenwright")
        
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

        # ============ THE MODE TABS ============
        self.ColorModeTabWidget = QTabWidget(self.centralwidget)
        self.ColorModeTabWidget.setGeometry(QRect(10, 300, 571, 201))

        # === >> THE CCT TAB << ===
        self.CCT = QWidget()

        # DRAW THE LINEAR GRADIENT TO INDICATE THE COLOR TEMPERATURE VALUE IN THE CCT TAB
        # NEW DEFAULT OF 5600K FOR LIGHTS THAT DON'T SCALE UP TO 8500K
        mySceneCCT = QGraphicsScene(self)

        gradient = QLinearGradient(0, 0, 532, 31)
        gradient.setColorAt(0.0, QColor(255, 187, 120, 255)) # 3200K
        gradient.setColorAt(0.25, QColor(255, 204, 153, 255)) # 3800K
        gradient.setColorAt(0.50, QColor(255, 217, 182, 255)) # 4400K
        gradient.setColorAt(0.75, QColor(255, 228, 206, 255)) # 5000K
        gradient.setColorAt(1.0, QColor(255, 238, 227, 255)) # 5600K
    
        mySceneCCT.setBackgroundBrush(gradient)
        
        self.CCT_Temp_Gradient_BG = QGraphicsView(mySceneCCT, self.CCT)
        self.CCT_Temp_Gradient_BG.setGeometry(QRect(9, 10, 552, 31))
        self.CCT_Temp_Gradient_BG.setFrameShape(QFrame.NoFrame)
        self.CCT_Temp_Gradient_BG.setFrameShadow(QFrame.Sunken)
        self.CCT_Temp_Gradient_BG.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignTop)
        
        self.Slider_CCT_Hue = QSlider(self.CCT)
        self.Slider_CCT_Hue.setGeometry(QRect(10, 20, 551, 16))
        self.Slider_CCT_Hue.setMinimum(32)
        self.Slider_CCT_Hue.setMaximum(56)
        self.Slider_CCT_Hue.setSliderPosition(56)
        self.Slider_CCT_Hue.setOrientation(Qt.Horizontal)

        self.TFL_CCT_Hue = QLabel(self.CCT)
        self.TFL_CCT_Hue.setGeometry(QRect(10, 40, 440, 17))
        self.TFL_CCT_Hue.setText("Color Temperature")
        self.TFL_CCT_Hue.setFont(mainFont)

        self.TFV_CCT_Hue = QLabel(self.CCT)
        self.TFV_CCT_Hue.setGeometry(QRect(510, 40, 51, 20))
        self.TFV_CCT_Hue.setText("5600K")
        self.TFV_CCT_Hue.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.Slider_CCT_Bright = QSlider(self.CCT)
        self.Slider_CCT_Bright.setGeometry(QRect(10, 70, 551, 16))
        self.Slider_CCT_Bright.setMaximum(100)
        self.Slider_CCT_Bright.setSliderPosition(100)
        self.Slider_CCT_Bright.setOrientation(Qt.Horizontal)

        self.TFV_CCT_Bright = QLabel(self.CCT)
        self.TFV_CCT_Bright.setGeometry(QRect(510, 90, 51, 20))
        self.TFV_CCT_Bright.setText("100")
        self.TFV_CCT_Bright.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.TFL_CCT_Bright = QLabel(self.CCT)
        self.TFL_CCT_Bright.setGeometry(QRect(10, 90, 440, 17))
        self.TFL_CCT_Bright.setText("Brightness")
        self.TFL_CCT_Bright.setFont(mainFont)
        
        # === >> THE HSI TAB << ===
        self.HSI = QWidget()

        # DRAW THE LINEAR GRADIENT TO INDICATE THE HUE VALUE IN THE HSI TAB
        mySceneHSI = QGraphicsScene(self)

        gradient = QLinearGradient(0, 0, 532, 31)
        gradient.setColorAt(0.0, QColor(255, 0, 0, 255))
        gradient.setColorAt(0.16, QColor(255, 255, 0, 255))
        gradient.setColorAt(0.33, QColor(0, 255, 0, 255))
        gradient.setColorAt(0.49, QColor(0, 255, 255, 255))
        gradient.setColorAt(0.66, QColor(0, 0, 255, 255))
        gradient.setColorAt(0.83, QColor(255, 0, 255, 255))
        gradient.setColorAt(1.0, QColor(255, 0, 0, 255))
    
        mySceneHSI.setBackgroundBrush(gradient)
        
        self.HSI_Hue_Gradient_BG = QGraphicsView(mySceneHSI, self.HSI)        
        self.HSI_Hue_Gradient_BG.setObjectName(u"HSI_Hue_Gradient_BG")
        self.HSI_Hue_Gradient_BG.setGeometry(QRect(9, 10, 552, 31))
        self.HSI_Hue_Gradient_BG.setFrameShape(QFrame.NoFrame)
        self.HSI_Hue_Gradient_BG.setFrameShadow(QFrame.Sunken)
        self.HSI_Hue_Gradient_BG.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignTop)

        self.Slider_HSI_1_H = QSlider(self.HSI)
        self.Slider_HSI_1_H.setGeometry(QRect(10, 20, 551, 16))
        self.Slider_HSI_1_H.setMaximum(360)
        self.Slider_HSI_1_H.setSliderPosition(240)
        self.Slider_HSI_1_H.setOrientation(Qt.Horizontal)

        self.TFL_HSI_1_H = QLabel(self.HSI)
        self.TFL_HSI_1_H.setGeometry(QRect(10, 40, 440, 17))
        self.TFL_HSI_1_H.setText("Hue")
        self.TFL_HSI_1_H.setFont(mainFont)

        self.TFV_HSI_1_H = QLabel(self.HSI)
        self.TFV_HSI_1_H.setGeometry(QRect(510, 40, 51, 20))
        self.TFV_HSI_1_H.setText("240")
        self.TFV_HSI_1_H.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.Slider_HSI_2_S = QSlider(self.HSI)
        self.Slider_HSI_2_S.setGeometry(QRect(10, 70, 551, 16))
        self.Slider_HSI_2_S.setMaximum(100)
        self.Slider_HSI_2_S.setSliderPosition(100)
        self.Slider_HSI_2_S.setOrientation(Qt.Horizontal)

        self.TFL_HSI_2_S = QLabel(self.HSI)
        self.TFL_HSI_2_S.setGeometry(QRect(10, 90, 440, 17))
        self.TFL_HSI_2_S.setText("Saturation")
        self.TFL_HSI_2_S.setFont(mainFont)

        self.TFV_HSI_2_S = QLabel(self.HSI)
        self.TFV_HSI_2_S.setGeometry(QRect(510, 90, 51, 20))
        self.TFV_HSI_2_S.setText("100")
        self.TFV_HSI_2_S.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        
        self.Slider_HSI_3_L = QSlider(self.HSI)
        self.Slider_HSI_3_L.setGeometry(QRect(10, 120, 551, 16))
        self.Slider_HSI_3_L.setMaximum(100)
        self.Slider_HSI_3_L.setSliderPosition(100)
        self.Slider_HSI_3_L.setOrientation(Qt.Horizontal)
        
        self.TFL_HSI_3_L = QLabel(self.HSI)
        self.TFL_HSI_3_L.setObjectName(u"TFL_HSI_3_L")
        self.TFL_HSI_3_L.setGeometry(QRect(10, 140, 481, 17))
        self.TFL_HSI_3_L.setText("Intensity (Brightness)")
        self.TFL_HSI_3_L.setFont(mainFont)
        
        self.TFV_HSI_3_L = QLabel(self.HSI)
        self.TFV_HSI_3_L.setObjectName(u"TFV_HSI_3_L")
        self.TFV_HSI_3_L.setGeometry(QRect(510, 140, 51, 20))
        self.TFV_HSI_3_L.setText("100")
        self.TFV_HSI_3_L.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        # === >> THE SCENE TAB << ===
        self.ANM = QWidget()

        self.Slider_ANM_Brightness = QSlider(self.ANM)
        self.Slider_ANM_Brightness.setGeometry(QRect(10, 10, 551, 16))
        self.Slider_ANM_Brightness.setMaximum(100)
        self.Slider_ANM_Brightness.setSliderPosition(100)
        self.Slider_ANM_Brightness.setOrientation(Qt.Horizontal)

        self.TFL_ANM_Brightness = QLabel(self.ANM)
        self.TFL_ANM_Brightness.setGeometry(QRect(10, 25, 300, 17))
        self.TFL_ANM_Brightness.setText("Brightness")
        self.TFL_ANM_Brightness.setFont(mainFont)

        self.TFV_ANM_Brightness = QLabel(self.ANM)
        self.TFV_ANM_Brightness.setGeometry(QRect(510, 25, 51, 20))
        self.TFV_ANM_Brightness.setText("100")
        self.TFV_ANM_Brightness.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        
        self.TFL_A_policeAnim = QLabel(self.ANM)
        self.TFL_A_policeAnim.setGeometry(QRect(10, 46, 40, 40))
        self.TFL_A_policeAnim.setText("<html><head/><body><p><font size=\"8\">&#x1F6A8;</font></p></body></html>")
        self.Button_1_police_A = QPushButton(self.ANM)
        self.Button_1_police_A.setGeometry(QRect(50, 50, 160, 31))
        self.Button_1_police_A.setText("(1) Squad Car")
        self.Button_1_police_B = QPushButton(self.ANM)
        self.Button_1_police_B.setGeometry(QRect(220, 50, 160, 31))
        self.Button_1_police_B.setText("(2) Ambulance")
        self.Button_1_police_C = QPushButton(self.ANM)
        self.Button_1_police_C.setGeometry(QRect(390, 50, 160, 31))
        self.Button_1_police_C.setText("(3) Fire Engine")

        self.TFL_B_partyAnim = QLabel(self.ANM)
        self.TFL_B_partyAnim.setGeometry(QRect(10, 84, 40, 40))
        self.TFL_B_partyAnim.setText("<html><head/><body><p><font size=\"8\">&#x1F389;</font></p></body></html>")
        self.Button_2_party_A = QPushButton(self.ANM)
        self.Button_2_party_A.setGeometry(QRect(50, 90, 160, 31))
        self.Button_2_party_A.setText("(4) Fireworks")
        self.Button_2_party_B = QPushButton(self.ANM)
        self.Button_2_party_B.setGeometry(QRect(220, 90, 160, 31))
        self.Button_2_party_B.setText("(5) Party")
        self.Button_2_party_C = QPushButton(self.ANM)
        self.Button_2_party_C.setGeometry(QRect(390, 90, 160, 31))
        self.Button_2_party_C.setText("(6) Candle Light")

        self.TFL_C_lightningAnim = QLabel(self.ANM)
        self.TFL_C_lightningAnim.setGeometry(QRect(10, 126, 40, 40))
        self.TFL_C_lightningAnim.setText("<html><head/><body><p><font size=\"8\">&#x26A1;</font></p></body></html>")
        self.Button_3_lightning_A = QPushButton(self.ANM)
        self.Button_3_lightning_A.setGeometry(QRect(50, 130, 160, 31))
        self.Button_3_lightning_A.setText("(7) Lightning")
        self.Button_3_lightning_B = QPushButton(self.ANM)
        self.Button_3_lightning_B.setGeometry(QRect(220, 130, 160, 31))        
        self.Button_3_lightning_B.setText("(8) Paparazzi")
        self.Button_3_lightning_C = QPushButton(self.ANM)
        self.Button_3_lightning_C.setGeometry(QRect(390, 130, 160, 31))     
        self.Button_3_lightning_C.setText("(9) Screen")
     
        # === >> THE LIGHT PREFS TAB << ===
        self.lightPrefs = QWidget()

        self.customNameTF = QLineEdit(self.lightPrefs)
        self.customNameTF.setGeometry(QRect(10, 34, 541, 20))
        self.customNameTF.setMaxLength(80)
        
        self.customNameDescription = QLabel(self.lightPrefs)
        self.customNameDescription.setGeometry(QRect(10, 14, 541, 16))
        self.customNameDescription.setText("Custom Name for this light: (optional)")
        self.customNameDescription.setFont(mainFont)

        self.widerRangeCheck = QCheckBox(self.lightPrefs)
        self.widerRangeCheck.setGeometry(QRect(10, 70, 541, 31))
        self.widerRangeCheck.setText("Allow wider range of color temperatures for the CCT slider\n(for lights that support it, like the SL-80)")
        self.widerRangeCheck.setFont(mainFont)

        self.onlyCCTModeCheck = QCheckBox(self.lightPrefs)        
        self.onlyCCTModeCheck.setGeometry(QRect(10, 120, 401, 31))
        self.onlyCCTModeCheck.setText("This light can only use CCT mode\n(for SNL-660 and other Neewer LED/Ring lights)")
        self.onlyCCTModeCheck.setFont(mainFont)
        
        self.saveLightPrefsButton = QPushButton(self.lightPrefs)
        self.saveLightPrefsButton.setGeometry(QRect(416, 130, 141, 23))
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
        self.rememberLightsOnExit_check = QCheckBox("Remember the last parameters set for lights on exit")
        self.maxNumOfAttempts_field = QLineEdit()
        self.maxNumOfAttempts_field.setFixedWidth(35)
        self.acceptable_HTTP_IPs_field = QTextEdit()
        self.acceptable_HTTP_IPs_field.setFixedHeight(70)
        self.saveGlobalPrefsButton = QPushButton("Save Global Preferences")

        # THE FIRST SECTION OF KEYBOARD MAPPING SECTION
        self.windowButtonsCW = QWidget()
        self.windowButtonsLay = QGridLayout(self.windowButtonsCW)
        
        self.SC_turnOffButton_field = singleKeySequenceEdit()
        self.windowButtonsLay.addWidget(QLabel("<strong>Window Top</strong><br>Turn Light(s) Off", alignment=Qt.AlignCenter), 1, 1)
        self.windowButtonsLay.addWidget(self.SC_turnOffButton_field, 2, 1)
        self.SC_turnOnButton_field = singleKeySequenceEdit()
        self.windowButtonsLay.addWidget(QLabel("<strong>Window Top</strong><br>Turn Light(s) On", alignment=Qt.AlignCenter), 1, 2)
        self.windowButtonsLay.addWidget(self.SC_turnOnButton_field, 2, 2)
        self.SC_scanCommandButton_field = singleKeySequenceEdit()
        self.windowButtonsLay.addWidget(QLabel("<strong>Window Top</strong><br>Scan/Re-Scan", alignment=Qt.AlignCenter), 1, 3)
        self.windowButtonsLay.addWidget(self.SC_scanCommandButton_field, 2, 3)
        self.SC_tryConnectButton_field = singleKeySequenceEdit()
        self.windowButtonsLay.addWidget(QLabel("<strong>Window Top</strong><br>Connect", alignment=Qt.AlignCenter), 1, 4)
        self.windowButtonsLay.addWidget(self.SC_tryConnectButton_field, 2, 4)

        # SWITCHING BETWEEN TABS KEYBOARD MAPPING SECTION
        self.tabSwitchCW = QWidget()
        self.tabSwitchLay = QGridLayout(self.tabSwitchCW)

        self.SC_Tab_CCT_field = singleKeySequenceEdit()
        self.tabSwitchLay.addWidget(QLabel("<strong>Switching Tabs</strong><br>To CCT", alignment=Qt.AlignCenter), 1, 1)
        self.tabSwitchLay.addWidget(self.SC_Tab_CCT_field, 2, 1)
        self.SC_Tab_HSI_field = singleKeySequenceEdit()
        self.tabSwitchLay.addWidget(QLabel("<strong>Switching Tabs</strong><br>To HSI", alignment=Qt.AlignCenter), 1, 2)
        self.tabSwitchLay.addWidget(self.SC_Tab_HSI_field, 2, 2)
        self.SC_Tab_SCENE_field = singleKeySequenceEdit()
        self.tabSwitchLay.addWidget(QLabel("<strong>Switching Tabs</strong><br>To SCENE", alignment=Qt.AlignCenter), 1, 3)
        self.tabSwitchLay.addWidget(self.SC_Tab_SCENE_field, 2, 3)
        self.SC_Tab_PREFS_field = singleKeySequenceEdit()
        self.tabSwitchLay.addWidget(QLabel("<strong>Switching Tabs</strong><br>To Light Prefs", alignment=Qt.AlignCenter), 1, 4)
        self.tabSwitchLay.addWidget(self.SC_Tab_PREFS_field, 2, 4)

        # BRIGHTNESS ADJUSTMENT KEYBOARD MAPPING SECTION
        self.brightnessCW = QWidget()
        self.brightnessLay = QGridLayout(self.brightnessCW)

        self.SC_Dec_Bri_Small_field = singleKeySequenceEdit()
        self.brightnessLay.addWidget(QLabel("<strong>Brightness</strong><br>Small Decrease", alignment=Qt.AlignCenter), 1, 1)
        self.brightnessLay.addWidget(self.SC_Dec_Bri_Small_field, 2, 1)
        self.SC_Dec_Bri_Large_field = singleKeySequenceEdit()
        self.brightnessLay.addWidget(QLabel("<strong>Brightness</strong><br>Large Decrease", alignment=Qt.AlignCenter), 1, 2)
        self.brightnessLay.addWidget(self.SC_Dec_Bri_Large_field, 2, 2)
        self.SC_Inc_Bri_Small_field = singleKeySequenceEdit()
        self.brightnessLay.addWidget(QLabel("<strong>Brightness</strong><br>Small Increase", alignment=Qt.AlignCenter), 1, 3)
        self.brightnessLay.addWidget(self.SC_Inc_Bri_Small_field, 2, 3)
        self.SC_Inc_Bri_Large_field = singleKeySequenceEdit()
        self.brightnessLay.addWidget(QLabel("<strong>Brightness</strong><br>Large Increase", alignment=Qt.AlignCenter), 1, 4)
        self.brightnessLay.addWidget(self.SC_Inc_Bri_Large_field, 2, 4)

        # SLIDER ADJUSTMENT KEYBOARD MAPPING SECTIONS
        self.sliderAdjustmentCW = QWidget()
        self.sliderAdjustmentLay = QGridLayout(self.sliderAdjustmentCW)

        self.SC_Dec_1_Small_field = singleKeySequenceEdit()
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 1</strong><br>Small Decrease", alignment=Qt.AlignCenter), 1, 1)
        self.sliderAdjustmentLay.addWidget(self.SC_Dec_1_Small_field, 2, 1)
        self.SC_Dec_1_Large_field = singleKeySequenceEdit()
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 1</strong><br>Large Decrease", alignment=Qt.AlignCenter), 1, 2)
        self.sliderAdjustmentLay.addWidget(self.SC_Dec_1_Large_field, 2, 2)
        self.SC_Inc_1_Small_field = singleKeySequenceEdit()
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 1</strong><br>Small Increase", alignment=Qt.AlignCenter), 1, 3)
        self.sliderAdjustmentLay.addWidget(self.SC_Inc_1_Small_field, 2, 3)
        self.SC_Inc_1_Large_field = singleKeySequenceEdit()
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 1</strong><br>Large Increase", alignment=Qt.AlignCenter), 1, 4)
        self.sliderAdjustmentLay.addWidget(self.SC_Inc_1_Large_field, 2, 4)

        self.SC_Dec_2_Small_field = singleKeySequenceEdit()
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 2</strong><br>Small Decrease", alignment=Qt.AlignCenter), 3, 1)
        self.sliderAdjustmentLay.addWidget(self.SC_Dec_2_Small_field, 4, 1)
        self.SC_Dec_2_Large_field = singleKeySequenceEdit()
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 2</strong><br>Large Decrease", alignment=Qt.AlignCenter), 3, 2)
        self.sliderAdjustmentLay.addWidget(self.SC_Dec_2_Large_field, 4, 2)
        self.SC_Inc_2_Small_field = singleKeySequenceEdit()
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 2</strong><br>Small Increase", alignment=Qt.AlignCenter), 3, 3)
        self.sliderAdjustmentLay.addWidget(self.SC_Inc_2_Small_field, 4, 3)
        self.SC_Inc_2_Large_field = singleKeySequenceEdit()
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 2</strong><br>Large Increase", alignment=Qt.AlignCenter), 3, 4)
        self.sliderAdjustmentLay.addWidget(self.SC_Inc_2_Large_field, 4, 4)

        self.SC_Dec_3_Small_field = singleKeySequenceEdit()
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 3</strong><br>Small Decrease", alignment=Qt.AlignCenter), 5, 1)
        self.sliderAdjustmentLay.addWidget(self.SC_Dec_3_Small_field, 6, 1)
        self.SC_Dec_3_Large_field = singleKeySequenceEdit()
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 3</strong><br>Large Decrease", alignment=Qt.AlignCenter), 5, 2)
        self.sliderAdjustmentLay.addWidget(self.SC_Dec_3_Large_field, 6, 2)
        self.SC_Inc_3_Small_field = singleKeySequenceEdit()
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 3</strong><br>Small Increase", alignment=Qt.AlignCenter), 5, 3)
        self.sliderAdjustmentLay.addWidget(self.SC_Inc_3_Small_field, 6, 3)
        self.SC_Inc_3_Large_field = singleKeySequenceEdit()
        self.sliderAdjustmentLay.addWidget(QLabel("<strong>Slider 3</strong><br>Large Increase", alignment=Qt.AlignCenter), 5, 4)
        self.sliderAdjustmentLay.addWidget(self.SC_Inc_3_Large_field, 6, 4)        

        # FINALLY, IT'S TIME TO BUILD THE PREFERENCES PANE ITSELF
        self.globalPrefsLay.addRow(QLabel("<strong><u>Main Program Options</strong></u>", alignment=Qt.AlignCenter))
        self.globalPrefsLay.addRow(self.findLightsOnStartup_check)
        self.globalPrefsLay.addRow(self.autoConnectToLights_check)
        self.globalPrefsLay.addRow(self.printDebug_check)
        self.globalPrefsLay.addRow(self.rememberLightsOnExit_check)
        self.globalPrefsLay.addRow("Maximum Number of attempts to try (linking, sending, etc.) before erroring out:", self.maxNumOfAttempts_field)
        self.globalPrefsLay.addRow(QLabel("<hr><strong><u>Acceptable IPs to use for the HTTP Server:</strong></u><br><em>Each line below is an IPV4 IP that allows access to NeewerLite-Python's HTTP server.<br>Wildcards for IP addresses can be entered by just leaving that section blank.<br>For example, 192.168.*.* would be entered as just 192.168 - 10.0.1.* is 10.0.1", alignment=Qt.AlignCenter))
        self.globalPrefsLay.addRow(self.acceptable_HTTP_IPs_field)
        self.globalPrefsLay.addRow(QLabel("<hr><strong><u>Custom GUI Keyboard Shortcut Mapping - GUI Buttons</strong></u><br><em>To switch a keyboard shortcut, click on the old shortcut and type a new one in.</em><br><br>These 4 keyboard shortcuts control the buttons on the top of the window.", alignment=Qt.AlignCenter))
        self.globalPrefsLay.addRow(self.windowButtonsCW)
        self.globalPrefsLay.addRow(QLabel("<hr><strong><u>Custom GUI Keyboard Shortcut Mapping - Switching Mode Tabs</strong></u><br><em>To switch a keyboard shortcut, click on the old shortcut and type a new one in.</em><br><br>These 4 keyboard shortcuts switch between the CCT, HSI, SCENE and LIGHT PREFS tabs.", alignment=Qt.AlignCenter))
        self.globalPrefsLay.addRow(self.tabSwitchCW)
        self.globalPrefsLay.addRow(QLabel("<hr><strong><u>Custom GUI Keyboard Shortcut Mapping - Increase/Decrease Brightness</strong></u><br><em>To switch a keyboard shortcut, click on the old shortcut and type a new one in.</em><br><br>These 4 keyboard shortcuts adjust the brightness of the selected light(s).", alignment=Qt.AlignCenter))
        self.globalPrefsLay.addRow(self.brightnessCW)
        self.globalPrefsLay.addRow(QLabel("<hr><strong><u>Custom GUI Keyboard Shortcut Mapping - Slider Adjustments</strong></u><br><em>To switch a keyboard shortcut, click on the old shortcut and type a new one in.</em><br><br>These 12 keyboard shortcuts adjust <em>up to 3 sliders</em> on the currently active tab.<br>If the currently active tab doesn't have a 2nd (SCENE) or 3rd (CCT) slider, then the<br>shortcuts for those sliders don't do anything on that tab.", alignment=Qt.AlignCenter))
        self.globalPrefsLay.addRow(self.sliderAdjustmentCW)
        self.globalPrefsLay.addRow(QLabel("<hr>"))
        self.globalPrefsLay.addRow(self.saveGlobalPrefsButton)

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

        # ============ CONNECTIONS ============
        self.Slider_CCT_Bright.valueChanged.connect(self.TFV_CCT_Bright.setNum)
        self.Slider_HSI_1_H.valueChanged.connect(self.TFV_HSI_1_H.setNum)
        self.Slider_HSI_2_S.valueChanged.connect(self.TFV_HSI_2_S.setNum)
        self.Slider_HSI_3_L.valueChanged.connect(self.TFV_HSI_3_L.setNum)
        self.Slider_ANM_Brightness.valueChanged.connect(self.TFV_ANM_Brightness.setNum)

class singleKeySequenceEdit(QKeySequenceEdit):
    # CUSTOM VERSION OF QKeySequenceEdit THAT ONLY ACCEPTS ONE COMBINATION BEFORE RETURNING
    def __init__(self):
        super(singleKeySequenceEdit, self).__init__()
        self.setFixedWidth(90) # set the size to all of these widgets to 90

    def keyPressEvent(self, event):
        super(singleKeySequenceEdit, self).keyPressEvent(event)

        theString = self.keySequence().toString(QKeySequence.NativeText)
            
        if theString:
            lastSequence = theString.split(",")[-1].strip()
            self.setKeySequence(lastSequence)