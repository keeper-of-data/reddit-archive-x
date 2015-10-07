import os
import time
import json
import praw
import socket
import logging
import threading
import traceback
from queue import Queue
from utils.sql import Sql
from utils.reddit import RedditData
from utils.general_utils import GeneralUtils


class RedditScraper(GeneralUtils):

    def __init__(self, reddit_oauth, watch_list_file, save_path, num_threads):
        super().__init__()

        LOG_FILENAME = save_path + '/logs/reddit_scrape.log'
        logging.basicConfig(filename=LOG_FILENAME, level=logging.INFO)

        self.base_dir = self.norm_path(save_path)

        self.sql = Sql(self.base_dir)

        # Users and subreddits watch list
        self.watch_list_file = watch_list_file

        # Threads: parse threads
        self.num_threads = num_threads
        self.q_posts = Queue(maxsize=0)
        self.q_comments = Queue(maxsize=0)

        # Enable bprint
        self.enable_bprint()
        # self.bprint_update()

        # Name of scraper to put in the user agent
        scraper_name = socket.gethostname()
        self.reddit = RedditData(reddit_oauth, scraper_name)

        # Dict of users and subreddits to scrape
        self.scrape = {}

        # Load content into self.scrape
        self.load_scrape_config()

        # Stats
        self.start_time = time.time()
        self.post_count = 0
        self.comment_count = 0

        # Run parser
        self.main()

        # Clean up
        self.cleanup()

    def main(self):

        self.bprint("Starting streams...", 'curr_a')


        # self.post_stream()
        # self.comment_stream()

        worker2 = threading.Thread(target=self.comment_stream)
        worker2.setDaemon(True)
        worker2.start()

        # worker = threading.Thread(target=self.post_stream)
        # worker.setDaemon(True)
        # worker.start()

        # Keep program alive
        while True:
            time.sleep(.2)

    def post_stream(self):
        ###
        # Thread processing of each post
        ###
        for i in range(self.num_threads):
            worker = threading.Thread(target=self.post_worker)
            worker.setDaemon(True)
            worker.start()

        try:
            post_stream = praw.helpers.submission_stream(self.reddit.r,
                                                         'all',
                                                         100,  # Max num of posts to get each call
                                                         0)
            for post in post_stream:
                # We found another post
                self.post_count += 1
                self.bprint(self.post_count, 'count_p')
                # Calc posts per second
                post_per_sec = ((self.post_count - 100) /  # -100 to offset the first large grab
                                (time.time() - self.start_time))
                self.bprint("%.2f" % post_per_sec, 'freq_p')
                # Add post to queue
                self.q_posts.put(post)
            self.q_posts.join()
        except:
            logging.exception('post stream')
            # self.log(traceback.print_exc(), level='error')
            return

    def comment_stream(self):
        ###
        # Thread processing of each post
        ###
        for i in range(self.num_threads):
            worker = threading.Thread(target=self.comment_worker)
            worker.setDaemon(True)
            worker.start()

        try:
            comment_stream = praw.helpers.comment_stream(self.reddit.r,
                                                         'all',
                                                         100,  # Max num of comments to get each call
                                                         0)
            for comment in comment_stream:
                # We found another post
                self.comment_count += 1
                self.bprint(self.comment_count, 'count_c')
                # Calc comments per second
                comments_per_sec = ((self.comment_count - 100) /  # -100 to offset the first large grab
                                    (time.time() - self.start_time))
                self.bprint("%.2f" % comments_per_sec, 'freq_c')
                # Add post to queue
                self.q_comments.put(comment)
            self.q_comments.join()
        except:
            logging.exception('comment stream')
            # self.log(traceback.print_exc(), level='error')
            return

    def post_worker(self):
        """
        Function to be used as the thread worker
        """
        try:
            while True:
                # Update post queue size on display
                self.bprint(self.q_posts.qsize(), 'queue_p')

                self.parse_post(self.q_posts.get())

                self.q_posts.task_done()
        except Exception as e:
            self.log("Exception in post_worker: " +
                     str(e) + "\n" +
                     str(traceback.format_exc()), level='error'
                     )

    def comment_worker(self):
        """
        Function to be used as the thread worker
        """
        try:
            while True:
                # Update comment queue size on display
                self.bprint(self.q_comments.qsize(), 'queue_c')

                self.parse_comment(self.q_comments.get())

                self.q_comments.task_done()
        except Exception as e:
            self.log("Exception in comments_worker: " +
                     str(e) + "\n" +
                     str(traceback.format_exc()), level='error'
                     )

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

        self.bprint(post['id'], 'last_p')
        self.bprint("Saving post " + post['id'], 'curr_a')

        # Check if full sub name is in reserved_words then append a `-`
        post['subreddit_save_folder'] = post['subreddit']
        if post['subreddit_save_folder'] in self.reserved_words:
            post['subreddit_save_folder'] = post['subreddit'] + "-"

        # Save json data
        json_save_file = self.create_sub_save_file(post['created_utc'],
                                                   post['subreddit_save_folder'],
                                                   post['id'] + "_t3_" + post['created_utc'])  # we add _t3 so we know its a post json file
        try:
            self.save_file(json_save_file, post, content_type='json')
        except Exception as e:
            self.log("Exception parse_post [json]: " +
                     post['subreddit'] + "\n" +
                     str(e) + " " + post['id'] + "\n" +
                     str(traceback.format_exc()), level='error'
                     )

        self.bprint("Waiting for content...", 'curr_a')
        # Done doing things here
        return True

    def parse_comment(self, raw_comment):
        """
        Process comment
        """
        comment = vars(raw_comment)['json_dict']

        # Check if we even want this post
        if 'all' not in self.scrape['subreddits']:
            if comment['subreddit'] not in self.scrape['subreddits'] and \
               comment['author'].lower() not in self.scrape['subreddits']:
                # This is not the post we are looking for, move along
                return

        self.bprint(comment['id'], 'last_c')
        self.bprint("Saving comment " + comment['id'], 'curr_a')

        json_str = json.dumps(comment, ensure_ascii=False)

        self.sql.sql_add_queue([comment['name'],
                                int(comment['created_utc']),
                                comment['link_id'],
                                comment['subreddit'],
                                comment['subreddit_id'],
                                comment['author'],
                                comment['parent_id'],
                                json_str
                                ])

        self.bprint("Waiting for content...", 'curr_a')
        # Done doing things here
        return True

    def load_scrape_config(self):
        """
        Load scrape.ini config file into self.scrape
        This will run every n seconds to get any updates to
          the config in its own thread
        """
        temp_list = {}
        self.scrape = {'subreddits': [], 'users': [], 'content': {}}

        with open(self.watch_list_file['subreddits']) as f:
            temp_list['subreddits'] = f.readlines()

        with open(self.watch_list_file['users']) as f:
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
            self.bprint("You have no users or subreddits listed", 'curr_a')

        # Reload again in n seconds
        t_reload = threading.Timer(10, self.load_scrape_config)
        t_reload.setDaemon(True)
        t_reload.start()

    def bprint_update(self):
        """
        Update these values to be displayed
        """
        self.bprint(self.sql.get_sql_queue(), 'queue_db')

        # Update values every n seconds
        t_reload = threading.Timer(.5, self.bprint_update)
        t_reload.setDaemon(True)
        t_reload.start()

    def cleanup(self):
        # Close the reddit session
        self.reddit.close()
