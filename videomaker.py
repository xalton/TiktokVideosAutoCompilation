
#!/usr/bin/python3

###############
### Modules ###
###############

import os
import json
import wget
import time
import requests
import datetime
import numpy as np
import pandas as pd
from lxml import html
from datetime import date
from moviepy.editor import *

#################
### Functions ###
#################

def checkDuplicates():
    #load data from txt file
    with open('dataVideo.txt') as f:
        dataVideo = json.load(f)

    #load data from txt file
    with open('dataVideo.txt') as f:
        dataVideo2 = json.load(f)

    for index in dataVideo:
        for index2 in dataVideo2:
            if index["id"] == index2["id"]:
                print("duplicate found", index2["id"])


def importTrendingDataToDB2():

    def getTrendingUrl():
        """
        function to generate the url with signature to retrieve the trending videos data. Trending page is opened in pyppeteer and all the requests url are captured
        INPUT: /
        OUTPUT: the urls are saved in the 2 global variable trendingUrl1 and trendingUrl2 and can be used to retrieve the trending data
        """
        #importing everything for the python version of Pupetteer
        import asyncio
        from pyppeteer import launch
        from pyppeteer_stealth import stealth
        import re

        def checkUrl(url):
            """function that receive all the request urls and filter on the url to retrieve the trending video data with the signature
            INPUT: url from all the requests being made by the tiktok trending page
            OUTPUT: the 2 url that are used to retrieve trending video data are saved in 2 global variables
            """
            #regex for the 2 types of url we are looking for
            pattern = re.compile("https://m.tiktok.com/share/item/list\?secUid=&id=&type=5&count=30&minCursor=0&maxCursor=0.*")
            pattern2 = re.compile("https://m.tiktok.com/share/item/list\?secUid=&id=&type=5&count=30&minCursor=0&maxCursor=1.*")
            if pattern.match(url):
                global trendingUrl1
                trendingUrl1 = url
                print('found trending url 1')
            elif pattern2.match(url):
                global trendingUrl2
                trendingUrl2 = url
                print('found trending url 2')
            else:
                pass
                #print('not found')

        async def main():
            """function to launch the browser and capture all the request that are being made by the tiktok page to tget the url with signature
            """
            #launching the browser in headless mode
            browser = await launch({'headless': True})
            page = await browser.newPage()
            #removing the timeout
            page.setDefaultNavigationTimeout(0)
            #adding the stealth mode to be undetected
            await stealth(page)
            #capture the url of every request and save the ones we want
            page.on('request', lambda request: checkUrl(request.url))
            await page.goto('https://www.tiktok.com/trending/?lang=en')
            #scroll down to trigger the second request to get trending video data
            await page.evaluate("""{window.scrollBy(0, document.body.scrollHeight);}""")
            await page.waitFor(2000)
            await browser.close()

        asyncio.get_event_loop().run_until_complete(main())
        return 1

    def processDataRequest(requestData):
        """function to process the data from the trending request
        INPUT: response from trending request
        OUTPUT: list of dictionnary with processed video data
        """
        listOfVideoDic = []
        data = requestData.json()
        if 'body' in data:
            for video in data['body']['itemListData']:
                #extracting the info we want to save
                dic = {}
                dic['id'] = video['itemInfos']['id']
                dic['timeCreated'] = video['itemInfos']['createTime']
                dic['likeCount'] = video['itemInfos']['diggCount']
                dic['shareCount'] = video['itemInfos']['shareCount']
                dic['playCount'] = video['itemInfos']['playCount']
                dic['commentCount'] = video['itemInfos']['commentCount']
                #dic['videoUsed'] = False
                #dic['videoUsedDate'] = ''
                listOfVideoDic.append(dic)
        return listOfVideoDic

    def sendRequest():
        """function that send request to retrieve trending video data
        INPUT: /
        OUTPUT: DF with the video data
        """
        listOfVideoDic = []
        #setting the headers where the User-Agent have to be the SAME as the one used by pupeteer
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3494.0 Safari/537.36",
                "Accept-Encoding": "gzip, deflate, br"}
        #store all the cookies
        session = requests.Session()
        #make the request type 1 for trending data
        requestData = session.get(url = trendingUrl1, headers=headers)
        #process data request and return in list of dictionnary
        listOfVideoDic = processDataRequest(requestData)       

        #make the request  type 2 100 times
        for _ in range(200):
            #print('request')
            time.sleep(1) #time between each request
            requestData = session.get(url = trendingUrl2, headers=headers)
            #merge result with list of dictionnary
            listOfVideoDic.extend(processDataRequest(requestData))

        #transforming list of dic into df
        newDataDF = pd.DataFrame(listOfVideoDic)
        newDataDF.set_index('id', inplace=True)
        return newDataDF

    def updateInsertDB(newData):
        #Loading data DB from txt file
        #DB = pd.read_json('dataVideo.json')

        def cleanBool(x):
            if x == True:
                return True
            else:
                return False
        
        def cleanDate(x):
            if pd.isnull(x):
                return ''
            else:
                return x
        
        with open('dataVideo.txt','r') as f:
            videos_dict = json.load(f)
        DB = pd.DataFrame.from_dict(videos_dict)
        print(DB)
        #Using the ID of the video as DF index
        DB.set_index('id', inplace=True)
        print(DB)
        #selecting records already used
        DBused = DB[DB['videoUsed'] == True]
        #selecting records not used
        Dbnotused = DB[DB['videoUsed'] != True]
        #update/insert new data (update ALL column)
        DB = pd.concat([Dbnotused[~Dbnotused.index.isin(newData.index)], newData])
        #update/insert already used data to overwrite the used status but lose the numbers update
        DB = pd.concat([DB[~DB.index.isin(DBused.index)], DBused])
        DB['videoUsed'] = DB['videoUsed'].apply(cleanBool)
        DB['videoUsedDate'] = DB['videoUsedDate'].apply(cleanDate)

        return DB

    #getting the trending url in global variable
    getTrendingUrl()
    #getting the new data into a DF
    newDataDF = sendRequest()
    #merging new data in DB
    DB = updateInsertDB(newDataDF)
    #putting back the index as a column to have it in the export
    DB['id'] = DB.index
    #saving DF as json into file
    DB.to_json(r'dataVideo.txt',orient="records")

