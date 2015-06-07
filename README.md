# reddit-archive-x
  
Developed using Python 3.4

- Use to archive subreddits and users in a way where they can be browsed via the web
- After 1 week of the post date, all of the comments from the post will be saved


## How files will be stored

    /  # Root web/save path
     ├─ logs
     |  └─ reddit-scraper.log
     |
     ├─ assets  # css and js files to be used in the templates
     |  └─ <asset files>
     |
     ├─ user
     |  └─ <username>
     |     ├─ posts
     |     |  └─ <year>
     |     |     └─ <month>
     |     |        └─ <day>
     |     |           ├─ <created_utc>  # epoch time
     |     |           |  ├─ index.html
     |     |           |  └─ post.json
     |     |           |
     |     |           └─ urls.csv  # list of links for all posts for <day> from user
     |     |
     |     ├─ files
     |     |  └─ <hashed subdir>
     |     |     └─ <hashed subdir>
     |     |        └─ <hashed file name>
     |     |
     |     ├─ view
     |     |  └─ index.html  # Search/view posts of this user
     |     |
     |     └─ index.html  # redirects to ./view
     |
     ├─ subreddit
     |  └─ <sub name>
     |     ├─ <year>
     |     |  └─ <month>
     |     |      └─ <day>
     |     |         └─ urls.csv  # list links of all posts in the subreddit for <day>
     |     |
     |     ├─ view
     |     |  └─ index.html  # Search/view posts of this subreddit
     |     |
     |     └─ index.html  # redirects to ./view


## Dependencies
- praw
- pdfkit


## Usage
- ...


## Supported External Hosts
- ...


## Will support in the furure
- Imgur
- Youtube
- Github
- Dropbox
- gfycat
- more to come...