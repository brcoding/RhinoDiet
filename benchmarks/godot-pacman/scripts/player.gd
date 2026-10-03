extends Node2D

# Queued turn applies when the actor reaches a cell.

var maze
var cell := Vector2i.ZERO
var from_cell := Vector2i.ZERO
var to_cell := Vector2i.ZERO
var direction := Vector2i.LEFT
var queued := Vector2i.LEFT
var progress := 1.0
var active := true
var cells_per_second := 6.0
var origin := Vector2.ZERO
var cell_size := 28


func setup(maze_ref, start: Vector2i, origin_px: Vector2, size: int) -> void:
	maze = maze_ref
	cell = start
	from_cell = start
	to_cell = start
	origin = origin_px
	cell_size = size
	_build_body()
	_place()


func occupied() -> Vector2i:
	if progress > 0.5:
		return to_cell
	return from_cell


func moving() -> bool:
	return from_cell != to_cell and progress < 1.0


func advance(delta: float) -> bool:
	if not active:
		return false
	_sample_keys()
	var arrived := false
	if progress >= 1.0:
		var step := direction
		if maze.walkable(cell + queued):
			step = queued
			direction = queued
		if not maze.walkable(cell + step):
			_place()
			return false
		from_cell = cell
		to_cell = cell + step
		progress = 0.0
	progress += cells_per_second * delta
	if progress >= 1.0:
		progress = 1.0
		cell = to_cell
		from_cell = cell
		to_cell = cell
		arrived = true
	_place()
	return arrived


func _sample_keys() -> void:
	if Input.is_key_pressed(KEY_UP) or Input.is_key_pressed(KEY_W) or Input.is_action_pressed("ui_up"):
		queued = Vector2i.UP
	elif Input.is_key_pressed(KEY_DOWN) or Input.is_key_pressed(KEY_S) or Input.is_action_pressed("ui_down"):
		queued = Vector2i.DOWN
	elif Input.is_key_pressed(KEY_LEFT) or Input.is_key_pressed(KEY_A) or Input.is_action_pressed("ui_left"):
		queued = Vector2i.LEFT
	elif Input.is_key_pressed(KEY_RIGHT) or Input.is_key_pressed(KEY_D) or Input.is_action_pressed("ui_right"):
		queued = Vector2i.RIGHT


func _build_body() -> void:
	var poly := Polygon2D.new()
	poly.color = Color("ffd84a")
	var pts := PackedVector2Array()
	# Wedge faces right. Node rotation turns it with direction.
	for i in range(2, 13):
		var ang := TAU * float(i) / 14.0
		pts.append(Vector2(cos(ang), sin(ang)) * 11.0)
	poly.polygon = pts
	add_child(poly)


func _place() -> void:
	var t := clampf(progress, 0.0, 1.0)
	var grid := Vector2(from_cell).lerp(Vector2(to_cell), t)
	position = origin + grid * float(cell_size) + Vector2(cell_size, cell_size) * 0.5
	rotation = _dir_angle(direction)


func _dir_angle(d: Vector2i) -> float:
	if d == Vector2i.LEFT:
		return PI
	if d == Vector2i.UP:
		return -PI * 0.5
	if d == Vector2i.DOWN:
		return PI * 0.5
	return 0.0
