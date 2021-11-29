import requests
import json
import time
import configparser

if __name__ == '__main__':
    cf = configparser.ConfigParser()
    cf.read("cfg/cfg.ini")
    HOST = cf.get("env", "host")
    user = cf.get("account", "username")
    pwd = cf.get("account", "passwd")

    login_url = HOST + "auth.cgi?api=SYNO.API.Auth&version=6&method=login&account=%s&passwd=%s" % (user, pwd)
    my_cookie = {"type": "tunnel"}
    ret = requests.get(login_url, cookies=my_cookie)
    print("1. login\n%s\n%s" % (login_url, ret.text))

    login_cookies = dict(ret.cookies)
    my_cookie.update(login_cookies)

    list_photos_url = HOST + "entry.cgi?offset=0&limit=100&album_id=4&api=SYNO.Photo.Browse.Item&method=list&version=2"
    ret = requests.get(list_photos_url, cookies=my_cookie)
    print("2. list\n%s\n%s\n" % (list_photos_url, ret.text))

    print("3. download")
    download_photo_url = HOST + "entry.cgi?id=[%s]&force_download=true&is_folder=false&api=SYNO.Photo.Browse.Item&method=download&version=2"
    photo_data = json.loads(ret.text)
    for photo in photo_data['data']['list']:
        startTime = time.time()
        with requests.get(download_photo_url % str(photo['id']), cookies=my_cookie, stream=True) as r:
            contentLength = int(r.headers['content-length'])
            downSize = 0
            with open("photos/" + photo['filename'], 'wb') as f:
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
            line = ', 共耗时: %.2f s, 平均速度: %.2f KB/s'
            line = line % (timeCost, downSize / 1024 / timeCost)
            print(line)
