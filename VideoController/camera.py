# camera.py

import sys
sys.path.append("..")
import cv2
import datetime
import numpy as np
import imutils
import time, os
from threading import Lock
from shared.CameraDbRow import CameraDbRow
from shared.ActivityDbRow import ActivityDbRow

class VideoCamera(object):
	def __init__(self, cameraDetails, mysql):
		# Using OpenCV to capture from device 0. If you have trouble capturing
		# from a webcam, comment the line below out and use a video file
		# instead.
		print("[INFO] loading model...")
		self.cameraDetails = cameraDetails
		self.mysql = mysql
		self.shutItDown = False
		self.camera = cv2.VideoCapture(0)
		self.net = cv2.dnn.readNetFromCaffe("MobileNetSSD_deploy.prototxt.txt", "MobileNetSSD_deploy.caffemodel")
		# initialize the list of class labels MobileNet SSD was trained to
		# detect, then generate a set of bounding box colors for each class
		
		ret, self.no_video = cv2.imencode('.jpg', cv2.imread(os.path.realpath("./no_video.jpg")));
		self.jpeg = self.no_video
		self.capturing=False
		self.lock = Lock()
		self.tracked_list = []

	def __del__(self):
		self.camera.release()

	def getNextDbId(self):
		cursor = self.mysql.connect().cursor()
		cursor.execute("SELECT max(id) from tracking")
		data = cursor.fetchall()
		return int(data[0][0])+1 if data[0][0] else 1

	def insertActivity(self, activity):
		conn = self.mysql.connect()
		cursor = conn.cursor()
		cursor.execute(activity.getInsertStatement())
		conn.commit()

	def saveActivity(self, activity):
		conn = self.mysql.connect()
		cursor = conn.cursor()
		cursor.execute(activity.getUpdateStatement())
		conn.commit()

	def getPredictedCameraId(self):
		return 2

	def start(self):
		GREEN = (0,255,0)
		while self.camera.isOpened():
			if self.shutItDown:
				self.camera.release()
				break

			self.capturing = True
			(grabbed, frame) = self.camera.read()
			if not grabbed:
				continue
			time.sleep(.1)
			# grab the frame from the threaded video stream and resize it
			# to have a maximum width of 400 pixels
			frame = imutils.resize(frame, width=400)

			# grab the frame dimensions and convert it to a blob
			(h, w) = frame.shape[:2]
			blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)),
				0.007843, (300, 300), 127.5)

			# pass the blob through the network and obtain the detections and
			# predictions
			self.net.setInput(blob)
			detections = self.net.forward()
			tracked_person_count = 0
			# loop over the detections
			for i in np.arange(0, detections.shape[2]):
				# extract the confidence (i.e., probability) associated with
				# the prediction
				confidence = detections[0, 0, i, 2]

				# filter out weak detections by ensuring the `confidence` is
				# greater than the minimum confidence
				if confidence > 0.2:
					# extract the index of the class label from the
					# `detections`, then compute the (x, y)-coordinates of
					# the bounding box for the object

					idx = int(detections[0, 0, i, 1]) # idx 15 is person
					box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
					(startX, startY, endX, endY) = box.astype("int")
					if confidence > 0.5 and (idx == 15):
						tracked_person_count += 1
						rect_start = (startX, startY)
						rect_end = (endX, endY)
						t = self.find_closest_tracked_activity(rect_start)
						t.setRect_start(rect_start)
						t.setRect_end(rect_end)
						print(str("x1=%d, x2=%d" % (t.getRect_start()[0], t.getRect_end()[0])))
						# draw the prediction on the frame
						label = "{}: {:.2f}%".format(t.getLabel(), confidence * 100)
						cv2.rectangle(frame, rect_start, rect_end, GREEN, 2)
						y = startY - 15 if startY - 15 > 15 else startY + 15
						cv2.putText(frame, label, (startX, y),
							cv2.FONT_HERSHEY_SIMPLEX, 0.5, GREEN, 2)

			# this means that a person has left the camera
			if tracked_person_count < len(self.tracked_list):
				removed_from_tracking=[]
				for t in self.tracked_list:
					if time.time() - t.getStart_time() > 2.1:
						if (self.went_left(t)):
							print("went left")
							t.setNext_camera_id(self.cameraDetails.left_camera_id)
							removed_from_tracking.append(t)
							self.saveActivity(t)
						elif (self.went_right(t)):
							print("went right")
							t.setNext_camera_id(self.cameraDetails.right_camera_id)
							removed_from_tracking.append(t)
							self.saveActivity(t)

				for t in removed_from_tracking:
					del self.tracked_list[self.tracked_list.index(t)]

			self.lock.acquire()
			ret, self.jpeg = cv2.imencode('.jpg', frame)
			self.lock.release()
		self.capturing=False
		self.lock.acquire()
		self.jpeg = self.no_video
		self.lock.release()
		print('camera released.')

	def find_closest_tracked_activity(self, p):
		# if list is empty then just add a new activity
		if not self.tracked_list:
			t = ActivityDbRow()
			t.setID(self.getNextDbId())
			t.setCamera_id(self.cameraDetails.getID())
			t.setLabel("Person %s" % t.getID())
			t.setRect_start(p)
			t.setStart_time(time.time())
			self.insertActivity(t)
			self.tracked_list.append(t)
			return t
		else:
			# otherwise use the distance formula to find the tracked activity that is closest to this new point
			closest_t = None
			for t in self.tracked_list:
				if closest_t:
					closest_t = t if distance(t.getRect_start(), p) < distance(closest_t.getRect_start(), p) else closest_t
				else:
					closest_t = t
			return closest_t

	def went_left(self, activity):
		return (activity.getRect_end()[0] > 345)

	def went_right(self, activity):
		return (activity.getRect_start()[0] < 65)

	def distance(p1, p2):
		# calculates the distance between 2 points
		return ((p2[0]-p1[0])**2+(p2[1]-p1[1])**2)**0.5

	def stop(self):
		self.shutItDown = True

	def is_capturing(self):
		return self.capturing

	def get_frame(self):
		self.lock.acquire()
		bytes = self.jpeg.tobytes()
		self.lock.release()
		return bytes
