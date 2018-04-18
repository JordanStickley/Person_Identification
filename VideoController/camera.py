# camera.py
# 4/10 9:51pm LH - person tracking enhancement and some comment
# 4/13 8:49pm JL - modified label assgignment logic to reuse original label for the same person at new camera.
# 4/16 8:07pm JD - better detection of when someone leaves view and more accurate label reuse
# 4/17 9:00pm LH,JS - Fixed the get_label query to update the has_arrived correctly
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

def distance(p1, p2):
	# calculates the distance between two points
	return ((p2[0]-p1[0])**2+(p2[1]-p1[1])**2)**0.5

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

	def getNextActivityDbId(self):
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

	def count_detections(self, detections):
		# filter out weak detections by ensuring the confidence is
		# greater than the minimum confidence 
		count = 0
		for i in np.arange(0, detections.shape[2]):
			confidence = detections[0, 0, i, 2]
			if confidence > 0.2:
				idx = int(detections[0, 0, i, 1])
				if confidence > 0.5 and (idx == 15):
					count += 1
		return count 

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
			# count how many people we are tracking up front here
			detected_person_count = self.count_detections(detections)
			# loop over the detections
			for t in self.tracked_list:
				t.set_detected(False)

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

					idx = int(detections[0, 0, i, 1])
					box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
					(startX, startY, endX, endY) = box.astype("int")
					if confidence > 0.5 and (idx == 15):
						rect_start = (startX, startY)
						rect_end = (endX, endY)
						t = self.find_closest_tracked_activity(rect_start, detected_person_count)
						t.set_detected(True)
						t.setRect_start(rect_start)
						t.setRect_end(rect_end)
						# draw the prediction on the frame
						label = "{}: {:.2f}%".format(t.getLabel(), confidence * 100)
						cv2.rectangle(frame, rect_start, rect_end, GREEN, 2)
						y = startY - 15 if startY - 15 > 15 else startY + 15
						cv2.putText(frame, label, (startX, y),
							cv2.FONT_HERSHEY_SIMPLEX, 0.5, GREEN, 2)

			# this means that a person has left the camera
			removed_from_tracking=[]
			for t in self.tracked_list:
				if not t.was_detected():
					#guard againest false positives 'person should not have been in view for only 2 seconds'
					if time.time() - t.getStart_time() > 2:
						if self.went_left(t):
							print("went left")
							t.setNext_camera_id(self.cameraDetails.left_camera_id)
							removed_from_tracking.append(t)
						elif self.went_right(t):
							print("went right")
							t.setNext_camera_id(self.cameraDetails.right_camera_id)
							removed_from_tracking.append(t)
				elif t.has_left_the_scene():
					#if someone leaves view and we don't detect it correctly, mark them arrived and remove from tracking
					#the threshold for this is 5 times through the loop and we don't see them
					t.set_arrived(True)
					removed_from_tracking.append(t)
						
			for t in removed_from_tracking:
				#remove tracked entries from tacked_list that were in removed_from_tracking list
				self.saveActivity(t)
				del self.tracked_list[self.tracked_list.index(t)]

			#update the jpeg that we serve back to clients
			self.lock.acquire()
			ret, self.jpeg = cv2.imencode('.jpg', frame)
			self.lock.release()

		self.capturing=False
		self.lock.acquire()
		self.jpeg = self.no_video
		self.lock.release()
	print('camera released.')

	def get_label(self, id):
		conn = self.mysql.connect()
		cursor = conn.cursor()
		#created clause to exclude labels already in used by other tracked people
		camera_id = self.cameraDetails.getID()
		l = "Person %s" % id
		cursor.execute("SELECT id, label from tracking where next_camera_id is not null and next_camera_id = %s and has_arrived = 'F' order by start_time asc limit 1" % (camera_id))
		data = cursor.fetchone()
		if data:
			previous_id = data[0]
			l = data[1]
			print("%s, %s" % (previous_id, l))
			conn.cursor().execute("update tracking set has_arrived = 'T' where id = %d" % previous_id)
			conn.commit()
		return l

	def find_closest_tracked_activity(self, rect_start, detected_person_count):
		# if list is empty then just add a new activity
		if not self.tracked_list:
			return self.begin_new_tracking(rect_start)
		else:
			# otherwise use the distance formula to find the tracked activity that is closest to this new point
			closest_t = None
			for t in self.tracked_list:
				if closest_t:
					closest_t = t if distance(t.getRect_start(), rect_start) < distance(closest_t.getRect_start(), rect_start) else closest_t
				else:
					closest_t = t

			#don't use this one, it's to far from the last rectangle
			#and we are tracking more than one person
			if detected_person_count > len(self.tracked_list) and distance(closest_t.getRect_start(), rect_start) > 100:
				closest_t = self.begin_new_tracking(rect_start)
			return closest_t

	def begin_new_tracking(self, rect_start):
		t = ActivityDbRow()
		t.setID(self.getNextActivityDbId())
		t.setCamera_id(self.cameraDetails.getID())
		t.setLabel(self.get_label(t.getID()))
		t.setRect_start(rect_start)
		t.setStart_time(time.time())
		self.insertActivity(t)
		self.tracked_list.append(t)
		return t

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
