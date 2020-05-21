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

def updateDB():
    """
    function to update the data about all the video in the DB
    1 request per video so the DB has to stay small
    """
    #Loading data DB from txt file
    with open('dataVideo.txt','r') as f:
        videos_dict = json.load(f)
    #loading the dic into a DF
    DB = pd.DataFrame.from_dict(videos_dict)
    #extract the list of ID:
    id_list = DB['id'].tolist()
    #Using the ID of the video as DF index
    DB.set_index('id', inplace=True)
    videoData = []
    for videoId in id_list:
        print(videoId)
        dic = {}
        page = requests.get('https://www.tiktok.com/embed/v2/'+videoId+'?lang=en')
        tree = html.fromstring(page.content)
        buyers = tree.xpath('//*[@id="__NEXT_DATA__"]/text()')
        jsonData = json.loads(buyers[0])
        if 'videoData' in jsonData['props']['pageProps']:
            dic['id'] = videoId
            dic['commentCount'] = jsonData['props']['pageProps']['videoData']['itemInfos']['commentCount']
            dic['likeCount'] = jsonData['props']['pageProps']['videoData']['itemInfos']['diggCount']
            dic['playCount'] = jsonData['props']['pageProps']['videoData']['itemInfos']['playCount']
            dic['shareCount'] = jsonData['props']['pageProps']['videoData']['itemInfos']['shareCount']
            print(dic)
            videoData.append(dic)
        else:
            print("video doesn't exist anymore and was deleted from the DB")
            DB.drop(videoId, inplace=True)
    
    newDataDF = pd.DataFrame(videoData)
    #setting the index with the id
    newDataDF.set_index('id', inplace=True)
    DB.update(newDataDF)
    #putting back the index as a column to have it in the export
    DB['id'] = DB.index
    #saving DF as json into file
    DB.to_json(r'dataVideo.txt',orient="records")

def filterTrendingVideo():
    with open('dataVideo.txt','r') as f:
            videos_dict = json.load(f)
    #loading the dic into a DF
    DB = pd.DataFrame.from_dict(videos_dict)
    #Using the ID of the video as DF index
    DB.set_index('id', inplace=True)
    #number of records before adding new data
    numOldRecord = len(DB)
    print(numOldRecord)
    filtered_df = DB[(DB['likeCount'] > 300000) | (DB['shareCount'] > 5000) | (DB['playCount'] > 2000000) & (DB['commentCount'] > 3000)]
    numNewRecord = len(filtered_df)
    print(numNewRecord)
    #putting back the index as a column to have it in the export
    filtered_df['id'] = filtered_df.index
    #saving DF as json into file
    filtered_df.to_json(r'dataVideo.txt',orient="records")

