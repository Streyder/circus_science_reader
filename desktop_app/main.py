import os
import struct
import time
import asyncio
import pandas as pd
from bleak import BleakClient, discover
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import multiprocessing as mp
from queue import Queue, Empty
import numpy as np
from collections import deque

ACCEL_STRING_UUID = 'fc0a2501-af4b-4c14-b795-a49e9f7e6b84'

MAXIMUM_RUNTIME = 600  # in s

PLOT_UPDATE_INTERVAL = 100  # in ms

NUMBER_OF_DATAPOINTS = 5000

CSV_FILE_PATH = "out.csv"

timestamp_name = "timestamp"

gyro_x_name = "gyro_x"
gyro_y_name = "gyro_y"
gyro_z_name = "gyro_z"

accel_x_name = "accel_x"
accel_y_name = "accel_y"
accel_z_name = "accel_z"


class Nano33BLE(object):
    def __init__(self, data_queue):
        # self.df = namespace.df

        self.data_queue = data_queue

        if os.path.exists(CSV_FILE_PATH):
            os.remove(CSV_FILE_PATH)

    def callback_data(self, _, data):
        floats = list()
        while len(data) > 0:
            floats.append(struct.unpack("f", data[0:4])[0])
            del data[0:4]

        new_df = pd.DataFrame()

        # We always send groups of 6 values, so we pick every sixth value to add to the specific list
        new_df[gyro_x_name] = floats[0::6]
        new_df[gyro_y_name] = floats[1::6]
        new_df[gyro_z_name] = floats[2::6]

        new_df[accel_x_name] = floats[3::6]
        new_df[accel_y_name] = floats[4::6]
        new_df[accel_z_name] = floats[5::6]

        for fl in new_df[accel_x_name]:
            self.data_queue.put(fl)

        # self.df = pd.concat([self.df, new_df], ignore_index=True)

        # self.df.to_csv(CSV_FILE_PATH)

    async def gather_data(self):
        print('Arduino Nano BLE Peripheral Central Service')
        print('Looking for "Arduino Nano 33 BLE Sense" Device...')

        devices = await discover()
        for d in devices:
            if d.name is not None:
                if 'Arduino Nano 33 BLE Sense' in d.name:
                    print('Found Arduino Nano 33 BLE Sense')
                    async with BleakClient(d.address) as client:
                        print(f'Connected to {d.address}')

                        await client.start_notify(ACCEL_STRING_UUID, self.callback_data)

                        await asyncio.sleep(MAXIMUM_RUNTIME)

                        await client.stop_notify(ACCEL_STRING_UUID)

    def process(self):
        asyncio.run(self.gather_data())


def init_plot():
    pass


def animate(frame, data_queue, x_accel_line):
    try:
        y = x_accel_line.get_ydata()

        new_data = deque()

        while True:
            try:
                # Get the index we sent in
                new_data.append(data_queue.get(False))

            except Empty:
                break

        y = np.append(y, new_data)[-NUMBER_OF_DATAPOINTS:]

        x = np.array(list(range(0, len(y))))
        x_accel_line.set_data(x, y)
        return x_accel_line,
    except AttributeError as e:
        pass


def plot(data_queue):
    figure = plt.figure()
    axis = plt.axes(xlim=(0, NUMBER_OF_DATAPOINTS),
                    ylim=(-2, 2))
    line, = axis.plot([], [])

    anim = FuncAnimation(figure, animate, blit=True, interval=PLOT_UPDATE_INTERVAL, fargs=(data_queue, line))

    plt.show()


if __name__ == '__main__':
    try:
        data_queue = mp.Queue()

        ard = Nano33BLE(data_queue)

        data_p = mp.Process(target=ard.process)
        plot_p = mp.Process(target=plot, args=(data_queue, ))

        data_p.start()
        plot_p.start()

        data_p.join()
        plot_p.join()
    except KeyboardInterrupt:
        print('\nReceived Keyboard Interrupt')
    finally:
        print('Program finished')
