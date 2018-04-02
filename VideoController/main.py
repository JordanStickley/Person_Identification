# main.py

import sys
sys.path.append("..")
from flask import Flask, request, render_template, Response
from flaskext.mysql import MySQL
from camera import VideoCamera
import time, os, threading, socket
from flask_cors import CORS
import configparser
from shared.CameraDbRow import CameraDbRow
import atexit

config = configparser.ConfigParser()
config.read('config')
app = Flask(__name__)
CORS(app)
mysql = MySQL()
app.config['MYSQL_DATABASE_USER'] = config['DB']['user']
app.config['MYSQL_DATABASE_PASSWORD'] = config['DB']['password']
app.config['MYSQL_DATABASE_DB'] = config['DB']['schema']
app.config['MYSQL_DATABASE_HOST'] = config['DB']['host']
mysql.init_app(app)

def updateDetailsInDb():
	global mysql
	cameraDetails = None
	try:
		i=0
		cameraDetails = CameraDbRow()
		cameraDetails.setID(config['APP']['camera_id'])
		cameraDetails.setIP(socket.gethostbyname(socket.gethostname()))
		if 'left_camera_id' in config['APP']:
			cameraDetails.setLeftCameraID(config['APP']['left_camera_id'])
		if 'right_camera_id' in config['APP']:
			cameraDetails.setRightCameraID(config['APP']['right_camera_id'])
		cameraDetails.setIsOnline(True)
		conn = mysql.connect()
		cursor = conn.cursor()
		cursor.execute(cameraDetails.getSelectStatement())
		data = cursor.fetchone()
		if data:
			if data[4] != "T":
				print(cameraDetails.getUpdateStatement())
				cursor.execute(cameraDetails.getUpdateStatement())
			else:
				cameraDetails = None
		else:
			print(cameraDetails.getInsertStatement())
			cursor.execute(cameraDetails.getInsertStatement())
		conn.commit()
	except:
		print("Unexpected error:", sys.exc_info())
	return cameraDetails

def shutdown_server():
	func = request.environ.get('werkzeug.server.shutdown')
	if func is None:
		raise RuntimeError('Not running with the Werkzeug Server')
	func()

camera=None
cameraDetails=None

def shutdownCamera():
	global mysql
	global camera
	try:
		cameraDetails.setIsOnline(False)
		conn = mysql.connect()
		cursor = conn.cursor()
		cursor.execute(cameraDetails.getUpdateStatement())
		conn.commit()
		if camera:
			camera.stop()
			camera = None
	except:
		print(sys.exc_info())

atexit.register(shutdownCamera)

cameraDetails = updateDetailsInDb()

if not cameraDetails:
	print("Not able to start video controller. Make sure this controller has a unique camera ID in config.")
	exit()

def checkCamera():
	global mysql
	global camera
	global cameraDetails
	if not camera:
		print('camera %s online' % cameraDetails.getID())
		camera = VideoCamera(cameraDetails, mysql)
		thread = threading.Thread(target=camera.start)
		thread.daemon = True
		thread.start()

@app.route('/shutdown')
def shutdown():
	shutdownCamera()
	return 'Camera stopped.'

@app.route('/')
def index():
	checkCamera()
	return render_template('index.html') 

def gen(camera):
	frame = None
	while True:
		if not frame:
			time.sleep(.2)
		frame = camera.get_frame()

		yield (b'--frame\r\n'
					 b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

@app.route('/video_feed')
def video_feed():
	checkCamera()
	return Response(gen(camera),
										mimetype='multipart/x-mixed-replace; boundary=frame')