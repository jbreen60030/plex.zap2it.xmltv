import sys , getopt

import os
import logging
import codecs

import time  
import datetime
import calendar
import _strptime

import urllib.request, urllib.error, urllib.parse
import gzip
import json 
import html
from html import escape
import xml.etree.ElementTree as ET
from xml.dom import minidom

from pprint import pprint
from collections import OrderedDict



def parseArgv(argv) : 
    ### get the args that may have been passed
    ### -c <config file>  --config=<configfile>
    ### -o <outfile>   --outfile=<outfile>
    ### -d <what>      --debug=<what> (debug-grid)
    argvDict = {}
    argvDict['configfile']  =   'zap2xmltv.ini'
    argvDict['tempdir']     =   'cache'
    argvDict['logfile']     =   'zap2xmltv.log'
    argvDict['outfile']     =   'xmltv.xml'
    try:
        opts, args = getopt.getopt(argv,"hd:c:o:t:l:",["config=","outfile=","debug=","tempdir=","logfile="])
    except getopt.GetoptError as e:
        print ('zap2xmltv.py -c <configfile> -o <outfile> -t <tempdir> -l <logfile>')
        print ('zap2xmltv.py --config=<configfile> --outfile=<outfile> --tempdir=<dir> --logfile=<logfile')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print ('zap2xmltv.py -c <configfile> -o <outfile> -t <tempdir> -l <logfile>')
            print ('zap2xmltv.py --config=<configfile> --outfile=<outfile> --tempdir=<dir> --logfile=<logfile')
            sys.exit()
        elif opt in ("-c", "--config"):
            argvDict['configfile'] = arg
        elif opt in ("-o", "--outfile"):
            argvDict['outfile'] = arg
        elif opt in ("-d","--debug") : 
            argvDict['debug'] = arg
        elif opt in ("-t","--tempdir") :
            argvDict['tempdir'] = arg
        elif opt in ("-l","--logfile") :
            argvDict['logfile'] = arg
    return argvDict


def parseConfig ( xConfigFile ) :
    import configparser
    xlocalConfig = {}
    xConfigSettings = {
        "zapinfo" : 
            {   "postal_code" : { "type" : "list" , "default" : "Required"} , 
                "country" :     { "type" : "string" , "default" : "USA" , 
                                 "valid" : ["USA", "CAN"]} ,
                "station_list" : { "type" : "string" , "default" : ""} , 
                "zapuser" : { "type" : "string" , "default" : "none"},
                "zappwd" : { "type" : "string" , "default" : "none"},
                "lineupcode" : { "type" : "string" , "default" : "lineupId"}, 
                "device" : { "type" : "string" , "default" : "-"}
            },
        "retrieve" : 
            {   "retrieve_days" : { "type" : "int" , "default" : "14" , "range" : ["0","14"] } ,
                "purge_days" : { "type" : "int" , "default" : "3", "range" : ["0", "14"] }
            },
        "listing" : 
            {   "language" : { "type": "string" , "default" : "en" ,
                                "valid" : ["en", "fr"] } ,
                "extended" : { "type" : "bool" , "default" : "True"},
                "icon" :     { "type": "string" , "default": "episode" , 
                               "valid" : [ "none" , "series" , "episode" ]},
                "categories" : { "type" : "string" , "default" : "original" ,
                                 "valid" : [ "none" , "original", "kodi_all" , "kodi_primary"] } ,
                "outfile" : {"type" : "string" , "default" : "xmltv.xml"}
            } ,
        "debug" : 
             {   "debug-grid" : {"type": "bool" , "default": "False"} 
             },
        "xdetails" : 
            {   "detail-parts" : { "type" : "list", "default" : "",
                            "valid" : [ "ratings","date","myear","new","live",
                                        "hd","cc","cast","season", "epis","episqts","prog","plot","descsort",
                                        "bullet", "hyphen", "newLine", "space", "colon", "vbar", "slash","comma"] }
            },
 }


    config = configparser.ConfigParser()

    config.read(xConfigFile)

    for xSection in xConfigSettings :
        xKeywords = xConfigSettings[xSection]
        for xKey in xKeywords : 
            #print (" xKey = ", xKey)
            #print (" xFallback = ", xKeywords[xKey])
            #print (" value in config")
            #pprint (xKeywords[xKey])
            xKeyList = {}
            xKeyList = (xKeywords[xKey])
            #pprint (xKeyList)
            if (xKeyList['type'] == 'bool') : 
                try:
                    xlocalConfig[xKey] = config.getboolean(xSection, xKey, fallback=xKeyList['default']) 
                except:
                    print ("exception doing a get boolean for ", xSection, "-", xKey)
                    xlocalConfig[xKey] = bool(xKeyList['default'])
            if (xKeyList['type'] == 'int') : 
                try:
                    xlocalConfig[xKey] = config.getint(xSection, xKey, fallback=xKeyList['default']) 
                    if 'range' in xKeyList : 
                        ###print ("INT range check for " , xKey , " (" , xKeyList['range'][0] , " - ", xKeyList['range'][1] , ")")
                        ###print (" INI value " , xlocalConfig[xKey] )
                        if int(xlocalConfig[xKey]) < int(xKeyList['range'][0]) or int(xlocalConfig[xKey]) > int(xKeyList['range'][1]) :
                            xlocalConfig[xKey] = xKeyList['default']  
                except BaseException as err:
                    print(f"Unexpected {err=}, {type(err)=} testing an INT for ", xSection, "-", xKey)
                    xlocalConfig[xKey] = xKeyList['default']    

            if (xKeyList['type'] == 'string') : 
                try:
                    xlocalConfig[xKey] = config.get(xSection, xKey, fallback=xKeyList['default'])
                    if 'valid' in xKeyList : 
                        if xlocalConfig[xKey] not in xKeyList['valid'] : 
                            xlocalConfig[xKey] = xKeyList['default']
                except:
                    print ("exception doing a get string for ", xSection, "-", xKey)
                    xlocalConfig[xKey] = xKeyList['default']    

            if (xKeyList['type'] == 'list') : 
