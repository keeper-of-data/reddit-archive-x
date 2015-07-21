import os
import re
import time
import json
import urllib
import shutil
import traceback
import threading
from datetime import datetime


class GeneralUtils:

    def __init__(self):

        # Lock file access when in use
        self.file_lock = {}

        # So we know how long the prev string printed was
        self.prev_cstr = ''

        # Block print display messages
        self.bprint_messages = [
                                ['Reddit Archiver by /u/xtream1101 ', ''],  # 0
                                ['Post Queue', ''],  # 1
                                ['DB Queue', ''],  # 2
                                ['Comment Queue', ''],  # 3
                                ['Last post', ''],  # 4
                                ['Curr Action', ''],  # 5
                               ]

        # Windows folders can not be these names
        self.reserved_words = ['con', 'prn', 'aux', 'nul', 'com1', 'com2',
                               'com3', 'com4', 'com5', 'com6', 'com7', 'com8',
                               'com9', 'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5',
                               'lpt6', 'lpt7', 'lpt8', 'lpt9'
                               ]

    def enable_bprint(self):
        # Start instance of block print
        self._bprint_display()

    def get_datetime(self, time):
        """
        :return: datetime object from epoch timestamp
        """
        return datetime.fromtimestamp(time)

    def get_utc_epoch(self):
        """
        :return: utc time since epoch
        """
        return int(time.time())

    def norm_path(self, path):
        """
        :return: Proper path for os
        """
        path = os.path.normcase(path)
        path = os.path.normpath(path)
        return path

    def create_path(self, path, is_dir=False):
        """
        Check if path exists, if not create it
        :param path: path or file to create directory for
        :param is_dir: pass True if we are passing in a directory, default = False
        :return: os safe path from `path`
        """
        path = self.norm_path(path)
        path_check = path
        does_path_exists = os.path.exists(path_check)

        if not is_dir:
            path_check = os.path.dirname(path)

        if does_path_exists:
            return path

        try:
            os.makedirs(path_check)
        except OSError:
            pass

        return path

    def create_sub_save_file(self, created_utc, subreddit_save, post_id):
        """
        `post_id` is just used for filename, so we can
          append `_comments` or anything else safely
        """
        created = self.get_datetime(created_utc)
        y = str(created.year)
        m = str(created.month)
        d = str(created.day)
        utc_str = str(int(created_utc))

        # Create .json savepath, filename will be created_utc_id.json
        # Create directory 3 deep (min length of a subreddit name)
        json_save_path = self.create_base_path('subreddits',
                                               subreddit_save[0:1],
                                               subreddit_save[0:2],
                                               subreddit_save,
                                               y, m, d
                                               )
        # Save path for json data
        json_save_file = os.path.join(
                                      json_save_path,
                                      utc_str + "_" + post_id + ".json"
                                      )
        return json_save_file

    def create_save_path(self, *args):
        """
        Creates directory from base_dir and appends on any dirs passed in on args
        :param args: List of items to create into a path
        """
        path = os.path.join(self.base_dir, "./" + "/".join(args))
        path = self.norm_path(path)
        # Adds tralling slash
        # if not path.endswith(os.path.sep):
        #     path += os.path.sep
        # -OR-
        path = os.path.join(path, '')
        # Create folders
        self.create_path(path, is_dir=True)
        return path

    def save_to_web_path(self, save_path):
        """
        :return: absolute web path for file from save_path
        """
        # Remove the save base_dir
        path = save_path.replace(self.base_dir, '')
        # Convert path to use `/`
        web_path = urllib.request.pathname2url(path)
        return web_path

    def create_joined_path(self, *args):
        """
        Creates directory of any dirs passed in on args
        :param args: List of items to create into a path
        """
        path = "/".join(args)
        path = self.norm_path(path)
        return path

    def create_base_path(self, *args):
        """
        Creates directory of any dirs passed in on args and appends to base_dir
        :param args: List of items to create into a path
        """
        path = os.path.join(self.base_dir, "./" + "/".join(args))
        path = self.norm_path(path)
        return path

    def bprint(self, bmsg, line_num):
        """
        bprint: Block Print
        self.bprint_messages[line_num][0] is always the display text
        self.bprint_messages[line_num][1] is always the value
        """
        self.bprint_messages[line_num][1] = bmsg

    def _bprint_display(self):
        self.bprint_messages[0][1] = time.time()

        os.system("cls")
        for msg in self.bprint_messages:
            print(msg[0] + ": " + str(msg[1]))

        # Update terminal every n seconds
        t_reload = threading.Timer(.5, self._bprint_display)
        t_reload.setDaemon(True)
        t_reload.start()

    def cprint(self, cstr, log=False):
        """
        Clear then print on same line
        :param cstr: string to print on current line
        """
        # Blank out whole line
        #   The +1 is ther just to make sure it clears all chars
        cstr = "Queue: " + str(self.q.qsize()) + " - " + cstr
        num_spaces = 0
        if len(cstr) < len(self.prev_cstr):
            num_spaces = abs(len(self.prev_cstr) - len(cstr))
        self.prev_cstr = cstr
        try:
            print(cstr + " "*num_spaces, end='\r')
        except UnicodeEncodeError:
            print('Processing...', end='\r')

        if log:
            pass
            # self.log(cstr)

    def log(self, msg, level='info'):
        """
        :param msg: Data to save to file
        :param level: Level to which to log msg, default: info
        :return: Data as a string to print to console
        """
        print("LOG:", msg)

    #######################################################
    #
    #    Functions that deal with file access
    #
    #######################################################
    def copy_file(self, source, destination):
        """
        Copy file source -> destination
        """
        # Make sure path exists
        self.create_path(destination)
        # Copy over file
        shutil.copy2(source, destination)
        self.log("Copied file '" + source + "' to '" + destination + "'", level='debug')

    def append_file(self, save_file, content):
        """
        Append content to end of file
        """
        # Create dict save name from savefile
        pattern = re.compile('[\W_]+')
        file_dict_name = pattern.sub('', save_file)
        # Create perfile Lock
        if file_dict_name not in self.file_lock:
            self.file_lock[file_dict_name] = threading.Lock()
        self.file_lock[file_dict_name].acquire()
        try:
            with open(self.create_path(save_file), 'a') as f:
                f.write(content + "\n")
        finally:
            self.file_lock[file_dict_name].release()

    def save_file(self, save_file, content, content_type='plain_text'):
        """
        Saves file json or plain text default=plain_text
        If content is not json it will save in plain text
        """
        with open(self.create_path(save_file), 'w') as f:
            if content_type == 'json':
                json.dump(content, f, sort_keys=True, indent=4)
            else:
                f.write(content)

    def debug_dump_to_file(self, dump_file, content, out_format=None):
        """
        Used for debugging only
        """
        with open(self.create_path(dump_file), 'w') as f:
            if out_format == 'json':
                json.dump(content, f, sort_keys=True, indent=4)
            else:
                f.write(str(content))
