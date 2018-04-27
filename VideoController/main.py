# main.py
# 4/11 6:55pm SH & JD - added extra call to updateDetailInDb()

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

#hacky way to get my own ip address - connect to mysql and then disconnect
def get_ip_address():
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	s.connect((config['DB']['host'], 3306))
	ip = s.getsockname()[0]
	s.close()
	return ip

def get_port():
	port = "5001"
	if 'listen_port' in config['APP']:
		port = config['APP']['listen_port']
	return port

def updateDetailsInDb():
	global mysql, config
	cameraDetails = None
	try:
		i=0
		cameraDetails = CameraDbRow()
		cameraDetails.setID(config['APP']['camera_id'])
		cameraDetails.setIP("%s:%s" % (get_ip_address(), get_port()))
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
			cursor.execute(cameraDetails.getUpdateStatement())
		else:
			cursor.execute(cameraDetails.getInsertStatement())
		conn.commit()
	except:
		print("Unexpected error:", sys.exc_info())
	return cameraDetails

camera=None
cameraDetails=None

#called by the shutdown flask route to stop the video camera hardware
def shutdownCamera():
	global mysql, camera
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

#a hook to try and shutdown the camer if the video controller exits ( doesn't seem to work on windows )
atexit.register(shutdownCamera)

cameraDetails = updateDetailsInDb()

if not cameraDetails:
	print("Not able to start video controller. Make sure this controller has a unique camera ID in config.")
	exit()

#a method called by flask to start the thread that manages the camera
def checkCamera():
	global config, mysql, camera, cameraDetails
	# this allows the method to be called more than once without starting an additional camera thread
	if not camera:
		cv2_index = config['APP']['cv2_index'] if 'cv2_index' in config['APP'] else 0
		camera = VideoCamera(cv2_index, cameraDetails, mysql)
		#the main camera loop in the start method is invoked here by the thread
		thread = threading.Thread(target=camera.start)
		thread.daemon = True
		thread.start()
	#this method also updates the database with current state of this camera instance
	updateDetailsInDb()

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
			time.sleep(.3)
		frame = camera.get_frame()

		yield (b'--frame\r\n'
					 b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

@app.route('/video_feed')
def video_feed():
	checkCamera()
	return Response(gen(camera),
										mimetype='multipart/x-mixed-replace; boundary=frame')