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
####import xml.etree.ElementTree as ET

from pprint import pprint
from collections import OrderedDict

###print (type(config))
###pprint(config.sections())
'''
for a in config.sections() : 
    b = config[a]

    for key in b : 
        print ("section ", b, "  keyword " , key, " and value of ", b[key] )
'''

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
                print ("processing list")
                try:
                    configList = config.get(xSection, xKey, fallback=xKeyList['default'])
                    xlocalConfig[xKey] = []
                    localList = configList.split(',')
                    if 'valid' in xKeyList : 
                        print ("validating list")
                        validList = xKeyList['valid']
                        pprint (validList)

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
                        print ("FLOAT range check for " , xKey , " (" , float(xKeyList['range'][0]) , " - ", float(xKeyList['range'][1]) , ")")
                        print (" INI value " , xlocalConfig[xKey] )
                        if float(xlocalConfig[xKey]) < float(xKeyList['range'][0]) or float(xlocalConfig[xKey]) > float(xKeyList['range'][1]) :
                           xlocalConfig[xKey] = float(xKeyList['default'])  
                except BaseException as err:
                    print(f"Unexpected {err=}, {type(err)=} testing an FLOAT for ", xSection, "-", xKey)
                    xlocalConfig[xKey] = xKeyList['default']    
    return xlocalConfig

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

def retrieveSaveGrid(saveFilename, gridtime, retrieveHours, postalCode, lineupCode, device , country ) :
    if not os.path.exists(saveFilename):
        try:
            logging.info('Downloading guide data for: %s (%s)', str(gridtime),datetime.datetime.fromtimestamp(gridtime).strftime('%Y-%m-%d %H:%M:%S'))
            url = 'http://tvlistings.zap2it.com/api/grid?lineupId=&timespan=' + str(retrieveHours) \
                            + '&headendId=' + lineupCode \
                            + '&country=' + country \
                            + '&device=' + device \
                            + '&postalCode=' + postalCode \
                            + '&time=' + str(gridtime) \
                            + '&pref=-&userId=-' \
                            + '&languagecode=' + xConfig['language']
            print ("URL will be ", url )
            saveContent = urllib.request.urlopen(url).read()

            try: 
                if not os.path.exists(cacheDir):
                    os.mkdir(cacheDir)
                print ("trying to save file ", saveFilename)
                with gzip.open(saveFilename,"wb+") as f:
                    f.write(saveContent)
                    f.close()
            except: 
                logging.warning('Could not save guide file for : %s', saveFilename)
        except OSError as e:
            logging.warning('Could not download guide data for: %s %s', str(gridtime), e.strerror)
            logging.warning('URL: %s', url)


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
    return_dict['info']['stationID'] = '\t<channel id=\"' + stationDict['channelId'] + '.zap2epg\">'
    return_dict['listing']['channelNumSign'] = '\t\t<display-name>' + channelNum + ' ' \
                        + html.escape(stationDict['callSign'], quote=True) + '</display-name>'
    return_dict['listing']['callSign']= '\t\t<display-name>' +  html.escape(stationDict['callSign'], quote=True)  + '</display-name>'
    return_dict['listing']['channelNo'] = '\t\t<display-name>' + channelNum + '</display-name>'
    return_dict['listing']['icon'] = '\t\t<icon src="http:' + stationDict['thumbnail'].split('?')[0] + '" />'         
    return return_dict


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
    pprint (xConfig)
    try:
### command line parameter should overrid the config file
        if 'outfile' not in arglineDict : 
            xmlfile = os.path.join(userdata, xConfig['outfile'])
        else :    
            xmlfile = os.path.join(userdata, arglineDict['outfile'])

        xmlencoding = 'utf-8'
        xmlfh = codecs.open(xmlfile, 'w+b', encoding=xmlencoding)
 
    except OSError as e : 
        logging.error("Unable to create output file %s - %s", xmlfile, e.strerror)
        print ("Error creating output file " , xmlfile , e.strerror)
        sys.exit(2)        


    ##### Validate that all of the required parameters have a value.. 
    ##### As of now, defaults exist for everything except the postal_code
    if xConfig['postal_code'][0] == 'Required' : ### which is the "default" 
        logging.error ("Postal Code is a REQUIRED parameter in the configuration")
        print ("Postal Code is a REQUIRED parameter in the configuration")
        sys.exit(2)

#    postalCodeList = xConfig['postal_code'].split( ",")

    ## start at the beginning of the current hour. 
    gridtimeStart = int(time.time()) - int(time.time())%3600 

    ### Walk the current times, incrementing by "gridHourInc" number of hours, but do it so that we're 
    ### always hitting the same hours every day. This way we're not shifting by an hour or so every time this executes.
    ### That would create even more schedule files laying around in the tempdir...Presuming that this doesn't run at the same time daily.
    thisGridTime = gridtimeStart
    retrievedFilenamesList = []

    if xConfig['debug-grid'] : xConfig['retrieve_days'] = 0.124
    if xConfig['debug-grid'] : gridHourInc = 1

    while thisGridTime <= gridtimeStart + (float(xConfig['retrieve_days']) * 24 * 3600) : 
        nextStart = (thisGridTime + (gridHourInc * 3600)) - ((thisGridTime + (gridHourInc * 3600))%(gridHourInc*3600))
        thisHours = int((nextStart - thisGridTime)/3600)

        for thisPostalCode in xConfig['postal_code'] : 
