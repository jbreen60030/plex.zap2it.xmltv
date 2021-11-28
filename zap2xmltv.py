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
    ### set defaults for the command line values so we don't have to test later.
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
                "station_list" : { "type" : "string" , "default" : "None"} , 
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
    return_dict['info']['callSign'] = stationDict['callSign']
    return_dict['info']['channelNum'] = channelNum
    return_dict['listing'] = []
    return_dict['listing'].append( ['display-name',  str(channelNum) + ' ' + stationDict['callSign'] ] )
    return_dict['listing'].append( ['display-name' , stationDict['callSign'] ] ) 
    return_dict['listing'].append( ['display-name' , str(channelNum) ] )
    return_dict['listing'].append( ['display-name' , str(stationDict['affiliateName'])])
    return_dict['listing'].append( ['icon' ,  'src="http:' + stationDict['thumbnail'].split('?')[0] + '"'])          
    return return_dict

def parseEvents ( currentSchedule , newEvents, language , cacheLocation) :

### This is where all the heavy lifting happens. 
#    print ("the current schedule as it's coming in")
#    pprint (currentSchedule)

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
    ####### if the event doesn't exist in the schedule (It might existbecause we have a 2nd postal code with same station
    ####### or more likely, it was in a previous parsed grid because it's a multi hour event that crosses grid boundaries)
    #######   add the event to the schedule

            eventProginfo = event['program'] #### get the embedded prog info
            extended_details = {}
            extended_details['status'] = 'unknown'
            if xConfig['extended'] : 
                extended_details = getExtendedDetails(eventProginfo.get('seriesId') , eventProginfo.get('tmsId'), cacheLocation )
                if extended_details['status']=='Retry' : 
                    extended_details = getExtendedDetails(eventProginfo.get('seriesId') , eventProginfo.get('tmsId'), cacheLocation )
                if extended_details['status'] != "OK" : extended_details['status']='FAIL'

            adddedEvents[thisEvent] = {}
            ### Figure out the local time including DST for the time of the event. Some systems can't take Zulu time
            ### And need to figure that out for both the start and end times... Wonder if there are any 1/2 hour events
            ### that start right at Standard time (non-summer) change.
            xStarttime = calendar.timegm(time.strptime(event.get('startTime'), '%Y-%m-%dT%H:%M:%SZ'))
            xis_dst = time.localtime(xStarttime).tm_isdst
            xtzoffset = " %.2d%.2d" %(- (time.altzone if xis_dst else time.timezone)/3600, 0)
            adddedEvents[thisEvent]['startTime'] = str( time.strftime("%Y%m%d%H%M%S", time.localtime(xStarttime))) + xtzoffset

            xendtime = calendar.timegm(time.strptime(event.get('endTime'), '%Y-%m-%dT%H:%M:%SZ'))
            xis_dst = time.localtime(xendtime).tm_isdst
            xtzoffset = " %.2d%.2d" %(- (time.altzone if xis_dst else time.timezone)/3600, 0)
            adddedEvents[thisEvent]['endTime'] = str( time.strftime("%Y%m%d%H%M%S", time.localtime(xendtime))) + xtzoffset

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

            if extended_details['status'] == 'OK':
#                print ("Adding the parsed extended details info")
#                pprint(extended_details)
                if "originalAirDate" in extended_details : 
#                    print (" there is an original air date ")
#                    print (extended_details['originalAirDate'])
                    adddedEvents[thisEvent]['4elements'].append( ["previously-shown" , "start" , extended_details['originalAirDate'], " " ] )

    ### Still need categories, description (with/without extended details) in this 4elements listing
    ###                adddedEvents[thisEvent]['4elements'].append()
    ########################                              
            if xConfig['icon'] == 'episode' : 
                adddedEvents[thisEvent]['icon'] = "https://zap2it.tmsimg.com/assets/" + event.get('thumbnail') + ".jpg"
            if xConfig['icon'] == 'series' :     
                ### Comes from the SERIES file 
                adddedEvents[thisEvent]['icon'] = "series icon here"
 #           print ("list of added events on the way back  ")
 #           pprint (adddedEvents)
    return adddedEvents

