# main.py
# 4/11 6:55pm SH & JD - Work realated with camera link ajax loding
# 4/11 7:36pm JD - work related to the prediction indicator
# 4/13 8:51pm JL - fixed a small bug in the querry of getCameraListWithPredictedMotion()

from flask import Flask, jsonify, render_template, Response, jsonify,json
from flaskext.mysql import MySQL
import time, socket, sys
import os
import configparser
sys.path.append("..")
from shared.CameraDbRow import CameraDbRow

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
	cursor = mysql.connect().cursor()
	cursor.execute("SELECT distinct camera_id from tracking where end_time = '0000-00-00 00:00:00' and start_time > DATE_SUB(current_timestamp, INTERVAL 5 MINUTE) order by camera_id desc")
	data = cursor.fetchall()
	return [c for sublist in data for c in sublist]

def getCameraListWithPredictedMotion():
	cursor = mysql.connect().cursor()
	cursor.execute("SELECT distinct next_camera_id from tracking where next_camera_id is not null and end_time > DATE_SUB(current_timestamp, INTERVAL 1 MINUTE) order by next_camera_id desc")
	data = cursor.fetchall()
	return [c for sublist in data for c in sublist]

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