def importTrendingDataToDB():
    """
    Update the DB with new trending video
    """
    #importing everything for the python version of Pupetteer
    import asyncio
    from pyppeteer import launch
    from pyppeteer_stealth import stealth
    import re

    def getTrendingUrl():
        """
        function to generate the url with signature to retrieve the trending videos data. Trending page is opened in pyppeteer and all the requests url are captured
        INPUT: /
        OUTPUT: the urls are saved in the 2 global variable trendingUrl1 and trendingUrl2 and can be used to retrieve the trending data
        """
        print("Getting trending url...")

        def checkUrl(url,browser):
            """function that receive all the request urls and filter on the url to retrieve the trending video data with the signature
            INPUT: url from all the requests being made by the tiktok trending page
            OUTPUT: the 2 url that are used to retrieve trending video data are saved in 2 global variables
            """
            #regex for the 2 types of url we are looking for (maxCursor is changing)
            pattern = re.compile("https://m.tiktok.com/api/item_list/\?count=30&id=1&type=5&secUid=&maxCursor=0&minCursor=0.*")
            pattern2 = re.compile("https://m.tiktok.com/api/item_list/\?count=30&id=1&type=5&secUid=&maxCursor=1&minCursor=0.*")
            if pattern.match(url):
                #print(url)
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
            page.setDefaultNavigationTimeout(40000)
            #adding the stealth mode to be undetected
            await stealth(page)
            global userAgent
            userAgent = await page.evaluate('navigator.userAgent')
            #capture the url of every request and save the ones we want
            page.on('request', lambda request: checkUrl(request.url,browser))
            await page.goto('https://www.tiktok.com/trending/?lang=en')
            await page.waitFor(2000)
            #scroll down to trigger the second request to get trending video data
            await page.evaluate("""{window.scrollBy(0, document.body.scrollHeight);}""")
            await page.waitFor(2000)
            await browser.close()

        try:
            asyncio.get_event_loop().run_until_complete(main())
        except:
            print("error to go on the trending page. Retrying...")
            time.sleep(10)
            asyncio.get_event_loop().run_until_complete(main())
        return 1

    def processDataRequest(requestData):
        """function to process the data from the trending request
        INPUT: response from trending request
        OUTPUT: list of dictionnary with processed video data
        """
        listOfVideoDic = []
        data = requestData.json()
        if 'items' in data:
            for video in data['items']:
                #extracting the info we want to save
                dic = {}
                dic['id'] = video['id']
                dic['timeCreated'] = video['createTime']
                dic['likeCount'] = video['stats']['diggCount']
                dic['shareCount'] = video['stats']['shareCount']
                dic['playCount'] = video['stats']['playCount']
                dic['commentCount'] = video['stats']['commentCount']
                dic['videoUsed'] = False
                dic['videoUsedDate'] = ''
                if (dic['likeCount'] > 300000) or (dic['shareCount'] > 5000) or (dic['playCount'] > 2000000) or (dic['commentCount'] > 3000):
                    listOfVideoDic.append(dic)
        else:
            print("Error processing the trending data")
        return listOfVideoDic

    def getTrendingVideoData():
        """function that send request to retrieve trending video data
        INPUT: /
        OUTPUT: DF with the video data
        """
        print("Getting trending video data")
        listOfVideoDic = []
        #setting the headers where the User-Agent have to be the SAME as the one used by pupeteer
        headers = {"User-Agent": userAgent
                #"Accept-Encoding": "gzip, deflate, br"
                }
        #store all the cookies
        session = requests.Session()
        #make the request type 1 for trending data
        try:
            requestData = session.get(url = trendingUrl1, headers=headers)
        except:
            print("Error with the first request to get trending data")

        #process data request and return in list of dictionnary
        listOfVideoDic = processDataRequest(requestData)       

        #make the request  type 2 x times
        for _ in range(120):
            #print('request')
            time.sleep(1) #time between each request
            try:
                requestData = session.get(url = trendingUrl2, headers=headers)
            except:
                print("Error to get the trending data")
            #merge result with list of dictionnary
            listOfVideoDic.extend(processDataRequest(requestData))
        #transforming list of dic into df
        newDataDF = pd.DataFrame(listOfVideoDic)
        #dropping the duplicates (appeared in API update why ?)
        newDataDF.drop_duplicates(subset='id',inplace=True,keep='last') 
        #setting the index with the id
        newDataDF.set_index('id', inplace=True)
        return newDataDF

    def updateInsertDB(newData):
        print("merging data into DB")
        #Loading data DB from txt file
        with open('dataVideo.txt','r') as f:
            videos_dict = json.load(f)
        #loading the dic into a DF
        DB = pd.DataFrame.from_dict(videos_dict)
        #Using the ID of the video as DF index
        DB.set_index('id', inplace=True)
        #number of records before adding new data
        numOldRecord = len(DB)

        #adding all the data that are not in DB = insert
        DB = pd.concat([DB, newData[~newData.index.isin(DB.index)]])
        #removing the columns that don't have to be updated
        newData.drop(['videoUsed', 'videoUsedDate'], axis=1, inplace=True)
        #updating the data = updating only the numbers
        DB.update(newData)
        #calulating the number of new records added
        numNewRecord = len(DB)
        numRecordAdded = numNewRecord - numOldRecord
        print("Number of records added in DB:", numRecordAdded)
        print("Total number of records:", numNewRecord)
        return DB

    #getting the trending url in global variable
    getTrendingUrl()
    #getting the new data into a DF
    newDataDF = getTrendingVideoData()
    #merging new data in DB
    DB = updateInsertDB(newDataDF)
    #putting back the index as a column to have it in the export
    DB['id'] = DB.index
    #saving DF as json into file
    DB.to_json(r'dataVideo.txt',orient="records")

