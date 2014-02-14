import sublime, sublime_plugin, re, os, functools, threading

def do_when(conditional, callback, *args, **kwargs):
	if conditional():
		return callback(*args, **kwargs)
	sublime.set_timeout(functools.partial(do_when, conditional, callback, *args, **kwargs), 50)

class SearchCall(threading.Thread):
	def __init__(self, word_for_search, proj_folders, excludedDirs, fileExcludePattern, mediators, methods):
		self.text = word_for_search
		self.proj_folders = proj_folders
		self.result = None
		self.nothing = False
		self.dir_exclude = excludedDirs
		self.file_exclude = fileExcludePattern		
		self.mediators = mediators
		self.methods = methods
		threading.Thread.__init__(self)

	def isNotExcludedDir(self, dir):
		for exclude in self.dir_exclude:
			if exclude in dir:
				return False
		return True

	def isNotExludedFile(self, filename):
		if not self.file_exclude:
			return True
		if re.match(self.file_exclude, filename):
			return False
		return True	

	def run(self):
		result = []
		for dir in self.proj_folders:			
			files = None
			for dir_path, subdir, files in os.walk(dir):
				#check for dir in exclude dirs
				if self.isNotExcludedDir(dir_path):
					for file_name in files:
						#check for file extension exclusion
						if self.isNotExludedFile(file_name):
							file_path = os.path.join(dir_path, file_name)
							file = open(file_path, "r")
							lines = file.readlines()					
							for n, line in enumerate(lines):
								if self.text in line:
									method = re.search('%s.%s\\((\'|\")(%s)(\'|\")' % (self.mediators, self.methods, self.text), line)
									if method:
										result.append([file_path, file_name, n, method.group(2)])
							file.close()
		if not len(result):
			self.nothing = True

		self.result = result;
		return self.result

class CapoCommand(sublime_plugin.TextCommand):
	def __init__(self, args):
		super(CapoCommand, self).__init__(args)

	def run(self, edit):
		regions = []
		view = self.view
		s = view.sel()[0]		
		region = sublime.Region(s.begin(), s.end())
		line = view.line(region) #return the line which contains region
		content = view.substr(line) #return content of region
		settings = sublime.load_settings("capo.sublime-settings")
		mediators = self.joinListToPattern(settings.get("mediators"))
		methods = self.joinListToPattern(settings.get("methods"))
		word = re.search('%s.%s\\((\'|\")(.*)(\'|\")' % (mediators, methods), content)
		if word == None:
			sublime.status_message('Can\'t find nothing in current line.')
			return

		#get folders to search
		window = sublime.active_window()
		proj_folders = window.folders()
		word_for_search = str(word.group(4))
		print(word_for_search)

		print "[Capo] Searching for " + word_for_search + "..."		
		
		dir_exclude = view.settings().get("folder_exclude_patterns", ['.git', '.svn'])
		file_exclude = self.getFileExcludePattern(view)

		thread = SearchCall(word_for_search, proj_folders, dir_exclude, file_exclude, mediators, methods)
		thread.start()
		self.handle_thread(thread, window, view)

	def handle_thread(self, thread, window, view):
		if thread.is_alive():
			view.set_status('Capo', 'Searching...')
			sublime.set_timeout(lambda: self.handle_thread(thread, window, view), 100)
			return
		if thread.nothing == True:
			sublime.status_message('No subscribers were found')
			view.erase_status('Capo')
			return

		view.erase_status('Capo')
		self.showQuickPanel(thread.result, window)

	def showQuickPanel(self, result, window):

		items = []		
		result.sort(key=lambda i: i[3])

		for item in result:
			path = item[0]
			file_name = item[1]
			line = item[2]
			method = item[3]
			items.append([method + ': ' + file_name + ' @' + str(line)])

		window.show_quick_panel(items, lambda i: self.on_click(i, result))

	def getFileExcludePattern(self, view):
		excludedFiles = view.settings().get("file_exclude_patterns", ['*.exe', '*.obj', '*.dll'])
		if not excludedFiles:
			return None

		patterns = []
		for pattern in excludedFiles:
			pattern = re.sub('\*\.', '.', pattern)
			pattern = re.escape(str(pattern))
			patterns.append(pattern)

		return self.joinListToPattern(patterns)	 

	def joinListToPattern(self, list):
		return "(" + "|".join(list) + ")"	

	#jump to file and set cursor to the given line
	def jumpToFile(self, view, line):
		point = view.text_point(line, 0)
		nav_point = view.text_point(line - 10, 0)
		vector = view.text_to_layout(nav_point)
		view.set_viewport_position(vector)

		view.sel().clear()
		view.sel().add(sublime.Region(point))
		view.show(point)

	def on_click(self, index, result):
		if index != -1:
			item = result[index]
			file = item[0]
			line = item[2]
			print "[Capo] Opening file " + file + " to line " + str(line)
			window = sublime.active_window()
			new_file = window.open_file(file)

			do_when(
				lambda: not new_file.is_loading(),
				lambda: self.jumpToFile(new_file, line)
			)
