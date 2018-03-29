# main.py

from flask import Flask, jsonify, render_template, Response
from flaskext.mysql import MySQL
import time, socket, sys
import os
import configparser

config = configparser.ConfigParser()
config.read('config')
mysql = MySQL()
app = Flask(__name__)
app.config['MYSQL_DATABASE_USER'] = 'secuser'
app.config['MYSQL_DATABASE_PASSWORD'] = 'password'
app.config['MYSQL_DATABASE_DB'] = 'securedb'
app.config['MYSQL_DATABASE_HOST'] = config['DB']['host']
mysql.init_app(app)

@app.route('/')
def index():
	cursor = mysql.connect().cursor()
	cursor.execute("SELECT * from camera order by id")
	data = cursor.fetchall()
	print(str(data))
	ip=socket.gethostbyname(socket.gethostname())
	return render_template('index.html', camera_list=data, database_ip=ip) 

@app.route('/view_camera/<int:camera_id>')
def view_camera(camera_id):
	cursor = mysql.connect().cursor()
	cursor.execute("SELECT camera_IP from camera where id = " + str(camera_id))
	data = cursor.fetchone()
	
	return render_template('view.html', camera_id=camera_id, ip=data[0])

@app.route('/home')
def home():
	return render_template('_home.html')
