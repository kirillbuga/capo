import sublime, sublime_plugin, re, os, functools, threading

def do_when(conditional, callback, *args, **kwargs):
	if conditional():
		return callback(*args, **kwargs)
	sublime.set_timeout(functools.partial(do_when, conditional, callback, *args, **kwargs), 50)

class SearchCall(threading.Thread):
	def __init__(self, args):
		self.pattern = args["pattern"]
		self.proj_folders = args["proj_folders"]
		self.result = None
		self.nothing = False
		self.dir_exclude = args["excludedDirs"]
		self.file_exclude = args["fileExcludePattern"]		
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
								method = re.search(self.pattern, line)
								if method:
									result.append({"path" : file_path, "name" : file_name, "line" : n, "method" : method.group(2)})
							file.close()
		if not len(result):
			self.nothing = True

		self.result = result;
		return self.result

class CapoCommand(sublime_plugin.TextCommand):
	def __init__(self, args):
		super(CapoCommand, self).__init__(args)
		# retrieve settings
		self.settings = sublime.load_settings("capo.sublime-settings")
		self.mediators = self.joinListToPattern(self.settings.get("mediators"))
		self.methods = self.joinListToPattern(self.settings.get("methods"))
		self.searchPattern = '%s.%s\\((\'|\")(%s)(\'|\")' % (self.mediators, self.methods, '$WORD_FOR_SEARCH$')

		#get folders to search
		self.window = sublime.active_window()
		self.proj_folders = self.window.folders()
		# thread = SearchCall({"pattern" : self.searchPattern,
		# 					 "proj_folders" : self.proj_folders, 
		# 					 "excludedDirs" : [],
		# 					 "fileExcludePattern" : ''})
		# thread.start()

	def run(self, edit):
		regions = []
		view = self.view
		s = view.sel()[0]		
		region = sublime.Region(s.begin(), s.end())
		line = view.line(region) #return the line which contains region
		content = view.substr(line) #return content of region

		word = re.search('%s.%s\\((\'|\")((\w|-|:)*)(\'|\")' % (self.mediators, self.methods), content)
		if word == None:
			sublime.status_message('Can\'t find nothing in current line.')
			return

		word_for_search = str(word.group(4))

		print "[Capo] Searching for " + word_for_search + "..."		
		
		dir_exclude = view.settings().get("folder_exclude_patterns", ['.git', '.svn'])
		file_exclude = self.getFileExcludePattern(view)

		searchPattern = self.searchPattern.replace('$WORD_FOR_SEARCH$', word_for_search)

		thread = SearchCall({"pattern" : searchPattern,
							"proj_folders" : self.proj_folders, 
							"excludedDirs" : dir_exclude,
							"fileExcludePattern" : file_exclude})

		thread.start()
		self.handle_thread(thread, self.window, view)

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
		result.sort(key=lambda i: i["method"])

		for item in result:
			items.append([item['method'] + ': ' + item['name'] + ' @' + str(item['line'])])

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
			file = item['path']
			line = item['line']
			print "[Capo] Opening file " + file + " to line " + str(line)
			window = sublime.active_window()
			new_file = window.open_file(file)

			do_when(
				lambda: not new_file.is_loading(),
				lambda: self.jumpToFile(new_file, line)
			)
