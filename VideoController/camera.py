# camera.py
# 4/10 9:51pm LH - person tracking enhancement and some comment
# 4/13 8:49pm JL - modified label assgignment logic to reuse original label for the same person at new camera.
# 4/16 8:07pm JD - better detection of when someone leaves view and more accurate label reuse
# 4/17 9:00pm LH,JS - Fixed the get_label query to update the has_arrived correctly
# 4/18 7:46pm SH,JL - add better matching logic when additional people come into view of a camera
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
	def __init__(self, cvs2_index, cameraDetails, mysql):
		# Using OpenCV to capture from device 0.
		self.cameraDetails = cameraDetails
		self.mysql = mysql
		self.shutItDown = False
		print(cvs2_index)
		self.camera = cv2.VideoCapture(int(cvs2_index))
		self.net = cv2.dnn.readNetFromCaffe("MobileNetSSD_deploy.prototxt.txt", "MobileNetSSD_deploy.caffemodel")
		# initialize the list of class labels MobileNet SSD was trained to
		# detect, then generate a set of bounding box colors for each class
		
		ret, self.no_video = cv2.imencode('.jpg', cv2.imread(os.path.realpath("./no_video.jpg")));
		self.jpeg = self.no_video
		self.capturing=False
		self.lock = Lock()
		self.tracked_list = []
		self.used_activity = []
		self.recently_left = None

	def __del__(self):
		self.camera.release()

	def getNextActivityDbId(self):
		cursor = self.mysql.connect().cursor()
		cursor.execute("SELECT max(id) from tracking")
		data = cursor.fetchall()
		return int(data[0][0])+1 if data[0][0] else 1

	def loadActivityDb(self, id):
		a = ActivityDbRow()
		a.setID(id)
		cursor = self.mysql.connect().cursor()
		cursor.execute(a.getSelectStatement())
		data = cursor.fetchone()
		if data:
			a = ActivityDbRow(data)
		return a

	def insertActivity(self, activity):
		conn = self.mysql.connect()
		cursor = conn.cursor()
		cursor.execute(activity.getInsertStatement())
		conn.commit()
		cursor = self.mysql.connect().cursor()
		sql = "select id from tracking where raw_time = '%s' and camera_id = %s" % (activity.getStart_time(), activity.getCamera_id())
		print(sql)
		cursor.execute(sql)
		data = cursor.fetchone()
		print(data)
		if data:
			activity.setID(data[0])

	def saveActivity(self, activity):
		if activity.getID():
			conn = self.mysql.connect()
			cursor = conn.cursor()
			cursor.execute(activity.getUpdateStatement())
			conn.commit()

	def getPredictedCameraId(self):
		return 2

	def get_all_detected_points(self, detections, h, w):
		# filter out weak detections by ensuring the confidence is
		# greater than the minimum confidence 
		points = []
		for i in np.arange(0, detections.shape[2]):
			confidence = detections[0, 0, i, 2]
			if confidence > 0.2:
				idx = int(detections[0, 0, i, 1])
				if confidence > 0.5 and (idx == 15):
					box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
					points.append(box.astype("int")[0:2])

		return points

	def start(self):
		GREEN = (0,255,0)
		while self.camera.isOpened():
			self.used_activity = []
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
			all_detected_points = self.get_all_detected_points(detections, h, w)
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
						t = self.find_closest_tracked_activity(rect_start, all_detected_points)
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
					t.set_has_arrived(True)
					removed_from_tracking.append(t)

			for t in removed_from_tracking:
				#remove tracked entries from tacked_list that were in removed_from_tracking list
				self.saveActivity(t)
				t.setEnd_time(time.time())
				self.recently_left = t

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

	def get_next_person_id(self):
		conn = self.mysql.connect()
		cursor = conn.cursor()
		cursor.execute("select count(distinct label) from tracking")
		data = cursor.fetchone()
		if data:
			return int(data[0])

	def get_label(self):
		conn = self.mysql.connect()
		cursor = conn.cursor()
		#created clause to exclude labels already in use by other tracked people
		camera_id = self.cameraDetails.getID()
		l = "Person %d" % (self.get_next_person_id() + 1)
		cursor.execute("SELECT id, label from tracking where next_camera_id is not null and next_camera_id = %s and has_arrived = 'F' order by start_time asc limit 1" % (camera_id))
		data = cursor.fetchone()
		if data:
			previous_id = data[0]
			l = data[1]
			if previous_id:
				conn.cursor().execute("update tracking set has_arrived = 'T' where id = %d" % previous_id)
				conn.commit()
		return l

	def find_closest_tracked_activity(self, rect_start, all_detected_points):
		detected_person_count = len(all_detected_points)
		all_detected_points_except_this_one = list(filter(lambda x: x[0] != rect_start[0] or x[1] != rect_start[1], all_detected_points))
		self.unused_tracked_list = list(set(self.tracked_list) - set(self.used_activity))
		# if list is empty then just add a new activity
		if not self.tracked_list:
			return self.begin_new_tracking(rect_start)
		else:
			# otherwise use the distance formula to find the tracked activity that is closest to this new point
			closest_t = None
			for t in self.unused_tracked_list:
				if closest_t:
					closest_t = t if distance(t.getRect_start(), rect_start) < distance(closest_t.getRect_start(), rect_start) else closest_t
				else:
					closest_t = t

			#don't use this one, it's to far from the last rectangle
			#and we are tracking more than one person
			more_people_than_activities = detected_person_count > len(self.tracked_list)
			if not closest_t or (more_people_than_activities and self.is_this_activity_closer_to_someone_else(closest_t, all_detected_points_except_this_one, rect_start)):
				closest_t = self.begin_new_tracking(rect_start)

			self.used_activity.append(closest_t)
			return closest_t

	def is_this_activity_closer_to_someone_else(self, activity, the_others, me):
		activity_rect = activity.getRect_start()
		distance_to_me = distance(activity_rect, me)
		matches = list(filter(lambda x: distance(activity_rect, x) < distance_to_me, the_others))
		return len(matches) > 0

	def begin_new_tracking(self, rect_start):
		t = None
		#see if a recently leaving activity has returned
		if (self.recently_left and
				distance(rect_start, self.recently_left.getRect_start()) < 60 and # did they return close to where they left?
				time.time() - self.recently_left.getEnd_time() < 6): # did they return in a reasonable amount of time?
			
			#check to see if they've arrived at their expected destination before trying to reuse here
			a = self.loadActivityDb(self.recently_left.getID())
			if not a.get_has_arrived():
				t = self.recently_left
				t.setEnd_time(None)
				t.setNext_camera_id(None)
				self.saveActivity(t)

			#blank out the recently_left field to indicate that we no longer expect someone to return soon
			self.recently_left = None

		#if no previous activity found then create a new one
		if not t:
			t = ActivityDbRow()
			t.setCamera_id(self.cameraDetails.getID())
			t.setLabel(self.get_label())
			t.setRect_start(rect_start)
			t.setStart_time(time.time())
			self.insertActivity(t)


		#keep track of the activity
		self.tracked_list.append(t)
		
		return t

	def went_left(self, activity):
		return (activity.getRect_end()[0] > 200)

	def went_right(self, activity):
		return (activity.getRect_start()[0] < 200)

	def stop(self):
		self.shutItDown = True

	def is_capturing(self):
		return self.capturing

	def get_frame(self):
		self.lock.acquire()
		bytes = self.jpeg.tobytes()
		self.lock.release()
		return bytes