def getExtendedDetails ( showID, episodeId,  cacheLocation) :
    episodeId = episodeId.lower()

    xDetails = {}
    xDetails['status']='OK'

    if showID not in showCache: 
        logging.info('Adding series %s to showCache', showID)
        filename = showID + '.json'
        fileDir = os.path.join(cacheDir, filename)
        showCache[showID] = {}
        showCache[showID]['filename']= filename 
        showCache[showID]['epcredits']= None
        try:
            if not os.path.exists(fileDir) and showID not in failList:
                retry = 3
                while retry > 0:
                    logging.info('Downloading details data for: %s', showID)
                    url = 'https://tvlistings.zap2it.com/api/program/overviewDetails'
                    data = 'programSeriesID=' + showID
                    data_encode = data.encode('utf-8')
                    try:
                        logging.info('downloading file %s', url )
                        URLcontent = urllib.request.Request(url, data=data_encode)
                        JSONcontent = urllib.request.urlopen(URLcontent).read()
                        if JSONcontent:
                            with open(fileDir,"wb+") as f:
                                f.write(JSONcontent)
                                f.close()
                            retry = 0
                        else:
                            time.sleep(1)
                            retry -= 1
                            logging.warning('Retry downloading missing details data for: %s', showID)
                    except urllib.error.URLError as e:
                        time.sleep(1)
                        retry -= 1
                        logging.warning('Retry downloading details data for: %s  -  %s', showID, e)
            if os.path.exists(fileDir):
                try: 
                    fileSize = os.path.getsize(fileDir)
                    if fileSize > 0:
                        try: 
                            with open(fileDir, 'rb') as f:
                                showDetails = json.loads(f.read())
                                f.close()
                            logging.info('Parsing %s', filename)
                            showCache[showID]['seriesImage'] = showDetails.get('seriesImage')
                            showCache[showID]['backgroundImage'] = showDetails.get('backgroundImage')
                            showCache[showID]['credits'] = showDetails['overviewTab']
                            genreString = showDetails.get('seriesGenres')
                            if filename.startswith("MV"):
                                genreString = 'Movie|' + genreString

                            showCache[showID]['genreDict'] = genreString.split('|')
                            showCache[showID]['stars'] = showDetails.get('starRating')
                            episodelist = showDetails['upcomingEpisodeTab']
                            TBAcheck = '' ## initialize it
                            remove_file = False
  #                          logging.info("Walking the upcoming episode list for %s", episodeId)
                            thisAiring={}
                            for airing in episodelist:
                                try: 
 #                                   logging.info("comparing %s to %s", episodeId, airing['tmsID'].lower())
                                    if episodeId == airing['tmsID'].lower():
                                        thisAiring = airing
                                        if not showID.startswith("MV"):
                                            try:
                                                TBAcheck = airing.get('episodeTitle')
                                            except : 
                                                TBAcheck = '' 
                                except :
                                        logging.warning('Unable to compare episodeID with an airing')
