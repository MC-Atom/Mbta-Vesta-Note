import requests
import datetime
from time import sleep
import keyboard
from dateutil import parser
from zoneinfo import ZoneInfo

BOARD_TITLE: str = 'Davis'
STOP: str = 'place-davis'
ROUTE: str = 'Red'
UPDATE_DELAY: int = 60

MBTA_API_LINK: str = "https://api-v3.mbta.com/"
VESTA_API_LINK: str = "https://cloud.vestaboard.com/"

def getMbtaHeader() -> dict:
    header = {}

    with open("./mbtaKey.txt", "r") as f:
        apiKey = f.read()
        header["X-API-Key"] = apiKey

    return header

def getVestboardHeader() -> dict:
    header = {}

    with open("./vestaboardKey.txt", "r") as f:
        apiKey = f.read()
        header = {"X-Vestaboard-Token":apiKey, "Content-Type":"application/json"}

    return header

def parseTrain(train: dict, header: dict[str, str], childStops: list[str] | None = None) -> dict:
    '''
    Coded to the guidelines provided to me by the MBTA at https://www.mbta.com/developers/real-time-display-guidelines

    '''
    outputDict = {}
    skipStopCheck = childStops == None

    if train["attributes"]["status"] != None:
        status = train["attributes"]["status"]
        outputDict["prediction"] = "Stopped"
    else:
        if train["attributes"]["arrival_time"] == None:
            return {}

        arrivalTime: datetime.datetime = parser.parse(train["attributes"]["arrival_time"])
        now: datetime.datetime = datetime.datetime.now(ZoneInfo("America/New_York"))
        
        timeTillArrival: datetime.timedelta = arrivalTime - now
        if timeTillArrival.total_seconds() < 0 and \
            (parser.parse(train["attributes"]["departure_time"]) - datetime.datetime.now(ZoneInfo("America/New_York"))).total_seconds() < 0:

            return {} # The train has left the station and ur not on it noob

        elif timeTillArrival.total_seconds() < 90:
            response = requests.get(MBTA_API_LINK + "vehicles/" + train["relationships"]["vehicle"]["data"]["id"], headers=header)
            vehicle: dict = response.json()["data"]
            if vehicle["attributes"]["current_status"] == "STOPPED_AT" and (vehicle["relationships"]["stop"]["data"]["id"] in childStops or skipStopCheck):
                outputDict["prediction"] = "BRD"
            else:
                if timeTillArrival.total_seconds() <= 30:
                    outputDict["prediction"] = "ARR"
                else:
                    outputDict["prediction"] = str(round(timeTillArrival.total_seconds() / 60)) + "Min"
        else:
            outputDict["prediction"] = str(round(timeTillArrival.total_seconds() / 60)) + "Min"
    
    response = requests.get(MBTA_API_LINK + "trips/" + train["relationships"]["trip"]["data"]["id"], headers=header)
    trip: dict = response.json()["data"]
    outputDict["headsign"] = trip["attributes"]["headsign"]

    return outputDict

def formatVestaOutput(mbtaInfo: dict[str,dict]) -> str:

    match mbtaInfo["color"]:
        case "DA291C": # Red
            color = "🟥"
        case "ED8B00": # Orange
            color = "🟧"
        case "FFC72C": # Yellow
            color = "🟨"
        case "00843D": # Green
            color = "🟩"
        case "003DA5": # Blue
            color = "🟦"
        case "80276C": # Purple
            color = "🟪"
        case _: # Blank
            color = " "

    line1 = BOARD_TITLE
    while len(line1) < 15:
        line1 = color + line1 + color
    line1 = line1[0:15]

    line2 = mbtaInfo["reverse"]["headsign"]
    line2 = line2[0:10] if len(line2) > 10 else line2
    spaceBetween = 15 - (len(line2) + len(mbtaInfo["reverse"]["prediction"]))
    for i in range(spaceBetween):
        line2 += " "
    line2 += mbtaInfo["reverse"]["prediction"]


    line3 = mbtaInfo["forward"]["headsign"]
    line3 = line3[0:10] if len(line3) > 10 else line3
    spaceBetween = 15 - (len(line3) + len(mbtaInfo["forward"]["prediction"]))
    for i in range(spaceBetween):
        line3 += " "
    line3 += mbtaInfo["forward"]["prediction"]

    return line1 + "\n" + line2 + "\n" + line3


''' ------ Begin Main Code ------ '''


mbtaHeader = getMbtaHeader()
response = requests.get(MBTA_API_LINK + "stops/" + STOP + "?include=child_stops", headers=mbtaHeader)
stop: dict = response.json()
childStopsData : list[dict] = stop["data"]["relationships"]["child_stops"]["data"]
childStops: list[str] = []

for stop in childStopsData:
    childStops.append(stop["id"])

response = requests.get(MBTA_API_LINK + "routes/" + ROUTE)
route: dict = response.json()
color = route["data"]["attributes"]["color"]


while True: # not keyboard.is_pressed('esc'):
    response = requests.get(MBTA_API_LINK + "predictions?filter[route]=" + ROUTE + "&filter[stop]=" + STOP, headers=mbtaHeader)

    if response.status_code == 200:
        responseJson: dict = response.json()["data"]

        forward: dict = {}
        reverse: dict = {}

        i: int = 0
        while i < len(responseJson) and (forward == {} or reverse == {}):
            train = responseJson[i]
            if train["attributes"]["direction_id"] == 0 and forward == {}:
                forward = parseTrain(train, mbtaHeader, childStops)

            elif train["attributes"]["direction_id"] == 1 and reverse == {}:
                reverse = parseTrain(train, mbtaHeader, childStops)

            i += 1

        if forward == {}:
            forward = {"prediction":"None","headsign":"N/A"}
        if reverse == {}:
            reverse = {"prediction":"None","headsign":"N/A"}

        vestaOutput = formatVestaOutput({"color":color,"forward":forward,"reverse":reverse})

        vestaHeader = getVestboardHeader()
        
        sendResponse = requests.post(VESTA_API_LINK,headers=vestaHeader, json={"text":vestaOutput})
        print(reverse, forward, sendResponse)
        
    else:
        print(response.status_code)

    sleep(UPDATE_DELAY)