###                print ("processing list")
                try:
                    configList = config.get(xSection, xKey, fallback=xKeyList['default'])
                    xlocalConfig[xKey] = []
                    localList = configList.split(',')
                    if 'valid' in xKeyList : 
###                        print ("validating list")
                        validList = xKeyList['valid']
###                        pprint (validList)

                        for thiskey in localList:
                            if thiskey in validList : 
                                xlocalConfig[xKey].append(thiskey)
                            else :  
                                xlocalConfig[xKey].append('unknown')
                    else : 
                        xlocalConfig[xKey] = localList
                except :
                    print ("exception doing a get/splitting a list for ", xSection, "-", xKey)
                    xlocalConfig[xKey] = ""   

            if (xKeyList['type'] == 'required') : 
                try:
                    xlocalConfig[xKey] = config.get(xSection, xKey, fallback=xKeyList['default']) 
                except:
                    print ("exception doing a get required for ", xSection, "-", xKey)
                    xlocalConfig[xKey] = xKeyList['default']    
            if (xKeyList['type'] == 'float') : 
                try:
                    xlocalConfig[xKey] = config.getfloat(xSection, xKey, fallback=xKeyList['default']) 
                    if 'range' in xKeyList : 
###                        print ("FLOAT range check for " , xKey , " (" , float(xKeyList['range'][0]) , " - ", float(xKeyList['range'][1]) , ")")
###                        print (" INI value " , xlocalConfig[xKey] )
                        if float(xlocalConfig[xKey]) < float(xKeyList['range'][0]) or float(xlocalConfig[xKey]) > float(xKeyList['range'][1]) :
                           xlocalConfig[xKey] = float(xKeyList['default'])  
                except BaseException as err:
                    print(f"Unexpected {err=}, {type(err)=} testing an FLOAT for ", xSection, "-", xKey)
                    xlocalConfig[xKey] = xKeyList['default']    
    return xlocalConfig


