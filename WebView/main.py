# main.py

from flask import Flask, render_template, Response
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
	return render_template('index.html', camera_list=camera_list) 

@app.route('/view_camera/<int:camera_id>')
def view_camera(camera_id):

	return render_template('view.html', camera_id=camera_id)

