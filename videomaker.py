
#!/usr/bin/python3
import os
#import json
#import numpy as np
#import pandas as pd
import wget
import requests
from lxml import html

def generateLinkFromId(videoId):
    page = requests.get('https://www.tiktok.com/embed/v2/'+videoId+'?lang=en')
    tree = html.fromstring(page.content)
    buyers = tree.xpath('//*[@id="main"]/div/div/div[1]/div/div/div/div[2]/div[1]/video/@src')
    return buyers[0]

#Loading data
#with open('dataVideo.json','r') as f:
#    videos_dict = json.load(f)

#Manipulate data
#df = pd.DataFrame.from_dict(videos_dict)
#df_shorter = df.drop(columns=['url','timeCreated','videoUsed','videoUsedDate'])
#columns_name = ['id','commentCount','likeCount','playCount','shareCount']
#df_shorter = df_shorter.head()
#df_shorter = df_shorter.reindex(columns=columns_name)

#dataNorm=((df_shorter-df_shorter.min())/(df_shorter.max()-df_shorter.min()))*1
#dataNorm["id"]=df_shorter["id"]
#print(dataNorm)
#TODO: calculate a score for all videos in order to select the x best videos

#Download videos localy
path = os.getcwd()+'\\'
#urls = df['url'].head()
#vid_dl = []
#for u in urls:
#    vid_dl.append(wget.download(u))
vid = wget.download(url[i],path+'.mp4')
print(vid)
#print(vid_dl)


#merge videos