#                            logging.info("end of list with episode = %s and found = %s", episodeId, thisAiring['tmsID'])
                            if episodeId != thisAiring['tmsID']:  ## didn't find the episode in existing file - been around a while
                                del showCache[showID]
                                xDetails['status']= 'Retry'
                                remove_file = True
                            else : 
                                if "TBA" in TBAcheck:
                                    logging.info('Deleting %s due to TBA listings', filename)
                                    remove_file = True

                            if remove_file : 
                                try : 
                                    os.remove(fileDir)
                                except OSError as e:
                                    logging.warning('Error Deleting: %s - %s.' % (e.filename, e.strerror))
                        except OSError as e:
                            logging.warning('Error opening Series File : %s - %s.' % (e.filename, e.strerror))
                except OSError as e : 
                    logging.warning ("Unable to get size of the downloaded file %s - %s", e.filename, e.strerror)
            else:
                logging.warning('Could not download details data for: %s - skipping episode', EPseries)
                failList.append(showID)
                del showCache[showID]   # Delete from cache to indicate we failed.
                xDetails['status']='FAIL'

            if showID in showCache:  # it won't if the download failed.   
                xDetails['seriesImage'] = showCache[showID]['seriesImage']
                xDetails['backgroundImage'] = showCache[showID]['backgroundImage']
                xDetails['credits'] = showCache[showID]['credits'] 
                xDetails['genre'] = showCache[showID]['genreDict']

            ### And details about this episode from the series file.
            xDetails['genre'] = thisAiring['isNew'] 
            xDetails['genre'] = thisAiring['isLive']
            xDetails['genre'] = thisAiring['isPremier'] 
            xDetails['genre'] = thisAiring['isFinale']

            if  not thisAiring['isNew'] and \
                not thisAiring['isLive'] and \
                not thisAiring['isPremier'] : 
            ## and original air date , is another Zulu datetime value... get it and convert it. 
                xoriginalAir = calendar.timegm(time.strptime(thisAiring['originalAirDate'], '%Y-%m-%dT%H:%MZ'))
                xis_dst = time.localtime(xoriginalAir).tm_isdst
                xtzoffset = "%.2d%.2d" %(- (time.altzone if xis_dst else time.timezone)/3600, 0)
                xDetails['originalAirDate'] = str( time.strftime("%Y%m%d%H%M%S", time.localtime(xoriginalAir))) + xtzoffset
#                print ("airing from before still good?") 
#                print (showID, episodeId)
#                pprint (thisAiring)
        except Exception as e:
            logging.exception('Exception: parseXdetails %s', e.strerror)

### This is where we go and get Series/Movie info and pull some of that in , like episode icon, play with the categories, etc. 

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
### Still need to figure out how to get a DOCTYPE element embedded
### e.g. <!DOCTYPE tv SYSTEM "xmltv.dtd">

    root = ET.Element("tv" , rootattr)
    logging.info("Building XML info")    
    return root

def printXMLStations (root, schedule) : 
    logging.info("Adding Stations to XML info")
    sortedDict = OrderedDict(sorted(schedule.items(),key=lambda x:x[0]))
    for thischannel in sortedDict  : 

    # Add sub element.
        xchannelattr = { "id" : schedule[thischannel]['info']['stationID'] }
        logging.info('Channel %s - %s (%s) - %s ', \
                            schedule[thischannel]['info']['stationID'].split('.')[0], \
                            schedule[thischannel]['info']['callSign'], \
                            schedule[thischannel]['info']['channelNum'], \
                            schedule[thischannel]['info']['postalCodes'])
        xchannel = ET.SubElement(root, "channel", xchannelattr)
        listings = schedule[thischannel]['station_listing']
        for thislistline in listings :
            channattr = ET.SubElement(xchannel , thislistline[0])
            channattr.text =  thislistline[1]

    return root

def printXMLEvents(root , schedule ) : 
    logging.info("Adding Events to the XML info")

    sortedDict = OrderedDict(sorted(schedule.items(),key=lambda x:x[0]))
    for thischannel in sortedDict  : 
        theseEvents = schedule[thischannel]['events']
#        print ("The number of events for channel ", thischannel, " is ", len(theseEvents))
        for thisEvent in theseEvents : 
  # <programme start="20211108160000 -0600" stop="20211108163000 -0600" channel="20454.zap2epg">
            eventattr = { "start" : theseEvents[thisEvent]['startTime'],
                        "stop": theseEvents[thisEvent]['endTime'],
                        "channel"  : schedule[thischannel]['info']['stationID'] }
            xevent = ET.SubElement(root, "programme" , eventattr)
            itemslist = theseEvents[thisEvent]['4elements']
