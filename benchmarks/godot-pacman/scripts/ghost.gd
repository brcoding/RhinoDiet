extends Node2D

# Greedy chase on open cells. Reverse only when boxed in.

var maze
var cell := Vector2i.ZERO
var from_cell := Vector2i.ZERO
var to_cell := Vector2i.ZERO
var direction := Vector2i.ZERO
var progress := 1.0
var active := true
var cells_per_second := 4.0
var prefer_horizontal := true
var origin := Vector2.ZERO
var cell_size := 28


func setup(
	maze_ref,
	start: Vector2i,
	origin_px: Vector2,
	size: int,
	tint: Color,
	speed: float,
	horizontal: bool,
) -> void:
	maze = maze_ref
	cell = start
	from_cell = start
	to_cell = start
	origin = origin_px
	cell_size = size
	cells_per_second = speed
	prefer_horizontal = horizontal
	_build_body(tint)
	_place()


func occupied() -> Vector2i:
	if progress > 0.5:
		return to_cell
	return from_cell


func moving() -> bool:
	return from_cell != to_cell and progress < 1.0


func advance(delta: float, target: Vector2i) -> void:
	if not active:
		return
	if progress >= 1.0:
		var step := _choose(target)
		if step == Vector2i.ZERO:
			_place()
			return
		direction = step
		from_cell = cell
		to_cell = cell + step
		progress = 0.0
	progress += cells_per_second * delta
	if progress >= 1.0:
		progress = 1.0
		cell = to_cell
		from_cell = cell
		to_cell = cell
	_place()


func _choose(target: Vector2i) -> Vector2i:
	var dirs: Array[Vector2i] = [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]
	var reverse := Vector2i.ZERO
	if direction != Vector2i.ZERO:
		reverse = -direction
	var best := Vector2i.ZERO
	var best_score := 1000000
	var only := Vector2i.ZERO
	for d in dirs:
		var nxt := cell + d
		if not maze.walkable(nxt):
			continue
		only = d
		if d == reverse:
			continue
		var score := absi(nxt.x - target.x) + absi(nxt.y - target.y)
		if prefer_horizontal:
			score += absi(nxt.y - target.y)
		else:
			score += absi(nxt.x - target.x)
		if score < best_score:
			best_score = score
			best = d
	if best != Vector2i.ZERO:
		return best
	return only


func _build_body(tint: Color) -> void:
	var poly := Polygon2D.new()
	poly.color = tint
	poly.polygon = PackedVector2Array([
		Vector2(-11, 8),
		Vector2(-11, -2),
		Vector2(-6, -11),
		Vector2(6, -11),
		Vector2(11, -2),
		Vector2(11, 8),
		Vector2(6, 4),
		Vector2(0, 8),
		Vector2(-6, 4),
	])
	add_child(poly)
	_eye(Vector2(-7, -6))
	_eye(Vector2(2, -6))


func _eye(at: Vector2) -> void:
	var eye := ColorRect.new()
	eye.color = Color("f7f7f2")
	eye.position = at
	eye.size = Vector2(4, 5)
	eye.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(eye)


func _place() -> void:
	var t := clampf(progress, 0.0, 1.0)
	var grid := Vector2(from_cell).lerp(Vector2(to_cell), t)
	position = origin + grid * float(cell_size) + Vector2(cell_size, cell_size) * 0.5
