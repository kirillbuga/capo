import sublime, sublime_plugin, re, os, functools, threading

def do_when(conditional, callback, *args, **kwargs):
	if conditional():
		return callback(*args, **kwargs)
	sublime.set_timeout(functools.partial(do_when, conditional, callback, *args, **kwargs), 50)

class SearchResult(object):
	def __init__(self):
		self.pathes = []
		self.readable = []

class SearchCall(threading.Thread):
	def __init__(self, word_for_search, proj_folders):
		self.text = word_for_search
		self.proj_folders = proj_folders
		self.result = None
		self.nothing = False
		threading.Thread.__init__(self)

	def run(self):
		result = SearchResult()
		for dir in self.proj_folders:
			files = None
			for dir_path, subdir, files in os.walk(dir):
				for file_name in files:
					file_path = os.path.join(dir_path, file_name)
					file = open(file_path, "r")
					lines = file.readlines()					
					for n, line in enumerate(lines):
						if self.text in line:
							result.pathes.append([file_path, n])
							result.readable.append(file_name + ' @' + str(n + 1))
					file.close()
		if not len(result.pathes):
			self.nothing = True

		self.result = result;
		return self.result

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
			sublime.status_message('Can\'t find nothing in current line.')
			return

		#get folders to search
		window = sublime.active_window()
		proj_folders = window.folders()
		word_for_search = str(word.group(2))

		print "[Capo] Searching for " + word_for_search + "..."

		thread = SearchCall(word_for_search, proj_folders)
		thread.start()
		self.handle_threads(thread, window, view)

	def handle_threads(self, thread, window, view):
		if thread.is_alive():
			view.set_status('Capo', 'Searching...')
			sublime.set_timeout(lambda: self.handle_threads(thread, window, view), 100)
			return
		if thread.nothing == True:
			sublime.status_message('No subscribers was found')
			view.erase_status('Capo')
			return

		view.erase_status('Capo')
		window.show_quick_panel(thread.result.readable, lambda i: self.on_click(i, thread.result.pathes))

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
