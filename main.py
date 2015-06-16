import os
import sys
import json
import praw
import socket
import signal
import warnings
import argparse
import threading
import traceback
import configparser
from queue import Queue
from utils.reddit import RedditData
from utils.log import setup_custom_logger
from utils.general_utils import GeneralUtils
from utils.static_assets import StaticTemplates
from utils.external_download import ExternalDownload

warnings.filterwarnings("ignore", category=DeprecationWarning)


class TestUrl(GeneralUtils):

    def __init__(self, save_path, test_url):
        super().__init__('test')
        self.base_dir = self.norm_path(save_path)
        self.download_path = self.create_save_path("download")

        # Setup external scraper
        self.ed = ExternalDownload(self.base_dir, self.download_path, 'test')
        print("Starting download")
        flist = self.ed.download(test_url, self.base_dir)
        print(flist)


class GetFailed(GeneralUtils):

    def __init__(self, save_path, num_threads):
        super().__init__('root')
        self.base_dir = self.norm_path(save_path)
        self.download_path = self.create_save_path("temp", "re-downloads")

        # Thread life
        self.num_threads = num_threads
        self.q = Queue(maxsize=0)

        # Setup external scraper
        self.ed = ExternalDownload(self.base_dir, self.download_path, 'failed')

        # Create failed domain down path
        self.failed_domain_file_original = os.path.join(self.base_dir, 'logs', 'failed_domains.csv')
        if not os.path.isfile(self.failed_domain_file_original):
            # If there is no failed domain file then we have nothing to do
            return

        # Rename file so we dont confilct with anything new added
        self.failed_domain_file = self.failed_domain_file_original + ".backloging"
        os.rename(self.failed_domain_file_original, self.failed_domain_file)

        # New failed domains list
        self.failed_domain_list = []

        # Get to work
        self.main()

        # Cleanup
        self.cleanup()

    def main(self):

        # Read in failed content
        with open(self.failed_domain_file) as f:
            failed_domains = f.readlines()

        ###
        # Thread processing of each failed post
        ###
        for i in range(self.num_threads):
            worker = threading.Thread(target=self.domain_worker)
            worker.setDaemon(True)
            worker.start()

        for domain in failed_domains:
            domain = domain.strip().split(',')
            self.q.put(domain)

        self.q.join()

        self.cprint("Completed\n")
        # Remove the copy we made
        os.remove(self.failed_domain_file)
        # Append failed downloads back to the original file
        with open(self.failed_domain_file_original, 'a') as f:
            for domain in self.failed_domain_list:
                f.write(domain + "\n")

    def domain_worker(self):
        try:
            while True:
                self.download_again(self.q.get())
                self.q.task_done()
        except Exception as e:
            self.log("Exception in main for posts: " + str(e) + "\n" + str(traceback.format_exc()), level='critical')

    def download_again(self, domain):
        # Check if we support that that domain
        if self.ed.check_domain(domain[0], domain[1]):
            self.log("We support that domain [download_again]: " + domain[0] + " for post " + domain[2])
            # Get the post json file and read it in
            post_json_file = os.path.join(domain[2], 'post.json')
            with open(post_json_file, 'r') as data_file:
                post = json.load(data_file)
            self.log("Downloading content [download_again]: " + domain[2])
            post = self.download_content(post)
            self.log("Saving content [download_again]: " + domain[2])
            # Save the new post data to the post.json file
            self.save_file(post_json_file, post, content_type='json')

        else:
            # Content failed again
            self.failed_domain_list.append((',').join(domain))

    def cleanup(self):
        try:
            os.removedirs(self.download_path)
        except OSError:
            pass


