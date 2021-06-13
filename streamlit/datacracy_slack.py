
import streamlit as st
import json
import requests
import sys
import os
import pandas as pd
import numpy as np
import re
from datetime import datetime as dt
import seaborn as sns
import matplotlib.pyplot as plt
st.set_page_config(layout="wide")

st.title('DataCracy ATOM Tiến Độ Lớp Học')
with open('D:/Downloads/env_variable.json','r') as j:
    json_data = json.load(j)

#SLACK_BEARER_TOKEN = os.environ.get('SLACK_BEARER_TOKEN') ## Get in setting of Streamlit Share
SLACK_BEARER_TOKEN = json_data['SLACK_BEARER_TOKEN']
DTC_GROUPS_URL = ('https://raw.githubusercontent.com/anhdanggit/atom-assignments/main/data/datacracy_groups.csv')
#st.write(json_data['SLACK_BEARER_TOKEN'])

@st.cache
def load_users_df():
    # Slack API User Data
    endpoint = "https://slack.com/api/users.list"
    headers = {"Authorization": "Bearer {}".format(json_data['SLACK_BEARER_TOKEN'])}
    response_json = requests.post(endpoint, headers=headers).json() 
    user_dat = response_json['members']

    # Convert to CSV
    user_dict = {'user_id':[],'name':[],'display_name':[],'real_name':[],'title':[],'is_bot':[]}
    for i in range(len(user_dat)):
      user_dict['user_id'].append(user_dat[i]['id'])
      user_dict['name'].append(user_dat[i]['name'])
      user_dict['display_name'].append(user_dat[i]['profile']['display_name'])
      user_dict['real_name'].append(user_dat[i]['profile']['real_name_normalized'])
      user_dict['title'].append(user_dat[i]['profile']['title'])
      user_dict['is_bot'].append(int(user_dat[i]['is_bot']))
    user_df = pd.DataFrame(user_dict) 
    # Read dtc_group hosted in github
    dtc_groups = pd.read_csv(DTC_GROUPS_URL)
    user_df = user_df.merge(dtc_groups, how='left', on='name')
    user_df = user_df.replace(np.nan,"khong_co_gi")
    return user_df

@st.cache
def load_channel_df():
    endpoint2 = "https://slack.com/api/conversations.list"
    data = {'types': 'public_channel,private_channel'} # -> CHECK: API Docs https://api.slack.com/methods/conversations.list/test
    headers = {"Authorization": "Bearer {}".format(SLACK_BEARER_TOKEN)}
    response_json = requests.post(endpoint2, headers=headers, data=data).json() 
    channel_dat = response_json['channels']
    channel_dict = {'channel_id':[], 'channel_name':[], 'is_channel':[],'creator':[],'created_at':[],'topics':[],'purpose':[],'num_members':[]}
    for i in range(len(channel_dat)):
        channel_dict['channel_id'].append(channel_dat[i]['id'])
        channel_dict['channel_name'].append(channel_dat[i]['name'])
        channel_dict['is_channel'].append(channel_dat[i]['is_channel'])
        channel_dict['creator'].append(channel_dat[i]['creator'])
        channel_dict['created_at'].append(dt.fromtimestamp(float(channel_dat[i]['created'])))
        channel_dict['topics'].append(channel_dat[i]['topic']['value'])
        channel_dict['purpose'].append(channel_dat[i]['purpose']['value'])
        channel_dict['num_members'].append(channel_dat[i]['num_members'])
    channel_df = pd.DataFrame(channel_dict) 
    return channel_df

