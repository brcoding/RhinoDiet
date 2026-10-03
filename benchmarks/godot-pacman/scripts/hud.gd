extends CanvasLayer

var score_label: Label
var state_label: Label


func _ready() -> void:
	score_label = Label.new()
	score_label.position = Vector2(16, 8)
	score_label.add_theme_font_size_override("font_size", 22)
	score_label.add_theme_color_override("font_color", Color("f3efe2"))
	add_child(score_label)
	state_label = Label.new()
	state_label.position = Vector2(160, 8)
	state_label.add_theme_font_size_override("font_size", 22)
	state_label.add_theme_color_override("font_color", Color("f3efe2"))
	add_child(state_label)
	show_score(0)
	show_state("Eat every pellet.")


func show_score(value: int) -> void:
	score_label.text = "Score %d" % value


func show_state(text: String) -> void:
	state_label.text = text