class RedditScraper(GeneralUtils):

    def __init__(self, reddit_data, save_path, num_threads, is_just_json):
        super().__init__('root')
        self.base_dir = self.norm_path(save_path)

        # Do we only want the json files?
        self.just_json = is_just_json

        # Thread life
        self.num_threads = num_threads
        self.q = Queue(maxsize=0)

        scraper_name = socket.gethostname()  # Name of scraper to put in the user agent
        self.reddit = RedditData(reddit_data, scraper_name)
        self.reddit.login()

        # We only need the static files if we are downloading the content as well
        if self.just_json is False:
            # Create a temp downloads folder
            self.download_path = self.create_save_path("temp", "downloads")

            # Add static templates to use
            self.static = StaticTemplates()

            # Create/update static assets
            self.gen_static_files()

            # Setup external scraper
            self.ed = ExternalDownload(self.base_dir, self.download_path, 'root')

            # Create failed domain down path
            self.failed_domain_file = os.path.join(self.base_dir, 'logs', 'failed_domains.csv')

        # Dict of users and subreddits to scrape
        self.scrape = {}

        # load content into self.scrape
        self.load_scrape_config()

        # Run parser
        self.main()

        # Clean up
        self.cleanup()

    def main(self):
        ###
        # Thread processing of each failed post
        ###
        for i in range(self.num_threads):
            worker = threading.Thread(target=self.post_worker)
            worker.setDaemon(True)
            worker.start()

        try:
            stream = praw.helpers.submission_stream(self.reddit.r, 'all', None, 0)
            for item in stream:
                self.q.put(item)
            self.q.join()
        except InterruptedError:
            return

    def post_worker(self):
        """
        Function to be used as the thread worker
        """
        try:
            while True:
                self.parse_post(self.q.get())
                self.q.task_done()
        except Exception as e:
            self.log("Exception in main for posts: " + str(e) + "\n" + str(traceback.format_exc()), level='critical')

    def load_scrape_config(self):
        """
        Load scrape.ini config file into self.scrape
        This will run every n seconds to get any updates to the config in its own thread
        """
        # Read scrap config file
        scrape_config_file = './configs/scrape.ini'
        if not os.path.isfile(scrape_config_file):
            self.cprint("\nScrape config file not found: " + scrape_config_file, log=True)
        config.read(scrape_config_file)

        temp_scrape = {'subreddits': [], 'users': [], 'content': {}}

        # Break down the params in the user and subreddit lists
        for feed in ['users', 'subreddits']:
            for subreddit in config['scrape'][feed].split("\n"):
                option = subreddit.lower().split(',')
                temp_scrape[feed].append(option[0].strip())
                if len(option) > 1:
                    temp_scrape['content'][option[0].strip()] = option[1].strip().lower()

        # Cpoy temp_scrape to self.scrape
        self.scrape = temp_scrape.copy()

        self.log("Reloaded scape config: " + str(self.scrape['subreddits']), level='debug')

        # Check to see if both the subreddit and user lists are blank
        #   If so exit the script as there is no reason to run
        if (len(temp_scrape['users']) == 1 and temp_scrape['users'][0] == '') and (len(temp_scrape['subreddits'])  == 1 and temp_scrape['subreddits'][0] == ''):
            self.cprint("You have no users or subreddits in ./configs/scrape.ini", log=True)
        else:
            self.cprint("Searching for posts", log=True)

        # Reload again in n seconds
        t_reload = threading.Timer(10, self.load_scrape_config)
        t_reload.setDaemon(True)
        t_reload.start()

    def parse_post(self, raw_post):
        """
        Process post
        """
        post = vars(raw_post)
        # Convert objects to strings
        if raw_post.author:
            post['author'] = raw_post.author.name
        else:
            post['author'] = '[deleted]'
        post['subreddit'] = raw_post.subreddit.display_name.lower()

        # Check if we even want this post
        if 'all' not in self.scrape['subreddits']:
            if post['subreddit'] not in self.scrape['subreddits'] and \
               post['author'].lower() not in self.scrape['subreddits']:
                # This is not the post we are looking for, move along
                return

        # Check if we want only sfw or nsfw content from this subreddit
        if 'all' not in self.scrape['content']:
            if post['subreddit'] in self.scrape['content']:
                if self.scrape['content'][post['subreddit']] == 'nsfw' and post['over_18'] is False:
                    return
                elif self.scrape['content'][post['subreddit']] == 'sfw' and post['over_18'] is True:
                    return
        else:
            if self.scrape['content']['all'] == 'nsfw' and post['over_18'] is False:
                return
            elif self.scrape['content']['all'] == 'sfw' and post['over_18'] is True:
                return

        # Remove, we do not need this
        post.pop('reddit_session')

        self.cprint("Checking post: " + post['id'])

        created = self.get_datetime(post['created_utc'])
        y = str(created.year)
        m = str(created.month)
        d = str(created.day)
        utc_str = str(int(post['created_utc']))

        # Check here if we just want the json
        #   If we do save `post` to json file and move on
        if self.just_json:
            # Also check if the first 3 letters match
            #  We already checked if the whole name was in bad_folders

            sub = post['subreddit'][0:3]
            sub_dir = sub
            # Check if first 3 letters of sub name is in bad_folders
            if sub in self.bad_folders or post['subreddit'] in self.bad_folders:
                sub_dir = sub + "_r_" + sub
            # Check if full sub name is in bad_folders
            if post['subreddit'] in self.bad_folders:
                post['subreddit_original'] = post['subreddit']
                post['subreddit'] = sub_dir

            # Create .json savepath, filename will be created_utc_id.json
            # Create directory 3 letters deep (min length of a subreddit name)
            self.log("Saving just json for subreddit: " + post['subreddit'], level='info')
            # Make sure the subreddit cannot create the folder `con` (Windows bug)
            jjson_save_path = self.create_base_path('subreddits',
                                                    post['subreddit'][0:1],
                                                    post['subreddit'][0:2],
                                                    sub_dir,
                                                    post['subreddit'],
                                                    y, m, d
                                                    )
            # Save json data
            jjson_save_file = os.path.join(jjson_save_path, utc_str + "_" + post['id'] + ".json")
            try:
                self.save_file(jjson_save_file, post, content_type='json')
            except Exception as e:
                self.log("Exception [just_json]: " + post['subreddit'] + "\n" + str(e) + " " + post['id'] + "\n" + str(traceback.format_exc()), level='critical')
            # We are done here
            return

        # Check for bad folder names, only care about authors if we are saving content
        if post['author'] in self.bad_folders:
            post['author_original'] = post['author']
            post['author'] = post['author'] + "_u_" + post['author']

        if post['subreddit'] in self.bad_folders:
            post['subreddit_original'] = post['subreddit']
            post['subreddit'] = post['subreddit'] + "_r_" + post['subreddit']

        ###
        # Used for linking on other pages
        ###
        post['user_web_path'] = self.create_web_path(post['author'], path_type="user")
        post['post_web_path'] = self.create_web_path(post['author'], y, m, d, utc_str, path_type="post")
        ###
        # Used to save files/content
        ###
        post['user_save_path'] = self.create_base_path(post['user_web_path'])
        post['post_save_path'] = self.create_base_path(post['post_web_path'])

        post_json_file = os.path.join(post['post_save_path'], "post.json")

        ###
        # If we already have the post then skip it
        ###
        if os.path.isfile(post_json_file):
            return True

        ###
        # If there is no user json file, create new user
        ###
        if not os.path.isfile(post['user_save_path'] + "user.json"):
            self.add_new_user(post)

        self.cprint("Getting post " + post['id'] + " by: " + post['author'])

        ###
        # Download thumbnail if there is one
        ###
        if len(post['thumbnail']) > 0 and post['thumbnail'].startswith('http'):
            post['thumbnail_original'] = post['thumbnail']
            download_response = self.ed.download(post['thumbnail_original'], post['user_save_path'])
            # If the thumbnail does not download then download_responce would have lenght 0
            if len(download_response) > 0:
                thumbnail_download = download_response[0]
                post['thumbnail'] = self.save_to_web_path(thumbnail_download)

        ###
        # Process post data and download any media needed
        ###
        if post['is_self'] is False:
            # Try to save the content
            post = self.download_content(post)

        ###
        # Now save post data to json
        ###
        self.save_file(post_json_file, post, content_type='json')

        ###
        # Create post html file
        ###
        self.save_file(os.path.join(post['post_save_path'], "index.html"), self.static.gen_frame('post_viewer'), content_type='html')

        url_appends = []
        ###
        # Add post to user urls
        ###
        user_post_base = self.create_base_path('user', post['author'][0], post['author'], 'posts')
        url_appends.append(self.create_joined_path(user_post_base, y))
        url_appends.append(self.create_joined_path(user_post_base, y, m))
        url_appends.append(self.create_joined_path(user_post_base, y, m, d))

        ###
        # Add post to subreddit urls
        ###
        subreddit_post_base = self.create_base_path('subreddit', post['subreddit'][0], post['subreddit'])
        url_appends.append(self.create_joined_path(subreddit_post_base, y))
        url_appends.append(self.create_joined_path(subreddit_post_base, y, m))
        url_appends.append(self.create_joined_path(subreddit_post_base, y, m, d))

        ###
        # Append urls to correct urls.csv files
        ###
        for path in url_appends:
            self.append_file(os.path.join(path, 'urls.csv'), post['post_web_path'])
            self.check_view_index(path)
            # self.log("Added " + post['post_web_path'] + " to " + path, level='debug')

        # Done doing things here
        return True

    def add_new_user(self, post):
        """
        Add new user to the system
        """
        # self.log("Adding new user: " + post['author'], level='info')
        # Create html redirect in users root to ./posts/
        self.save_file(os.path.join(post['user_save_path'], "index.html"), self.static.gen_redirect("./posts"), content_type='html')

    def check_view_index(self, path):
        """
        Check if there is an index.html in each of year, month, and day directories
        If not, create one
        """
        index_view_file = os.path.join(path, 'index.html')
        if not os.path.isfile(index_view_file):
            # self.log("Creating view index at: " + index_view_file, level='debug')
            self.save_file(index_view_file, self.static.gen_frame('csv_viewer'), content_type='html')

    def create_web_path(self, base, *args, path_type=''):
        """
        Creates absolute path that will be used on the web server
        """
        path = ''
        if path_type == 'user' or path_type == 'post':
            path = "/user/" + base[0] + "/" + base + "/"
            if path_type == 'post':
                path += "posts/" + "/".join(args) + "/"
        else:
            path = "/" + "/".join(args)

        return path

    def gen_static_files(self):
        """
        Every run, create/update the static files
        """
        save_path_js = self.create_base_path("assets", "js")
        self.copy_file("./static_assets/js/jquery.js", os.path.join(save_path_js, "jquery.js"))
        self.copy_file("./static_assets/js/csvToArray.js", os.path.join(save_path_js, "csvToArray.js"))
        self.copy_file("./static_assets/js/functions.js", os.path.join(save_path_js, "functions.js"))

        save_path_css = self.create_base_path("assets", "css")
        self.copy_file("./static_assets/css/styles.css", os.path.join(save_path_css, "styles.css"))

        save_path_templates = self.create_base_path("assets", "templates")
        self.copy_file("./static_assets/templates/csv_viewer.html", os.path.join(save_path_templates, "csv_viewer.html"))
        self.copy_file("./static_assets/templates/post_viewer.html", os.path.join(save_path_templates, "post_viewer.html"))

    def cleanup(self):
        self.reddit.close()


