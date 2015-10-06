# reddit-archive-x
Developed using Python 3.4  

This is V2 of the script  
Right now it will just archive the json data and comments in an organized folder structure.  
Support for downloading/saving media posted will come later 

Supports both users and subreddits  

The script will stream everything from /r/all as it happens and only grab the post if it is a subreddit or user that you are following  

If you see `Queue: xx` size growing, you need to add more threads.

Content filtering is now supported for subreddits. This is done by adding `,nsfw` or `,sfw` after a subreddit.  
In the example below:
- `pics` will only save posts tagged `nsfw`
- `gif` will download all content
- `funny` will only download content NOT tagged `nsfw`

    pics,nsfw   
    gif   
    funny,sfw   


## Dependencies
- praw
- prawoauth2
- requests


## Usage
- Remove `.sample` from files in `/configs/`
- Edit `configs/config.ini`
- Add subreddits/users to `configs/subreddits.txt` and `configs/users.txt` respectfully.
- Run: `python3 main.py` and let it rip

## Supported External Hosts

## Will soon support

## How json files are stored

    /  # Root web/save path
     ├─ configs
     |  ├─ config.ini  # Main config file
     |  ├─ subreddits.txt  # List of subreddits, each on its own line
     |  └─ users.txt  # List of users, each on its own line
     |
     ├─ logs
     |  └─ reddit_scraper.log  # Main log to store everything that happens
     |  
     ├─ subreddit
     |  └─ <subreddit_name[0:1]>  # First letter of subreddit
     |     └─ <subreddit_name[0:2]>  # First two letters of subreddit
     |        └─ <subreddit_name>
     |           └─ <year>
     |              └─ <month>
     |                 └─ <day>
     |                    └─ <hour>
     |                       ├─ <utc_time>_<post_id>.json  # Post info
     |                       └─ <utc_time>_<post_id>_comments.json  # All comments from post and their children
     |
     └─ running.lock  # Is here when the programing is running


## Planned Features
