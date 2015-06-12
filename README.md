# reddit-archive-x
  
Developed using Python 3.4

Supports both users and subreddits  

The script will stream everything from /r/all as it happens and only grab the post if it is a subreddit or user that you are following  

Content filtering is now supported for subreddits. This is done by adding `,nsfw` or `,sfw` after a subreddit.  
In the example below:
- `pics` will only save posts tagged `nsfw`
- `gif` will download all content
- `funny` will only download content NOT tagged `nsfw`

    subreddits = pics,nsfw   
                 gif   
                 funny,sfw   

The browsable interface still has a ways to go so dont worry about that right now

- Use to archive subreddits and users in a way where they can be browsed via the web
- To browse the files, set the root of the server to be your save path. You can run a simple http server using python `python -m SimpleHTTPServer 8080`

## Dependencies
- praw
- requests
- youtube-dl
- pdfkit (not used yet)


## Usage
- Remove `.sample` from config files in `/configs/`
- Edit `configs/config.ini`
- Add subreddits/users to `configs/scrap.ini`
- Run: `python3 main.py` and let it rip
- If another site gets supported, just update the code base and run the command `python3 main.py --get_failed`. This will take the backlog of media that was not supported and download it as well as update the correct post.json file.  


## Supported External Hosts
- Any link that links directly to a file
- imgur.com & i/m.imgur.com
- media.tumblr.com
- gfycat.com
- youtube.com
- vid.me
- vimeo.com


## Will soon support
- Github
- Dropbox
- more to come...


## How files are stored

    /  # Root web/save path
     ├─ assets  # css and js files to be used in the templates
     |  ├─ css
     |  |  └─ styles.css  # Global style sheet
     |  |
     |  ├─ js
     |  |  ├─ csvToArray.js  # csvToArray Library: https://code.google.com/p/jquery-csv/
     |  |  ├─ functions.js  # Global functions script
     |  |  └─ jquery.js  # jquery Library: https://jquery.com/
     |  |
     |  └─ templates
     |     ├─ csv_viewer.html  # View for multiple posts
     |     └─ post_viewer.html  # View for single post
     |
     ├─ logs
     |  ├─ failed_domains.csv  # Stores media from <domain> that cannot be downloaded
     |  └─ reddit_scraper.log  # Main log to store everything that happens
     |  
     ├─ subreddit
     |  └─ <subreddit_name[0]>  # First letter of subreddit
     |     └─ <subreddit_name>
     |        ├─ <year>
     |        |  ├─ <month>
     |        |  |  ├─ <day>
     |        |  |  |  ├─ index.html  # day view
     |        |  |  |  └─ urls.csv  # list of links for day
     |        |  |  |
     |        |  |  ├─ index.html  # month view
     |        |  |  └─ urls.csv  # list of links for month
     |        |  |
     |        |  ├─ index.html  # year view
     |        |  └─ urls.csv  # list of links for year
     |        |
     |        └─ last_post.txt  # Post id of the newest post saved for <subreddit>
     |
     ├─ temp
     |  └─ downloads  # Store files while downloading
     |
     ├─ user
     |  └─ <username[0]>  # First letter of username
     |     └─ <username>
     |        ├─ files
     |        |  └─ <hashed_subdir>
     |        |     └─ <hashed_subdir>
     |        |        └─ <hashed_file_name>
     |        |
     |        ├─ posts
     |        |  └─ <year>
     |        |     ├─ <month>
     |        |     |  ├─ <day>
     |        |     |  |  ├─ <created_utc>  # epoch time
     |        |     |  |  |  ├─ index.html  # Single post view
     |        |     |  |  |  └─ post.json  # Orginal data from reddit as well as added content
     |        |     |  |  |
     |        |     |  |  ├─ index.html  # day view
     |        |     |  |  └─ urls.csv  # list of links for day
     |        |     |  |
     |        |     |  ├─ index.html  # month view
     |        |     |  └─ urls.csv  # list of links for month
     |        |     |
     |        |     ├─ index.html  # year view
     |        |     └─ urls.csv  # list of links for year
     |        |
     |        └─ index.html  # redirects to ./posts
     |
     └─ running.lock  # Is here when the programing is running


## Planned Features (maybe)
- After 1 week of the post date, all of the comments from the post will be saved