'''

###  For finding Sports and determining Teams
    xCompetitionSports=['Football' ,
                        'Baseball'  ,
                        'Hockey', 
                        'Soccer' , 
                        'Tennis' , 
                        'Volleyball', 'Footvolley',
                        'Boxing',
                        'Auto racing', 
                        'Mixed martial arts' ]

'''
def purgegrids(  cacheDir, purge_days, debug ): 

    gridtimeStart = int(time.time()) - int(time.time())%3600 
    logging.info('Checking for old cache files...')
    try:
        if os.path.exists(cacheDir):
            entries = os.listdir(cacheDir)
            for entry in entries:
                oldfile = entry.split('.')[0]
                if "-" in oldfile : 
                    oldfile = oldfile.split('-')[2]
                if oldfile.isdigit():
                    fn = os.path.join(cacheDir, entry)
                    if (int(oldfile)) < (gridtimeStart + (int(purge_days) * 86400)):
                        try:
                            os.remove(fn)
                            logging.info('Deleting old cache: %s', entry)
                        except OSError as e:
                            logging.warning('Error Deleting: %s - %s.' % (e.filename, e.strerror))
    except Exception as e:
        logging.exception('Exception: deleteOldCache - %s', e.strerror)



def retrieveallgrids ( retrieveDays , postalCodes , lineupCode, device , country , debug ) : 
   ## start at the beginning of the current hour. 
    gridHourInc = 4 
    gridtimeStart = int(time.time()) - int(time.time())%3600 

    ### Walk the current times, incrementing by "gridHourInc" number of hours, but do it so that we're 
    ### always hitting the same hours every day. This way we're not shifting by an hour or so every time this executes.
    ### That would create even more schedule files laying around in the tempdir...Presuming that this doesn't run at the same time daily.
    thisGridTime = gridtimeStart
    returnFilelist = []

    if debug : retrieveDays = 0.124
    if debug : gridHourInc = 1

    while thisGridTime <= gridtimeStart + (float(retrieveDays) * 24 * 3600) : 
        nextStart = (thisGridTime + (gridHourInc * 3600)) - ((thisGridTime + (gridHourInc * 3600))%(gridHourInc*3600))
        thisHours = int((nextStart - thisGridTime)/3600)

        for thisPostalCode in postalCodes : 
### And for each of the postal codes that were configured... Let's get a new grid file for this time slot.
### Need to identify which ones are which or the file names will collide.

            filename = thisPostalCode.strip() + '-' + lineupCode.strip() + "-" + str(thisGridTime) + '.json.gz'
            fileDir = os.path.join(cacheDir, filename)
            if not os.path.exists(fileDir):
                try:
                   retrieveSaveGrid(fileDir, thisGridTime, thisHours , thisPostalCode.strip() , lineupCode, device , country , debug)
                except OSError as e :
                    logging.warning('unable to retrive the grid when trying... error %s', e.strerror )
### Save the file name if it exists or if we just created it 
            returnFilelist.append(fileDir)
        thisGridTime = nextStart

    return returnFilelist


def retrieveSaveGrid(saveFilename, gridtime, retrieveHours, postalCode, lineupCode, device , country , debug ) :
    if not os.path.exists(saveFilename):
        try:
            logging.info('Downloading guide data for: %s  %s (%s)', postalCode, datetime.datetime.fromtimestamp(gridtime).strftime('%Y-%m-%d %H:%M:%S'), str(gridtime))
            url = 'http://tvlistings.zap2it.com/api/grid?lineupId=&timespan=' + str(retrieveHours) \
                            + '&headendId=' + lineupCode \
                            + '&country=' + country \
                            + '&device=' + device \
                            + '&postalCode=' + postalCode \
                            + '&time=' + str(gridtime) \
                            + '&pref=-&userId=-' \
                            + '&languagecode=' + xConfig['language']
            if debug : print ("URL will be ", url )
            saveContent = urllib.request.urlopen(url).read()

            try: 
                if not os.path.exists(cacheDir):
                    os.mkdir(cacheDir)
                if debug : print ("trying to save file ", saveFilename)
                with gzip.open(saveFilename,"wb+") as f:
                    f.write(saveContent)
                    f.close()
            except: 
                logging.warning('Could not save guide file for : %s', saveFilename)
        except OSError as e:
            logging.warning('Could not download guide data for: %s %s', str(gridtime), e.strerror)
            logging.warning('URL: %s', url)

