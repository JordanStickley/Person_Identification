CREATE TABLE tracking (
	id					number primary key,
	label				varchar(50),
	start_time			timestamp,
	end_time			timestamp,
	camera_id			number foreign key
	next_camera_id		number foreign key
);


CREATE TABLE camera (
	camera_id		number primary key,
	camera_IP		number,
	left_cam_id 	number,
	right_cam_id	number
);