def signal_handler(signum, frame):
    print("Quit the running process and clean up")


def check_lock_file(lock_file):
    # Check if there is a lock file
    if os.path.isfile(lock_file):
        print("There is already an instance of the program running\n \
               Please stop any running instances and try again\n \
               If you know this program is not running elsewhere then you can remove the lock file at:\n \
               \t" + lock_file + "\n \
               and try again.")
        sys.exit(0)
    else:
        # Create "lock" file so we know the program is running
        open(lock_file, 'a').close()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    # Get any args that got passed in
    parser = argparse.ArgumentParser()
    parser.add_argument('--get_failed', action='store_true')
    parser.add_argument('--test_url', nargs=2)
    args = parser.parse_args()

    # Get access to some helper functions
    utils = GeneralUtils('root')
    config = configparser.ConfigParser()
    # Read main config file
    config_file = './configs/config.ini'
    if not os.path.isfile(config_file):
        print("Config file not found: " + config_file)
        sys.exit(0)
    config.read(config_file)

    # Read scrap config file
    scrape_config_file = './configs/scrape.ini'
    if not os.path.isfile(scrape_config_file):
        print("Scrape config file not found: " + scrape_config_file)
        sys.exit(0)
    config.read(scrape_config_file)

    # Verify config
    # Check that there is a log file to write to
    log_path = utils.create_path(os.path.expanduser(config['parser']['log_path']), is_dir=True)

    # Create logger to use
    logger = setup_custom_logger('root', os.path.join(log_path, "reddit_scraper.log"))

    # Check save path
    save_path = utils.create_path(os.path.expanduser(config['parser']['save_path']), is_dir=True)

    # Just json
    is_just_json = False
    if config['parser']['just_json'].strip().lower() == 'true':
        is_just_json = True
        # make sure that we are not saving in a dir where reddit content is saved
        if os.path.isdir(os.path.join(save_path, "user")):
            print("The save directory seems to be where you save reddit content\n \
                   Please pick a location that will be just for json files.")
            sys.exit(0)
        # Create file to say this is a json only directory
        open(os.path.join(save_path, "only_json.lock"), 'a').close()
    else:
        # Make sure we are not saving content where we only save json files
        if os.path.isfile(os.path.join(save_path, "only_json.lock")):
            print("The save directory seems to be where you only save json files\n \
                   Please pick a location that will be just for saving content.")
            sys.exit(0)

    lock_file = os.path.join(save_path, "running.lock")

    # Get number of threads to use from config
    num_threads = int(config['parser']['num_threads'])
    if num_threads <= 0:
        num_threads = 1

    # Do something based on the arg passed
    if args.get_failed:
        failed_logger = setup_custom_logger('failed', os.path.join(log_path, "reddit_get_failed.log"))
        get_failed = GetFailed(save_path, num_threads)
    elif args.test_url:
        test_path = utils.create_path(os.path.expanduser(args.test_url[0]), is_dir=True)
        # Create logger to use
        test_logger = setup_custom_logger('test', os.path.join(test_path, "test_download.log"))
        test_url = TestUrl(test_path, args.test_url[1])
    else:
        check_lock_file(lock_file)
        reddit = RedditScraper(config['reddit_login'], save_path, num_threads, is_just_json)
        # Remove lock file when we are done
        os.remove(lock_file)
