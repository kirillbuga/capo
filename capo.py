import sublime, sublime_plugin, re, os, functools

def do_when(conditional, callback, *args, **kwargs):
	if conditional():
		return callback(*args, **kwargs)
	sublime.set_timeout(functools.partial(do_when, conditional, callback, *args, **kwargs), 50)

class CapoCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		regions = []
		view = self.view
		s = view.sel()[0]

		region = sublime.Region(s.begin(), s.end())
		line = view.line(region) #return the line which contains region
		content = view.substr(line) #return content of region
		word = re.search('mediator.publish\\((\'|\")(.*)(\'|\")', content)
		if word == None:
			return

		#get folders to search
		window = sublime.active_window()
		proj_folders = window.folders()

		print "[Capo] Searching for " + word.group(2) + "..."
		result = []
		pathes = []
		for dir in proj_folders:
			files = None
			for dir_path, subdir, files in os.walk(dir):
				for file_name in files:
					file_path = os.path.join(dir_path, file_name)
					file = open(file_path, "r")
					lines = file.readlines()
					word_for_search = str(word.group(2))
					for n, line in enumerate(lines):
						if word_for_search in line:
							result.append([file_path, n])
							pathes.append(file_name + ' @' + str(n + 1))
					file.close()

		window.show_quick_panel(pathes, lambda i: self.on_click(i, result))
		print(result)

	#jump to file and set cursor to the given line
	def jumpToFile(self, view, line):
		point = view.text_point(line, 0)
		nav_point = view.text_point(line - 10, 0)
		vector = view.text_to_layout(nav_point)
		view.set_viewport_position(vector)

		view.sel().add(sublime.Region(point))
		view.show(point)


	def on_click(self, index, results):
		if index != -1:
			item = results[index]
			file = item[0]
			line = item[1]
			print "[Capo] Opening file " + file + " to line " + str(line)
			window = sublime.active_window()
			new_file = window.open_file(file)

			do_when(
				lambda: not new_file.is_loading(),
				lambda: self.jumpToFile(new_file, line)
			)

#Backbone.trigger('namespace:method')
#nothinghere('namespace3:method3')
#mediator.publish('game:turn-local')
#mediator.publish("namespace4:method4")
#mediator.publish("namespace5:method5", function() {})