def importTrendingDataToDB():
    """function to save the trending video data in the DB. If the video ID already exist, the data gets updated
    INPUT:
    OUTPUT: writing the data into the txt file
    """

    def checkDataInDB(videoID):
        """function to check if the video already exist in the DB
        INPUT: id of the video we check, DB with all the video already saved
        OUTPUT: if the id is found, return the position in the list. If the id is not found return False
        """
        #looping through each element in the list to check if the video id already exist
        for index, item in enumerate(DB):
            if item['id'] == videoID:
                return index
        return 'not found'

    def addInDB(data):
        """function to add a new video in the DB
        INPUT: DB, data of the video to add
        OUTPUT: DB with new data
        """
        #extracting the info we want to save
        dic = {}
        dic['id'] = data['itemInfos']['id']
        dic['timeCreated'] = data['itemInfos']['createTime']
        dic['likeCount'] = data['itemInfos']['diggCount']
        dic['shareCount'] = data['itemInfos']['shareCount']
        dic['playCount'] = data['itemInfos']['playCount']
        dic['commentCount'] = data['itemInfos']['commentCount']
        dic['videoUsed'] = False
        dic['videoUsedDate'] = ''
        DB.append(dic)
        print('added data in db')
        #writing the output json in a txt file
        #return DB
        #with open('dataVideo.txt', 'w') as outfile:
        #    json.dump(DB, outfile)

    def updateDataDB(data, videoIndex):
        """function to update the data of video that already exist in the DB
        INPUT: DB, data for video to update, index of the video to update in DB list
        OUTPUT: updated DB
        """
        #updating data with latest data
        DB[videoIndex]['likeCount'] = data['itemInfos']['diggCount']
        DB[videoIndex]['shareCount'] = data['itemInfos']['shareCount']
        DB[videoIndex]['playCount'] = data['itemInfos']['playCount']
        DB[videoIndex]['commentCount'] = data['itemInfos']['commentCount']
        print('updated data in db')
        #return DB
        #writing the output json in txt file
        #with open('dataVideo.txt', 'w') as outfile:
        #    json.dump(DB, outfile)

    def dataToDB(requestData):
        """function to process the data from the trending request
        INPUT: response from trending request
        OUTPUT: dispatch to function to write in DB
        """
        #load data from txt file
        #with open('dataVideo.txt') as f:
        #    dataVideo = json.load(f)
        # extracting data in json format
        data = requestData.json()

        if 'body' in data:
            #looping through each video in the response json
            for video in data['body']['itemListData']:
                #check if the DB is already in the DB
                videoIndex = checkDataInDB(video['itemInfos']['id'])
                #add or update the data in the DB
                if videoIndex == 'not found':
                    addInDB(video)
                else:
                    updateDataDB(video, videoIndex)
                #with open('dataVideo.txt', 'w') as outfile:
                #    json.dump(dataVideo, outfile)
        else:
            print("no body")

    def getTrendingUrl():
        """
        function to generate the url with signature to retrieve the trending videos data. Trending page is opened in pyppeteer and all the requests url are captured
        INPUT: /
        OUTPUT: the urls are saved in the 2 global variable trendingUrl1 and trendingUrl2 and can be used to retrieve the trending data
        """
        #importing everything for the python version of Pupetteer
        import asyncio
        from pyppeteer import launch
        from pyppeteer_stealth import stealth
        import re

        def checkUrl(url):
            """function that receive all the request urls and filter on the url to retrieve the trending video data with the signature
            INPUT: url from all the requests being made by the tiktok trending page
            OUTPUT: the 2 url that are used to retrieve trending video data are saved in 2 global variables
            """
            #regex for the 2 types of url we are looking for
            pattern = re.compile("https://m.tiktok.com/share/item/list\?secUid=&id=&type=5&count=30&minCursor=0&maxCursor=0.*")
            pattern2 = re.compile("https://m.tiktok.com/share/item/list\?secUid=&id=&type=5&count=30&minCursor=0&maxCursor=1.*")
            if pattern.match(url):
                global trendingUrl1
                trendingUrl1 = url
                print('found trending url 1')
            elif pattern2.match(url):
                global trendingUrl2
                trendingUrl2 = url
                print('found trending url 2')
            else:
                pass
                #print('not found')

        async def main():
            """function to launch the browser and capture all the request that are being made by the tiktok page to tget the url with signature
            """
            #launching the browser in headless mode
            browser = await launch({'headless': True})
            page = await browser.newPage()
            #removing the timeout
            page.setDefaultNavigationTimeout(0)
            #adding the stealth mode to be undetected
            await stealth(page)
            #capture the url of every request and save the ones we want
            page.on('request', lambda request: checkUrl(request.url))
            await page.goto('https://www.tiktok.com/trending/?lang=en')
            #scroll down to trigger the second request to get trending video data
            await page.evaluate("""{window.scrollBy(0, document.body.scrollHeight);}""")
            await page.waitFor(2000)
            await browser.close()

        asyncio.get_event_loop().run_until_complete(main())
        return 1

    def sendRequest():
        """function that send request to retrieve trending video data
        INPUT: /
        OUTPUT: send the data to function to process them
        """
        #setting the headers where the User-Agent have to be the SAME as the one used by pupeteer
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3494.0 Safari/537.36",
                "Accept-Encoding": "gzip, deflate, br"}
        #store all the cookies
        session = requests.Session()
        #make the request type 1 for trending data
        requestData = session.get(url = trendingUrl1, headers=headers)
        #process data and write it to DB
        dataToDB(requestData)

        #make the request  type 2 100 times
        for _ in range(200):
            time.sleep(1) #time between each request
            requestData = session.get(url = trendingUrl2, headers=headers)
            dataToDB(requestData)

    #load data from txt file
    with open('dataVideo.txt') as f:
        DB = json.load(f)

    #save the signed trending url in global variable
    getTrendingUrl()
    #send request to retrieve the data
    sendRequest()
    with open('dataVideo.txt', 'w') as outfile:
            json.dump(DB, outfile)
    #load data from txt file
    with open('dataVideo.txt') as f:
        dataVideo = json.load(f)
    print("Number of records in DB:", len(dataVideo))

