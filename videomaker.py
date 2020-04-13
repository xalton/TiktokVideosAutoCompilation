
#!/usr/bin/python3

#Modules
import os
import json
import numpy as np
import pandas as pd
import wget
import requests
from lxml import html
from moviepy.editor import *
from datetime import date

#Functions
def normalization(colum,df):
    tot = colum.sum()
    colum = colum/tot
    return colum
def generateLinkFromId(videoId):
    page = requests.get('https://www.tiktok.com/embed/v2/'+videoId+'?lang=en')
    tree = html.fromstring(page.content)
    buyers = tree.xpath('//*[@id="main"]/div/div/div[1]/div/div/div/div[2]/div[1]/video/@src')
    return buyers[0]
def download(df):
    path = os.getcwd()+'\\'
    df['urls'] = df['id'].apply(lambda x: generateLinkFromId(x))
    vid_dl = []
    i = 1
    for u in df['urls']:
        name = str(i)+'.mp4'
        vid_dl.append(wget.download(u,path+name))
        i = i+1
    return vid_dl
def merge(vidlist):
    today = date.today()
    d = today.strftime("%Y/%m/%d")
    clips = []
    for vid in vidlist:
        if vid.endswith(".mp4"):
            clips.append(VideoFileClip(vid))
    finalrender = concatenate_videoclips(clips,method='compose')
    finalrender.write_videofile('TiktokCompile'+d+'.mp4',codec='libx264')

#Loading data
with open('dataVideo.json','r') as f:
    videos_dict = json.load(f)

#Manipulate data
df = pd.DataFrame.from_dict(videos_dict)
df_shorter = df.drop(columns=['url','timeCreated','videoUsed','videoUsedDate'])
columns_name = ['id','commentCount','likeCount','playCount','shareCount']
df_shorter = df_shorter.head(10)
df_shorter = df_shorter.reindex(columns=columns_name)

likeCount = normalization(df_shorter['likeCount'],df_shorter)
playCount = normalization(df_shorter['playCount'],df_shorter)
shareCount = normalization(df_shorter['shareCount'],df_shorter)
commentCount = normalization(df_shorter['commentCount'],df_shorter)

#Select x best videos
score = 60 * likeCount + 25*playCount + 10* shareCount + 5*commentCount
df_shorter['score'] = score
print(df_shorter)
df_shorter = df_shorter[df_shorter.score > 30]

#Check ID of selected videos and updtate videoUsed status
for id in df_shorter['id']:
    df.loc[df['id'] == id,'VideoUsed'] = True

print(df)
#Download videos localy
#vid_dl = download(df_shorter)
#print(vid_dl)
#merge videos


#publish on YT
