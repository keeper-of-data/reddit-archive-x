import praw
from prawoauth2 import PrawOAuth2Mini
from utils.general_utils import GeneralUtils


class RedditData(GeneralUtils):

    def __init__(self, reddit_oauth, parser_name):
        super().__init__()

        # Create reddit object
        self.r = praw.Reddit(user_agent='reddit-archiver-x on ' + parser_name)
        self.r.config.store_json_result = True

        self.oauth_helper = PrawOAuth2Mini(
                           self.r,
                           app_key=reddit_oauth['app_key'],
                           app_secret=reddit_oauth['app_secret'],
                           access_token=reddit_oauth['access_token'],
                           refresh_token=reddit_oauth['refresh_token'],
                           scopes='read'
                           )

        # When running commands, do a try except
        #   to see if we need to refresh
        self.oauth_helper.refresh()

    def get_comments(self, post_id):
        """
        Get and expand all comments for post and return a list
        """
        self.oauth_helper.refresh()

        i = self.r.get_info(thing_id=post_id)
        comments = i.comments
        comments = self.expand_comments(comments)
        c = []
        for comment in comments:
            c.append(self.get_replies(vars(comment)['json_dict']))

        return c

    def get_replies(self, comment_dict):
        """
        Recursive function to get all comments and child comments
          from a post
        """
        try:
            if comment_dict['replies'] == '':
                num_of_replies = 0
            else:
                comment_dict['replies']['data']['children'] = self.expand_comments(comment_dict['replies']['data']['children'])
                num_of_replies = len(comment_dict['replies']['data']['children'])
        except KeyError:
            print("key error")
            num_of_replies = 0

        # If no replies then return
        if num_of_replies == 0:
            return comment_dict

        for idx, reply in enumerate(comment_dict['replies']['data']['children']):
            c_replay = vars(reply)['json_dict']
            comment_dict['replies']['data']['children'][idx] = self.get_replies(c_replay)

        return comment_dict

    def expand_comments(self, comment_list):
        """
        If last item in list is more...
          then get them and repeat until we get them all
        :return: lits of all of the comment objects
        """
        try:
            while type(comment_list[-1]) == praw.objects.MoreComments:
                print("Expanding comments...")
                comment_list = comment_list[:-1] + comment_list[-1].comments()
        except IndexError:
            pass

        return comment_list

    def close(self):
        """
        Clean up
        """
        pass
