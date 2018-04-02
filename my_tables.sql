CREATE TABLE camera (
	id		int primary key,
	camera_IP		int,
	left_cam_id 	int,
	right_cam_id	int,
	is_online		char(1)
);

CREATE TABLE tracking (
	id				int primary key,
	label			varchar(50),
	start_time		timestamp default current_timestamp,
	end_time			timestamp,
	camera_id			int,
	next_camera_id		int,
	foreign key 		(camera_id) references camera(id),
	foreign key 		(next_camera_id) references camera(id)
);