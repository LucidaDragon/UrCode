import os

_loaded_fonts: "list[str]" = []

def load_font(path: str) -> bool:
	if path in _loaded_fonts: return True
	if not os.path.exists(path): return False

	fonts_loaded: int = 0
	if os.name == "nt":
		from ctypes import windll, byref, create_unicode_buffer
		fonts_loaded = int(windll.gdi32.AddFontResourceExW(byref(create_unicode_buffer(path)), 0x10, 0))
		if fonts_loaded > 0: _loaded_fonts.append(path)
		
	return fonts_loaded > 0