#            print ("for event ", thisEvent," these are the items to print")
#            pprint (itemslist)
#            print (" and there are ", len(theseEvents[thisEvent]['4elements']), " in the item list.")
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
### Still need to figure out how to get a DOCTYPE element embedded
### e.g. <!DOCTYPE tv SYSTEM "xmltv.dtd">
    logging.info("Writing XML file %s ", xmloutfile)
    xmlstr = minidom.parseString(ET.tostring(root , encoding=xmlencoding, method='xml' )).\
                        toprettyxml(indent = "\t", encoding=xmlencoding)
    with open(xmloutfile, "wb") as f:
       f.write(xmlstr)



  
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

    retrievedFilenamesList = []
    retrievedFilenamesList = retrieveallgrids( xConfig['retrieve_days']  , \
                                                xConfig['postal_code'] , \
                                                xConfig['lineupcode'], \
                                                xConfig['device'], \
                                                xConfig['country'], \
                                                xConfig['debug-grid'])
### just some global dictionaries/caches.

    if xConfig['lineupcode'] == 'lineupId' : 
        usingOTA = True 
    else :
        usingOTA = False

    scheduleDict ={} 
    detailCache = {}
    showCache = {}
    failList = {}

    total_events = 0 
    logged_events = 0

    stationList = []
    pprint (xConfig['station_list'])
    try: 
        stationList = xConfig['station_list'].split(',')
    except BaseException as e: 
        logging.warning("Error splitting the list of stations ... Setting to all channels - %s ", e.msg )
        print ("Error splitting up the list of stations - %s ", e.msg)
        stationList = [] ### Make a null list

    if stationList[0] == 'None' : stationList = []
    pprint(stationList)

    for gridFile in retrievedFilenamesList : 
        if os.path.exists(gridFile):
            gridJSON = loadGrid(gridFile , xConfig['debug-grid'])
            thisPostalCode = gridFile.split('-')[0].split('/')[-1]
            for station in gridJSON['channels'] :
#### if the channelID is in stationlist, or there is no station list (default is all stations represented by "" )
                if station['channelId'] in stationList or len(stationList) == 0 :   
                    if xConfig['debug-grid'] : 
                        print ("next Station ID is " , station['channelId'] , " and call sign is ", station['callSign'] , " and channel num ", station['channelNo'])
                    station_data = build_station_data(station, usingOTA) 
                    station_key=station_data['info']['station_key']
####### IF  channel doesn't exist in the current schedule
#######      add the channel info
                    if station_key not in scheduleDict:
                        scheduleDict[station_key] = {}
                        scheduleDict[station_key]['info']=station_data['info']
                        scheduleDict[station_key]['info']['postalCodes'] = []
                        scheduleDict[station_key]['info']['postalCodes'].append(thisPostalCode)
                        scheduleDict[station_key]['station_listing'] = station_data['listing']
                        scheduleDict[station_key]['events'] = {}
                    if thisPostalCode not in scheduleDict[station_key]['info']['postalCodes'] : 
                        scheduleDict[station_key]['info']['postalCodes'].append(thisPostalCode)
                    additionalEvents = parseEvents( scheduleDict[station_key]['events'] , \
                                                    station['events'],\
                                                    xConfig['language'], \
                                                    cacheDir)
#                    print (" size of events before adding the parsed events ", len(scheduleDict[station_key]['events']))
#                    print ("Size of events returned ", len(additionalEvents))
                    for newEvent in additionalEvents : 
                        scheduleDict[station_key]['events'][newEvent] = additionalEvents[newEvent]
#                        pprint( additionalEvents[newEvent])
#                    print (" size of events AFTER adding the parsed events ", len(scheduleDict[station_key]['events']))
#                    pprint(scheduleDict[station_key]['events'])
### And now, let's build the XML info and write it all out. 

    xmlroot = printXMLHeader ( )  
 #   print ("prior to printing the stations, the list looks like ")
 #   pprint (scheduleDict)

    xmlroot = printXMLStations ( xmlroot, scheduleDict)

 #   print ("prior to printing the events, the list looks like ")
 #   pprint (scheduleDict)
    
    xmlroot =  printXMLEvents(xmlroot , scheduleDict)

    if 'outfile' not in arglineDict : 
        xmlfile = os.path.join(userdata, xConfig['outfile'])
    else :    
        xmlfile = os.path.join(userdata, arglineDict['outfile'])
    xmlencoding = 'utf-8'
    printXMLFooter(xmlroot,  xmlfile, xmlencoding)

    sys.exit(0)
