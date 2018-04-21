# 4/16 8:07pm JD - added has arrived attributes to keep track of when a tracked person arrives at the predicted camera

class ActivityDbRow(object):
	def __init__(self, row=None):
		self.id = None
		self.label = None
		self.start_time = None
		self.end_time = None
		self.camera_id = None
		self.next_camera_id = None
		self.has_arrived = None
		self.rect_start = None
		self.rect_end = None
		self.detected = False
		self.not_detected_count = 0

		if row:
			self.id = row[0]
			self.label = row[1]
			self.start_time = row[2]
			self.end_time = row[3]
			self.camera_id = row[4]
			self.next_camera_id = row[5]
			self.has_arrived = True if row[6] and row[6] == 'T' else False

	def getID(self):
		return self.id

	def setID(self, id):
		self.id = id;

	def getLabel(self):
		return self.label

	def setLabel(self, label):
		self.label = label;

	def getStart_time(self):
		return self.start_time

	def setStart_time(self, start_time):
		self.start_time = start_time;

	def getEnd_time(self):
		return self.end_time

	def setEnd_time(self, end_time):
		self.end_time = end_time;

	def getCamera_id(self):
		return self.camera_id

	def setCamera_id(self, camera_id):
		self.camera_id = camera_id;

	def getNext_camera_id(self):
		return self.next_camera_id

	def setNext_camera_id(self, next_camera_id):
		self.next_camera_id = next_camera_id;

	def get_has_arrived(self):
		return self.has_arrived

	def set_has_arrived(self, b):
		self.has_arrived =b 

	def getRect_start(self):
		return self.rect_start

	def setRect_start(self, point):
		self.rect_start = point

	def getRect_end(self):
		return self.rect_end

	def setRect_end(self, point):
		self.rect_end = point

	def set_detected(self, b):
		if b:
			self.not_detected_count = 0
		self.detected = b

	def was_detected(self):
		return self.detected

	def has_left_the_scene(self):
		self.not_detected_count += 1
		return self.not_detected_count > 5

	def getSelectStatement(self):
		return "select id, label, start_time, end_time, camera_id, next_camera_id, has_arrived from tracking where id = %s" % self.id

	def getUpdateStatement(self):
		return "update tracking set end_time = current_timestamp, next_camera_id = %s, has_arrived = '%s' where id = %s" % ((self.next_camera_id if self.next_camera_id else 'null'), 'T' if self.has_arrived else 'F', self.id)

	def getInsertStatement(self):
		return "insert into tracking (id, label, camera_id, has_arrived) values(%s, '%s', %s, 'F')" % (self.id, self.label, (self.camera_id if self.camera_id else 'null'))