def importChallengeDataToDB():

    #importing everything for the python version of Pupetteer
    import asyncio
    from pyppeteer import launch
    from pyppeteer_stealth import stealth
    import re

    def getChallengesList():
        """function to get the signed discover url that will allow to get the list of challenges
        IN: /
        OUT: discover url is saved in global variable
        """
        print("getting the discover url...")

        listOfChallenges = []

        def saveListOfChallenge(listOfChallengeData):
            print("Saving the list of challenge...")
            #putting list of challenge into a DF
            DFChallengeData = pd.DataFrame.from_dict(listOfChallengeData)
            DFChallengeData.set_index('musicId', inplace=True)
            #loading list of challenge from txt
            with open('listChallenge.txt','r') as f:
                videos_dict = json.load(f)
            challengeDB = pd.DataFrame.from_dict(videos_dict)
            #Using the music ID as DF index
            challengeDB.set_index('musicId', inplace=True)
            #adding all the data that are not in DB = insert
            challengeDB = pd.concat([challengeDB, DFChallengeData[~DFChallengeData.index.isin(challengeDB.index)]])
            #removing the columns that don't have to be updated
            DFChallengeData.drop(['challengeUsed', 'challengeUsedDate'], axis=1, inplace=True)
            #updating the data = updating only the numbers
            challengeDB.update(DFChallengeData)
            #putting back the index as a column to have it in the export
            challengeDB['musicId'] = challengeDB.index
            #saving DF as json into file
            challengeDB.to_json(r'listChallenge.txt',orient="records")

        def processDataRequestDiscover(data):
            listOfChallengeData = []
            if 'body' in data:
                for challenge in data['body'][2]['exploreList']:
                    if challenge['cardItem']['type'] == 1: #check that it is a music challenge type
                        listOfChallenges.append('https://www.tiktok.com'+challenge['cardItem']['link'])
                        dic = {}
                        dic['link'] = 'https://www.tiktok.com'+challenge['cardItem']['link']
                        dic['musicId'] = challenge['cardItem']['extraInfo']['musicId']
                        dic['numberOfVideos'] = challenge['cardItem']['extraInfo']['posts']
                        dic['challengeUsed'] = False
                        dic['challengeUsedDate'] = ''
                        listOfChallengeData.append(dic)
                    else:
                        print("wrong type in discover")
            else:
                print("no body in discover data")
            saveListOfChallenge(listOfChallengeData)
            return listOfChallenges

        async def interceptResponse(response):
            url = response.url
            if not response.ok:
                print('request %s failed' % url)
                return
            pattern = re.compile("https://m.tiktok.com/node/share/discover?.*")
            if pattern.match(url):
                try:
                    json_data = await response.json()
                    processDataRequestDiscover(json_data)
                except Exception as e:
                    print(e)
                    print("error to parse json")

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
            global userAgent
            userAgent = await page.evaluate('navigator.userAgent')
            #capture the request response of every request and save the ones we want
            page.on('response', lambda response: asyncio.ensure_future(interceptResponse(response)))
            await page.goto('https://www.tiktok.com/trending/?lang=en')
            await page.waitFor(3000)
            await browser.close()

        try:
            asyncio.get_event_loop().run_until_complete(main())
            print(listOfChallenges)
            return listOfChallenges
        except:
            print("error to get list of challenges on the trending page. Retrying...")
            time.sleep(10)
            asyncio.get_event_loop().run_until_complete(main())

    def getChallengeData(urlChallenge):
        """function to intercept the request with challenge data
        INPUT: challenge urls
        OUTPUT: challenge video data
        """
        print("Getting the challenge data...")
        listOfVideoDic = []

        def processDataRequest(requestData):
            """function to process the data from the trending request
            INPUT: response from trending request
            OUTPUT: list of dictionnary with processed video data
            """
            try:
                data = requestData
                if 'body' in data:
                    for video in data['body']['itemListData']:
                        #extracting the info we want to save
                        dic = {}
                        dic['id'] = video['itemInfos']['id']
                        dic['musicId'] = video['itemInfos']['musicId']
                        dic['timeCreated'] = video['itemInfos']['createTime']
                        dic['likeCount'] = video['itemInfos']['diggCount']
                        dic['shareCount'] = video['itemInfos']['shareCount']
                        dic['playCount'] = video['itemInfos']['playCount']
                        dic['commentCount'] = video['itemInfos']['commentCount']
                        dic['videoUsed'] = False
                        dic['videoUsedDate'] = ''
                        print(dic)
                        listOfVideoDic.append(dic)
            except Exception as e:
                print(e)

        async def interceptResponse(response):
            url = response.url
            if not response.ok:
                print('request %s failed' % url)
                return
            pattern = re.compile("https://m.tiktok.com/share/item/list\?secUid.*")
            if pattern.match(url):
                try:
                    json_data = await response.json()
                    #listOfVideoDic.extend(processDataRequest(json_data))
                    processDataRequest(json_data)
                except Exception as e:
                    print("error to parse json")
                    print(e)

        async def main():
            """function to launch the browser and capture all the request that are being made by the tiktok page to tget the url with signature
            """
            #launching the browser in headless mode
            browser = await launch({'headless': True})
            page = await browser.newPage()
            #removing the timeout
            page.setDefaultNavigationTimeout(100000)
            #adding the stealth mode to be undetected
            await stealth(page)
            global userAgent
            userAgent = await page.evaluate('navigator.userAgent')
            #capture the response of every request and save the ones we want
            page.on('response', lambda response: asyncio.ensure_future(interceptResponse(response)))
            await page.goto(urlChallenge)
            await page.waitFor(1000)
            #scroll down to trigger the requests to get video data
            for _ in range(5):
                await page.evaluate("""{window.scrollBy(0, document.body.scrollHeight);}""")
                await page.waitFor(1000)
            await page.waitFor(3000)
            await browser.close()

        try:
            asyncio.get_event_loop().run_until_complete(main())
            #print(listOfVideoDic)
            return listOfVideoDic
        except Exception as e:
            print(e)
            print("Error to get the challenge url data")
            return listOfVideoDic

    def updateInsertDB(newData):
        
        #loading video challenge data into DF
        with open('dataVideoChallenge.txt','r') as f:
            videos_dict = json.load(f)
        DB = pd.DataFrame.from_dict(videos_dict)
        numOldRecord = len(DB)
        #Using the ID of the video as DF index
        DB.set_index('id', inplace=True)
        #adding all the data that are not in DB = insert
        DB = pd.concat([DB, newData[~newData.index.isin(DB.index)]])
        #removing the columns that don't have to be updated
        newData.drop(['videoUsed', 'videoUsedDate'], axis=1, inplace=True)
        #updating the data = updating only the numbers
        DB.update(newData)

        numNewRecord = len(DB)
        numRecordAdded = numNewRecord - numOldRecord
        print("Number of records added in DB:", numRecordAdded)
        print("Total number of records:", numNewRecord)
        return DB

    #get the list of challenge urls
    challengeList = getChallengesList()
    #looping through each challenge and getting the data url for each challenge
    listOfVideoDic = []
    for challenge in challengeList:
        time.sleep(10) #time between each request
        listOfVideoDic.extend(getChallengeData(challenge))
    #transforming list of dic into df
    newDataDF = pd.DataFrame(listOfVideoDic)
    #dropping the duplicates (appeared in API update why ?)
    newDataDF.drop_duplicates(subset='id',inplace=True,keep='last') 
    #setting the index with the id
    newDataDF.set_index('id', inplace=True)
    #merging new data in DB
    DB = updateInsertDB(newDataDF)
    #putting back the index as a column to have it in the export
    DB['id'] = DB.index
    #saving DF as json into file
    DB.to_json(r'dataVideoChallenge.txt',orient="records")