def loadGrid( thisgridfile , debug ) : 

    try:
    ### Open each file with gzip since we saved it that way
        with gzip.open(thisgridfile, 'rb') as f:
            gridContent = f.read()
            f.close()
        logging.info('Parsing %s', thisgridfile)
    except OSError as e :
        logging.warning('Opening grid file : %s - %s', thisgridfile , e.strerror)
        os.remove(gridFile)

    try:     
    ### parse the json 
        jsonLoad = json.loads(gridContent)

        if debug  : print (" file " , gridFile, ' has ' , len(jsonLoad['channels']) , ' channel records  ')

    except OSError as e  : 
        logging.warning ('Exception occurred parsing JSON data in grid - %s - %s' , thisgridfile , e.strerror)
    ### and ignore this file
        jsonLoad = ""
    return jsonLoad 


def build_station_data(stationDict , OTA=True) : 

    return_dict = {}
    return_dict['listing'] = {}
    return_dict['info'] = {} 
    channelNum = stationDict['channelNo']
    callSign = stationDict['callSign']

    if (OTA) : 
        ### Sometimes the OTA channel num comes in with just the primary number and not the subchannel
        ### If that's the case, see if the subchannel is embedded in the call sign and append
        if '.' not in channelNum and callSign is not None:
            chsub = re.search('(\d+)$', callSign)
            if chsub is not None:
                channelNum =  channelNum + '.' + chsub.group(0)
            else:
                channelNum =  channelNum + '.1'
    station_key_part = str(channelNum.split('.')[0]).zfill(5)
    if '.' in channelNum : 
        station_key_part = station_key_part + \
                str(int(channelNum.split('.')[1])*10).zfill(4) 
    return_dict['info']['station_key'] = station_key_part +  "-" +  str(stationDict['channelId'])
    return_dict['info']['stationID'] = stationDict['channelId'] + '.zap2epg'
    return_dict['listing'] = []
    return_dict['listing'].append( ['display-name',  str(channelNum) + ' ' + stationDict['callSign'] ] )
    return_dict['listing'].append( ['display-name' , stationDict['callSign'] ] ) 
    return_dict['listing'].append( ['display-name' , str(channelNum) ] )
    return_dict['listing'].append( ['icon' ,  'src="http:' + stationDict['thumbnail'].split('?')[0] + '"'])          
    return return_dict

def parseEvents ( currentSchedule , newEvents, language ) :

### This is where all the heavy lifting happens. 

    adddedEvents = {}

    for event in newEvents :
    ####### get all the scheduled events for this channel
    ####### convert start time to GMT and use that as a key... only 1 event at that time per channel
        thisEvent = str(calendar.timegm(time.strptime(event.get('startTime'), '%Y-%m-%dT%H:%M:%SZ')))
#        print ("new event")
 #       pprint(event)

###        total_events+=1
        if thisEvent not in currentSchedule and \
           thisEvent not in adddedEvents :
    ####### if the event doesn't exist in the schedule (It may be because we have a 2nd postal code with same station
    ####### or more likely, it was in a previous parsed grid because it's a multi hour event that crosses grid boundaries)
    #######   add the event to the schedule

                eventProginfo = event['program'] #### get the embedded prog info
                if xConfig['extended'] : 
                    extended_details = getExtendedDetails(eventProginfo.get('seriesId') , eventProginfo.get('tmsId') )
                adddedEvents[thisEvent] = {}
                adddedEvents[thisEvent]['startTime'] = str(calendar.timegm(time.strptime(event.get('startTime'), '%Y-%m-%dT%H:%M:%SZ')))
                adddedEvents[thisEvent]['endTime'] = str(calendar.timegm(time.strptime(event.get('endTime'), '%Y-%m-%dT%H:%M:%SZ')))

                adddedEvents[thisEvent]['4elements'] = []
                adddedEvents[thisEvent]['4elements'].append( ["episode-num" , "system" , "dd_progid", \
                                                str(eventProginfo.get('tmsId')[:-4] + "." + eventProginfo.get('tmsId')[-4:]) ] )
                adddedEvents[thisEvent]['4elements'].append( ["title" , "lang" , language , eventProginfo.get('title') ] )
                adddedEvents[thisEvent]['4elements'].append( ["sub-title", "lang" , language , eventProginfo.get('episodeTitle') ] )
                if xConfig['extended'] == False : 
                    adddedEvents[thisEvent]['4elements'].append ([ 'desc', "lang" , language , eventProginfo.get('shortDesc') ] )
                adddedEvents[thisEvent]['4elements'].append( ["length", "units", "minutes", event.get('duration')])
                if eventProginfo.get('season') is not None and eventProginfo.get('episode') is not None :

                    adddedEvents[thisEvent]['4elements'].append( ["episode-num", "system", "onscreen" , \
                                        str("S" + eventProginfo.get('season').zfill(2) + "E" + eventProginfo.get('episode').zfill(2) ) ] )
                    adddedEvents[thisEvent]['4elements'].append( ["episode-num", "system", "xmltv_ns" , \
                                        str(int(eventProginfo.get('season'))-1) + "." + str(int(eventProginfo.get('episode'))-1) + "."] )
