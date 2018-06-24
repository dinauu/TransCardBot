import math
import os
import pickle
import re
import shutil
import time

import cv2
import numpy as np
import requests
from PIL import Image
from bs4 import BeautifulSoup
from keras.models import load_model

from settings import (MODEL_CAPTCHA_FILENAME, MODEL_DIGIT_FILENAME,
                      CAPTCHA_FOLDER, CAPTCHA_IMAGE)

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'


def save_captcha_image(soup, save_dir, captcha_url='http://81.23.146.8/'):
    headers = {
        'Host': '81.23.146.8',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
                      'Chrome/67.0.3396.79 Safari/537.36',
        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        'Referer': 'http://81.23.146.8/default.aspx',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    captcha = requests.get(captcha_url + soup.img.get('src'), headers=headers, stream=True)
    if captcha.status_code == 200:
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        with open(os.path.join(save_dir, CAPTCHA_IMAGE), 'wb') as image:
            captcha.raw.decode_content = True
            shutil.copyfileobj(captcha.raw, image)
            return image.name


def slice_image(image, save_dir, slice_size=50):
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    img = Image.open(image)
    width, height = img.size
    lower = 0
    left = 0
    slices = int(math.ceil(width / slice_size))
    slice_count = 1
    for i in range(slices):
        if slice_count == slices:
            right = width
        else:
            right = int(slice_count * slice_size)
        bbox = (left, lower, right, height)
        working_slice = img.crop(bbox)
        left += slice_size
        working_slice.save(os.path.join(save_dir, str(i + 1) + '.jpg'))
        slice_count += 1


def solve_captcha(images_dir):
    with open(MODEL_DIGIT_FILENAME, 'rb') as f:
        lb = pickle.load(f)
    model = load_model(MODEL_CAPTCHA_FILENAME)
    captcha_text = ''
    for i in range(1, 5):
        image_file = os.path.join(images_dir, '{}.jpg'.format(i))
        digit_image = cv2.imread(image_file)
        digit_image = cv2.cvtColor(digit_image, cv2.COLOR_BGR2GRAY)
        digit_image = np.expand_dims(digit_image, axis=2)
        digit_image = np.expand_dims(digit_image, axis=0)
        prediction = model.predict(digit_image)
        digit = lb.inverse_transform(prediction)[0]
        print('Digit {} on {} step'.format(digit, i))
        captcha_text += digit
    print('Text of captcha:', captcha_text)
    return captcha_text


def get_info_of_card(card_number, user_id, all_info=False):
    check_card = re.match(r'\d{10,20}', card_number)
    if check_card is None:
        return 'Введен неверный номер карты 😞'
    main_url = 'http://81.23.146.8/default.aspx'
    headers = {
        'Host': '81.23.146.8',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
                      'Chrome/67.0.3396.79 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    get_request = requests.get(main_url, headers=headers)
    page = get_request.text
    soup = BeautifulSoup(page, 'html.parser')
    event_validation = soup.find(id='__EVENTVALIDATION').get('value')
    view_state = soup.find(id='__VIEWSTATE').get('value')
    captcha_for_user = os.path.join(CAPTCHA_FOLDER, str(user_id))
    captcha_image = save_captcha_image(soup, captcha_for_user)
    digits_for_user = os.path.join(captcha_for_user, 'digits')
    slice_image(captcha_image, digits_for_user)
    captcha_text = solve_captcha(digits_for_user)
    time.sleep(5)
    headers.update({
        'Origin': 'http://81.23.146.8',
        'Referer': 'http://81.23.146.8/default.aspx',
        'Content-Type': 'application/x-www-form-urlencoded'
    })
    post_request = requests.post(main_url, headers=headers, data={
        '__EVENTTARGET': '',
        'EVENTARGUMENT': '',
        '__VIEWSTATE': view_state,
        'cardnum': card_number,
        'checkcode': captcha_text,
        'Button2': 'Выполнить запрос',
        '__EVENTVALIDATION': event_validation
    })
    page = post_request.text
    soup = BeautifulSoup(page, 'html.parser')
    items_value = soup.findAll('td', class_='FieldValue')
    items = list()
    length_items = len(items_value)
    if length_items == 10:
        if all_info:
            for item in items_value:
                items.append(item.text)
            return items
        else:
            balance = str(items_value[2].text)
            return 'Баланс: {}'.format(balance)
    elif length_items == 8:
        if all_info:
            for item in items_value:
                items.append(item.text)
            return items
        else:
            balance = 'Для вашей карты не предусмотрен баланс 🤷‍♂️'
            return balance
    else:
        invalid_card = soup.find('div', class_='ErrorMessage')
        invalid_captcha = soup.find(id='CustomValidator1')
        if invalid_card is not None:
            return 'Введен неверный номер карты 😞'
        elif invalid_captcha is not None:
            return 'Не удалось решить капчу 😞'
        else:
            return 'Что-то пошло не так 😞'