def importChallengeDataToDB():

    #importing everything for the python version of Pupetteer
    import asyncio
    from pyppeteer import launch
    from pyppeteer_stealth import stealth
    import re

    def getDiscoverUrl():
        """function to get the signed discover url that will allow to get the list of challenges
        IN: /
        OUT: discover url is saved in global variable
        """

        def checkUrlDiscover(url):
            """function that receive all the request urls and filter on the discover url with the signature
            INPUT: url from all the requests being made by the tiktok trending page
            OUTPUT: discover url in global variable
            """
            #print(url)
            pattern = re.compile("https://m.tiktok.com/node/share/discover?.*")
            if pattern.match(url):
                global discoverUrl
                discoverUrl = url
                print('found discover url')
            else:
                pass
                #print('not found')

        async def main():
            """function to launch the browser and capture all the request that are being made by the tiktok page to get the url with signature
            """
            #launching the browser in headless mode
            browser = await launch({'headless': True})
            page = await browser.newPage()
            #removing the timeout
            page.setDefaultNavigationTimeout(0)
            #adding the stealth mode to be undetected
            await stealth(page)
            #capture the url of every request and save the ones we want
            page.on('request', lambda request: checkUrlDiscover(request.url))
            await page.goto('https://www.tiktok.com/trending/?lang=en')
            await page.waitFor(2000)
            await browser.close()

        asyncio.get_event_loop().run_until_complete(main())
        return 1

    def getChallengesList():
        """function to retrieve the list of current challenges url
        INPUT:
        OUTPUT: list of all th current challenges link
        """
        #setting the headers where the User-Agent have to be the same as the one used by pupeteer
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3494.0 Safari/537.36",
                "Accept-Encoding": "gzip, deflate, br"}
        #store all the cookies
        session = requests.Session()
        #make the request type 1 for trending data
        r = session.get(url = discoverUrl, headers=headers)
        data = r.json()
        listOfLinks = []
        if 'body' in data:
            for video in data['body'][1]['exploreList']:
                if video['cardItem']['type'] == 3: #check that is it challenge type
                    listOfLinks.append('https://www.tiktok.com'+video['cardItem']['link'])
                else:
                    print("wrong type in discover")
        else:
            print("no body in discover data")
        return listOfLinks

    def getChallengeUrl(urlChallenge):
        """function to retrieve the data urls for each challenge using pyppeteer
        INPUT: challenge urls
        OUTPUT: challenge datas urls
        """
        urlList = []

        def checkUrlChallenge(url):
            pattern = re.compile("https://m.tiktok.com/share/item/list\?secUid.*")
            if pattern.match(url):
                print('found challenge data url')
                urlList.append(url)
            else:
                pass
                #print('not found')

        async def main():
            """function to launch the browser and capture all the request that are being made by the tiktok page to tget the url with signature
            """
            #launching the browser in headless mode
            browser = await launch({'headless': True})
            page = await browser.newPage()
            #removing the timeout
            page.setDefaultNavigationTimeout(0)
            #adding the stealth mode to be undetected
            await stealth(page)
            #capture the url of every request and save the ones we want
            page.on('request', lambda request: checkUrlChallenge(request.url))
            await page.goto(urlChallenge)
            await page.waitFor(1000)
            #scroll down to trigger the second request to get trending video data
            #for _ in range(2):
            #    await page.evaluate("""{window.scrollBy(0, document.body.scrollHeight);}""")
            #    await page.waitFor(1000)
            await page.waitFor(5000)
            print('closing th ebrowser')
            await browser.close()

        asyncio.get_event_loop().run_until_complete(main())
        return urlList

    def addInDB(dataVideo, data, challenge):
        """function to add a new video in the DB
        INPUT: DB, data of the video to add
        OUTPUT: new video is saved in the txt file
        """
        #extracting the info we want to save
        dic = {}
        dic['id'] = data['itemInfos']['id']
        dic['timeCreated'] = data['itemInfos']['createTime']
        dic['likeCount'] = data['itemInfos']['diggCount']
        dic['shareCount'] = data['itemInfos']['shareCount']
        dic['playCount'] = data['itemInfos']['playCount']
        dic['commentCount'] = data['itemInfos']['commentCount']
        dic['videoUsed'] = False
        dic['videoUsedDate'] = ''
        if challenge not in dataVideo:
            dataVideo[challenge] = []
        dataVideo[challenge].append(dic)
        print('added data in db')
        #writing the output json in a txt file
        with open('dataVideoChallenge.txt', 'w') as outfile:
            json.dump(dataVideo, outfile)

    def updateDataDB(dataVideo, data, videoIndex, challenge):
        """function to update the data of video that already exist in the DB
        INPUT: DB, data for video to update, index of the video to update in DB list
        OUTPUT: video data updated in the txt file
        """
        #updating data with latest data
        dataVideo[challenge][videoIndex]['likeCount'] = data['itemInfos']['diggCount']
        dataVideo[challenge][videoIndex]['shareCount'] = data['itemInfos']['shareCount']
        dataVideo[challenge][videoIndex]['playCount'] = data['itemInfos']['playCount']
        dataVideo[challenge][videoIndex]['commentCount'] = data['itemInfos']['commentCount']
        print('updated data in db')
        #writing the output json in txt file
        with open('dataVideoChallenge.txt', 'w') as outfile:
            json.dump(dataVideo, outfile)

    def checkDataInDB(videoID, dataVideo, challenge):
        """function to check if the video already exist in the DB
        INPUT: id of the video we check, DB with all the video already saved
        OUTPUT: if the id is found, return the position in the list. If the id is not found return False
        """
        #looping through each element in the list to check if the video id already exist
        if challenge in dataVideo:
            for index, item in enumerate(dataVideo[challenge]):
                if item['id'] == videoID:
                    return index
            return False
        else:
            return False

    def dataToDB(requestData,challenge):
        """function to process the data from the challenge data request
        INPUT: response from challenge data request
        OUTPUT: dispatch to function to write in DB
        """
        #load data from txt file
        with open('dataVideoChallenge.txt') as f:
            dataVideo = json.load(f)
        # extracting data in json format
        data = requestData.json()

        if 'body' in data:
            #looping through each video in the response json
            for video in data['body']['itemListData']:
                #check if the DB is already in the DB
                videoIndex = checkDataInDB(video['itemInfos']['id'], dataVideo, challenge)
                #add or update the data in the DB
                if videoIndex == False:
                    addInDB(dataVideo, video, challenge)
                else:
                    updateDataDB(dataVideo, video, videoIndex, challenge)
        else:
            print("no body")

    def getChallengeVideoData(challengeUrlDic):
        """function to make the request to retrieve video data for all the challenge and call the finction to process it
        INPUT: dic containing all the challenge data url where the challenges are the key
        OUTPUT: sending the response to function to process data
        """
        for challenge in challengeUrlDic:
            for url in challengeUrlDic[challenge]:
                #setting the headers where the User-Agent have to be the same as the one used by pupeteer
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3494.0 Safari/537.36",
               "Accept-Encoding": "gzip, deflate, br"}
                #store all the cookies
                session = requests.Session()
                #make the request type 1 for trending data
                requestData = session.get(url = url, headers=headers)
                #process data and write it to DB
                dataToDB(requestData,challenge)

    challengeUrlDic = {}
    getDiscoverUrl()
    challengeList = getChallengesList()
    #looping through each challenge
    for challenge in challengeList:
        challengeUrlDic[challenge] = getChallengeUrl(challenge)
    getChallengeVideoData(challengeUrlDic)

