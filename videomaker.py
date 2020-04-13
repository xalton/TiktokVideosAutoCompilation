
#!/usr/bin/python3

#Modules
import os
import json
import wget
import requests
import numpy as np
import pandas as pd
from lxml import html
from datetime import date
from moviepy.editor import *


#Functions
def data(file):
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
    df_shorter = df.drop(columns=['url','timeCreated','videoUsed','videoUsedDate'])
    columns_name = ['id','commentCount','likeCount','playCount','shareCount']
    df_shorter = df_shorter.reindex(columns=columns_name)
    likeCount = df_shorter['likeCount']/df_shorter['likeCount'].max()
    playCount = df_shorter['playCount']/df_shorter['playCount'].max()
    shareCount = df_shorter['shareCount']/df_shorter['shareCount'].max()
    commentCount = df_shorter['commentCount']/df_shorter['commentCount'].max()
    return df,df_shorter,likeCount,playCount,shareCount,commentCount
def select(df_shorter,likeCount,playCount,shareCount,commentCount):
    """
        Function to select a range of best videos according to the value of its score
        defined as combinaton of likeCount, playCount, shareCount and commentCount
        INPUT: DataFrame
        OUTPUT: New DataFrame with a score column

    """
    score = (35/100 * likeCount + 20/100*playCount + 35/100* shareCount + 10/100*commentCount)*100
    df_shorter['score'] = score
    df_shorter = df_shorter[df_shorter.score > 30]
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
        df.loc[df['id'] == id,'VideoUsed'] = True
        df.loc[df['id'] == id,'VideoDate'] = d
    df.to_json(r'dataVideo'+d+'.json')


#Import and manip dataVideo
df,df_shorter,likeCount,playCount,shareCount,commentCount  = data('dataVideo.json')
#Select x best videos and download them
df_shorter = select(df_shorter,likeCount,playCount,shareCount,commentCount)
vid_dl = download(df_shorter)
#merge videos
merge(vid_dl)
#Check ID of selected videos and updtate videoUsed status
update(df,df_shorter)

#publish on YT
