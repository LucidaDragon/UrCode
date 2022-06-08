import inspect
from math import floor, log
from multiprocessing import Queue
import tkinter as tk
import tkinter.font as tkfont
from typing import Any, Callable, Literal, Tuple, Union

class ui:
	@staticmethod
	def get_default_font() -> str:
		root = tk.Tk()
		source = tk.Label()
		result = source["font"]
		root.destroy()
		return result

	PIXEL: tk.PhotoImage

	@staticmethod
	def get_scale() -> float:
		screen = tk.Tk()
		result = screen.winfo_fpixels("1i") / 96.0
		screen.destroy()
		return result

	@staticmethod
	def dip(value: float) -> float:
		return value * ui.get_scale()

	class CodeColors:
		font_name = "Consolas"
		font_size = 11

		window_background = "#333333"
		background = "#1D1D1D"
		error = "#FF776B"
		warning = "#FFE36B"
		breakpoint = "#E41400"
		location = "#4B4B18"
		hotpath = "#EA8227"
		caret = "#FFFFFF"
		comment = "#699954"
		completion_background = "#383D49"
		completion_font = "#CDCFD1"
		function = "#DBDBAA"
		keyword = "#569CD6"
		variable = "#9CDBFD"
		number = "#B5CDA8"
		string = "#CD9077"
		macro = "#C586C0"
		text = "#D4D4D4"
		text_selected = "#264F78"
		text_disabled = "#969696"
		type = "#4DC8AF"

		def get_colors(self) -> "dict[str, str]":
			result: dict[str, str] = {}
			for name, member in inspect.getmembers(self):
				if isinstance(member, str) and len(member) == 7 and not (name.startswith("_") or name.startswith("font")): result[name] = member
			return result

		def get_color(self, name: str) -> str:
			result = getattr(self, name.strip("_"), "#000000")
			return result if isinstance(result, str) and len(result) == 7 else "#000000"
		
		def parse_color(self, name: str) -> Tuple[float, float, float]:
			try:
				color = self.get_color(name).lstrip("#")
				return int(color[0:2], 16) / 255.0, int(color[2:4], 16) / 255.0, int(color[4:6], 16) / 255.0
			except: return (0.0, 0.0, 0.0)
		
		def get_lerp_color(self, nameA: str, nameB: str, amount: float) -> str:
			def lerp(a: float, b: float, t: float) -> float: return (a * (1 - t)) + (b * t)
			ra, ga, ba = self.parse_color(nameA)
			rb, gb, bb = self.parse_color(nameB)
			return "#" + hex((floor(lerp(ra, rb, amount) * 255) << 16) | (floor(lerp(ga, gb, amount) * 255) << 8) | floor(lerp(ba, bb, amount) * 255)).lstrip("0x").upper().rjust(6, "0")

	class CodeObject:
		def __init__(self, type: str, regex: str) -> None:
			self.type = type
			self.regex = regex

	class MultiBinding:
		def __init__(self) -> None:
			self.targets: list[Callable] = []
		
		def bind(self, target: Callable) -> None:
			self.targets.append(target)
		
		def unbind(self, target: Callable) -> None:
			self.targets.remove(target)
		
		def event(self, *args, **kwargs) -> None:
			for target in self.targets: target(*args, **kwargs)

	class DelayedEvent:
		def __init__(self, owner: tk.Widget, delay_ms: int) -> None:
			self.owner = owner
			self.delay_ms = delay_ms
			self.targets: list[Callable[[], None]] = []
			self.recall: Union[str, None] = None

		def bind(self, target: Callable[[], None]) -> None:
			self.targets.append(target)
		
		def unbind(self, target: Callable[[], None]) -> None:
			self.targets.remove(target)

		def fire(self) -> None:
			if self.recall != None: self.owner.after_cancel(self.recall)
			self.recall = self.owner.after(self.delay_ms, self._on_run)
		
		def _on_run(self) -> None:
			self.recall = None
			for target in self.targets: target()

	class HighlightText(tk.Text):
		def __init__(self, *args, **kwargs):
			super().__init__(*args, **kwargs)
			self.configure(borderwidth=0, highlightthickness=0)
			self.highlight_event = ui.DelayedEvent(self, 300)
			self.highlight_event.bind(self.highlight)
			self.definitions: list[ui.CodeObject] = []
			self.bind("<Key>", lambda e: self.highlight_event.fire() if e.char else None)
			self.set_colors(ui.CodeColors())
		
		def set_colors(self, colors: "ui.CodeColors") -> None:
			self.configure(foreground=colors.text, background=colors.background, insertbackground=colors.caret, selectbackground=colors.text_selected, font=(colors.font_name, colors.font_size), tabs=tkfont.Font(name=colors.font_name, size=colors.font_size).measure("    "))
			types: dict[str, str] = colors.get_colors()
			for type in types: self.tag_configure(type, foreground=types[type])
			self.tag_configure("location_back", background=colors.location)
			for level in range(256): self.tag_configure(f"hotpath_{level}", background=colors.get_lerp_color("background", "hotpath", level / 255.0))

		def add_object_type(self, type: str, regex: str) -> None: self.definitions.append(ui.CodeObject(type, regex))

		def get_text(self) -> str:
			return self.get("1.0", "end").rstrip("\n")

		def set_text(self, text: str) -> None:
			self.delete(self.index("1.0"), self.index("end"))
			self.insert(self.index("1.0"), text)

		def clear_highlight(self, start="1.0", end="end", type=None) -> None:
			start = self.index(start)
			end = self.index(end)
			if type == None:
				for tag in self.tag_names(): self.tag_remove(tag, start, end)
			else: self.tag_remove(type, start, end)
		
		def override_highlight(self, type: str, start="1.0", end="end") -> None:
			self.clear_highlight(start, end)
			self.tag_add(type, self.index(start), self.index(end))

		def error(self, line: int) -> None:
			self.override_highlight("error", f"{line}.0", f"{line + 1}.0")
		
		def warning(self, line: int) -> None:
			self.override_highlight("warning", f"{line}.0", f"{line + 1}.0")

		def get_text(self) -> str: return self.get("1.0", "end")

		def set_location(self, line: int) -> None:
			self.clear_highlight(type="location_back")
			self.tag_add("location_back", self.index(f"{line}.0"), self.index(f"{line+1}.0"))
			self.see(f"{line}.0")

		def clear_location(self) -> None:
			self.clear_highlight(type="location_back")
		
		def set_hotpath(self, hotpath: "dict[int, float]") -> None:
			self.clear_hotpath()
			for line in hotpath:
				self.tag_add(f"hotpath_{floor(hotpath[line] * 255)}", self.index(f"{line}.0"), self.index(f"{line+1}.0"))
		
		def set_hotpath_line(self, line: int, amount: float) -> None:
			self.clear_hotpath(line)
			self.tag_add(f"hotpath_{floor(amount * 255)}", self.index(f"{line}.0"), self.index(f"{line+1}.0"))
		
		def clear_hotpath(self, line: int = 0) -> None:
			if line == 0:
				for level in range(256): self.clear_highlight(type=f"hotpath_{level}")
			else:
				for level in range(256): self.clear_highlight(f"{line}.0", f"{line + 1}.0", f"hotpath_{level}")

		def highlight(self) -> None:
			self.clear_highlight()

			count = tk.IntVar()
			for definition in self.definitions:
				self.mark_set("matchStart", self.index("1.0"))
				self.mark_set("matchEnd", self.index("1.0"))
				self.mark_set("searchLimit", self.index("end"))

				while True:
					index = self.search(definition.regex, "matchEnd", "searchLimit", count=count, regexp=True)
					if index == "" or count.get() == 0: break
					self.mark_set("matchStart", index)
					self.mark_set("matchEnd", f"{index}+{count.get()}c")
					for tag in self.tag_names(): self.tag_remove(tag, "matchStart", "matchEnd")
					self.tag_add(definition.type, "matchStart", "matchEnd")

	class LineNumbers(tk.Text):
		def __init__(self, *args, bind_to: tk.Text, scroll_bind: "Union[ui.MultiBinding, None]" = None, key_bind: "Union[ui.MultiBinding, None]" = None, **kwargs) -> None:
			super().__init__(*args, **kwargs)

			def get_digits(value: int) -> int: return floor(log(max(value, 1), 10)) + 1

			def on_modified() -> None:
				bind_to.update_idletasks()
				lines = int(bind_to.index("end").split(".")[0]) - 1
				if lines != self.last_line_count:
					self.configure(state="normal")
					while self.last_line_count > lines:
						self.delete(f"{self.last_line_count}.0", f"{self.last_line_count + 1}.0")
						self.last_line_count -= 1
					while self.last_line_count < lines:
						self.last_line_count += 1
						self.insert(f"{self.last_line_count}.0", ("" if self.last_line_count == 1 else "\n") + str(self.last_line_count), "right_align")
					self.configure(state="disabled", width=get_digits(self.last_line_count))
				on_scroll()
			
			def on_scroll(*args):
				self.yview_moveto(bind_to.yview()[0])

			self.last_line_count: int = 0
			self.configure(borderwidth=0, highlightthickness=0, wrap="none", cursor="arrow")
			self.tag_configure("right_align", justify="right")
			if key_bind == None: bind_to.bind("<KeyRelease>", lambda e: on_modified())
			else: key_bind.bind(lambda e: on_modified())
			if scroll_bind == None: bind_to.configure(yscrollcommand=on_scroll)
			else: scroll_bind.bind(on_scroll)
			self.set_colors(ui.CodeColors())
			on_modified()
			self.on_modified = on_modified
		
		def set_colors(self, colors: "ui.CodeColors") -> None:
			self.configure(background=colors.window_background, foreground=colors.text_disabled, font=(colors.font_name, colors.font_size))

	class LineInfo(tk.Text):
		def __init__(self, *args, bind_to: tk.Text, scroll_bind: "Union[ui.MultiBinding, None]" = None, key_bind: "Union[ui.MultiBinding, None]" = None, **kwargs) -> None:
			super().__init__(*args, **kwargs)

			self.lines: list[str] = []

			def on_modified() -> None:
				bind_to.update_idletasks()
				lines = int(bind_to.index("end").split(".")[0]) - 1
				if lines != self.last_line_count:
					self.configure(state="normal")
					while self.last_line_count > lines:
						self.delete(f"{self.last_line_count}.0", f"{self.last_line_count + 1}.0")
						self.last_line_count -= 1
					while self.last_line_count < lines:
						self.last_line_count += 1
						if len(self.lines) < self.last_line_count: self.lines.append("")
						self.insert(f"{self.last_line_count}.0", ("" if self.last_line_count == 1 else "\n") + self.lines[self.last_line_count - 1], "align")
					self.configure(state="disabled")
				on_scroll()
			
			def on_scroll(*args):
				self.yview_moveto(bind_to.yview()[0])

			self.last_line_count: int = 0
			self.configure(width=0, borderwidth=0, highlightthickness=0, wrap="none", cursor="arrow")
			self.tag_configure("align", justify="left")
			if key_bind == None: bind_to.bind("<KeyRelease>", lambda e: on_modified())
			else: key_bind.bind(lambda e: on_modified())
			if scroll_bind == None: bind_to.configure(yscrollcommand=on_scroll)
			else: scroll_bind.bind(on_scroll)
			self.set_colors(ui.CodeColors())
			on_modified()
			self.on_modified = on_modified
		
		def show(self) -> None:
			self.grid_remove()
		
		def hide(self) -> None:
			self.grid_remove()
		
		def set_alignment(self, justify: Literal["left", "center", "right"]) -> None:
			self.tag_configure("align", justify=justify)
		
		def set_line(self, line: int, value: Any) -> None:
			while len(self.lines) < line: self.lines.append("")
			self.lines[line - 1] = str(value)
		
		def set_width(self, chars: int) -> None:
			self.configure(width=chars)

		def set_colors(self, colors: "ui.CodeColors") -> None:
			self.configure(background=colors.window_background, foreground=colors.text_disabled, font=(colors.font_name, colors.font_size))

	class BreakPointButton(tk.Button):
		def __init__(self, *args, line: int = 0, on_set: Callable[[int], None] = lambda line: None, on_remove: Callable[[int], None] = lambda line: None, **kwargs) -> None:
			super().__init__(*args, **kwargs)
			self.line = line
			self.on_set = on_set
			self.on_remove = on_remove
			self.toggled = False
			self.configure(width=1, height=1, text="· ", image=ui.PIXEL, compound="c", borderwidth=0, highlightthickness=0, padx=0, pady=0, command=self.toggle, cursor="arrow")
			self.bind("<Enter>", lambda e: self.configure(background=self.colors.text_selected, foreground=self.colors.breakpoint))
			self.bind("<Leave>", lambda e: self.set_colors(self.colors))
			self.set_colors(ui.CodeColors())
		
		def toggle(self) -> None:
			self.toggled = not self.toggled
			self.set_colors(self.colors)
			self.on_set(self.line) if self.toggled else self.on_remove(self.line)

		def set_colors(self, colors: "ui.CodeColors") -> None:
			self.colors = colors
			height = tkfont.Font(font=(self.colors.font_name, self.colors.font_size)).metrics("linespace")
			self.configure(background=colors.window_background, foreground=colors.breakpoint if self.toggled else colors.window_background, activebackground=colors.text_selected, activeforeground=colors.breakpoint, font=(colors.font_name, colors.font_size), width=height, height=height)

	class BreakPoints(tk.Text):
		def __init__(self, *args, bind_to: tk.Text, scroll_bind: "Union[ui.MultiBinding, None]" = None, key_bind: "Union[ui.MultiBinding, None]" = None, on_set: Callable[[int], None] = lambda line: None, on_remove: Callable[[int], None] = lambda line: None, **kwargs) -> None:
			super().__init__(*args, **kwargs)

			self.buttons: list[ui.BreakPointButton] = []
			self.on_set = on_set
			self.on_remove = on_remove

			def on_modified() -> None:
				bind_to.update_idletasks()
				lines = int(bind_to.index("end").split(".")[0]) - 1
				if lines != self.last_line_count:
					self.configure(state="normal")
					while self.last_line_count > lines:
						self.delete(f"{self.last_line_count}.0", f"{self.last_line_count + 1}.0")
						button = self.buttons.pop()
						if button.toggled: button.toggle()
						button.destroy()
						self.last_line_count -= 1
					while self.last_line_count < lines:
						self.last_line_count += 1
						button = ui.BreakPointButton(self, line=self.last_line_count, on_set=self.on_set, on_remove=self.on_remove)
						button.set_colors(self.colors)
						self.buttons.append(button)
						self.insert(f"{self.last_line_count}.0", " " if self.last_line_count == 1 else " \n")
						self.window_create(f"{self.last_line_count}.0", window=button)
					self.configure(state="disabled")
				on_scroll()
			
			def on_scroll(*args):
				self.yview_moveto(bind_to.yview()[0])

			self.last_line_count: int = 0
			self.configure(width=1, height=0, borderwidth=0, highlightthickness=0, wrap="none", cursor="arrow")
			if key_bind == None: bind_to.bind("<KeyRelease>", lambda e: on_modified())
			else: key_bind.bind(lambda e: on_modified())
			if scroll_bind == None: bind_to.configure(yscrollcommand=on_scroll)
			else: scroll_bind.bind(on_scroll)
			self.set_colors(ui.CodeColors())
			on_modified()
			self.on_modified = on_modified
		
		def show(self) -> None:
			self.grid_remove()
		
		def hide(self) -> None:
			self.grid_remove()

		def set_colors(self, colors: "ui.CodeColors") -> None:
			self.colors = colors
			self.configure(background=colors.window_background, foreground=colors.text_disabled, font=(colors.font_name, colors.font_size))
			for button in self.buttons: button.set_colors(colors)

	class ConsoleText(tk.Text):
		def __init__(self, *args, **kwargs):
			super().__init__(*args, **kwargs)
			self.configure(font=("Consolas", 11), foreground="white", background="black", insertbackground="black")
			self.buffer: str = ""
			self.input_bind = ui.MultiBinding()
			self.clear()
		
		def clear(self) -> None:
			self.configure(state="normal")
			self.delete("1.0", "end")
			self.configure(state="disabled")

		def append_buffer(self, text: str) -> None:
			self.buffer += text
			self.input_bind.event()
		
		def read(self) -> str:
			result = self.buffer
			self.buffer = ""
			return result

		def write(self, text: str) -> None:
			self.configure(state="normal")
			self.insert("end", text)
			self.configure(state="disabled")

	class ConsoleInput(tk.Entry):
		def __init__(self, output: "ui.ConsoleText", *args, **kwargs):
			super().__init__(*args, **kwargs)
			self.output = output
			self.configure(font=("Consolas", 11), foreground="white", background="black", insertbackground="white")
			self.bind("<Key>", lambda e: self.input_text() if e.char == '\n' or e.char == '\r' else None)
		
		def input_text(self) -> None:
			text = self.get()
			if len(text) > 0: self.delete(0, "end")
			self.output.append_buffer(text + "\n")

	class ActionBar(tk.Frame):
		def __init__(self, *args, **kwargs):
			super().__init__(*args, **kwargs)
			self.grid_rowconfigure(0, weight=1)
			self.actions: dict[int, tk.Button] = {}
			self.back_color: Union[str, None] = None
			self.select_color: str = "#0000FF"
			self._next_id: int = 0
		
		def set_colors(self, colors: "ui.CodeColors") -> None:
			self.back_color = colors.window_background
			self.select_color = colors.text_selected
			self.configure(background=self.back_color)
			for id in self.actions: self.actions[id].configure(background=self.back_color, activebackground=self.select_color)

		def add_action(self, name: str, callback: Callable[[], None], color: str = "#000000", font: Union[str, None] = None) -> int:
			button = tk.Button(self, text=name, command=callback, foreground=color, activeforeground=color, border=0)
			if font != None: button.configure(font=(font))
			if self.back_color != None: button.configure(background=self.back_color, activebackground=self.select_color)
			button.bind("<Enter>", lambda e: button.configure(background=self.select_color))
			button.bind("<Leave>", lambda e: button.configure(background=self.back_color))
			button.grid(row=0, column=len(self.children) - 1)
			id = self._next_id
			self._next_id += 1
			self.actions[id] = button
			return id

		def enable_action(self, id: int) -> None:
			if id >= 0: self.actions[id].grid()

		def disable_action(self, id: int) -> None:
			if id >= 0: self.actions[id].grid_remove()

	class Tabs(tk.Frame):
		def __init__(self, *args, resize_row: bool = False, resize_column: bool = False, **kwargs):
			super().__init__(*args, **kwargs)
			self.grid_columnconfigure(0, weight=1)
			self.grid_rowconfigure(1, weight=1)
			self.resize_row = resize_row
			self.resize_column = resize_column
			self.collapse_button: Union[tk.Button, None] = None
			self.tab_bar = tk.Frame(self)
			self.tab_bar.grid(row=0, column=0, sticky="WE")
			self.tab_widgets: list[Union[tk.Widget, None]] = []
			self.tab_buttons: list[tk.Button] = []
			self.tab_events: list[Callable[[], None]] = []
			self.set_colors(ui.CodeColors())
		
		def set_colors(self, colors: "ui.CodeColors") -> None:
			self.colors = colors
			self.configure(background=colors.window_background)
			self.tab_bar.configure(background=colors.window_background)
			for button in self.tab_buttons + ([self.collapse_button] if self.collapse_button != None else []):
				button.configure(background=colors.window_background, foreground=colors.text_disabled, disabledforeground=colors.text, activeforeground=colors.text, activebackground=colors.text_selected)

		def add_collapse_button(self, select: bool = False, on_selected: Callable[[], None] = lambda: None) -> None: self.add(None, "-", select=select, on_selected=on_selected)

		def add(self, widget: Union[tk.Widget, None], text: str = "", select: bool = False, on_selected: Callable[[], None] = lambda: None) -> None:
			index = len(self.tab_widgets)
			button = tk.Button(self.tab_bar, text=text, command=lambda: self.select_tab(index), borderwidth=0)
			button.configure(background=self.colors.window_background, foreground=self.colors.text_disabled, disabledforeground=self.colors.text, activeforeground=self.colors.text, activebackground=self.colors.text_selected)
			button.bind("<Enter>", lambda e: button.configure(background=self.colors.text_selected))
			button.bind("<Leave>", lambda e: button.configure(background=self.colors.window_background))
			button.grid(row=0, column=index)
			self.tab_buttons.append(button)
			self.tab_events.append(on_selected)
			if widget != None:
				widget.grid(row=1, column=0, sticky="NSEW")
				widget.grid_remove()
			self.tab_widgets.append(widget)
			if select: self.select_tab(index)
		
		def select_tab(self, index: int) -> None:
			for tab in self.tab_widgets:
				if tab != None: tab.grid_remove()
			for button in self.tab_buttons: button.configure(state="normal")
			info = self.grid_info()
			row = info.get("row")
			column = info.get("column")
			weight = 0
			if index >= 0:
				tab = self.tab_widgets[index]
				if tab != None:
					tab.grid()
					weight = 1
				self.tab_buttons[index].configure(state="disabled")
				self.tab_events[index]()
			if self.resize_row: self.master.grid_rowconfigure(row, weight=weight)
			if self.resize_column: self.master.grid_columnconfigure(column, weight=weight)

	class ScrollView(tk.Frame):
		def __init__(self, *args, **kwargs):
			super().__init__(*args, **kwargs)
			self.vscroll = tk.Scrollbar(self, orient="vertical")
			self.vscroll.pack(fill="y", side="right", expand=False)
			self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, yscrollcommand=self.vscroll.set)
			self.canvas.pack(fill="both", side="left", expand=True)
			self.vscroll.configure(command=self.canvas.yview)
			self.canvas.xview_moveto(0)
			self.canvas.yview_moveto(0)
			self.scroll_root = tk.Frame(self.canvas)
			scroll_root_id = self.canvas.create_window(0, 0, window=self.scroll_root, anchor="nw")

			def _resize_scroll_root():
				width = self.scroll_root.winfo_reqwidth()
				self.canvas.configure(scrollregion=f"0 0 {width} {self.scroll_root.winfo_reqheight()}")
				if width != self.canvas.winfo_width(): self.canvas.config(width=width)

			def _resize_canvas():
				if self.scroll_root.winfo_reqwidth() != self.canvas.winfo_width():
					self.canvas.itemconfigure(scroll_root_id, width=self.canvas.winfo_width())

			self.scroll_root.bind('<Configure>', lambda e: _resize_scroll_root())
			self.canvas.bind('<Configure>', lambda e: _resize_canvas())

	class HighlightLabel(tk.Label):
		def __init__(self, *args, type: str = "text", **kwargs) -> None:
			super().__init__(*args, **kwargs)
			self.type = type
		
		def set_colors(self, colors: "ui.CodeColors") -> None:
			self.configure(foreground=colors.get_color(self.type), background=colors.window_background)

	class VariableList(ScrollView):
		def __init__(self, *args, **kwargs):
			super().__init__(*args, **kwargs)
			self.widgets: list[tk.Frame] = []
			self.labels: list[ui.HighlightLabel] = []
			self.scroll_root.grid_columnconfigure(0, weight=1)
			self.scroll_root.grid_columnconfigure(1, weight=1)
			self.set_colors(ui.CodeColors())
		
		def set_colors(self, colors: "ui.CodeColors") -> None:
			self.colors = colors
			self.configure(background=colors.window_background)
			self.canvas.configure(background=colors.window_background)
			self.scroll_root.configure(background=colors.window_background)
			for widget in self.widgets: widget.configure(background=colors.window_background)
			for label in self.labels: label.set_colors(colors)
		
		def clear_variables(self) -> None:
			for widget in self.widgets: widget.destroy()
			self.widgets.clear()
			for label in self.labels: label.destroy()
			self.labels.clear()

		def set_variables(self, variables: "dict[str, Any]", int_format: Callable[[int], Tuple[str, str]] = lambda value: (str(value), "number"), float_format: Callable[[float], Tuple[str, str]] = lambda value: (str(value), "number"), string_format: Callable[[str], Tuple[str, str]] = lambda value: ("\"" + value.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t").replace("\"", "\\\"") + "\"", "string"), object_format: Callable[[Any], Tuple[str, str]] = lambda value: (str(value), "text_disabled")) -> None:
			self.clear_variables()
			index = 0
			for name in variables:
				rawValue = variables[name]
				value_string: str
				value_type: str
				if isinstance(rawValue, int): value_string, value_type = int_format(rawValue)
				elif isinstance(rawValue, float): value_string, value_type = float_format(rawValue)
				elif isinstance(rawValue, str): value_string, value_type = string_format(rawValue)
				else: value_string, value_type = object_format(rawValue)
				pair = tk.Frame(self.scroll_root)
				pair.grid_columnconfigure(1, weight=1)
				key = ui.HighlightLabel(pair, text=name, type="text")
				key.grid(row=0, column=0)
				self.labels.append(key)
				value = ui.HighlightLabel(pair, text=value_string, type=value_type, anchor=("e" if value_type == "number" else "w"))
				value.grid(row=0, column=1, sticky="WE")
				self.labels.append(value)
				pair.grid(row=(index >> 1), column=(index & 1), sticky="WE")
				self.widgets.append(pair)
				index += 1
			self.set_colors(self.colors)

	class StackList(ScrollView):
		def __init__(self, *args, **kwargs):
			super().__init__(*args, **kwargs)
			self.widgets: list[tk.Frame] = []
			self.labels: list[ui.HighlightLabel] = []
			self.scroll_root.grid_columnconfigure(0, weight=1)
			self.set_colors(ui.CodeColors())
		
		def set_colors(self, colors: "ui.CodeColors") -> None:
			self.colors = colors
			self.configure(background=colors.window_background)
			self.canvas.configure(background=colors.window_background)
			self.scroll_root.configure(background=colors.window_background)
			for widget in self.widgets: widget.configure(background=colors.window_background)
			for label in self.labels: label.set_colors(colors)
		
		def clear_stack(self) -> None:
			for widget in self.widgets: widget.destroy()
			self.widgets.clear()
			for label in self.labels: label.destroy()
			self.labels.clear()

		def set_stack(self, stack: "list[Tuple[int, Union[str, None]]]", address_format: Callable[[int], str] = lambda value: str(value), value_format: Callable[[Union[int, None]], str] = lambda value: str(value)) -> None:
			self.clear_stack()
			index = 0
			for address, value in stack:
				pair = tk.Frame(self.scroll_root)
				pair.grid_columnconfigure(1, weight=1)
				key = ui.HighlightLabel(pair, text=address_format(address), type="number", anchor="w")
				key.grid(row=0, column=0)
				self.labels.append(key)
				value = ui.HighlightLabel(pair, text=value_format(value), type="number", anchor="w")
				value.grid(row=0, column=1, sticky="WE")
				self.labels.append(value)
				pair.grid(row=index, column=0, sticky="WE")
				self.widgets.append(pair)
				index += 1
			self.set_colors(self.colors)

	class CallList(ScrollView):
		def __init__(self, *args, **kwargs):
			super().__init__(*args, **kwargs)
			self.widgets: list[tk.Frame] = []
			self.labels: list[ui.HighlightLabel] = []
			self.scroll_root.grid_columnconfigure(0, weight=1)
			self.set_colors(ui.CodeColors())
		
		def set_colors(self, colors: "ui.CodeColors") -> None:
			self.colors = colors
			self.configure(background=colors.window_background)
			self.canvas.configure(background=colors.window_background)
			self.scroll_root.configure(background=colors.window_background)
			for widget in self.widgets: widget.configure(background=colors.window_background)
			for label in self.labels: label.set_colors(colors)
		
		def clear_calls(self) -> None:
			for widget in self.widgets: widget.destroy()
			self.widgets.clear()
			for label in self.labels: label.destroy()
			self.labels.clear()

		def set_calls(self, calls: "list[Tuple[int, Union[str, None]]]", address_format: Callable[[int], str] = lambda value: str(value), name_format: Callable[[Union[str, None]], str] = lambda value: value) -> None:
			self.clear_calls()
			index = 0
			for address, name in calls:
				pair = tk.Frame(self.scroll_root)
				pair.grid_columnconfigure(1, weight=1)
				key = ui.HighlightLabel(pair, text=address_format(address), type="number", anchor="w")
				key.grid(row=0, column=0)
				self.labels.append(key)
				value = ui.HighlightLabel(pair, text=name_format(name), type="function", anchor="w")
				value.grid(row=0, column=1, sticky="WE")
				self.labels.append(value)
				pair.grid(row=index, column=0, sticky="WE")
				self.widgets.append(pair)
				index += 1
			self.set_colors(self.colors)

	class HexEntry(tk.Entry):
		def __init__(self, *args, **kwargs) -> None:
			super().__init__(*args, borderwidth=0, **kwargs)
			self.configure(validate="key", validatecommand=(self.register(self.on_validate), "%s"))
		
		def set_colors(self, colors: "ui.CodeColors") -> None:
			self.configure(background=colors.background, foreground=colors.text, insertbackground=colors.caret, selectbackground=colors.text_selected)
		
		def on_validate(self, value: str) -> bool:
			for c in value:
				if not c in "0123456789ABCDEFabcdef":
					self.bell()
					return False
			return True

	class MemoryList(ScrollView):
		def __init__(self, *args, **kwargs):
			super().__init__(*args, **kwargs)
			self.address_label = tk.Label(self.scroll_root, text="Address: 0x")
			self.address_label.grid(row=0, column=0)
			self.address_entry = ui.HexEntry(self.scroll_root)
			self.address_entry.bind("<Return>", lambda e: self.clear_memory() if len(self.address_entry.get()) == 0 else self.set_memory(int(self.address_entry.get(), 16)))
			self.address_entry.grid(row=0, column=1, sticky="WE")
			self.widgets: list[tk.Frame] = []
			self.labels: list[ui.HighlightLabel] = []
			self.scroll_root.grid_columnconfigure(1, weight=1)
			self.request_callback: Union[Callable[[int], int], None] = None
			self.last_address: Union[int, None] = None
			self.last_count: int = 20
			self.set_colors(ui.CodeColors())
		
		def set_colors(self, colors: "ui.CodeColors") -> None:
			self.colors = colors
			self.configure(background=colors.window_background)
			self.canvas.configure(background=colors.window_background)
			self.scroll_root.configure(background=colors.window_background)
			self.address_label.configure(background=colors.window_background, foreground=colors.text)
			self.address_entry.set_colors(colors)
			for widget in self.widgets: widget.configure(background=colors.window_background)
			for label in self.labels: label.set_colors(colors)
		
		def set_request_callback(self, callback: Callable[[int], int]) -> None:
			self.request_callback = callback

		def clear_memory(self) -> None:
			self.last_address = None
			for widget in self.widgets: widget.destroy()
			self.widgets.clear()
			for label in self.labels: label.destroy()
			self.labels.clear()
		
		def set_address_format(self, address_format: Callable[[int], str] = lambda value: str(value)) -> None:
			self.address_format = address_format
		
		def set_value_format(self, value_format: Callable[[int], str] = lambda value: str(value)) -> None:
			self.value_format = value_format
		
		def refresh_memory(self) -> None:
			if self.last_address == None: self.clear_memory()
			else: self.set_memory(self.last_address, self.last_count)

		def set_memory(self, start_address: int, count: int = 20) -> None:
			self.clear_memory()
			self.last_address = start_address
			self.last_count = count
			if self.request_callback == None: return
			for address in range(start_address, start_address + count, 1):
				pair = tk.Frame(self.scroll_root)
				pair.grid_columnconfigure(1, weight=1)
				key = ui.HighlightLabel(pair, text=self.address_format(address), type="number", anchor="e")
				key.grid(row=0, column=0)
				self.labels.append(key)
				value = ui.HighlightLabel(pair, text=self.value_format(self.request_callback(address)), type="number", anchor="e")
				value.grid(row=0, column=1, sticky="WE")
				self.labels.append(value)
				pair.grid(row=(address - start_address) + 1, column=0, columnspan=2, sticky="WE")
				self.widgets.append(pair)
			self.set_colors(self.colors)

	class PerformanceList(ScrollView):
		def __init__(self, *args, **kwargs):
			super().__init__(*args, **kwargs)
			self.buttons: list[ui.HighlightLabel] = []
			self.scroll_root.grid_columnconfigure(0, weight=1)
			self.show_callback: Callable[[str], None] = lambda name: None
			self.set_colors(ui.CodeColors())
		
		def set_colors(self, colors: "ui.CodeColors") -> None:
			self.colors = colors
			self.configure(background=colors.window_background)
			self.canvas.configure(background=colors.window_background)
			self.scroll_root.configure(background=colors.window_background)
			for button in self.buttons: button.configure(background=colors.window_background, foreground=colors.function, activebackground=colors.text_selected, activeforeground=colors.function)
		
		def set_show_callback(self, callback: Callable[[str], None]) -> None:
			self.show_callback = callback

		def clear_functions(self) -> None:
			for button in self.buttons: button.destroy()
			self.buttons.clear()

		def set_functions(self, functions: "list[str]", name_format: Callable[[Union[str, None]], str] = lambda value: value) -> None:
			self.clear_functions()
			index = 0
			for name in functions:
				button = tk.Button(self.scroll_root, text=name_format(name), borderwidth=0)
				button.grid_columnconfigure(1, weight=1)
				def bind_button(self: "ui.PerformanceList", name: str, button: tk.Button):
					button.configure(command=lambda: self.show_callback(name))
					button.bind("<Enter>", lambda e: button.configure(background=self.colors.text_selected))
					button.bind("<Leave>", lambda e: button.configure(background=self.colors.window_background))
				bind_button(self, name, button)
				button.grid(row=index, column=0, sticky="WE")
				self.buttons.append(button)
				index += 1
			self.set_colors(self.colors)

	@staticmethod
	def set_colors(colors: CodeColors) -> None:
		ui.window.configure(background=colors.window_background)
		ui.action_bar.set_colors(colors)
		ui.editor_area.configure(background=colors.window_background)
		ui.break_points.set_colors(colors)
		ui.line_numbers.set_colors(colors)
		ui.line_info.set_colors(colors)
		ui.text_editor.set_colors(colors)
		ui.lower_tabs.set_colors(colors)
		ui.variables_tab.set_colors(colors)
		ui.stack_tab.set_colors(colors)
		ui.calls_tab.set_colors(colors)
		ui.memory_tab.set_colors(colors)
		ui.performance_tab.set_colors(colors)

	_busy_waits: "dict[int, Callable[[], None]]" = {}
	_next_busy_id = 0

	@staticmethod
	def check_busy_waits() -> None:
		for id in list(ui._busy_waits.keys()):
			try: ui._busy_waits.get(id, lambda: None)()
			except: pass
		ui.window.after(100, ui.check_busy_waits)

	@staticmethod
	def bind_busy_wait(condition: Callable[[], bool], callback: Callable[[], None]) -> int:
		id = ui._next_busy_id
		ui._next_busy_id += 1
		ui._busy_waits[id] = lambda: callback() if condition() else None
		return id

	@staticmethod
	def unbind_busy_wait(id: int) -> None:
		if id >= 0: ui._busy_waits.pop(id)

	@staticmethod
	def show_ui() -> None:
		ui.window.deiconify()
		ui.window.mainloop()
	
	@staticmethod
	def update_ui() -> None:
		ui.text_editor.highlight()
		ui.break_points.on_modified()
		ui.line_numbers.on_modified()
		ui.line_info.on_modified()

	window: tk.Tk
	action_bar: ActionBar
	editor_area: tk.Frame
	text_editor_scroll_bind: MultiBinding
	text_editor_key_bind: MultiBinding
	text_editor: HighlightText
	breakpoint_added_bind: MultiBinding
	breakpoint_removed_bind: MultiBinding
	break_points: BreakPoints
	line_numbers: LineNumbers
	line_info: LineInfo
	lower_tabs: Tabs
	console_tab: tk.Frame
	console: ConsoleText
	console_input: ConsoleInput
	variables_tab: VariableList
	stack_tab: StackList
	calls_tab: CallList
	memory_tab: MemoryList
	performance_tab: PerformanceList
	
	@staticmethod
	def initialize() -> None:
		ui.window = tk.Tk()
		ui.window.withdraw()
		ui.window.geometry("640x480")
		ui.window.bind("<Configure>", lambda e: ui.action_bar.configure(background=ui.window["background"]))
		ui.window.grid_columnconfigure(0, weight=1)
		ui.window.grid_rowconfigure(1, weight=1)
		ui.window.grid_rowconfigure(2, weight=1)

		ui.PIXEL = tk.PhotoImage(width=1, height=1)

		ui.action_bar = ui.ActionBar(ui.window)
		ui.action_bar.grid(row=0, column=0, sticky="WE")

		ui.editor_area = tk.Frame(ui.window)
		ui.editor_area.grid(row=1, column=0, sticky="NSEW")
		ui.editor_area.grid_columnconfigure(3, weight=1)
		ui.editor_area.grid_rowconfigure(0, weight=1)

		ui.text_editor_scroll_bind = ui.MultiBinding()
		ui.text_editor_key_bind = ui.MultiBinding()

		ui.text_editor = ui.HighlightText(ui.editor_area, yscrollcommand=ui.text_editor_scroll_bind.event)
		ui.text_editor.bind("<KeyRelease>", ui.text_editor_key_bind.event)
		ui.text_editor.grid(row=0, column=3, sticky="NSEW")

		ui.breakpoint_added_bind = ui.MultiBinding()
		ui.breakpoint_removed_bind = ui.MultiBinding()

		ui.break_points = ui.BreakPoints(ui.editor_area, bind_to=ui.text_editor, scroll_bind=ui.text_editor_scroll_bind, key_bind=ui.text_editor_key_bind, on_set=ui.breakpoint_added_bind.event, on_remove=ui.breakpoint_removed_bind.event)
		ui.break_points.grid(row=0, column=0, sticky="NS")

		ui.line_numbers = ui.LineNumbers(ui.editor_area, bind_to=ui.text_editor, scroll_bind=ui.text_editor_scroll_bind, key_bind=ui.text_editor_key_bind)
		ui.line_numbers.grid(row=0, column=1, sticky="NS")

		ui.line_info = ui.LineInfo(ui.editor_area, bind_to=ui.text_editor, scroll_bind=ui.text_editor_scroll_bind, key_bind=ui.text_editor_key_bind)
		ui.line_info.grid(row=0, column=2, sticky="NS")
		ui.line_info.hide()

		ui.lower_tabs = ui.Tabs(ui.window, resize_row=True)
		ui.lower_tabs.grid(row=2, column=0, sticky="WE")

		ui.console_tab = tk.Frame(ui.lower_tabs, borderwidth=0)
		ui.console_tab.grid_columnconfigure(0, weight=1)
		ui.console_tab.grid_rowconfigure(0, weight=1)

		ui.console = ui.ConsoleText(ui.console_tab)
		ui.console.grid(row=0, column=0, sticky="WE")

		ui.console_input = ui.ConsoleInput(ui.console, ui.console_tab)
		ui.console_input.grid(row=1, column=0, sticky="WE")

		ui.variables_tab = ui.VariableList(ui.lower_tabs)
		ui.stack_tab = ui.StackList(ui.lower_tabs)
		ui.calls_tab = ui.CallList(ui.lower_tabs)
		ui.memory_tab = ui.MemoryList(ui.lower_tabs)
		ui.performance_tab = ui.PerformanceList(ui.lower_tabs)

		ui.lower_tabs.add_collapse_button(True, on_selected=lambda: ui.text_editor.clear_hotpath())
		ui.lower_tabs.add(ui.console_tab, text="Console")
		ui.lower_tabs.add(ui.variables_tab, "Variables")
		ui.lower_tabs.add(ui.stack_tab, "Stack")
		ui.lower_tabs.add(ui.calls_tab, "Calls")
		ui.lower_tabs.add(ui.memory_tab, "Memory")
		ui.lower_tabs.add(ui.performance_tab, "Performance")

		ui.set_colors(ui.CodeColors())

		ui.window.after(100, ui.check_busy_waits)