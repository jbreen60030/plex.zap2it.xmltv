# plex.zap2it.xmltv
This is a proof of concept project to source data from zap2it.com and create a useable xmltv file 
for consumption by Plex Media Server. It is based on reviewing other sources that are centric
to other utilities like TVheadend and Kodi.

Support - 
	multi market schedules - for those on the border of two markets, multiple postal codes will be supported and merged as a single schedule. 

	OTA, Cable and Satellite grid retrieval (only a single one)

	User define number of days to purge to refresh grid info (cache everything else). Supporting the idea that the underlying source of data changes (mid-)day.


Requires Python 3	
Use at your own risk. 
This is still a work in progress. 