import os
import re
import uuid
import shutil
import hashlib
import requests
import traceback
import youtube_dl
from bs4 import BeautifulSoup
from utils.general_utils import GeneralUtils


class ExternalDownload(GeneralUtils):

    def __init__(self, base_dir, download_path, logger_name):
        super().__init__(logger_name)
        self.base_dir = base_dir
        self._url_header = {'User-Agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
        self._download_path = download_path

        # More types here: http://fileinfo.com/filetypes/common
        self._supported_ext = [  # Video formats
                                   '3g2', '3gp', 'asf', 'asx', 'avi', 'flv',
                                   'm2ts', 'mkv', 'mov', 'mp4', 'mpg', 'mpeg',
                                   'rm', 'swf', 'vob', 'wmv',
                                 # Audio formats
                                   'mp3', 'wma', 'wav', 'ra', 'ram', 'rm',
                                   'mid', 'ogg', 'acc', 'm4a',
                                 # Image formats
                                   'jpeg', 'jpg', 'tiff', 'rif', 'gif', 'bmp',
                                   'png', 'svg', 'gifv',
                                 # File formats
                                   'pdf', 'zip', 'rar', 'tar', 'gz', '7z',
                               ]

    ##########
    # STAGE 1
    ##########
    def download(self, url, user_save_path):
        """
        Called from the client
        Figure out which finction to run
        :return: list of downloaded files
        """
        file_list = []
        self.log(user_save_path + " " + url)
        # Make sure the url does not have a space in it with content after
        #   Reason: This happend 'http://i.imgur.com/82y5SCN.png [x-post from /r/comics]'
        url = url.split(' ')[0]
        # Sometimes the url has unconverted char in it
        url = url.replace('&amp;', '&')

        # Where user files are stored
        user_files_save_path = os.path.join(user_save_path, "files")

        ###
        # Direct file links
        ###
        # Check to see if url is a file
        url_temp = url.split('?')[0]
        if url_temp.split('.')[-1].lower() in self._supported_ext:
            file_list = self._single_file(url, user_files_save_path)

        ###
        # Imgur links
        ###
        elif re.match('.*imgur.com.*', url):
            file_list = self._imgur(url, user_files_save_path)

        ###
        # Download using youtube-dl
        ###
        elif re.match('.*youtu(be\.com|\.be).*', url) or \
             re.match('.*vid\.me.*', url) or \
             re.match('.*vimeo\.com.*', url) or \
             \
             re.match('.*xvideos\.com.*', url) or \
             re.match('.*xvids\.us.*', url) or \
             re.match('.*xvid6\.com.*', url) or \
             re.match('.*soundgasm\.net.*', url) or \
             re.match('.*mrpeepers\.net.*', url) or \
             re.match('.*lovefreeporn\.com.*', url) or \
             re.match('.*extremetube\.com.*', url) or \
             re.match('.*xhamster\.com.*', url):
             
            file_list = self._youtube_dl(url, user_files_save_path)

        ###
        # Get gfycat links
        ###
        elif re.match('.*gfycat\.com.*', url):
            file_list = self._gfycat(url, user_files_save_path)

        ###
        # Get gfycat link from pornbot.net
        ###
        elif re.match('.*pornbot\.net.*', url):
            file_list = self._pornbot(url, user_files_save_path)

        # self.log("Returned file list [external_downloads]: " + str(file_list), level='debug')
        return file_list

    ##########
    # STAGE 2
    ##########
    def _single_file(self, url, user_files_save_path):
        """
        Only ever a single file
        :return: List of save file paths
        """
        self.log("_single_file [external_downloads]: " + url, level='debug')
        temp_files = []

        # Some time the url will have ? in the end which we do not need
        url = url.split('?')[0]

        # Download the original gif file
        if url.endswith('.gifv'):
            url = url.replace('.gifv', '.gif')

        # Get file ext, sometimes the url has other data after the ext
        file_ext = url.split('.')[-1]
        # Add all files that need to be downloaded
        temp_files.append(self._download_file(url, file_ext))

        saved_image_list = self._process_dl_files(temp_files, user_files_save_path)

        return saved_image_list

    def _gfycat(self, url, user_files_save_path):
        """
        Download both the mp4 and gif versions of file
        api: http://gfycat.com/api
        :return: List of save file paths
        """
        temp_files = []
        gfycat_file = url.split('/')[-1]
        gfycat = self._get_html("http://gfycat.com/cajax/get/" + gfycat_file, self._url_header, is_json=True)

        if gfycat is not False:
            data = gfycat['gfyItem']
            temp_files.append(self._download_file(data['gifUrl'], 'gif'))
            temp_files.append(self._download_file(data['mp4Url'], 'mp4'))

        saved_image_list = self._process_dl_files(temp_files, user_files_save_path)
        return saved_image_list

    def _pornbot(self, url, user_files_save_path):
        """
        Get gfycat link from page and pass to _gfycat to download and process
        :return: List of save file paths
        """
        saved_image_list = []
        gfycat_link = None

        # Remove v. subdomain
        url = url.replace('v.', '')

        # Scrape the gfycat link
        page_soup = self._get_html(url, self._url_header)
        if page_soup is not False:
            try:
                content_list = page_soup.find_all("a", {"target": "_new"})
                for content in content_list:
                    link = content['href']
                    # If we find the link thats it
                    if re.match('.*gfycat.com.*', link):
                        gfycat_link = link
                        break
            except AttributeError:
                self.log("Failed to find link on page [_pornbot]: " + url, level='error')
                return []

        if gfycat_link is not None:
            # Download file using _gfycat
            saved_image_list = self._gfycat(gfycat_link, user_files_save_path)
        else:
            self.log("Failed to find link on page [_pornbot]: " + url, level='error')
            return []

        return saved_image_list

    def _imgur(self, url, user_files_save_path):
        """
        Download images from imgur albums or single images on page
        :return: List of save file paths
        """
        saved_image_list = []
        temp_files = []

        # Some time the url will have ? or # in the end which we do not need
        url = url.split('?')[0]
        url = url.split('#')[0]

        # Need to append /noscript to url to parse imgur.com/a/...
        if '/a/' in url:
            url += "/noscript"

        # Scrape the images from imgur
        imgur = self._get_html(url, self._url_header)
        if imgur is not False:
            try:
                content_list = imgur.find_all("div", {"class": "image"})
                for content in content_list:
                    imgur_url = None
                    image_url = content.find("img")
                    if image_url is not None:  # If it is an image or gif
                        imgur_url = image_url['src']
                        self.log("Found image [_imgur]: " + url, level='debug')
                    else:
                        video_url = content.find("source", {"type": "video/mp4"})
                        if video_url:  # If we found a video instead
                            self.log("Found video [_imgur]: " + url, level='debug')
                            imgur_url = video_url['src']

                    # Check if we found a video/gif/image
                    if imgur_url is not None:
                        # Now process the link
                        if imgur_url.startswith('//'):
                            imgur_url = 'http:' + imgur_url
                        imgur_url = imgur_url.split('?')[0]
                        imgur_ext = imgur_url.split('.')[-1]
                        temp_files.append(self._download_file(imgur_url, imgur_ext))
            except AttributeError:
                self.log("Failed to find images in url [_imgur]: " + url, level='error')
                return []

            saved_image_list = self._process_dl_files(temp_files, user_files_save_path)
        return saved_image_list

    def _youtube_dl(self, url, user_files_save_path):
        """
        Using youtube-dl, save video
        :return: List of save file paths
        """
        saved_image_list = []

        temp_file = self._create_temp_file('mp4')
        ydl_opts = {
            'format': 'mp4',
            'outtmpl': temp_file,
            'quiet': True,
            'no_warnings': True
        }
        self.log("Download video [_youtube_dl]: " + url, level='info')
        try:
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except youtube_dl.utils.ExtractorError as e:
            self.log("ExtractorError [_youtube_dl]: " + str(e) + " " + url, level='error')
        except youtube_dl.utils.DownloadError as e:
            self.log("DownloadError [_youtube_dl]: " + str(e) + " " + url, level='error')
        except Exception as e:
            self.log("Exception [_youtube_dl]: " + str(e) + " " + url + "\n" + str(traceback.format_exc()), level='error')
        else:
            saved_image_list = self._process_dl_files([temp_file], user_files_save_path)

        return saved_image_list

    # more functions to process different domains.....

    ##########
    # STAGE 3
    ##########
    def _download_file(self, url, file_ext, header={}):
        """
        """
        self.log("Download file [external_downloads]: " + url + " w/ext " + file_ext, level='debug')
        self.log("Starting download: " + url)
        temp_file = self._create_temp_file(file_ext)
        try:
            response = requests.get(url, headers=header, stream=True)
            if response.status_code == 200:
                with open(temp_file, 'wb') as f:
                    for chunk in response.iter_content():
                        f.write(chunk)
                return_value = temp_file
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            return_value = False
            self.log("Error [download]: " + str(e.response.status_code) + " " + url, level='error')
        except requests.exceptions.ConnectionError as e:
            return_value = False
            self.log("ConnectionError [download]: " + str(e) + " " + url, level='error')
        except requests.exceptions.InvalidSchema as e:
            return_value = False
            self.log("InvalidSchema [download]: " + str(e) + " " + url, level='error')
        except OSError as e:
            return_value = False
            self.log("OSError [download]: " + str(e) + " " + url, level='error') 
        finally:
            # https://github.com/kennethreitz/requests/issues/1882
            response.connection.close()

        return return_value

    ##########
    # STAGE 4
    ##########
    def _process_dl_files(self, file_list, user_files_save_path):
        """
        After all files have been downloaded, do stuff to them
        """
        saved_image_list = []
        for temp_file in file_list:
            if temp_file is not False:
                self.log("_process_dl_files [external_downloads] temp file: " + temp_file, level='debug')
                # Post process the temp file
                post_processed = self._post_process(temp_file, user_files_save_path)
                # Now save the file name/path to be passed back to the client
                saved_image_list.append(post_processed)

        return saved_image_list

    ##########
    # STAGE 5
    ##########
    def _post_process(self, temp_file, user_files_save_path):
        """
        After downloads have finished, rename and move them
        """
        # Get file hash
        file_hash = self._get_file_hash(temp_file)
        # self.log("_post_process [external_downloads] file hash: " + file_hash, level='debug')
        # Get file ext
        file_ext = temp_file.split('.')[-1]
        # Create hash folders for new save path
        hashed_save_path = self._create_hash_folders(user_files_save_path, file_hash)
        # self.log("_post_process [external_downloads] hashed save path: " + hashed_save_path, level='debug')
        new_save_file = os.path.join(hashed_save_path, file_hash + "." + file_ext)
        # Move temp file to new save location
        self._move_file(temp_file, self.create_path(new_save_file))
        return new_save_file

    ##########
    # STAGE 6
    ##########
    def _get_file_hash(self, temp_file):
        """
        Get sha256 hash of files
        :return: sha256 hash of the file
        """
        file_hash = self._hashfile(open(temp_file, 'rb'), hashlib.sha256())
        return file_hash

    ##########
    # STAGE 7
    ##########
    def _create_hash_folders(self, user_files_save_path, file_hash):
        """
        Create folders based on hash in users files dir
        """
        hashed_path = self.create_joined_path(user_files_save_path,
                                              file_hash[0:2],
                                              file_hash[2:4]
                                              )
        return hashed_path

    ##########
    # STAGE 8
    ##########
    def _move_file(self, source, destination):
        """
        Move temp download file to users hashed files
        """
        shutil.move(source, destination)

    ##########
    # Helpers
    ##########
    def _create_temp_file(self, file_ext):
        """
        :return: Full save path of temp file
        """
        temp_name = str(uuid.uuid4())
        temp_file = os.path.join(self._download_path, temp_name + "." + file_ext)
        return temp_file
        
    def _hashfile(self, afile, hasher, blocksize=65536):
        """
        Taken from: http://stackoverflow.com/questions/3431825/generating-a-md5-checksum-of-a-file
        Creates hash of file passed in
        """
        buf = afile.read(blocksize)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(blocksize)
        afile.close()
        return hasher.hexdigest()

    def _get_html(self, url, header={}, is_json=False):
        """
        :return: soup of json from url, False if something broke
        """
        try:
            response = requests.get(url, headers=header)
            if response.status_code == requests.codes.ok:
                if is_json:
                    data = response.json()
                else:
                    data = BeautifulSoup(response.text)

                return data

            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            self.log("HTTPError [_get_site]: " + str(e.response.status_code) + " " + url, level='error')
        except requests.exceptions.ConnectionError as e:
            self.log("ConnectionError [_get_site]: " + str(e) + " " + url, level='error')
        except requests.exceptions.TooManyRedirects as e:
            self.log("TooManyRedirects [_get_site]: " + str(e) + " " + url, level='error')
        except Exception as e:
            self.log("Exception [_get_site]: " + str(e) + " " + url + "\n" + str(traceback.format_exc()), level='critical')
        finally:
            # https://github.com/kennethreitz/requests/issues/1882
            response.connection.close()

        return False