def loadDbIntoDf2(content):
    """
        Function that load the json file into a DF
        INPUT: json file
        OUTPUT; dataframes and columns
    """
    #Loading data into DF
    if content == 'trending':
        file = 'dataVideo.txt'
    elif content == 'music':
        file = 'dataVideoChallenge.txt'
    else:
        file = 'dataVideo.txt'
    with open(file,'r') as f:
        videos_dict = json.load(f)
    df = pd.DataFrame.from_dict(videos_dict)
    #filter on challenge
    if content == 'music':
        df = df[df.musicId == "6745161928949106690"]
    return df

def selectTop(dfProcess,period,periodNumber,ranking):
    """
        Function to select the top videos for a given period and a given scoring system
        INPUT: DataFrame, period: month/week, ranking: trending/shared/like/view
        OUTPUT: New DataFrame  with only x top videos sorted by score

    """
    #creating new columns
    dfProcess['timeCreated'] = pd.to_datetime(dfProcess['timeCreated'], unit='s')
    if period == 'week':
        dfProcess['weekNumber'] = dfProcess['timeCreated'].dt.week
        dfProcess = dfProcess[dfProcess.weekNumber == periodNumber]
    elif period == 'month':
        dfProcess['monthNumber'] = dfProcess['timeCreated'].dt.month
        dfProcess = dfProcess[dfProcess.monthNumber == periodNumber]
    else:
        print("Period parameter is unknown")
    #select useful columns
    columns_name = ['id','commentCount','likeCount','playCount','shareCount']
    dfProcess = dfProcess[columns_name]
    #calculating score
    dfProcess = dfProcess.apply(lambda x: x/x.max() if x.name in columns_name[1:] else x) #normalisation
    if ranking == 'trending':
        score = (35/100 * dfProcess['likeCount'] + 20/100*dfProcess['playCount'] + 35/100* dfProcess['shareCount']
    + 10/100*dfProcess['commentCount'])*100
    elif ranking == 'share':
        score = dfProcess['shareCount']
    elif ranking == 'like':
        score = dfProcess['likeCount']
    elif ranking == 'view':
        score = dfProcess['playCount']
    else:
        print('ranking unknown')
        score = dfProcess['playCount']
    dfProcess['score'] = score
    #selecting top
    dfProcess = dfProcess.sort_values('score',ascending=False)
    dfProcess = dfProcess.head(50)
    return dfProcess

