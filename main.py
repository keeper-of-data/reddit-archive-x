import os
import sys
import signal
import sqlite3
import argparse
import warnings
import configparser
from utils.general_utils import GeneralUtils
from utils.reddit_scraper import RedditScraper

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=ResourceWarning)


def signal_handler(signum, frame):
    print("Quit the running process and clean up")


def check_lock_file(lock_file):
    # Check if there is a lock file
    if os.path.isfile(lock_file):
        print("""
There is already an instance of the program running.
Please stop any running instances and try again.
If you know this program is not running elsewhere then you can \
remove the lock file at:
\t""" + lock_file + "\n"
              )
        sys.exit(0)
    else:
        # Create "lock" file so we know the program is running
        open(lock_file, 'a').close()


def setup_database():
    # If we do not have a database file then create it
    if not os.path.isfile(db_file):
        conn = sqlite3.connect(db_file)
        conn.execute('''CREATE TABLE posts
                     (id             INTEGER    PRIMARY KEY  AUTOINCREMENT,
                      created        INTEGER    NOT NULL,
                      created_utc    INTEGER    NOT NULL,
                      post_id        VARCHAR(20)  UNIQUE NOT NULL,
                      subreddit      VARCHAR(100)    NOT NULL,
                      subreddit_save VARCHAR(100)    NOT NULL,
                      author         VARCHAR(100)    NOT NULL,
                      have_comments  INTEGER      DEFAULT 0
                     );
                     ''')
        conn.close()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    # Get any args that got passed in
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--configdir', nargs='?', default='./configs/', help='dir that has config files')
    args = parser.parse_args()

    config_dir = os.path.abspath(os.path.expanduser(args.configdir))

    # Get access to some helper functions
    utils = GeneralUtils()
    config = configparser.ConfigParser()

    # Mandatory config file
    config_file = os.path.join(config_dir, 'config.ini')
    if not os.path.isfile(config_file):
        print("Config file not found: " + config_file)
        sys.exit(0)
    config.read(config_file)

    # User and subreddit lists, if not exists, create blank ones
    watch_list_file = {
                       'users': os.path.join(config_dir, 'users.txt'),
                       'subreddits': os.path.join(config_dir, 'subreddits.txt')
                      }
    if not os.path.isfile(watch_list_file['users']):
        open(watch_list_file['users'], 'a').close()
    if not os.path.isfile(watch_list_file['subreddits']):
        open(watch_list_file['subreddits'], 'a').close()

    # Verify config
    # Check that there is a log file to write to
    log_path = utils.create_path(
                   os.path.expanduser(
                       config['parser']['log_path']), is_dir=True
                   )

    # Check save path
    save_path = utils.create_path(
                    os.path.expanduser(
                        config['parser']['save_path']), is_dir=True
                    )

    lock_file = os.path.join(save_path, "running.lock")

    db_file = os.path.join(save_path, 'logs', 'test.db')
    setup_database()

    # Get number of threads to use from config
    num_threads = int(config['parser']['num_threads'])
    # We need at least 1 thread running
    if num_threads <= 0:
        num_threads = 1

    check_lock_file(lock_file)
    reddit = RedditScraper(config['oauth'], watch_list_file, save_path, num_threads)
    # Remove lock file when we are done
    os.remove(lock_file)