def loadDbIntoDf(file):
    """
        Function that load the json file with all the data and treat them to return
        original dataframe and a shorter one and likeCount,commentCount,...
        columns rescalled for the score calculation.
        INPUT: json file
        OUTPUT; dataframes and columns
    """
    #Loading data
    with open(file,'r') as f:
        videos_dict = json.load(f)
    df = pd.DataFrame.from_dict(videos_dict)
    df_shorter = df[df.videoUsed == False] #take only videos no used before
    df_shorter = df_shorter.drop(columns=['timeCreated','videoUsed','videoUsedDate'])
    columns_name = ['id','commentCount','likeCount','playCount','shareCount']
    df_shorter = df_shorter.reindex(columns=columns_name)
    df_shorter = df_shorter.apply(lambda x: x/x.max() if x.name in columns_name[1:] else x)
    return df,df_shorter

def select(df_shorter,nbvideos):
    """
        Function to select a range of best videos according to the value of its score
        defined as combinaton of likeCount, playCount, shareCount and commentCount
        INPUT: DataFrame
        OUTPUT: New DataFrame  with only x top videos sorted by score

    """
    score = (35/100 * df_shorter['likeCount'] + 20/100*df_shorter['playCount'] + 35/100* df_shorter['shareCount']
    + 10/100*df_shorter['commentCount'])*100
    df_shorter['score'] = score
    df_shorter = df_shorter.sort_values('score',ascending=False)
    df_shorter = df_shorter.head(nbvideos)
    return df_shorter

