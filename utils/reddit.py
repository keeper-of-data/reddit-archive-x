import praw
from prawoauth2 import PrawOAuth2Mini
from utils.general_utils import GeneralUtils


class RedditData(GeneralUtils):

    def __init__(self, reddit_oauth, parser_name):
        super().__init__()

        # Create reddit object
        self.r = praw.Reddit(user_agent='reddit-archiver-x on ' + parser_name)
        self.r.config.store_json_result = True

        oauth_helper = PrawOAuth2Mini(
                           self.r,
                           app_key=reddit_oauth['app_key'],
                           app_secret=reddit_oauth['app_secret'],
                           access_token=reddit_oauth['access_token'],
                           refresh_token=reddit_oauth['refresh_token'],
                           scopes='read'
                           )

        # When running commands, do a try except
        #   to see if we need to refresh
        oauth_helper.refresh()

    def close(self):
        """
        Clean up
        """
        pass
