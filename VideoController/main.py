# main.py

from flask import Flask, request, render_template, Response
from camera import VideoCamera
import time
import os
import threading
from flask_cors import CORS
import configparser

config = configparser.ConfigParser()
config.read('config')
app = Flask(__name__)
CORS(app)

camera=None

def checkCamera():
	global camera
	if not camera:
		camera = VideoCamera()
		thread = threading.Thread(target=camera.start)
		thread.daemon = True
		thread.start()

def shutdown_server():
	func = request.environ.get('werkzeug.server.shutdown')
	if func is None:
		raise RuntimeError('Not running with the Werkzeug Server')
	func()

@app.route('/shutdown')
def shutdown():
	global camera
	if camera:
		camera.stop()
	shutdown_server()
	return 'Server shutting down...'

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