def generateLinkFromId(videoId):
    """
        function to generate a valid link to download a video from a video ID. Link is extracted from html trending page
    INPUT: video ID
    OUTPUT: valid video link

    """
    page = requests.get('https://www.tiktok.com/embed/v2/'+videoId+'?lang=en')
    tree = html.fromstring(page.content)
    buyers = tree.xpath('//*[@id="main"]/div/div/div[1]/div/div/div/div[2]/div[1]/video/@src')
    return buyers[0]

def download(df_shorter):
    """
        Functions to download videos selected using urls.
        INPUT: DataFrame
        OUTPUT: list of videos dowloaded and stored on the folder
    """
    path = os.getcwd()+'\\'
    df_shorter['urls'] = df_shorter['id'].apply(lambda x: generateLinkFromId(x))
    vid_dl = []
    i = 1
    for u in df_shorter['urls']:
        name = str(i)+'.mp4'
        vid_dl.append(wget.download(u,path+name))
        i = i+1
    return vid_dl

def merge(vidlist):
    """
        Function to merge videos dowloaded in one video.
        INPUT: list of videos downloaded
        OUTPUT: One video (not stored as variable)
    """
    today = date.today()
    d = today.strftime("%Y_%m_%d")
    clips = []
    for vid in vidlist:
        if vid.endswith(".mp4"):
            clips.append(VideoFileClip(vid))
    m = max(c.h for c in clips)
    clips = [c.resize(height=m) for c in clips]
    #print(clips[0].size)
    finalrender = concatenate_videoclips(clips,method='compose')
    finalrender.write_videofile('TiktokCompile'+d+'.mp4',codec='libx264')

