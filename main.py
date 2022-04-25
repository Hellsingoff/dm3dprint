import os
from asyncio import sleep
from glob import glob
from os import environ, getenv
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types.input_file import InputFile
import logging
import ffmpeg
from sql import Admin

environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"
import cv2

bot = Bot(token=getenv('TG_TOKEN'))
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('broadcast')
cam_settings = {'saturation': 200,
                'focus': 90,
                'exposure': -7.5,
                'gain': 40,
                'cam': 0,
                'sleep': 10.0,
                'record': False,
                'last_photo': ''}
cam = cv2.VideoCapture(cam_settings['cam'])
cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
cam.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
cam.set(cv2.CAP_PROP_AUTOFOCUS, 0)


def cam_set(cam_id: int):
    global cam
    cam = cv2.VideoCapture(cam_id)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    cam.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
    cam.set(cv2.CAP_PROP_AUTOFOCUS, 0)


def is_admin(user_id: int):
    return Admin.select().where(Admin.id == user_id).exists()


def photo():
    cam.set(cv2.CAP_PROP_SATURATION, cam_settings['saturation'])
    cam.set(cv2.CAP_PROP_FOCUS, cam_settings['focus'])
    cam.set(cv2.CAP_PROP_EXPOSURE, cam_settings['exposure'])
    cam.set(cv2.CAP_PROP_GAIN, cam_settings['gain'])
    return cam.read()


async def record():
    while cam_settings['record']:
        result, image = photo()
        if result:
            filename = f'{datetime.now().strftime("%Y.%m.%d.%H.%M.%S")}.png'
            cv2.imwrite(filename, image)
            cam_settings['last_photo'] = filename
            await sleep(cam_settings['sleep'])


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer('Hello!')


# start the record
@dp.message_handler(commands=['start_record'])
async def start_record(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer('You have no permission')
        return
    if cam_settings['record']:
        await message.answer('Have already started.')
    else:
        cam_settings['record'] = True
        await record()
        await message.answer('Started.')


# stop the record
@dp.message_handler(commands=['stop_record'])
async def stop_record(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer('You have no permission')
        return
    if not cam_settings['record']:
        await message.answer('Have already stopped.')
    else:
        cam_settings['record'] = False
        await message.answer('Stopped.')


# camera settings
@dp.message_handler(commands=['settings'])
async def settings(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer('You have no permission')
        return
    if len(text := message.text.split()) == 1 or len(text) % 2 == 0:
        await message.answer('Example:\n'
                             '/settings saturation 200 focus 90 exposure -7.5 gain 40 sleep 10\n'
                             'saturation: 0 - 255\nfocus: 0 - 255 (center ~85, bigger is closer)\n'
                             'exposure: -10 - 0\ngain: 0 - 255\nsleep: time between photo in seconds')
    else:
        for key in range(1, len(text), 2):
            if text[key] in ('saturation', 'focus', 'exposure', 'gain', 'sleep'):
                if text[key + 1].isdigit():
                    cam_settings[text[key]] = int(text[key + 1])
                else:
                    try:
                        cam_settings[text[key]] = float(text[key + 1])
                    except ValueError:
                        continue
                await message.answer(f'{text[key]} = {key+1}')
        cam_settings['sleep'] = max(0.95, cam_settings['sleep'] - 0.05)


# camera changing
@dp.message_handler(commands=['camera'])
async def cam_changing(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer('You have no permission')
        return
    if len(text := message.text.split()) > 1 and text[1].isdigit():
        cam_set(int(text[1]))
        await message.answer('Changed.')
    else:
        await message.answer('Example: /camera 0')


# last photo
@dp.message_handler(commands=['last_photo'])
async def last_photo(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer('You have no permission')
        return
    if cam_settings['last_photo'] == '':
        try:
            cam_settings['last_photo'] = glob('*.png')[-1]
        except IndexError:
            await message.answer('Have no photo.')
            return
    file = InputFile(cam_settings['last_photo'])
    await bot.send_photo(message.from_user.id, file, caption=f'{datetime.now().strftime("%Y/%m/%d %H:%M:%S")}')
    file = InputFile(cam_settings['last_photo'])
    await bot.send_document(message.from_user.id, file, caption=cam_settings['last_photo'])


# make photo
@dp.message_handler(commands=['make_photo'])
async def make_photo(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer('You have no permission')
        return
    result = False
    while not result:
        photo()
        await sleep(3)
        result, image = photo()
    cv2.imwrite('tmp.png', image)
    file = InputFile('tmp.png')
    await bot.send_photo(message.from_user.id, file, caption=f'{datetime.now().strftime("%Y/%m/%d %H:%M:%S")}')
    file = InputFile('tmp.png')
    await bot.send_document(message.from_user.id, file, caption=f'{datetime.now().strftime("%Y/%m/%d %H:%M:%S")}')


def render(message, begin, end, fps, preset, crf):
    renamed = dict()
    files = glob('*.png')
    first, last = files.index(begin), files.index(end)
    counter = 1
    for file in files[first:last+1]:
        os.rename(file, new_name := f'{0 * (9 - len(str(counter)))}{str(counter)}')
        renamed[new_name] = file
        counter += 1
    try:
        (ffmpeg
            .input('%09d.png', framerate=int(fps))
            .filter('deflicker', mode='pm', size=10)
            .output(filename := f'{datetime.now().strftime("%Y.%m.%d %H.%M.%S")}.mp4',
                    vcodec='libx265',
                    crf=int(crf),
                    preset=preset,
                    movflags='faststart',
                    pix_fmt='yuv420p')
            .run())
    except ValueError:
        message.answer('Something wrong...')
    else:
        file = InputFile(filename)
        bot.send_document(message.from_user.id, file, caption=filename)
    finally:
        for file in renamed.keys():
            os.rename(file, renamed[file])


# camera settings
@dp.message_handler(commands=['video'])
async def video(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer('You have no permission')
        return
    if len(text := message.text.split()) != 6:
        await message.answer('Usage:\n/video start end fps preset crf\nExample:\n'
                             '/video 2022.02.02.12.55.57.png 2022.02.02.13.55.50.png 60 slow 28')
    else:
        render(message, *text[1:])


# unknown command
@dp.message_handler(lambda message: len(message.text) > 0 and
                    message.text[0] == '/')
async def wut(message: types.Message):
    await message.answer('WUT?')


@dp.message_handler()
async def password(message: types.Message):
    if message.text == getenv('TG_PASS') and not is_admin(message.from_user.id):
        Admin.create(id=message.from_user.id)
        await message.answer('Yep.')
    await bot.delete_message(message.chat.id, message.message_id)


# error handler
@dp.errors_handler()
async def error_log(*args):
    log.error(f'Error handler: {args}')


if __name__ == '__main__':
    executor.start_polling(dp)
