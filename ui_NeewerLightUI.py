from PySide2.QtCore import QRect
from PySide2.QtGui import QFont, QLinearGradient, QColor, Qt
from PySide2.QtWidgets import QWidget, QPushButton, QTableWidget, QTableWidgetItem, QAbstractScrollArea, QAbstractItemView, \
                              QTabWidget, QGraphicsScene, QGraphicsView, QFrame, QSlider, QLabel, QLineEdit, QCheckBox, QStatusBar

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        # ============ FONTS AND OTHER WINDOW SPECIFICS ============
        mainFont = QFont()
        mainFont.setBold(True)
        mainFont.setWeight(75)

        MainWindow.setFixedSize(590, 521) # the main window should be this size at launch, and no bigger
        MainWindow.setWindowTitle("NeewerLite-Python 0.6b by Zach Glenwright")
        
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
     
        # === >> THE PREFS TAB << ===
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
        
        # === >> ADD THE TABS TO THE TAB WIDGET << ===
        self.ColorModeTabWidget.addTab(self.CCT, "CCT Mode")
        self.ColorModeTabWidget.addTab(self.HSI, "HSI Mode")
        self.ColorModeTabWidget.addTab(self.ANM, "Scene Mode")
        self.ColorModeTabWidget.addTab(self.lightPrefs, "Light Preferences")

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