### And for each of the postal codes that were configured... Let's get a new grid file for this time slot.
### Need to identify which ones are which or the file names will collide.

            filename = thisPostalCode.strip() + '-' + xConfig['lineupcode'].strip() + "-" + str(thisGridTime) + '.json.gz'
            fileDir = os.path.join(cacheDir, filename)
            if not os.path.exists(fileDir):
                try:
                   retrieveSaveGrid(fileDir, thisGridTime, thisHours , thisPostalCode.strip() , xConfig['lineupcode'], xConfig['device'] , xConfig['country'])
                except OSError as e :
                    logging.warning('unable to retrive the grid when trying... error %s', e.strerror )
### Save the file name if it exists or if we just created it 
            retrievedFilenamesList.append(fileDir)

        thisGridTime = nextStart


    overallDict ={} 
    total_events = 0 
    logged_events = 0

    if xConfig['lineupcode'] == 'lineupId' : 
        usingOTA = True 
    else :
        usingOTA = False

    stationList = []
    try: 
        stationList = xConfig['station_list'].split(',')
    except BaseException as e: 
        print ("Error splitting up the list of stations - %s ", e.msg)
        stationList = [] ### Make a null list

    pprint (stationList)
    pprint (retrievedFilenamesList)

    for gridFile in retrievedFilenamesList : 
        if os.path.exists(fileDir):
            try:
        ### Open each file with gzip since we saved it that way
                with gzip.open(gridFile, 'rb') as f:
                    gridContent = f.read()
                    f.close()
                logging.info('Parsing %s', gridFile)
            except OSError as e :
                logging.warning('Opening grid file : %s - %s', gridFile , e.strerror)
                os.remove(gridFile)

            try:     
    ### parse the json 
                gridJSON = json.loads(gridContent)
                pprint (xConfig['debug-grid'])

                if xConfig['debug-grid'] : 
                    print (" file " , gridFile, ' has ' , len(gridJSON['channels']) , ' channel records  ')

            except OSError as e  : 
                logging.warning ('Exception occurred parsing JSON data in grid - %s - %s' , gridFile , e.strerror)
### and ignore this file
                pass 

            for station in gridJSON['channels'] :
#### if the channelID is in stationlist, or there is no station list (default is all stations represented by "" )
                if station['channelId'] in stationList or stationList is None :   
                    if xConfig['debug-grid'] : 
                        print ("next Station ID is " , station['channelId'] , " and call sign is ", station['callSign'] , " and channel num ", station['channelNo'])
                    station_data = build_station_data(station, usingOTA) 
                    station_key=station_data['info']['station_key']
####### IF  channel doesn't exist in the current schedule
#######      add the channel info
                    if station_key not in overallDict:
                        overallDict[station_key] = {}
                        overallDict[station_key]['info']=station_data['info']
                        overallDict[station_key]['station_listing'] = station_data['listing']

                    for event in station['events']:
####### get all the scheduled events for this channel
####### convert start time to GMT and use that as a key... only 1 event at that time per channel
                        thisEvent = str(calendar.timegm(time.strptime(event.get('startTime'), '%Y-%m-%dT%H:%M:%SZ')))
                        total_events+=1
                        if thisEvent not in  overallDict[station_key] :
####### if the event doesn't exist in the schedule (It may be because we have a 2nd postal code with same station)
#######   add the event to the schedule
                            overallDict[station_key][thisEvent] = {}
                            logged_events+=1
                        else : 
                            logging.info('not logging event %s-%s with station key of %s', str(thisEvent),event['seriesId'], station_key)


    print ("There are a total of ", len(overallDict), " stations when all folded together")
    print ("There were ", total_events, " total events in the grids of which ", logged_events, " were logged")

    for station in overallDict : 

        print (overallDict[station]['info']['stationID'])
        for y in overallDict[station]['station_listing'] : 
            print (overallDict[station]['station_listing'][y])
        print ("\t</channel>")

    sys.exit(0)

    '''
gridHourInc = 4  ## the number of hours to pull from Zap2it with each request. 


#pprint (overallDict)

'''
'''


progtime = "2021-10-31T23:00:00Z"

that_start = str(calendar.timegm(time.strptime(progtime, '%Y-%m-%dT%H:%M:%SZ')))
print ("progtime" , that_start)

prog_dst = time.localtime(that_start).tm_isdst
print ()

'''
