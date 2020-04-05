
#!/usr/bin/python3
import json
import numpy as np
import pandas as pd

with open('dataVideo.json','r') as f:
    videos_dict = json.load(f)
#for videos in videos_dict:
    print(videos['id'])
data = pd.DataFrame.fom_dict(videos_dict)
