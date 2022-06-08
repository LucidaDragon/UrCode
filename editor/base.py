from importlib import import_module
from io import TextIOBase
import os, sys
import subprocess
from typing import Union
import tkinter.filedialog as tkfd
from editor.font_loader import load_font

from editor.ui import ui
ui.initialize()

ICON_FONT = os.path.abspath(os.path.join(os.path.dirname(__file__), "./codicon.ttf"))
ICON_FONT_NAME = "codicon"

_current_plugin: Union[str, None] = None
_current_file: Union[str, None] = None

def get_icon_font() -> Union[str, None]: return ICON_FONT_NAME if load_font(ICON_FONT) else None
def load_icon(icon: str, fallback: str) -> str: return icon if load_font(ICON_FONT) else fallback
def get_file_plugin(file: str) -> str:
	parts = os.path.splitext(file)
	return parts[len(parts) - 1].lstrip(".") if len(parts) > 1 else "txt"

def load_editor_plugins() -> None:
	path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
	for name in os.listdir(os.path.join(path, "./editor_plugins")):
		if name.endswith(f"{os.pathsep}py"): name = name[:len(name) - (len(os.pathsep) + 2)]
		try: import_module("editor_plugins." + name)
		except Exception as ex: print("\"editor_plugins." + name + "\" could not be imported: ", str(ex))

def load_plugin(name: str) -> bool:
	try:
		path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
		import_module("plugins." + name, path)
		return True
	except Exception as ex:
		print(ex)
		return False

def open_file(file: Union[str, None] = None) -> None:
	global _current_file
	global _current_plugin
	if file == None: file = tkfd.askopenfilename()
	if file == "": return
	elif _current_file != None:
		subprocess.Popen([sys.executable, os.path.abspath(os.path.join(os.path.dirname(__file__), "../__init__.py")), file], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
	else:
		stream: TextIOBase = open(file, "r")
		content = "".join(stream.readlines())
		stream.close()
		_current_file = file
		_current_plugin = get_file_plugin(_current_file)
		ui.text_editor.set_text(content)
		if not load_plugin(_current_plugin):
			_current_plugin = "txt"
			load_plugin(_current_plugin)
		ui.update_ui()

def save_file(file: Union[str, None] = None) -> None:
	global _current_file
	global _current_plugin
	if file == None: file = _current_file
	if file == None:
		file = tkfd.asksaveasfilename()
		_current_file = file
	stream: TextIOBase = open(file, "w")
	stream.write(ui.text_editor.get_text())
	stream.close()
	if _current_plugin == None:
		_current_plugin = get_file_plugin(_current_file)
		if not load_plugin(_current_plugin):
			_current_plugin = "txt"
			load_plugin(_current_plugin)

def show_ui() -> None:
	ui.show_ui()

ui.window.title("UrCode")
ui.action_bar.add_action("\uEAF7" if load_font(ICON_FONT) else "Open", open_file, color="#75BEFF", font=get_icon_font())
ui.action_bar.add_action("\uEB4B" if load_font(ICON_FONT) else "Save", save_file, color="#75BEFF", font=get_icon_font())
load_editor_plugins()