@st.cache(allow_output_mutation=True)
def load_msg_dict():
    endpoint3 = "https://slack.com/api/conversations.history"
    headers = {"Authorization": "Bearer {}".format(SLACK_BEARER_TOKEN)}
    msg_dict = {'channel_id':[],'msg_id':[], 'msg_ts':[], 'user_id':[], 'latest_reply':[],'reply_user_count':[],'reply_users':[],'github_link':[],'text':[]}
    for channel_id, channel_name in zip(channel_df['channel_id'], channel_df['channel_name']):
        print('Channel ID: {} - Channel Name: {}'.format(channel_id, channel_name))
        try:
            data = {"channel": channel_id} 
            response_json = requests.post(endpoint3, data=data, headers=headers).json()
            msg_ls = response_json['messages']
            for i in range(len(msg_ls)):
                if 'client_msg_id' in msg_ls[i].keys():
                    msg_dict['channel_id'].append(channel_id)
                    msg_dict['msg_id'].append(msg_ls[i]['client_msg_id'])
                    msg_dict['msg_ts'].append(dt.fromtimestamp(float(msg_ls[i]['ts'])))
                    msg_dict['latest_reply'].append(dt.fromtimestamp(float(msg_ls[i]['latest_reply'] if 'latest_reply' in msg_ls[i].keys() else 0))) ## -> No reply: 1970-01-01
                    msg_dict['user_id'].append(msg_ls[i]['user'])
                    msg_dict['reply_user_count'].append(msg_ls[i]['reply_users_count'] if 'reply_users_count' in msg_ls[i].keys() else 0)
                    msg_dict['reply_users'].append(msg_ls[i]['reply_users'] if 'reply_users' in msg_ls[i].keys() else 0) 
                    msg_dict['text'].append(msg_ls[i]['text'] if 'text' in msg_ls[i].keys() else 0) 
                    ## -> Censor message contains tokens
                    text = msg_ls[i]['text']
                    github_link = re.findall('(?:https?://)?(?:www[.])?github[.]com/[\w-]+/?', text)
                    msg_dict['github_link'].append(github_link[0] if len(github_link) > 0 else None)
        except:
            print('====> '+ str(response_json))
    msg_df = pd.DataFrame(msg_dict)
    return msg_df

def process_msg_data(msg_df, user_df, channel_df):
    ## Extract 2 reply_users
    msg_df['reply_user1'] = msg_df['reply_users'].apply(lambda x: x[0] if x != 0 else '')
    msg_df['reply_user2'] = msg_df['reply_users'].apply(lambda x: x[1] if x != 0 and len(x) > 1 else '')
    ## Merge to have a nice name displayed
    msg_df = msg_df.merge(user_df[['user_id','name','DataCracy_role']].rename(columns={'name':'submit_name'}), \
        how='left',on='user_id')
    msg_df = msg_df.merge(user_df[['user_id','name']].rename(columns={'name':'reply1_name','user_id':'reply1_id'}), \
        how='left', left_on='reply_user1', right_on='reply1_id')
    msg_df = msg_df.merge(user_df[['user_id','name']].rename(columns={'name':'reply2_name','user_id':'reply2_id'}), \
        how='left', left_on='reply_user2', right_on='reply2_id')
    ## Merge for nice channel name
    msg_df = msg_df.merge(channel_df[['channel_id','channel_name','created_at']], how='left',on='channel_id')
    ## Format datetime cols
    msg_df['created_at'] = msg_df['created_at'].dt.strftime('%Y-%m-%d')
    msg_df['msg_date'] = msg_df['msg_ts'].dt.strftime('%A')
    msg_df['msg_time'] = msg_df['msg_ts'].dt.hour
    msg_df['wordcount'] = msg_df.text.apply(lambda s: len(s.split()))
    return msg_df


# Table data
user_df = load_users_df()
channel_df = load_channel_df()
msg_df = load_msg_dict()

# st.write(user_df)
user_df_learner = user_df[user_df.DataCracy_role.str.startswith('Learner')]
result_dict = {'Learner_id':[], 'submited_ass':[], '%_review':[],'gr_wordcount':[],'Ass1_created_at_time':[],'Ass1_created_at_date':[],'Ass2_created_at_time':[],'Ass2_created_at_date':[],'Ass3_created_at_time':[],'Ass3_created_at_date':[],'Ass4_created_at_time':[],'Ass4_created_at_date':[],'Ass5_created_at_time':[],'Ass5_created_at_date':[]}
# st.write(user_df_learner[['user_id','DataCracy_role']])
for i in user_df_learner['user_id']:
# Learner_id
    result_dict['Learner_id'].append(i)
    process_msg_data(msg_df, user_df, channel_df)
    filter_msg_df = msg_df[(msg_df.user_id == i) | (msg_df.reply_user1 == i) | (msg_df.reply_user2 == i)]
    p_msg_df = process_msg_data(filter_msg_df, user_df, channel_df)

    submit_df = p_msg_df[p_msg_df.channel_name.str.contains('assignment')]
    submit_df = submit_df[submit_df.DataCracy_role.str.contains('Learner')]
    submit_df = submit_df[submit_df.user_id == i]
    latest_ts = submit_df.groupby(['channel_name', 'user_id']).msg_ts.idxmax() ## -> Latest ts
    submit_df = submit_df.loc[latest_ts]