### Still need categories, description (with/without extended details) in this 4elements listing
###                adddedEvents[thisEvent]['4elements'].append()
 ########################                              
                if xConfig['icon'] == 'episode' : 
                    adddedEvents[thisEvent]['icon'] = "https://zap2it.tmsimg.com/assets/" + event.get('thumbnail') + ".jpg"
                if xConfig['icon'] == 'series' :     
                    ### Comes from the SERIES file 
                    adddedEvents[thisEvent]['icon'] = "series icon here"

    return adddedEvents

def getExtendedDetails ( episodeId, showID) :
    xDetails = {}
### This is where we go and get Series/Movie info and pull some of that in , like episode icon, play with the categories, etc. 

    print (" in extended defails for episode ", episodeId , " for the show ", showID)
    return xDetails


def massageGenres (EPfilter , EPgenre , EPlang, EPmatchLevel ) : 

    xLangGenres = { 
        "Lang_en" :  
                { "Level_kodi_all" :
                    {  "Movies" : "Movie / Drama",
                        "movie" : "Movie / Drama",
                        "Movie" : "Movie / Drama",
                        'News' : "News / Current affairs" ,
                        'Game show' : "Game show / Quiz / Contest",
                        'Law' : "Show / Game show",
                        'Culture' : "Arts / Culture (without music)",
                        'Art' :  "Arts / Culture (without music)",
                        'Entertainment' : "Popular culture / Traditional Arts",
                        'Politics'  :  "Social / Political issues / Economics",
                        'Social'  :  "Social / Political issues / Economics",
                        'Public affairs' :  "Social / Political issues / Economics",
                        'Education' : "Education / Science / Factual topics",
                        'How-to' : "Leisure hobbies",
                        'Travel' : "Tourism / Travel",
                        'Sitcom' : "Variety show",
                        'Talk' : "Talk show",
                        'Children' : "Children's / Youth programs",
                        'Animated' :  "Cartoons / Puppets",
                        'Music' : "Music / Ballet / Dance"
                   }  
                        ,
                "Level_kodi_primary" :  
                    {  "Movies" : "Movie / Drama",
                        "movie" : "Movie / Drama",
                        "Movie" : "Movie / Drama",
                        'News' : "News / Current affairs",
                        'News magazine' : "News magazine",
                        'Public affairs' : "News / Current affairs",
                        'Interview' : "Discussion / Interview / Debate",
                        'Game show' : "Game show / Quiz / Contest",
                        'Talk' : "Talk show",
                        'Sports' : "Sports",
                        'sports' : "Sports",
                        'Sitcom' : "Variety show",
                        'Children' : "Children's / Youth programs"
                    },
                "Level_original" : 
                    {   "None" : "None"
                    } ,
                "Level_none" : 
                    {   "None" : "None"
                    }

                } ,
        "Lang_fr" :  
                {"Level_kodi_primary" : 
                    {  "Movies" : "fr_1_Movies",
                        "movie" : "fr_1_movie",
                        "Movie" : "fr_1_Movie"
                    }  ,
                "Level_kodi_all" : 
                    {  "Movies"  : "fr_2_Movies",
                        "movie" : "fr_2_movie",
                        "Movie" : "fr_2_Movie"
                    },
                "Level_original" :
                    {   "None" : "None"
                    },
                "Level_none" : 
                    {   "None" : "None"
                    }
               }
       }

    genreList = []
    xEpgenre1_found = 0

    for g in EPgenre:
        if (g == 'Comedy') and (EPmatchLevel == 'kodi_all'):
                pass
        else :
            genreList.append(g)
    myLang = 'Lang_' + EPlang
    myLevel = "Level_" + str(EPmatchLevel)
    myGenDict = xLangGenres[myLang][myLevel]
    for g in myGenDict:
        if g in genreList :
            if EPmatchLevel == 'kodi_primary' : 
                genreList.clear()
                genreList.append (myGenDict[g])
                xEpgenre1_found = 1 
            elif EPmatchLevel == 'kodi_all' : 
                genreList.insert(0,myGenDict[g])
            else:
                pass
