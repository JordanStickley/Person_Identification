# main.py

from flask import Flask, jsonify, render_template, Response
import time
import os

app = Flask(__name__)

@app.route('/')
def index():
	camera_list = []
	camera_list.append(1)
	camera_list.append(2)
	camera_list.append(3)
	camera_list.append(4)
	camera_list.append(5)
	return render_template('index.html', camera_list=camera_list) 

@app.route('/view_camera/<int:camera_id>')
def view_camera(camera_id):
	ip = '192.168.1.'+str(camera_id)
	if (camera_id==1):
		ip = 'localhost'
	return render_template('view.html', camera_id=camera_id, ip=ip)