def update(df,df_shorter):
    """
        Function to update videoUsed and videoUsedDate info in the original dataframe
        and save it as json.
    """
    today = date.today()
    d = today.strftime("%Y_%m_%d")
    for id in df_shorter['id']:
        df.loc[df['id'] == id,'videoUsed'] = True
        df.loc[df['id'] == id,'videoUsedDate'] = d
    print(df)
    df.to_json(r'dataVideo.txt',orient="records")

def importData():
    ### Import new challenge data in the DB ###
    #importChallengeDataToDB()
    #importTrendingDataToDB()
    importTrendingDataToDB2()

def makeVideo():
    ### Import and manip dataVideo ###
    df,df_shorter = loadDbIntoDf('dataVideo.txt')
    print('Initialization is done...')
    print('')
    ##################
    ### Processing ###
    ##################

    print('##################')
    print('### Processing ###')
    print('##################')
    print('')

    ### Select x best videos and download them ###
    df_shorter = select(df_shorter,20)
    vid_dl = download(df_shorter)

    ### merge videos ###
    #merge(vid_dl)

    ### Check ID of selected videos and updtate videoUsed status ###
    #update(df,df_shorter)

######################
### Initialization ###
######################
start_time = time.time()
print('######################')
print('### Initialization ###')
print('######################')
print('')
print('...')
### Global variable for the trending urls (should be avoided) ###
trendingUrl1 = ''
trendingUrl2 = ''
discoverUrl = ''

importData()
#makeVideo()

print('Processing is done... ')
print("--- %s seconds ---" % (time.time() - start_time))
print('')
print('############')
print('### DONE ###')
print('############')

############
### Publish on YT ###
