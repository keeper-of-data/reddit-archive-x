import os
import re
import json
import urllib
import shutil
import logging
import traceback
import threading
from datetime import datetime


class GeneralUtils:

    def __init__(self, logger_name):
        # Get loggers
        self.log_name = logger_name
        self.logger = logging.getLogger(self.log_name)

        # Lock file access when in use
        self.file_lock = {}

        # So we know how long the prev string printed was
        self.prev_cstr = ''

        # Windows folders can not be these names
        self.bad_folders = ['con', 'prn', 'aux', 'nul', 'com1', 'com2', 'com3',
                            'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
                            'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6',
                            'lpt7', 'lpt8', 'lpt9'
                            ]

    def get_datetime(self, time):
        """
        :return: datetime object from epoch timestamp
        """
        return datetime.fromtimestamp(time)

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

    def download_content(self, post):
        """
        :return: Modified post dict
        """
        # Create an empty file list
        file_list = []

        self.cprint("Downloading external data for: " + post['id'] + " from " + post['domain'], log=True)
        try:
            file_list = self.ed.download(post['url'], post['user_save_path'])
        except Exception as e:
            self.log("Download failed: " + str(e) + "\n" + str(traceback.format_exc()), level='error')

        # If file_list is empty, that means that the downloads failed and we need to tray again
        if len(file_list) == 0:
            failed_content = post['domain'] + "," + post['url'] + "," + post['post_save_path']
            self.append_file(self.failed_domain_file, failed_content)
            self.log("Failed domain: " + post['domain'] + " post: " + post['post_save_path'], level='error')

        # Add file list to selftext_html to be viewed
        post['selftext_html'] = '<h2>Files:</h2><a href="' + post['url'] + '">External link</a><br />'
        post['file_downloads'] = file_list
        post['file_downloads_web'] = []
        for dl_file in file_list:
            web_file = self.save_to_web_path(dl_file)
            post['file_downloads_web'].append(web_file)
            post['selftext_html'] += '<div class="file"> \
                                      <a href="' + web_file + '">Local link</a> \
                                      </div>'

        return post

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
        msg = msg.strip()
        if level == 'debug':
            # pass
            self.logger.debug(msg)
        elif level == 'critical':
            self.logger.critical(msg)
        elif level == 'error':
            self.logger.error(msg)
        elif level == 'warning':
            self.logger.warning(msg)
        else:
            # pass
            self.logger.info(msg)

        return str(msg)

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
