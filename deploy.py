import sys
import os 
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..') )

import nltk
nltk.download('stopwords')

from flask import request
from flask import Flask
from flask import render_template

import json

import pandas as pd

import pickle
from datetime import datetime

from utils.utils import TextProcessor
from models.distance import DistanceModel
from predictor.predictor import Predictor, Formatter
from preprocessors.queproc import QueProc
from preprocessors.proproc import ProProc
import traceback
import time
import psutil

start_time = time.time()

pd.set_option('display.max_columns', 100, 'display.width', 1024)

# Set oath to data
DATA_PATH = 'data'
SAMPLE_PATH = 'demo_data'
DUMP_PATH = 'dump'

# init model
model = DistanceModel(que_dim= 34 - 2 + 8 - 2,
                                  que_input_embs=[102, 42], que_output_embs=[2, 2],
                                  pro_dim=42 - 2,
                                  pro_input_embs=[102, 102, 42], pro_output_embs=[2, 2, 2],
                                  inter_dim=20, output_dim=10)
# load weights
model.load_weights(os.path.join(DUMP_PATH, 'model.h5'))

# load dumped data
with open(os.path.join(DUMP_PATH, 'light_dump.pkl'), 'rb') as file:
    d = pickle.load(file)
    que_proc = d['que_proc']
    pro_proc = d['pro_proc']
    del d

# init text processor
tp = TextProcessor()

# prepare the data
#professionals_sample = pd.read_csv(os.path.join(SAMPLE_PATH, 'pro_sample.csv'))
#pro_tags_sample = pd.read_csv(os.path.join(SAMPLE_PATH, 'tag_users_sample.csv'))

with open(os.path.join(DUMP_PATH, 'origin_data_dump.pkl'), 'rb') as file:
    d = pickle.load(file)
    questions = d['questions']
    answers = d['answers']
    del d
    


#professionals_sample['professionals_date_joined'] = pd.to_datetime(professionals_sample['professionals_date_joined'], infer_datetime_format=True)

answers['answers_date_added'] = pd.to_datetime(answers['answers_date_added'], infer_datetime_format=True)

questions['questions_date_added'] = pd.to_datetime(questions['questions_date_added'], infer_datetime_format=True)


pred = Predictor(model, que_proc, pro_proc)
del que_proc
del pro_proc

formatter = Formatter(DATA_PATH)

# init flask server
app = Flask(__name__, static_url_path='', template_folder='view')

# Routes
print("--- %s seconds ---" % (time.time() - start_time))

@app.route('/')
def index():
  return render_template('index.html')


@app.route("/api/question", methods = ['POST'])
def question():
    try:
      que_dict = {
          'questions_id': ['0'],
          'questions_author_id': [],
          'questions_date_added': [str(datetime.now())],
          'questions_title': [],
          'questions_body': [],
          'questions_tags': []
      }

      data = request.get_json()

      for key, val in data.items():
        if key in que_dict and val:
          que_dict[key].append(str(val))


      for key, val in que_dict.items():
        if not val:
           return json.dumps([], default=str)

      que_df, que_tags = Formatter.convert_que_dict(que_dict)

      print('before : ',psutil.Process(os.getpid()).memory_info().rss)

      tmp = pred.find_ques_by_que(que_df, que_tags)
      final_df = formatter.get_que(tmp).fillna('')
      final_data = final_df.to_dict('records')
      print('after : ',psutil.Process(os.getpid()).memory_info().rss)
      return json.dumps(final_data, allow_nan=False) 

    except Exception as e:
      traceback.print_exc()
      return json.dumps([], default=str)



@app.route("/api/professional", methods = ['POST'])
def professional():
  try:
    pro_dict = {
        'professionals_id': [],
        'professionals_location': [],
        'professionals_industry': [],
        'professionals_headline': [],
        'professionals_date_joined': [],
        'professionals_subscribed_tags': []
      }

    data = request.get_json()
    for professionals_sample in pd.read_csv(os.path.join(SAMPLE_PATH, 'pro_sample.csv'), chunksize=16):
      pro = professionals_sample[professionals_sample['professionals_id'] == data['professionals_id']]
      if pro.shape[0]>0 :
        break
    pro['professionals_date_joined'] = pd.to_datetime(pro['professionals_date_joined'], infer_datetime_format=True)

    pro = pro.to_dict('records')[0]
    for pro_tags_sample in pd.read_csv(os.path.join(SAMPLE_PATH, 'tag_users_sample.csv'), chunksize=16) : 
      tag = pro_tags_sample[pro_tags_sample['tag_users_user_id'] == data['professionals_id']]
      if tag.shape[0] > 0:
        break

    for key, val in pro.items():
        if key in pro_dict and val:
          pro_dict[key].append(str(val))
    
    pro_dict['professionals_subscribed_tags'].append(' '.join(list(tag['tags_tag_name'])))    
    
    for key, val in pro_dict.items():
      if not val:          
         return json.dumps([], default=str)
    
    pro_df, pro_tags = Formatter.convert_pro_dict(pro_dict)
    print('before : ',psutil.Process(os.getpid()).memory_info().rss)
    tmp = pred.find_ques_by_pro(pro_df, questions, answers, pro_tags)
    final_df = formatter.get_que(tmp).fillna('')
    
    final_data = final_df.to_dict('records')
    print('after : ',psutil.Process(os.getpid()).memory_info().rss)
    return json.dumps(final_data, allow_nan=False) 
      
  except Exception as e:
    traceback.print_exc()
    return json.dumps([], default=str)


if __name__ == '__main__':
  app.run(debug=False, host='0.0.0.0', port = 8000)