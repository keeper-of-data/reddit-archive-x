import sys
import praw
from utils.general_utils import GeneralUtils


class RedditData(GeneralUtils):

    def __init__(self, reddit_data, parser_name):
        super().__init__()
        self.user = reddit_data['user']
        self.passwd = reddit_data['pass']
        if reddit_data['force'].lower().title() == "True":
            self.force_login = True
        else:
            self.force_login = False

        # Create reddit object
        self.r = praw.Reddit(user_agent='reddit-archiver-x ' + parser_name)

    def login(self):
        """
        Try and login using your reddit account
        """
        if (len(self.user.strip()) > 0 and len(self.passwd.strip()) > 0) or self.force_login:
            try:
                self.r.login(self.user, self.passwd)
                self.log("Login Successful, force=" + str(self.force_login), level='info')
            except praw.errors.InvalidUserPass:
                self.log("Invalid User/Password, force=" + str(self.force_login), level='error')
                sys.exit(0)
        else:
            self.log("Skipping login, force=" + str(self.force_login), level='warning')

    def is_logged_in(self):
        """
        :return: `True` if logged in, `False` if not
        """
        return self.r.is_logged_in()

    def close(self):
        """
        Clean up
        """
        self.r.clear_authentication()