# submitted_ass
    result_dict['submited_ass'].append(len(submit_df))

    review_cnt = 100 * len(submit_df[submit_df.reply_user_count > 0])/len(submit_df) if len(submit_df) > 0  else 0
# %_review
    result_dict['%_review'].append(review_cnt)
# Ass_created
    if len(submit_df[submit_df['channel_name'] == 'atom-assignment1']) > 0:
        time_ts = submit_df[submit_df['channel_name'] == 'atom-assignment1']['msg_time'].iloc[0]
        date_ts = submit_df[submit_df['channel_name'] == 'atom-assignment1']['msg_date'].iloc[0]
        result_dict['Ass1_created_at_time'].append(time_ts)
        result_dict['Ass1_created_at_date'].append(date_ts)
    else:
        result_dict['Ass1_created_at_time'].append('NAN')
        result_dict['Ass1_created_at_date'].append('NAN')
    
    if len(submit_df[submit_df['channel_name'] == 'atom-assignment2']) > 0:
        time_ts = submit_df[submit_df['channel_name'] == 'atom-assignment2']['msg_time'].iloc[0]
        date_ts = submit_df[submit_df['channel_name'] == 'atom-assignment2']['msg_date'].iloc[0]
        result_dict['Ass2_created_at_time'].append(time_ts)
        result_dict['Ass2_created_at_date'].append(date_ts)
    else:
        result_dict['Ass2_created_at_time'].append('NAN')
        result_dict['Ass2_created_at_date'].append('NAN')

    if len(submit_df[submit_df['channel_name'] == 'atom-assignment3']) > 0:
        time_ts = submit_df[submit_df['channel_name'] == 'atom-assignment3']['msg_time'].iloc[0]
        date_ts = submit_df[submit_df['channel_name'] == 'atom-assignment3']['msg_date'].iloc[0]
        result_dict['Ass3_created_at_time'].append(time_ts)
        result_dict['Ass3_created_at_date'].append(date_ts)
    else:
        result_dict['Ass3_created_at_time'].append('NAN')
        result_dict['Ass3_created_at_date'].append('NAN')

    if len(submit_df[submit_df['channel_name'] == 'atom-assignment4']) > 0:
        time_ts = submit_df[submit_df['channel_name'] == 'atom-assignment4']['msg_time'].iloc[0]
        date_ts = submit_df[submit_df['channel_name'] == 'atom-assignment4']['msg_date'].iloc[0]
        result_dict['Ass4_created_at_time'].append(time_ts)
        result_dict['Ass4_created_at_date'].append(date_ts)
    else:
        result_dict['Ass4_created_at_time'].append('NAN')
        result_dict['Ass4_created_at_date'].append('NAN')
    
    if len(submit_df[submit_df['channel_name'] == 'atom-assignment5']) > 0:
        time_ts = submit_df[submit_df['channel_name'] == 'atom-assignment5']['msg_time'].iloc[0]
        date_ts = submit_df[submit_df['channel_name'] == 'atom-assignment5']['msg_date'].iloc[0]
        result_dict['Ass5_created_at_time'].append(time_ts)
        result_dict['Ass5_created_at_date'].append(date_ts)
    else:
        result_dict['Ass5_created_at_time'].append('NAN')
        result_dict['Ass5_created_at_date'].append('NAN')
# discussion   
    discuss_df = p_msg_df[p_msg_df.channel_name.str.contains('discuss')]
    result_dict['gr_wordcount'].append(sum(discuss_df['wordcount']))
result_df = pd.DataFrame(result_dict)
st.write(result_df)

