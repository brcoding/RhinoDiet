extends Node2D

# Wires the maze, player, two ghosts, score, win, and lose.

const MazeScript = preload("res://scripts/maze.gd")
const PlayerScript = preload("res://scripts/player.gd")
const GhostScript = preload("res://scripts/ghost.gd")
const ORIGIN := Vector2(14, 40)

var maze
var player
var ghosts: Array = []
var pellet_nodes := {}
var score := 0
var over := false

@onready var hud: CanvasLayer = $Hud


func _ready() -> void:
	maze = MazeScript.new()
	_paint()
	player = PlayerScript.new()
	player.name = "Player"
	add_child(player)
	player.setup(maze, maze.player_start, ORIGIN, MazeScript.CELL)
	var speeds := [4.2, 3.6]
	var tints := [Color("ff4b4b"), Color("ff7ad1")]
	for index in maze.ghost_starts.size():
		var ghost = GhostScript.new()
		ghost.name = "Ghost%d" % index
		add_child(ghost)
		ghost.setup(
			maze,
			maze.ghost_starts[index],
			ORIGIN,
			MazeScript.CELL,
			tints[index],
			speeds[index],
			index == 0,
		)
		ghosts.append(ghost)
	hud.show_score(0)
	hud.show_state("Eat every pellet.")


func _process(delta: float) -> void:
	if over:
		return
	if player.advance(delta) and maze.eat(player.cell):
		score += 10
		pellet_nodes[player.cell].visible = false
		hud.show_score(score)
	for ghost in ghosts:
		ghost.advance(delta, player.cell)
	if _hit():
		_end(false)
	elif maze.remaining() == 0:
		_end(true)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_R:
		get_tree().reload_current_scene()


func _paint() -> void:
	var bg := ColorRect.new()
	bg.color = Color("070910")
	bg.position = Vector2.ZERO
	bg.size = Vector2(560, 660)
	bg.z_index = -10
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var cell := MazeScript.CELL
	for y in maze.ROWS.size():
		var line := str(maze.ROWS[y])
		for x in line.length():
			var at := ORIGIN + Vector2(x, y) * cell
			if line[x] == "#":
				var wall := ColorRect.new()
				wall.color = Color("2f4ec4")
				wall.position = at
				wall.size = Vector2(cell - 1, cell - 1)
				wall.mouse_filter = Control.MOUSE_FILTER_IGNORE
				add_child(wall)
			elif line[x] == ".":
				var pellet := ColorRect.new()
				pellet.color = Color("ffd56a")
				pellet.position = at + Vector2(11, 11)
				pellet.size = Vector2(6, 6)
				pellet.mouse_filter = Control.MOUSE_FILTER_IGNORE
				add_child(pellet)
				pellet_nodes[Vector2i(x, y)] = pellet


func _hit() -> bool:
	for ghost in ghosts:
		if ghost.occupied() == player.occupied():
			return true
		if player.moving() and ghost.moving():
			if player.from_cell == ghost.to_cell and player.to_cell == ghost.from_cell:
				return true
	return false


func _end(won: bool) -> void:
	over = true
	player.active = false
	for ghost in ghosts:
		ghost.active = false
	if won:
		hud.show_state("You win. Press R to restart.")
	else:
		hud.show_state("You lose. Press R to restart.")
