# main.py

from flask import Flask, render_template, Response
from camera import VideoCamera
import time
import os
import threading
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

camera=None

@app.route('/')
def index():
	global camera
	if not camera:
		camera = VideoCamera()
		thread = threading.Thread(target=camera.start)
		thread.daemon = True
		thread.start()

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
	global camera
	return Response(gen(camera),
										mimetype='multipart/x-mixed-replace; boundary=frame')