### And if it isn't one of the Level1 categories, then make it a default.
    if EPmatchLevel== 'kodi_primary' and xEpgenre1_found == 0 : 
        genreList = ["Variety show"]

    if 'Movie' in genreList:
        genreList.remove('Movie')
        genreList.insert(0, 'Movie')
    return genreList

def printXMLHeader ( ) : 
    rootattr = { "source-info-url" :  "http://tvschedule.zap2it.com" , 
                "source-info-name" : "zap2it.com" } 

    root = ET.Element("tv" , rootattr)
    
    return root

def printXMLStations (root, schedule) : 

    for thischannel in schedule  : 
    # Add sub element.
        xchannelattr = { "id" : schedule[thischannel]['info']['stationID'] }
        xchannel = ET.SubElement(root, "channel", xchannelattr)
 #       listings = []
        listings = schedule[thischannel]['station_listing']
        for thislistline in listings :
            channattr = ET.SubElement(xchannel , thislistline[0])
            channattr.text =   thislistline[1]

    return root

def printXMLEvents(root , schedule ) : 

    for thischannel in schedule  : 
        theseEvents = schedule[thischannel]['events']
        for thisEvent in theseEvents : 
  # <programme start="20211108160000 -0600" stop="20211108163000 -0600" channel="20454.zap2epg">
            eventattr = { "start" : theseEvents[thisEvent]['startTime'],
                        "stop": theseEvents[thisEvent]['endTime'],
                        "channel"  : schedule[thischannel]['info']['stationID'] }
            xevent = ET.SubElement(root, "programme" , eventattr)
            itemslist = theseEvents[thisEvent]['4elements']
            for thisitem in itemslist :
#                print ("next item to print") 
#                pprint(thisitem)
                itemattr = {}
                itemattr[thisitem[1]] = thisitem[2]
 #               print("Item attributes")
  #              pprint (itemattr)
   #             print (type(itemattr))
                xitem = ET.SubElement(xevent , thisitem[0], itemattr)
                xitem.text = thisitem[3]

            if "icon" in theseEvents[thisEvent] : 
                itemattr = {"src" : theseEvents[thisEvent].get('icon')}
                xitem = ET.SubElement(xevent , 'icon', itemattr)
    return root 


def printXMLFooter (root, xmloutfile , xmlencoding  ) : 
    xmlstr = minidom.parseString(ET.tostring(root , encoding=xmlencoding, method='xml' )).\
                        toprettyxml(indent = "\t", encoding=xmlencoding)
    with open(xmloutfile, "wb") as f:
       f.write(xmlstr)


def somethingelse() : 
    mygenres = { "Talk", "Culture", "Movie"}

    newgenres = massageGenres('', mygenres, xConfig['language'], xConfig['categories'])

    pprint (newgenres)


  
#########################
#########################

if __name__ == '__main__':

    arglineDict = parseArgv(sys.argv[1:])
    userdata = os.getcwd()
    try:
        log = os.path.join(userdata, arglineDict['logfile'])
        logging.basicConfig(filename=log, filemode='w', format='%(asctime)s %(message)s', datefmt='%Y/%m/%d %H:%M:%S', level=logging.DEBUG)

        logging.info ('Starting zap2xmltv ')
    except OSError as e :
        print ("Error initializing logging - %s" , e.strerror)
        sys.exit(2)        

    try:
        cacheDir = os.path.join(userdata, arglineDict['tempdir'])
        if not os.path.exists(cacheDir):
            os.mkdir(cacheDir)
    except OSError as e : 
        logging.exception("Unable to create tempdir directory %s - %s", cacheDir, e.strerror)
        print ("Error creating cache directory - %s" , e.strerror)
        sys.exit(2)        

    xConfig = {} 
    xConfig = parseConfig ( arglineDict['configfile'] )

    logging.info ("Configuration loaded. ")
