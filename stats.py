import datetime
import numpy as np
import matplotlib.pyplot as plt
from main import Database


db = Database()

days_array = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
week = datetime.date.today() - datetime.timedelta(days = 7)
today_weekday = datetime.date.today().weekday()    

week_array_names = []
week_dict = dict()
for day in range(today_weekday-6, today_weekday+1):     # Get last 7 days names and dict
    if day <= 0:
        day += 7
    week_dict[day] = 0
    week_array_names.append(days_array[day-1])
    
    
for user in db.get_all_users():                 # Get last 7 days new subs
    if datetime.datetime.strptime(user[2].split()[0], '%Y-%m-%d').date() > week:
        try:
            week_dict[datetime.datetime.strptime(user[2].split()[0], '%Y-%m-%d').weekday()] += 1
        except KeyError:
            week_dict[datetime.datetime.strptime(user[2].split()[0], '%Y-%m-%d').weekday()] = 1

# PLOTTING

data = week_dict.values()
labels = week_dict.keys()

labels_position = np.arange(len(labels))    # Labels position on the plot

fig, ax = plt.subplots(dpi=300)
bar_plot = ax.bar(labels_position, data)
ax.set_title('Last 7 days stats')
ax.set_ylabel('Number of new members')
ax.set_xlabel('Days')
ax.set_xticks(labels_position)
ax.set_xticklabels(week_array_names)        # X-axis names
ax.grid(axis='x')



fig, ax = plt.subplots(figsize=(10, 7), subplot_kw=dict(aspect="equal"), dpi=300)
labels= ['Main requests','Searched requests']
data = [len(db.get_main_requests()) , len(db.get_searched_requests())]

wedges, texts, autotext = ax.pie(data, wedgeprops=dict(width=0.5), startangle=135, autopct='%1.1f%%', textprops=dict(color="w", fontsize=10, ha="center", weight='bold'))
plt.legend(labels, loc='lower right')

plt.figtext(0.69, 0.205, 'Author\'s channel: @regular_patty', ha="center", fontsize=7)
ax.set_title("Main/searched requests", weight="bold", fontsize=18)
plt.show()