fig1, axs = plt.subplots(1,3, figsize = (30,10))
sns.distplot(a = result_df['gr_wordcount'], kde = False, color = "g", ax = axs[0])
axs[0].set_title('Distribution of the number of discussion word-count')
axs[0].set_ylabel('Number')
axs[0].set_xlabel('The number of word-count')

sns.distplot(a = result_df['%_review'], kde = False, color = "r", ax = axs[1] )
axs[1].set_title('Distribution of the reviewed assignment')
axs[1].set_ylabel('Percent')
axs[1].set_xlabel('The reviewed assignment')

sns.distplot(a = result_df['submited_ass'], kde = False, color = "y", ax = axs[2] )
axs[2].set_title('Distribution of the submission assignment number')
axs[2].set_ylabel('Number')
axs[2].set_xlabel('Number of Assignments')
st.pyplot(fig1)

fig2, axs = plt.subplots(1,5, figsize = (30,10))

sns.countplot(x = 'Ass1_created_at_time', data = result_df, color = "m", ax = axs[0])
axs[0].set_title('Distribution of the submited time of assignment 1')
axs[0].set_ylabel('Number')
axs[0].set_xlabel('Submited time (h)')

sns.countplot(x = 'Ass2_created_at_time', data = result_df, color = "m", ax = axs[1])
axs[1].set_title('Distribution of the submited time of assignment 2')
axs[1].set_ylabel('Number')
axs[1].set_xlabel('Submited time (h)')

sns.countplot(x = 'Ass3_created_at_time', data = result_df, color = "m", ax = axs[2])
axs[2].set_title('Distribution of the submited time of assignment 3')
axs[2].set_ylabel('Number')
axs[2].set_xlabel('Submited time (h)')

sns.countplot(x = 'Ass4_created_at_time', data = result_df, color = "m", ax = axs[3])
axs[3].set_title('Distribution of the submited time of assignment 4')
axs[3].set_ylabel('Number')
axs[3].set_xlabel('Submited time (h)')

sns.countplot(x = 'Ass5_created_at_time', data = result_df, color = "m", ax = axs[4])
axs[4].set_title('Distribution of the submited time of assignment 5')
axs[4].set_ylabel('Number')
axs[4].set_xlabel('Submited time (h)')

st.pyplot(fig2)

fig3, axs = plt.subplots(1,5, figsize = (30,10))

sns.countplot(x = 'Ass1_created_at_date', data = result_df, color = "m", ax = axs[0])
axs[0].set_title('Distribution of the submited date of assignment 1')
axs[0].set_ylabel('Number')
axs[0].set_xlabel('Submited date')

sns.countplot(x = 'Ass2_created_at_date', data = result_df, color = "m", ax = axs[1])
axs[1].set_title('Distribution of the submited date of assignment 2')
axs[1].set_ylabel('Number')
axs[1].set_xlabel('Submited date')

sns.countplot(x = 'Ass3_created_at_date', data = result_df, color = "m", ax = axs[2])
axs[2].set_title('Distribution of the submited date of assignment 3')
axs[2].set_ylabel('Number')
axs[2].set_xlabel('Submited date')

sns.countplot(x = 'Ass4_created_at_date', data = result_df, color = "m", ax = axs[3])
axs[3].set_title('Distribution of the submited date of assignment 4')
axs[3].set_ylabel('Number')
axs[3].set_xlabel('Submited date')

sns.countplot(x = 'Ass5_created_at_date', data = result_df, color = "m", ax = axs[4])
axs[4].set_title('Distribution of the submited date of assignment 5')
axs[4].set_ylabel('Number')
axs[4].set_xlabel('Submited date')

st.pyplot(fig3)

# fig1, ax1= plt.subplots()
# df_1 = result_df['submited_ass']
# ax1.hist(df_1,bins = 30)
# st.markdown('## Phân phối số lượng assignment đã nộp')
# st.pyplot(fig1)

# fig1, ax1= plt.subplots()
# df_1 = result_df['%_review']
# ax1.hist(df_1,bins = 30)
# st.markdown('## Phân phối tỷ lệ bài được review')
# st.pyplot(fig1)

# fig1, ax1= plt.subplots()
# df_1 = result_df['gr_wordcount']
# ax1.hist(df_1,bins = 30)
# st.markdown('## Phân phối số wordcount được thảo luận')
# st.pyplot(fig1)






