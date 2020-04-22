
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

def importTrendingDataToDB():
    """
    Update the DB with new trending video
    """

    def getTrendingUrl():
        """
        function to generate the url with signature to retrieve the trending videos data. Trending page is opened in pyppeteer and all the requests url are captured
        INPUT: /
        OUTPUT: the urls are saved in the 2 global variable trendingUrl1 and trendingUrl2 and can be used to retrieve the trending data
        """
        print("getting trending url")
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
            #regex for the 2 types of url we are looking for (maxCursor is changing)
            pattern = re.compile("https://m.tiktok.com/api/item_list/\?count=30&id=1&type=5&secUid=&maxCursor=0&minCursor=0.*")
            pattern2 = re.compile("https://m.tiktok.com/api/item_list/\?count=30&id=1&type=5&secUid=&maxCursor=1&minCursor=0.*")
            if pattern.match(url):
                print(url)
                global trendingUrl1
                trendingUrl1 = url
                #print('found trending url 1')
            elif pattern2.match(url):
                global trendingUrl2
                trendingUrl2 = url
                #print('found trending url 2')
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
                listOfVideoDic.append(dic)
        return listOfVideoDic

    def getTrendingVideoData():
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

        #make the request  type 2 x times
        for _ in range(100):
            #print('request')
            time.sleep(1) #time between each request
            requestData = session.get(url = trendingUrl2, headers=headers)
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
        #make the request to get the list of challenge
        r = session.get(url = discoverUrl, headers=headers)
        data = r.json()
        listOfLinks = []
        if 'body' in data:
            for video in data['body'][2]['exploreList']:
                if video['cardItem']['type'] == 1: #check that it is a music challenge type
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
            page.setDefaultNavigationTimeout(40000)
            #adding the stealth mode to be undetected
            await stealth(page)
            #capture the url of every request and save the ones we want
            page.on('request', lambda request: checkUrlChallenge(request.url))
            await page.goto(urlChallenge)
            await page.waitFor(1000)
            #scroll down to trigger the second request to get trending video data
            for _ in range(20):
                await page.evaluate("""{window.scrollBy(0, document.body.scrollHeight);}""")
                await page.waitFor(1000)
            await page.waitFor(1000)
            print('closing th ebrowser')
            await browser.close()

        try:
            asyncio.get_event_loop().run_until_complete(main())
            return urlList
        except:
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
            return listOfVideoDic

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

    def updateInsertDB(newData):
        #Loading data DB from txt file
        #DB = pd.read_json('dataVideo.json')
        
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

    def getChallengeVideoData(challengeUrlDic):
        """function to make the request to retrieve video data for all the challenge and call the function to process it
        INPUT: dic containing all the challenge data url where the challenges are the key
        OUTPUT: sending the response to function to process data
        """
        listOfVideoDic = []
        for challenge in challengeUrlDic:
            for url in challengeUrlDic[challenge]:
                time.sleep(1)
                #setting the headers where the User-Agent have to be the same as the one used by pupeteer
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3494.0 Safari/537.36",
               "Accept-Encoding": "gzip, deflate, br"}
                #store all the cookies
                session = requests.Session()
                #make the request type 1 for trending data
                requestData = session.get(url = url, headers=headers)

                listOfVideoDic.extend(processDataRequest(requestData))
        print(listOfVideoDic)
        #transforming list of dic into df
        newDataDF = pd.DataFrame(listOfVideoDic)
        newDataDF.set_index('id', inplace=True)
        return newDataDF
                #process data and write it to DB
                #dataToDB(requestData,challenge)

    challengeUrlDic = {}
    #save discover url in global variable
    getDiscoverUrl()
    #get the list of music challenges url
    challengeList = getChallengesList()
    #print(challengeList)
    #looping through each challenge and getting the data url for each challenge
    for challenge in challengeList:
         challengeUrlDic[challenge] = getChallengeUrl(challenge)
    #print(challengeUrlDic)
    newDataDF = getChallengeVideoData(challengeUrlDic)
    #merging new data in DB
    DB = updateInsertDB(newDataDF)
    #putting back the index as a column to have it in the export
    DB['id'] = DB.index
    #saving DF as json into file
    DB.to_json(r'dataVideoChallenge.txt',orient="records")

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
    df_shorter = df_shorter[df_shorter.id != '6815763642621889797']
    df_shorter = df_shorter[df_shorter.id != '6810425865206304006']
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
    print(df_shorter)
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
    importTrendingDataToDB()

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

for _ in range(10):
    time.sleep(60) #time between each request
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
