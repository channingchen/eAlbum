import os

import requests
import json
import time
import configparser
import ffmpeg
import cv2

HOST = 'host'
USER = 'user'
PWD = 'pwd'
ALBUM_ID = 'album_id'
WATCH_INTERVAL = 'interval'
SCREEN_WIDTH = "screen_width"
SCREEN_HEIGHT = "screen_height"


class AlbumWatcher:
    cfg = dict()
    login_cookies = {"type": "tunnel"}
    stop = False

    def __init__(self, cfg_file_path: str):
        cf = configparser.ConfigParser()
        cf.read(cfg_file_path)

        self.cfg[HOST] = cf.get("default", HOST)
        self.cfg[USER] = cf.get("default", USER)
        self.cfg[PWD] = cf.get("default", PWD)
        self.cfg[ALBUM_ID] = cf.get("default", ALBUM_ID)
        self.cfg[WATCH_INTERVAL] = cf.get("default", WATCH_INTERVAL)
        self.cfg[SCREEN_WIDTH] = cf.get("default", SCREEN_WIDTH)
        self.cfg[SCREEN_HEIGHT] = cf.get("default", SCREEN_HEIGHT)

    def login(self):
        login_url = self.cfg[HOST] + "auth.cgi?api=SYNO.API.Auth&version=6&method=login&account=%s&passwd=%s" % \
                    (self.cfg[USER], self.cfg[PWD])
        ret = requests.get(login_url, cookies=self.login_cookies)
        self.login_cookies.update(dict(ret.cookies))
        return login_url, ret.text

    def list_album(self, limit: int, offset: int) -> dict:
        list_photos_url = self.cfg[HOST] + \
                          "entry.cgi?offset=%d&limit=%d&album_id=%s&api=SYNO.Photo.Browse.Item&method=list&version=2"
        ret = requests.get(list_photos_url % (offset, limit, self.cfg[ALBUM_ID]), cookies=self.login_cookies)
        return json.loads(ret.text)

    def download(self, photo: dict):
        download_photo_url = self.cfg[HOST] + \
                             "entry.cgi?id=[%s]&force_download=true&is_folder=false&api=SYNO.Photo.Browse.Item&method=download&version=2"

        startTime = time.time()
        file_path = "photos/" + photo['filename']
        temp_file_path = file_path + ".downloading"

        with requests.get(download_photo_url % photo['id'], cookies=self.login_cookies, stream=True) as r:
            contentLength = int(r.headers['content-length'])
            downSize = 0
            if os.path.exists(file_path) or os.path.exists(self.new_file_name(file_path)):
                print(file_path + " exists, pass.")
                return file_path

            with open(temp_file_path, 'wb') as f:
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                    downSize += len(chunk)
                    line = photo['filename'] + ', %d KB/s - %.2f MB， 共 %.2f MB'
                    line = line % (
                        downSize / 1024 / (time.time() - startTime), downSize / 1024 / 1024,
                        contentLength / 1024 / 1024)
                    if downSize >= contentLength:
                        print(line, end='')
                        break
                    print(line, end='\r')
            timeCost = time.time() - startTime
            os.rename(temp_file_path, file_path)
            line = ', 共耗时: %.2f s, 平均速度: %.2f KB/s'
            line = line % (timeCost, downSize / 1024 / timeCost)
            print(line)
        return file_path

    def image_compress(self, file_path: str):
        output_path = self.new_file_name(file_path)

        if os.path.exists(output_path):
            print(output_path + " exists, pass.")
            return output_path

        img = cv2.imread(file_path)
        width = img.shape[1]
        height = img.shape[0]
        new_w, new_h = self.cal_new_shape(width, height)
        input_vid = ffmpeg.input(file_path)
        input_vid.filter('scale', new_w, new_h).output(output_path).overwrite_output().run()
        return output_path

    def video_compress(self, file_path: str):
        output_path = self.new_file_name(file_path)

        if os.path.exists(output_path):
            print(output_path + " exists, pass.")
            return output_path

        cap = cv2.VideoCapture(file_path)
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        new_w, new_h = self.cal_new_shape(width, height)
        input_vid = ffmpeg.input(file_path)
        input_vid.filter('scale', new_w, new_h).output(output_path).overwrite_output().run()
        return output_path

    def cal_new_shape(self, width: int, height: int):
        new_w = self.cfg[SCREEN_WIDTH] if width > height else -1
        new_h = self.cfg[SCREEN_WIDTH] if width <= height else -1
        return new_w, new_h

    def new_file_name(self, file_path: str) -> str:
        split_arr = file_path.rsplit(".")
        return split_arr[0] + "_compressed." + split_arr[1]

    def run(self):
        while not self.stop:
            localtime = time.asctime(time.localtime(time.time()))
            print("------------------- process started @ " + localtime + " -------------------")
            print("1. login\n%s\n%s" % self.login())

            limit = 3
            cnt = limit
            offset = 0
            while cnt == limit:
                photo_data = self.list_album(limit, offset)
                print("2. list\n%s\n" % photo_data)
                photo_arrs = photo_data['data']['list']
                cnt = len(photo_arrs)
                offset += cnt

                print("3. process")
                for photo in photo_arrs:
                    print("3.1 downloading...")
                    file_path = self.download(photo)
                    print("3.2 compressing...")
                    if photo['type'] == 'photo':
                        self.image_compress(file_path)
                    if photo['type'] == 'video':
                        self.video_compress(file_path)
                    print("3.3 delete original file")
                    if os.path.exists(file_path):
                        os.remove(file_path)

            time.sleep(int(self.cfg[WATCH_INTERVAL]))


if __name__ == '__main__':
    instance = AlbumWatcher("cfg/cfg.ini")
    instance.run()