def generateLinkFromId(videoId):
    """
        function to generate a valid link to download a video from a video ID. Link is extracted from html trending page
    INPUT: video ID
    OUTPUT: valid video link
    """
    page = requests.get('https://www.tiktok.com/embed/v2/'+videoId+'?lang=en')
    tree = html.fromstring(page.content)
    buyers = tree.xpath('//*[@id="main"]/div/div/div[1]/div/div/div/div[2]/div[1]/video/@src')
    if len(buyers) > 0:
        return buyers[0]
    else:
        return False

def download(df_shorter,folderName):
    """
        Functions to download videos given their ID.
        INPUT: DataFrame
        OUTPUT: list of videos dowloaded and stored in the folder
    """
    os.mkdir(str(folderName))
    path = os.getcwd()+'\\'+str(folderName)+'\\'
    #add column with video link generated from IDs
    df_shorter['urls'] = df_shorter['id'].apply(lambda x: generateLinkFromId(x))
    vid_dl = []
    i = 1
    for url in df_shorter['urls']:
        if url != False:
            name = str(i)+'.mp4'
            vid_dl.append(wget.download(url,path+name))#retrun the path of the saved video
            i = i+1
    return vid_dl

def merge(vidlist,weekNumber):
    """
        Function to merge videos dowloaded in one video.
        INPUT: list of videos downloaded
        OUTPUT: One video (not stored as variable)
    """
    #generate day for file name
    today = date.today()
    d = today.strftime("%Y_%m_%d")
    #resizing video
    clips = []
    for vid in vidlist:
        if vid.endswith(".mp4"):
            video = VideoFileClip(vid)
            ratio = video.h / video.w
            if ratio < (16/9 - 0.01):
                video = video.resize(width=1080)
            else:
                video = video.resize(height=1920)
            clips.append(video)
    finalrender = concatenate_videoclips(clips,method='compose')
    finalrender.write_videofile(str(weekNumber)+'.mp4',codec='libx264')

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
    df.to_json(r'dataVideo.txt',orient="records")

def importData():
    """
    function that call the different function to get video data
    """
    #importChallengeDataToDB()
    importTrendingDataToDB()

def makeVideo():
    """
    function that call the different function to make a video
    """
    weekNumber = 11
    for _ in range(10):
        df = loadDbIntoDf2('trending')
        df_copy = df.copy()
        df_shorter = selectTop(df_copy,'week',weekNumber , 'trending')
        vid_dl = download(df_shorter,weekNumber)
        merge(vid_dl,weekNumber)
        weekNumber = weekNumber + 1

start_time = time.time()

### Global variable for the trending urls (should be avoided) ###
trendingUrl1 = ''
trendingUrl2 = ''
discoverUrl = ''
userAgent = '' #will contain the user agent of chromium

#loop to import data
# for _ in range(200):
#     start_time = time.time()
#     importData()
#     time.sleep(1) #time between each request
#     print("--- %s seconds ---" % (time.time() - start_time))

#makeVideo()
# print("--- %s seconds ---" % (time.time() - start_time))

# https://www.tiktok.com/node/share/video/@mrbeast/6804065248375508230
#filterTrendingVideo()
#updateDB()
# print("--- %s seconds ---" % (time.time() - start_time))