# Input
# st.sidebar.markdown('## Thông tin')
# user_id = st.sidebar.text_input("Nhập Mã Số Người Dùng", 'U01xxxx')

# st.write(process_msg_data(msg_df, user_df, channel_df))
# valid_user_id = user_df['user_id'].str.contains(user_id).any()
# if valid_user_id:
#     filter_user_df = user_df[user_df.user_id == user_id] ## dis = display =]]
#     filter_msg_df = msg_df[(msg_df.user_id == user_id) | (msg_df.reply_user1 == user_id) | (msg_df.reply_user2 == user_id)]
#     p_msg_df = process_msg_data(filter_msg_df, user_df, channel_df)

#     ## Submission
#     submit_df = p_msg_df[p_msg_df.channel_name.str.contains('assignment')]
#     submit_df = submit_df[submit_df.DataCracy_role.str.contains('Learner')]
#     submit_df = submit_df[submit_df.user_id == user_id]
#     latest_ts = submit_df.groupby(['channel_name', 'user_id']).msg_ts.idxmax() ## -> Latest ts
#     submit_df = submit_df.loc[latest_ts]
#     dis_cols1 = ['channel_name', 'created_at','msg_date','msg_time','reply_user_count', 'reply1_name']
    
#     # Review
#     review_df = p_msg_df[p_msg_df.user_id != user_id] ##-> Remove the case self-reply
#     review_df = review_df[review_df.channel_name.str.contains('assignment')]
#     review_df = review_df[review_df.DataCracy_role.str.contains('Learner')]
#     dis_cols2 = ['channel_name', 'created_at','msg_date','msg_time','reply_user_count','submit_name']
    
#     ## Discussion
#     discuss_df = p_msg_df[p_msg_df.channel_name.str.contains('discuss')]
#     discuss_df = discuss_df.sort_values(['msg_date','msg_time'])
#     dis_cols3 = ['channel_name','msg_date', 'msg_time','wordcount','reply_user_count','reply1_name']
    
#     st.markdown('Hello **{}**!'.format(list(filter_user_df['real_name'])[0]))
#     st.write(filter_user_df)
#     st.markdown('## Lịch sử Nộp Assignment')
#     st.write(submit_df[dis_cols1])
#     st.markdown('## Lịch sử Review Assignment')
#     st.write(review_df[dis_cols2])
#     st.markdown('## Lịch sử Discussion')
#     st.write(discuss_df[dis_cols3])

#     # Number cards on Sidebar
#     st.sidebar.markdown(f'''<div class="card text-info bg-info mb-3" style="width: 18rem">
#     <div class="card-body">
#     <h5 class="card-title">ĐÃ NỘP</h5>
#     <p class="card-text">{len(submit_df):02d}</p>
#     </div>
#     </div>''', unsafe_allow_html=True)

#     review_cnt = 100 * len(submit_df[submit_df.reply_user_count > 0])/len(submit_df) if len(submit_df) > 0  else 0
#     st.sidebar.markdown(f'''<div class="card text-info bg-info mb-3" style="width: 18rem">
#     <div class="card-body">
#     <h5 class="card-title">ĐƯỢC REVIEW</h5>
#     <p class="card-text">{review_cnt:.0f}%</p>
#     </div>
#     </div>''', unsafe_allow_html=True)

#     st.sidebar.markdown(f'''<div class="card text-info bg-info mb-3" style="width: 18rem">
#     <div class="card-body">
#     <h5 class="card-title">ĐÃ REVIEW</h5>
#     <p class="card-text">{len(review_df):02d}</p>
#     </div>
#     </div>''', unsafe_allow_html=True)

#     st.sidebar.markdown(f'''<div class="card text-info bg-info mb-3" style="width: 18rem">
#     <div class="card-body">
#     <h5 class="card-title">THẢO LUẬN</h5>
#     <p class="card-text">{sum(discuss_df['wordcount']):,d} chữ</p>
#     </div>
#     </div>''', unsafe_allow_html=True)
    
# else:
#     st.markdown('Không tìm thấy Mã Số {}'.format(user_id))

## Run: streamlit run streamlit/datacracy_slack.py