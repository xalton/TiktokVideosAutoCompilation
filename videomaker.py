
#!/usr/bin/python3
import os
import json
import numpy as np
import pandas as pd
import wget
import requests
from lxml import html
from moviepy.editor import *

def generateLinkFromId(videoId):
    page = requests.get('https://www.tiktok.com/embed/v2/'+videoId+'?lang=en')
    tree = html.fromstring(page.content)
    buyers = tree.xpath('//*[@id="main"]/div/div/div[1]/div/div/div/div[2]/div[1]/video/@src')
    return buyers[0]
def normalization(colum,df):
    tot = colum.sum()
    colum = colum/tot
    return colum
#Loading data
with open('dataVideo.json','r') as f:
    videos_dict = json.load(f)

#Manipulate data
df = pd.DataFrame.from_dict(videos_dict)
df_shorter = df.drop(columns=['url','timeCreated','videoUsed','videoUsedDate'])
columns_name = ['id','commentCount','likeCount','playCount','shareCount']
df_shorter = df_shorter.head()
df_shorter = df_shorter.reindex(columns=columns_name)
#print(df_shorter)
#print(df_shorter['likeCount'].max())

likeCount = normalization(df_shorter['likeCount'],df_shorter)
playCount = normalization(df_shorter['playCount'],df_shorter)
shareCount = normalization(df_shorter['shareCount'],df_shorter)
commentCount = normalization(df_shorter['commentCount'],df_shorter)

#TODO: calculate a score for all videos in order to select the x best videos
score = 60 * likeCount + 25*playCount + 10* shareCount + 5*commentCount
df_shorter['score'] = score
df_shorter = df_shorter[df_shorter.score > 30]

#Download videos localy
path = os.getcwd()+'\\'
df_shorter['urls'] = df_shorter['id'].apply(lambda x: generateLinkFromId(x))
vid_dl = []
for u in df_shorter['urls']:
    vid_dl.append(wget.download(u,path+'.mp4'))

#merge videos
finalrender = concatenate_videoclips([vid_dl[0],v])
finalrender.write_videofile('render.mp4',codec='libx264')

#publish on YT
