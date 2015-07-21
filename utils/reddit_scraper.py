import os
import praw
import socket
import sqlite3
import threading
import traceback
from queue import Queue
from utils.reddit import RedditData
from utils.general_utils import GeneralUtils


class RedditScraper(GeneralUtils):

    def __init__(self, reddit_oauth, save_path, num_threads):
        super().__init__()
        self.base_dir = self.norm_path(save_path)

        self.db_file = os.path.join(self.base_dir, 'logs', 'test.db')
        self.sql_queue = []
        self.add_to_db()  # Call once to get the timer started

        # Thread life
        self.num_threads = num_threads
        self.q = Queue(maxsize=0)

        # Name of scraper to put in the user agent
        scraper_name = socket.gethostname()
        self.reddit = RedditData(reddit_oauth, scraper_name)

        # Dict of users and subreddits to scrape
        self.scrape = {}

        # Load content into self.scrape
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
            stream = praw.helpers.submission_stream(self.reddit.r,
                                                    'all',
                                                    None,
                                                    0)
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
            self.log("Exception in main for posts: " +
                     str(e) + "\n" +
                     str(traceback.format_exc())
                     )

    def load_scrape_config(self):
        """
        Load scrape.ini config file into self.scrape
        This will run every n seconds to get any updates to
          the config in its own thread
        """
        temp_list = {}
        self.scrape = {'subreddits': [], 'users': [], 'content': {}}

        subreddit_list_file = './configs/subreddits.txt'
        with open(subreddit_list_file) as f:
            temp_list['subreddits'] = f.readlines()

        user_list_file = './configs/users.txt'
        with open(user_list_file) as f:
            temp_list['users'] = f.readlines()

        # Break down the params in the user and subreddit lists
        for feed in ['users', 'subreddits']:
            for item in temp_list[feed]:
                option = item.lower().split(',')
                option[0] = option[0].strip()
                # Add subreddit/user to list of things to watch for
                self.scrape[feed].append(option[0])
                # Check to see if we have any prams
                if len(option) > 1:
                    option[1] = option[1].strip().lower()
                    self.scrape['content'][option[0]] = option[1]

        # Check to see if both the subreddit and user lists are blank
        #   If so exit the script as there is no reason to run
        if len(self.scrape['users']) == 0 and \
           len(self.scrape['subreddits']) == 0:
            self.cprint("You have no users or subreddits listed")
        else:
            self.cprint("Searching for posts")

        # Reload again in n seconds
        t_reload = threading.Timer(10, self.load_scrape_config)
        t_reload.setDaemon(True)
        t_reload.start()

    def sql_add_queue(self, query):
        """
        Add queries to a list to be processed by add_to_db()
        """
        self.sql_queue.append(query)

    def add_to_db(self):
        """
        Every n seconds, open a database connection and write everything
          from self.sql_queue to database
        """
        conn = sqlite3.connect(self.db_file)
        cur = conn.cursor()
        for query in self.sql_queue:
            cur.execute(query)
            self.sql_queue.remove(query)

        # Save (commit) the changes
        conn.commit()
        # Close sqlite db connection
        conn.close()
        # Reload again in n seconds
        t_reload = threading.Timer(5, self.add_to_db)
        t_reload.setDaemon(True)
        t_reload.start()

    def parse_post(self, raw_post):
        """
        Process post
        """
        post = vars(raw_post)['json_dict']

        # Check if we even want this post
        if 'all' not in self.scrape['subreddits']:
            if post['subreddit'] not in self.scrape['subreddits'] and \
               post['author'].lower() not in self.scrape['subreddits']:
                # This is not the post we are looking for, move along
                return

        # Check if we want only sfw or nsfw content from this subreddit
        if 'all' not in self.scrape['content']:
            if post['subreddit'] in self.scrape['content']:
                if self.scrape['content'][post['subreddit']] == 'nsfw' and \
                   post['over_18'] is False:
                    return
                elif self.scrape['content'][post['subreddit']] == 'sfw' and \
                     post['over_18'] is True:
                    return
        else:
            if self.scrape['content']['all'] == 'nsfw' and \
               post['over_18'] is False:
                return
            elif self.scrape['content']['all'] == 'sfw' and \
                 post['over_18'] is True:
                return

        self.cprint("Checking post: " + post['id'])

        created = self.get_datetime(post['created_utc'])
        y = str(created.year)
        m = str(created.month)
        d = str(created.day)
        utc_str = str(int(post['created_utc']))

        # Check if full sub name is in reserved_words then append a `-`
        post['subreddit_save_folder'] = post['subreddit']
        if post['subreddit_save_folder'] in self.reserved_words:
            post['subreddit_save_folder'] = post['subreddit'] + "-"

        # Create .json savepath, filename will be created_utc_id.json
        # Create directory 3 deep (min length of a subreddit name)
        json_save_path = self.create_base_path('subreddits',
                                               post['subreddit'][0:1],
                                               post['subreddit'][0:2],
                                               post['subreddit_save_folder'],
                                               y, m, d
                                               )
        # Save json data
        json_save_file = os.path.join(
                                      json_save_path,
                                      utc_str + "_" + post['id'] + ".json"
                                      )
        try:
            self.save_file(json_save_file, post, content_type='json')
        except Exception as e:
            self.log("Exception [json]: " +
                     post['subreddit'] + "\n" +
                     str(e) + " " + post['id'] + "\n" +
                     str(traceback.format_exc())
                     )

        query = 'INSERT INTO \
                posts (created, created_utc, subreddit, subreddit_save, author) \
                VALUES (' + \
                str(int(post['created'])) + ', ' + \
                str(int(post['created_utc'])) + ', "' + \
                post['subreddit'] + '", "' + \
                post['subreddit_save_folder'] + '", "' + \
                post['author'] + '")'

        self.sql_add_queue(query)

        # Done doing things here
        return True

    def cleanup(self):
        # Close the reddit session
        self.reddit.close()
