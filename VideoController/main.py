# main.py

from flask import Flask, render_template, Response
from camera import VideoCamera
import threading
import time

app = Flask(__name__)
camera = None

@app.route('/')
def index():
        global camera
        if camera == None:
                camera = VideoCamera()
                thread = threading.Thread(target=camera.start)
                thread.daemon = True
                thread.start()
        time.sleep(2)
        return render_template('index.html') 

def gen(camera):
	while True:
		time.sleep(.2)
		frame = camera.get_frame()
		yield (b'--frame\r\n'
					 b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

@app.route('/video_feed')
def video_feed():
		return Response(gen(camera),
										mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
	app.run(host='0.0.0.0', debug=True)
			
