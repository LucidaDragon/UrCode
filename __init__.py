import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import editor.base

def run():
	if len(sys.argv) > 1:
		for file in sys.argv[1:]: editor.base.open_file(file)
	editor.base.show_ui()

if __name__ == "__main__": run()