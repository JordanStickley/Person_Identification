# main.py
# 4/11 6:55pm SH & JD - Work realated with camera link ajax loding
# 4/11 7:36pm JD - work related to the prediction indicator
# 4/13 8:51pm JL - fixed a small bug in the querry of getCameraListWithPredictedMotion()
# 4/15 5:05pm LH - added method to load activity from database and added route to sent it back to the browser
# 4/16 6:34pm JD - updated query to exclude activity where the expected person has arrived
# 4/18 8:00pm JL - added a clean_trackings method for resetting the activity table

from flask import Flask, jsonify, render_template, Response, jsonify,json, redirect
from flaskext.mysql import MySQL
import time, socket, sys
import os
import configparser
sys.path.append("..") #Add my parent folder so that I can get access to shared classes
from shared.CameraDbRow import CameraDbRow
from shared.ActivityDbRow import ActivityDbRow

config = configparser.ConfigParser()
config.read('config')
mysql = MySQL()
app = Flask(__name__)
app.config['MYSQL_DATABASE_USER'] = config['DB']['user']
app.config['MYSQL_DATABASE_PASSWORD'] = config['DB']['password']
app.config['MYSQL_DATABASE_DB'] = config['DB']['schema']
app.config['MYSQL_DATABASE_HOST'] = config['DB']['host']
mysql.init_app(app)

def getCameraList():
	global mysql
	cursor = mysql.connect().cursor()
	cursor.execute("SELECT * from camera order by id")
	data = cursor.fetchall()
	camera_list=[]
	cameras_with_motion = getCameraListWithMotion()
	cameras_with_predicted_motion = getCameraListWithPredictedMotion()
	for d in data:
		c = CameraDbRow(d)
		camera_list.append(c)
		if c.getID() in cameras_with_motion:
			c.setHasMotion(True)
		if c.getID() in cameras_with_predicted_motion:
			c.setHasPredictedMotion(True)
	return camera_list

def getCameraListWithMotion():
	global mysql
	cursor = mysql.connect().cursor()
	cursor.execute("SELECT distinct camera_id from tracking where end_time is null and start_time > DATE_SUB(current_timestamp, INTERVAL 5 MINUTE) order by camera_id desc")
	data = cursor.fetchall()
	return [c for sublist in data for c in sublist]

def getCameraListWithPredictedMotion():
	global mysql
	cursor = mysql.connect().cursor()
	cursor.execute("SELECT distinct a.next_camera_id from tracking a left join tracking b on a.next_camera_id = b.camera_id and a.label = b.label where a.next_camera_id is not null and b.camera_id is null and a.has_arrived = 'F' and a.end_time > DATE_SUB(current_timestamp, INTERVAL 1 MINUTE)")
	data = cursor.fetchall()
	return [c for sublist in data for c in sublist]
	
def getActivityList():
	global mysql
	cursor = mysql.connect().cursor()
	cursor.execute("SELECT * from tracking order by start_time desc limit 20")
	activity_list = []
	data = cursor.fetchall()
	for d in data:
		a = ActivityDbRow(d)
		activity_list.append(a)
	return activity_list


@app.route('/')
def index():
	camera_list = getCameraList()

	ip=socket.gethostbyname(socket.gethostname())
	return render_template('index.html', camera_list=camera_list, database_ip=ip, home_content=render_template('_home.html')) 

@app.route('/view_camera/<int:camera_id>')
def view_camera(camera_id):
	cursor = mysql.connect().cursor()
	cursor.execute("SELECT * from camera where id = " + str(camera_id))
	data = cursor.fetchone()
	
	return render_template('view.html', camera_id=camera_id, data=data)
	
#Flask route for pulling by Jquery to update the activity_list html
@app.route('/activity')
def activity():
	activity_list = getActivityList()
	return render_template('_activity.html', activity_list=activity_list)
	
@app.route('/cameras')
def cameras():
	camera_list = getCameraList()
	return render_template('_cameras.html', camera_list=camera_list)


@app.route('/home')
def home():
	return render_template('_home.html')

@app.route('/poll_for_status')
def poll_for_status():
	data = getCameraListWithMotion()
	return jsonify(data);

@app.route('/clean_trackings')
def clean_trackings():
        global mysql
        conn = mysql.connect()
        cursor = conn.cursor()
        cursor.execute("update tracking set end_time = current_timespend where end_time is null")
        conn.commit()
        return redirect("/")