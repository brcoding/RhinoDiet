extends RefCounted

# 19 by 21. Hash wall, dot pellet, P player, G ghost.

const COLS := 19
const ROW_COUNT := 21
const CELL := 28

const ROWS: PackedStringArray = [
	"###################",
	"#........#........#",
	"#.##.###.#.###.##.#",
	"#.#...............#",
	"#.##.#.#####.#.##.#",
	"#....#...#...#....#",
	"#.##.###.#.###.##.#",
	"#..#.#.......#.#..#",
	"####.#.##G##.#.####",
	"#......#...#......#",
	"#.##.#.#####.#.##.#",
	"#..#.#.......#.#..#",
	"####.#.#.G##.#.####",
	"#....#...#...#....#",
	"#.##.#.#####.#.##.#",
	"#.#...............#",
	"#.##.###.#.###.##.#",
	"#........P........#",
	"#.##.###.#.###.##.#",
	"#.................#",
	"###################",
]

var pellets: Dictionary = {}
var player_start := Vector2i.ZERO
var ghost_starts: Array[Vector2i] = []


func _init() -> void:
	if ROWS.size() != ROW_COUNT:
		push_error("maze row count")
	for row in ROWS:
		if row.length() != COLS:
			push_error("maze row width")
	for y in ROWS.size():
		var line := str(ROWS[y])
		for x in line.length():
			var cell := Vector2i(x, y)
			var ch := line[x]
			if ch == ".":
				pellets[cell] = true
			elif ch == "P":
				player_start = cell
			elif ch == "G":
				ghost_starts.append(cell)


func wall(cell: Vector2i) -> bool:
	if cell.x < 0 or cell.y < 0 or cell.y >= ROWS.size() or cell.x >= COLS:
		return true
	return str(ROWS[cell.y])[cell.x] == "#"


func walkable(cell: Vector2i) -> bool:
	return not wall(cell)


func eat(cell: Vector2i) -> bool:
	if not pellets.has(cell):
		return false
	pellets.erase(cell)
	return true


func remaining() -> int:
	return pellets.size()
