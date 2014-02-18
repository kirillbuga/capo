import sublime, sublime_plugin, re, os, functools, threading

def do_when(conditional, callback, *args, **kwargs):
	if conditional():
		return callback(*args, **kwargs)
	sublime.set_timeout(functools.partial(do_when, conditional, callback, *args, **kwargs), 50)

class CacheCall(threading.Thread):
	def __init__(self, args):
		self.proj_folders = args["proj_folders"]
		self.dir_exclude = args["excludedDirs"]
		threading.Thread.__init__(self)

	def isNotExcludedDir(self, dir):
		for exclude in self.dir_exclude:
			if exclude in dir:
				return False
		return True

	def run(self):
		result = {}
		print("[Capo] Building cache...")
		for dir in self.proj_folders:			
			files = None
			for dir_path, subdir, files in os.walk(dir):
				#check for dir in exclude dirs
				if self.isNotExcludedDir(dir_path):
					for file_name in files:
						#check for file extension exclusion
						if re.search('.js$', file_name) != None:
							file_path = os.path.join(dir_path, file_name)		
							file = open(file_path, encoding="ISO-8859-1")
							lines = file.readlines()					
							result[file_path] = lines
							file.close()
		self.result = result
		print("[Capo] Building cache finished...")

class SearchCall(threading.Thread):
	def __init__(self, args):
		self.pattern = args["pattern"]
		self.proj_folders = args["proj_folders"]
		self.result = None
		self.nothing = False
		self.dir_exclude = args["excludedDirs"]	
		self.currentFile = args["currentFile"]
		self.cache = args["cache"]
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
						if re.search('.js$', file_name) != None:
							file_path = os.path.join(dir_path, file_name)
							lines = self.cache[file_path]		
							for n, line in enumerate(lines):
								if file_path == self.currentFile["name"] and n == self.currentFile["line"]:
									continue
								method = re.search(self.pattern, line)
								if method:
									result.append({"path" : file_path, "name" : file_name, "line" : n, "method" : method.group(3)})
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
		self.searchPattern = '({0}.{1}\\((\'|\")({2})(\'|\"))|({1}\(({0}.)?{0},(\'|\")({2})(\'|\"))'.format(self.mediators, self.methods, '$WORD_FOR_SEARCH$')

		#get folders to search
		self.window = sublime.active_window()
		self.proj_folders = self.window.folders()
		self.folders = self.window.project_data()['folders']
		self.dir_exclude = []
		self.cache = None

		for folder in self.folders:
			exclude_folders = folder.get('folder_exclude_patterns');
			if exclude_folders != None:
				for dir in exclude_folders:
					self.dir_exclude.append(dir)

		if self.settings.get('useDefaultExcludePattern'):
			defaultExcludePattern = self.settings.get('folder_exclude_patterns')
			for folder in defaultExcludePattern:
				self.dir_exclude.append(folder)

		if self.cache == None:
			thread = CacheCall({ "proj_folders" : self.proj_folders, 
								 "excludedDirs" : []})
			thread.start()
			self.handle_caching(thread, self.view)

	def run(self, edit):
		regions = []
		view = self.view
		s = view.sel()[0]		
		region = sublime.Region(s.begin(), s.end())
		line = view.line(region) #return the line which contains region
		lineNumber = view.rowcol(s.begin())[0]
		content = view.substr(line).replace(' ', '') #return content of region

		if self.cache == None:
			sublime.status_message('Building the cache to make awesome performance...')
			return

		word = re.search('({0}.{1}\\((\'|\")((\w|-|:)*)(\'|\"))|(.{1}\(({0}.)?{0},(\'|\")((\w|-|:)*)(\'|\"))'.format(self.mediators, self.methods), content)
		print('({0}.{1}\\((\'|\")((\w|-|:)*)(\'|\"))|(.{1}\(({0}.)?{0},(\'|\")((\w|-|:)*)(\'|\"))'.format(self.mediators, self.methods))
		if word == None:
			sublime.status_message('Can\'t find publishers/subscribers in the current line.')
			return

		word_for_search = str(word.group(5) or word.group(14))

		print("[Capo] Searching for " + word_for_search + "...")

		searchPattern = self.searchPattern.replace('$WORD_FOR_SEARCH$', word_for_search)
		thread = SearchCall({"pattern" : searchPattern,
							"proj_folders" : self.proj_folders, 
							"excludedDirs" : self.dir_exclude,
							"cache" : self.cache,
							"currentFile" : { "name" : view.file_name(), "line" : lineNumber}})

		thread.start()
		self.handle_thread(thread, self.window, view, word_for_search)

	def handle_thread(self, thread, window, view, word):
		if thread.is_alive():
			view.set_status('Capo', 'Searching %s ...' %word)
			sublime.set_timeout(lambda: self.handle_thread(thread, window, view, word), 100)
			return
		if thread.nothing == True:
			sublime.status_message('No subscribers were found')
			view.erase_status('Capo')
			return

		view.erase_status('Capo')
		self.showQuickPanel(thread.result, window)

	def handle_caching(self, thread, view):
		if thread.is_alive():
				sublime.set_timeout(lambda: self.handle_caching(thread, view), 100)
				return
		self.cache = thread.result
		view.erase_status('Capo')

	def showQuickPanel(self, result, window):

		items = []		
		result.sort(key=lambda i: (i["method"], i["line"]))

		for item in result:
			items.append([item['method'] + ': ' + item['name'] + ' @' + str(item['line'])])

		window.show_quick_panel(items, lambda i: self.on_click(i, result))

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
			print("[Capo] Opening file " + file + " to line " + str(line))
			window = sublime.active_window()
			new_file = window.open_file(file)

			do_when(
				lambda: not new_file.is_loading(),
				lambda: self.jumpToFile(new_file, line)
			)

	def on_post_save_async(self, view):
		file = open(view.file_name(), encoding="ISO-8859-1")
		lines = file.readlines()					
		self.cache[view.file_name()] = lines
		file.close()