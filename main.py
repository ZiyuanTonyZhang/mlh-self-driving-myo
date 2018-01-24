import argparse
import base64
from datetime import datetime
import os
import shutil

import numpy as np
import socketio
import eventlet
import eventlet.wsgi
from PIL import Image
from flask import Flask
from io import BytesIO

from keras.models import load_model

import utils
import cv2 as cv
import matplotlib.pyplot as plt
import keyboard
import time

sio = socketio.Server()
app = Flask(__name__)
model = None
prev_image_array = None

import myo
from myo.lowlevel import pose_t, stream_emg
from myo.six import print_

myo.init()

SHOW_OUTPUT_CHANCE = 0.01

pose_now = ''

import os, sys
sys.path.append(os.path.join("./myo"))



class Listener(myo.DeviceListener):
    # return False from any method to stop the Hub
    def on_connect(self, myo, timestamp):
        print_("Connected to Myo")
        myo.vibrate('short')
        myo.request_rssi()
    def on_rssi(self, myo, timestamp, rssi):
        print_("RSSI:", rssi)
    def on_event(self, event):
        r""" Called before any of the event callbacks. """
    def on_event_finished(self, event):
        r""" Called after the respective event callbacks have been
        invoked. This method is *always* triggered, even if one of
        the callbacks requested the stop of the Hub. """
    def on_pair(self, myo, timestamp):
        print_('Paired')
        print_(
            "If you don't see any responses to your movements, try re-running the program or making sure the Myo works with Myo Connect (from Thalmic Labs).")
        print_("Double tap enables EMG.")
        print_("Spreading fingers disables EMG.\n")
    def on_disconnect(self, myo, timestamp):
        print_('on_disconnect')
    def on_pose(self, myo, timestamp, pose):
        global pose_now
        pose_now = str(pose)
    def on_unlock(self, myo, timestamp):
        print_('unlocked')
    def on_lock(self, myo, timestamp):
        print_('locked')
    def on_sync(self, myo, timestamp):
        print_('synced')
    def on_unsync(self, myo, timestamp):
        print_('unsynced')




MAX_SPEED = 25
MIN_SPEED = 20
AutoMode = True
AutoMode_previous = True
pose_status = 0

hub = myo.Hub()
hub.set_locking_policy(myo.locking_policy.none)
hub.run(1000, Listener())

@sio.on('telemetry')
def telemetry(sid, data):
    global AutoMode
    global AutoMode_previous

    # print('AutoMode:', AutoMode)
    print('AutoMode:{} pose_status:{}'.format(AutoMode, pose_now))

    global pose_status
    try:
        # myo.time.sleep(0.2)
        # print(str(pose_now))
        if 'rest' in pose_now:
            pose_status = 0
        elif 'wave_in' in pose_now:
            pose_status = 1
        elif 'wave_out' in pose_now:
            pose_status = 2
        elif 'fist' in pose_now:
            pose_status = 3
        elif 'double' in pose_now:
            pose_status = 4
        elif 'fingers_spread' in pose_now:
            pose_status = 5

    # hub.
    except KeyboardInterrupt:
        print_("Quitting ...")
        hub.stop(True)

    if pose_status == 5:
        AutoMode = True
    if pose_status == 3:
        AutoMode = False

        # if AutoMode == True:
        #     if AutoMode_previous == False:
        #         AutoMode = False
        # else:
        #     if AutoMode_previous == True:
        #         AutoMode = True
        #
        # AutoMode_previous = AutoMode
        time.sleep(0.5)


    if AutoMode == True:
        # try:
        if pose_status == 1:
            MAX_SPEED = 20
            MIN_SPEED = 10
            time.sleep(0.1)
            # print('Speeding up 1 mph, current speed:',speed_limit)
        elif pose_status == 2:
            MAX_SPEED = 30
            MIN_SPEED = 25
            time.sleep(0.1)
            # print('Reducing down 1 mph, current speed:',speed_limit)

        # elif pose_status == 3:
        #     MAX_SPEED = 40
        #     MIN_SPEED = 30
        #     print('Max Speeding On')
        #     time.sleep(0.1)
        # except:
        #     pass



        global MAX_SPEED
        global MIN_SPEED
        global AutoMode
        speed_limit = MAX_SPEED

        if data:

                # The current steering angle of the car
                steering_angle = float(data["steering_angle"])
                # The current throttle of the car
                throttle = float(data["throttle"])
                # The current speed of the car
                speed = float(data["speed"])
                # The current image from the center camera of the car
                image = Image.open(BytesIO(base64.b64decode(data["image"])))
                # save frame
                # if args.image_folder != '':
                #     timestamp = datetime.utcnow().strftime('%Y_%m_%d_%H_%M_%S_%f')[:-3]
                #     image_filename = os.path.join(args.image_folder, timestamp)
                #     image.save('{}.jpg'.format(image_filename))

                try:
                    image = np.asarray(image)       # from PIL image to numpy array
                    # cv.imshow('display', image)
                    # plt.imshow(image)
                    # cv.ShowImage(win_name, image)("Cameras", image)
                    image = utils.preprocess(image) # apply the preprocessing
                    image = np.array([image])       # the model expects 4D array


                    # predict the steering angle for the image
                    steering_angle = float(model.predict(image, batch_size=1))

                    # PID control here
                    if speed > speed_limit:
                        speed_limit = MIN_SPEED  # slow down
                    else:
                        speed_limit = MAX_SPEED
                    throttle = 1.0 - steering_angle**2 - (speed/speed_limit)**2

                    # print('{} {} {}'.format(steering_angle, throttle, speed))
                    send_control(steering_angle, throttle)
                    # send_control(2, 2)
                except Exception as e:
                    print(e)
    else:

            MAX_SPEED = 20
            MIN_SPEED = 10

            if pose_status == 0:
                MAX_SPEED = 20
                MIN_SPEED = 10
                steering_angle = 0
                time.sleep(0.1)
            if pose_status == 1:
                steering_angle = -0.4
                print('left',steering_angle)
                time.sleep(0.1)
            elif pose_status == 2:
                steering_angle = 0.4
                print('right', steering_angle)
                time.sleep(0.1)
            # elif pose_status == 3:
            #     pass
                # time.sleep(0.1)

            speed_limit = MAX_SPEED

            if data:

                speed = float(data["speed"])

                try:

                    global steering_angle
                    # PID control here
                    if speed > speed_limit:
                        speed_limit = MIN_SPEED  # slow down
                    else:
                        speed_limit = MAX_SPEED
                    throttle = 1.0 - steering_angle ** 2 - (speed / speed_limit) ** 2
                    if pose_status == 3:
                        throttle = 0
                        time.sleep(0.1)

                    # print('{} {} {}'.format(steering_angle, throttle, speed))
                    send_control(steering_angle, throttle)
                    # send_control(2, 2)

                except Exception as e:
                    print(e)


@sio.on('connect')
def connect(sid, environ):
    print("connect ", sid)
    send_control(0, 0)


def send_control(steering_angle, throttle):
    sio.emit(
        "steer",
        data={
            'steering_angle': steering_angle.__str__(),
            'throttle': throttle.__str__()
        },
        skip_sid=True)


if __name__ == '__main__':

    # parser = argparse.ArgumentParser(description='Remote Driving')
    # parser.add_argument(
    #     'model',
    #     type=str,
    # )
    # args = parser.parse_args()
    #
    # model = load_model(args.model)
    model = load_model('./model.h5')

    app = socketio.Middleware(sio, app)

    eventlet.wsgi.server(eventlet.listen(('', 4567)), app)
