#############################################################
## Neweer-PyLite
## by Zach Glenwright
#############################################################
## Based on the NeweerLight project by @keefo (Xu Lian)
##   > https://github.com/keefo/NeewerLite <
#############################################################
## Animation parameters:
#############################################################
## 1 - Emergency Mode A (Police Sirens)
## 2 - Emergency Mode B (One color?)
## 3 - Emergency Mode C (Ambulance)
## 4 - Party Mode A (Alternating colors)
## 5 - Party Mode B (Same as above, but faster)
## 6 - Party Mode C (Candle-light)
## 7 - Lightning Mode A
## 8 - Lightning Mode B
## 9 - Lightning Mode C
#############################################################

def calculateByteString(**modeArgs):
    if modeArgs["colorMode"] == "CCT":
        # We're in CCT (color balance) mode
        # TODO: check to see if we can set higher color temp for lights that support it -
        # the SL-80 seems to be able to go as high as 8000K for color temp
        
        #          pfx   mode # of bytes
        #          ----  ---  -
        lightCmd = [120, 135, 2, 0, 0, 0]

        lightCmd[3] = int(modeArgs["temp"]) # the color temp value, ranging from 32(00K) to 56(00)K
        lightCmd[4] = int(modeArgs["brightness"]) # the brightness value
        lightCmd[5] = calculateChecksum(lightCmd) # compute the checksum
    elif modeArgs["colorMode"] == "HSV":
        # We're in HSV (any color of the spectrum) mode
        
        #          pfx   mode # of bytes
        #          ----  ---  -
        lightCmd = [120, 134, 4, 0, 0, 0, 0, 0]

        lightCmd[3] = int(modeArgs["HSV_H"]) & 255 # hue value, up to 255
        lightCmd[4] = (int(modeArgs["HSV_H"]) & 65280) >> 8 # offset value, computed from above value
        lightCmd[5] = int(modeArgs["HSV_S"]) # saturation value
        lightCmd[6] = int(modeArgs["HSV_L"]) # brightness value
        lightCmd[7] = calculateChecksum(lightCmd) # compute the checksum
    elif modeArgs["colorMode"] == "ANM":
        # We're in ANM (animation) mode
        
        #          pfx   mode # of bytes
        #          ----  ---  -
        lightCmd = [120, 136, 2, 0, 0, 0]

        lightCmd[3] = int(modeArgs["brightness"]) # brightness value
        lightCmd[4] = int(modeArgs["animation"]) # the number of animation you're going to run (check comments above)
        lightCmd[5] = calculateChecksum(lightCmd) # compute the checksum


    print("You're currently in " + modeArgs["colorMode"] + " mode - ")
    
    for a in range(0, len(lightCmd)):
        print(str(lightCmd[a]) + " / Hex: " + str(hex(lightCmd[a])))

def calculateChecksum(lightCmd):
    checkSum = 0

    for a in range(0, len(lightCmd) - 1):
        if lightCmd[a] < 0:
            checkSum = checkSum + int(lightCmd[a] + 256)
        else:
            checkSum = checkSum + int(lightCmd[a])

    checkSum = checkSum & 255
    return checkSum

# TESTING VALUES!
#calculateByteString(colorMode="HSV", HSV_H="230", HSV_S="85", HSV_L="100")
#calculateByteString(colorMode="HSV", HSV_H="154", HSV_S="89", HSV_L="25")
calculateByteString(colorMode="HSV", HSV_H="300", HSV_S="89", HSV_L="25")
calculateByteString(colorMode="CCT", temp="32", brightness="100")
calculateByteString(colorMode="ANM", brightness="100", animation="2")