##    pprint (xConfig)
 

    ##### Validate that all of the required parameters have a value.. 
    ##### As of now, defaults exist for everything except the postal_code
    if xConfig['postal_code'][0] == 'Required' : ### which is the "default" 
        logging.error ("Postal Code is a REQUIRED parameter in the configuration")
        print ("Postal Code is a REQUIRED parameter in the configuration")
        sys.exit(2)

    ### Purge out the old grid files from previous runs along with the next purge_days number of days 
    ### this is to get the most recent version of the grid for the time slots required. They do change, sometimes daily

    purgegrids (cacheDir,  xConfig['purge_days'], xConfig['debug-grid'])

#    postalCodeList = xConfig['postal_code'].split( ",")

    retrievedFilenamesList = []
    retrievedFilenamesList = retrieveallgrids( xConfig['retrieve_days']  , \
                                                xConfig['postal_code'] , \
                                                xConfig['lineupcode'], \
                                                xConfig['device'], \
                                                xConfig['country'], \
                                                xConfig['debug-grid'])

    if xConfig['lineupcode'] == 'lineupId' : 
        usingOTA = True 
    else :
        usingOTA = False

    scheduleDict ={} 
    total_events = 0 
    logged_events = 0
    stationList = []
    try: 
        stationList = xConfig['station_list'].split(',')
    except BaseException as e: 
        logging.warning("Error splitting the list of stations ... Setting to all channels - %s ", e.msg )
        print ("Error splitting up the list of stations - %s ", e.msg)
        stationList = [] ### Make a null list


    for gridFile in retrievedFilenamesList : 
        if os.path.exists(gridFile):
            gridJSON = loadGrid(gridFile , xConfig['debug-grid'])

            for station in gridJSON['channels'] :
#### if the channelID is in stationlist, or there is no station list (default is all stations represented by "" )
                if station['channelId'] in stationList or stationList is None :   
                    if xConfig['debug-grid'] : 
                        print ("next Station ID is " , station['channelId'] , " and call sign is ", station['callSign'] , " and channel num ", station['channelNo'])
                    station_data = build_station_data(station, usingOTA) 
#                    print (station_data)
                    station_key=station_data['info']['station_key']
####### IF  channel doesn't exist in the current schedule
#######      add the channel info
                    if station_key not in scheduleDict:
                        scheduleDict[station_key] = {}
                        scheduleDict[station_key]['info']=station_data['info']
                        scheduleDict[station_key]['station_listing'] = station_data['listing']
                        scheduleDict[station_key]['events'] = {}
###                    additionalEvents = {}
                    additionalEvents = parseEvents( scheduleDict[station_key] , \
                                                    station['events'],
                                                    xConfig['language'])
#                    print (" events that came back from parsing")
#                    pprint (additionalEvents)

                    for newEvent in additionalEvents : 
                        scheduleDict[station_key]['events'][newEvent] = additionalEvents[newEvent]

    print ("There are a total of ", len(scheduleDict), " stations when all folded together")
#    print ("There were ", total_events, " total events in the grids of which ", logged_events, " were logged")

 #   pprint (scheduleDict)

    xmlroot = printXMLHeader ( )  
    xmlroot = printXMLStations ( xmlroot, scheduleDict)
    xmlroot =  printXMLEvents(xmlroot , scheduleDict)

    if 'outfile' not in arglineDict : 
        xmlfile = os.path.join(userdata, xConfig['outfile'])
    else :    
        xmlfile = os.path.join(userdata, arglineDict['outfile'])
    xmlencoding = 'utf-8'
    printXMLFooter(xmlroot,  xmlfile, xmlencoding)

    sys.exit(0)

    '''
gridHourInc = 4  ## the number of hours to pull from Zap2it with each request. 


#pprint (scheduleDict)

'''
'''


progtime = "2021-10-31T23:00:00Z"

that_start = str(calendar.timegm(time.strptime(progtime, '%Y-%m-%dT%H:%M:%SZ')))
print ("progtime" , that_start)

prog_dst = time.localtime(that_start).tm_isdst
print ()

'''
