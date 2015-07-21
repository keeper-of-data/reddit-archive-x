import os
import json
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

        # Enable bprint
        self.enable_bprint()

        # Name of scraper to put in the user agent
        scraper_name = socket.gethostname()
        self.reddit = RedditData(reddit_oauth, scraper_name)

        # Dict of users and subreddits to scrape
        self.scrape = {}

        # Load content into self.scrape
        self.load_scrape_config()

        # Check comment gathering
        self.check_comments()

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
            self.bprint("You have no users or subreddits listed", 1)

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
        if len(self.sql_queue) > 0:
            conn = sqlite3.connect(self.db_file)
            cur = conn.cursor()
            temp_queue = self.sql_queue
            cur.executemany("INSERT INTO \
                posts (created, created_utc, post_id, subreddit, subreddit_save, author) \
                VALUES (?,?,?,?,?,?)", temp_queue)

            # Save (commit) the changes
            conn.commit()
            # Close sqlite db connection
            conn.close()

            # Now remove what we just added
            for item in temp_queue:
                self.sql_queue.remove(item)

        # Db queue size
        self.bprint(len(self.sql_queue), 2)

        # Reload again in n seconds
        t_reload = threading.Timer(1, self.add_to_db)
        t_reload.setDaemon(True)
        t_reload.start()

    def check_comments(self):
        """
        From SQL database, get all posts that are X old
          and `have_comments` is not `1`
        Pass this list to get_comments() to save to file
        """
        # CHANGE
        check_interval = 6  # In hours, dev set to .08 (aprox. 5 mins)
        min_age = 7  # In days, dev set to .02 (aprox. 30 mins)
        # STOP CHANGE

        min_age_sec = min_age * 86400  # 86400 is sec in a day
        min_age_utc = int(abs(self.get_utc_epoch() - min_age_sec))
        conn = sqlite3.connect(self.db_file)
        cur = conn.cursor()

        cur.execute("SELECT created_utc, post_id, subreddit_save FROM posts WHERE \
                     have_comments != 1 AND \
                     created_utc <= ?", [min_age_utc])

        rows = cur.fetchall()
        self.bprint(len(rows), 3)
        for idx, row in enumerate(rows):
            # Comment queue size
            self.bprint(len(rows)-idx+1, 3)
            created_utc = row[0]
            post_id = row[1]
            subreddit_save = row[2]

            if self.get_comments(created_utc, post_id, subreddit_save):
                cur.execute("UPDATE posts SET have_comments=1 \
                             WHERE post_id=?", [post_id])
                conn.commit()

        # Reload again in n seconds
        t_reload = threading.Timer((check_interval*60)*60, self.check_comments)
        t_reload.setDaemon(True)
        t_reload.start()

    def get_comments(self, created_utc, post_id, subreddit_save):
        """
        Get all comments and child comments from post
        Save to json file
        :return: True if successful, else False
        """
        # Make some reddit api calls to get the data
        all_comments = self.reddit.get_comments(post_id)

        # Post id being passed in includes `t3_`
        post_save_name = post_id.split('_')[1] + "_comments"

        # Save the comments in a json file
        comments_save_file = self.create_sub_save_file(created_utc,
                                                       subreddit_save,
                                                       post_save_name)
        with open(comments_save_file, 'w') as fp:
            json.dump(all_comments, fp)
        return True

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

        self.bprint(post['id'], 4)

        # Check if full sub name is in reserved_words then append a `-`
        post['subreddit_save_folder'] = post['subreddit']
        if post['subreddit_save_folder'] in self.reserved_words:
            post['subreddit_save_folder'] = post['subreddit'] + "-"

        # Save json data
        json_save_file = self.create_sub_save_file(post['created_utc'],
                                                   post['subreddit_save_folder'],
                                                   post['id'])
        try:
            self.save_file(json_save_file, post, content_type='json')
        except Exception as e:
            self.log("Exception [json]: " +
                     post['subreddit'] + "\n" +
                     str(e) + " " + post['id'] + "\n" +
                     str(traceback.format_exc())
                     )

        self.sql_add_queue([int(post['created']),
                            int(post['created_utc']),
                            post['name'],  # Post id with t3_
                            post['subreddit'],
                            post['subreddit_save_folder'],
                            post['author']
                            ])

        # Done doing things here
        return True

    def cleanup(self):
        # Close the reddit session
        self.reddit.close()
