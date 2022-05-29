import struct
import asyncio
from bleak import BleakClient, discover
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import multiprocessing as mp
from queue import Empty
import numpy as np
from collections import deque
from typing import Deque

BLE_DATA_UUID = 'fc0a2501-af4b-4c14-b795-a49e9f7e6b84'

MAXIMUM_RUNTIME = 600  # in s
PLOT_UPDATE_INTERVAL = 100  # in ms
NUMBER_OF_DATA_POINTS = 5000
PLOT_MARGIN = 10  # in %


class DataPoint(object):
    def __init__(self, timestamp: float, gyro_x: float, gyro_y: float, gyro_z: float, accel_x: float, accel_y: float, accel_z: float):
        self.timestamp: float = timestamp

        self.gyro_x: float = gyro_x
        self.gyro_y: float = gyro_y
        self.gyro_z: float = gyro_z

        self.accel_x: float = accel_x
        self.accel_y: float = accel_y
        self.accel_z: float = accel_z


class Nano33BLE(object):
    def __init__(self, plot_q: mp.Queue, serial_q: mp.Queue):
        self.plot_queue: mp.Queue = plot_q
        self.serial_queue: mp.Queue = serial_q

        self.current_datapoint = 0  # Temporary until we get timestamp

    def callback_data(self, _, data):
        floats = deque()
        while len(data) > 0:
            floats.append(struct.unpack("f", data[0:4])[0])
            del data[0:4]

        for i in range(0, len(floats), 6):
            dp = DataPoint(self.current_datapoint,  # Placeholder. we want to add the actual timestamp in seconds here, but it is not yet sent by the arduino
                           floats[i + 0],
                           floats[i + 1],
                           floats[i + 2],
                           floats[i + 3],
                           floats[i + 4],
                           floats[i + 5])

            self.current_datapoint += 1

            # We send the data once to the plotter and once to the serial writer
            self.plot_queue.put(dp)
            self.serial_queue.put(dp)

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

                        await client.start_notify(BLE_DATA_UUID, self.callback_data)

                        await asyncio.sleep(MAXIMUM_RUNTIME)

                        await client.stop_notify(BLE_DATA_UUID)

    def process(self):
        asyncio.run(self.gather_data())


class Plotter(object):
    def __init__(self, dq: mp.Queue):
        self.data_queue = dq

        self.figure = None
        self.axes = None
        self.animation = None

        self.accel_plots = None
        self.gyro_plots = None

        self.accel_x_plot = None
        self.accel_y_plot = None
        self.accel_z_plot = None

        self.gyro_x_plot = None
        self.gyro_y_plot = None
        self.gyro_z_plot = None

    def init_plots(self):
        self.figure, self.axes = plt.subplots(2, figsize=(15, 10))
        self.figure.tight_layout()

        self.accel_plots = self.axes[0]
        self.gyro_plots = self.axes[1]

        self.accel_plots.set_title("Accelerations")
        self.accel_plots.set_xlabel("Timestamp [s]")
        self.accel_plots.set_ylabel("Acceleration [G]")
        self.accel_plots.set_xlim(0, NUMBER_OF_DATA_POINTS)
        self.accel_plots.set_ylim(-2, 2)

        self.gyro_plots.set_title("Gyro")
        self.gyro_plots.set_xlabel("Timestamp [s]")
        self.gyro_plots.set_ylabel("Position")
        self.gyro_plots.set_xlim(0, NUMBER_OF_DATA_POINTS)
        self.gyro_plots.set_ylim(-100, 100)

        self.accel_x_plot, = self.accel_plots.plot([], [], label="Accel X")
        self.accel_y_plot, = self.accel_plots.plot([], [], label="Accel Y")
        self.accel_z_plot, = self.accel_plots.plot([], [], label="Accel Z")

        self.gyro_x_plot, = self.gyro_plots.plot([], [], label="Gyro X")
        self.gyro_y_plot, = self.gyro_plots.plot([], [], label="Gyro Y")
        self.gyro_z_plot, = self.gyro_plots.plot([], [], label="Gyro Z")

        self.figure.legend()

    def animate(self, frame: int):
        accel_x_y = self.accel_x_plot.get_ydata()
        accel_y_y = self.accel_y_plot.get_ydata()
        accel_z_y = self.accel_z_plot.get_ydata()

        gyro_x_y = self.gyro_x_plot.get_ydata()
        gyro_y_y = self.gyro_y_plot.get_ydata()
        gyro_z_y = self.gyro_z_plot.get_ydata()

        x = self.accel_x_plot.get_xdata()

        new_data: Deque[DataPoint] = deque()

        while True:
            try:
                new_data.append(self.data_queue.get(False))

            except Empty:
                break

        if len(new_data) == 0:
            return self.accel_x_plot, self.accel_y_plot, self.accel_z_plot, self.gyro_x_plot, self.gyro_y_plot, self.gyro_z_plot

        new_x_data = deque()

        new_accel_x_data = deque()
        new_accel_y_data = deque()
        new_accel_z_data = deque()

        new_gyro_x_data = deque()
        new_gyro_y_data = deque()
        new_gyro_z_data = deque()

        for dp in new_data:
            dp: DataPoint

            new_x_data.append(dp.timestamp)

            new_accel_x_data.append(dp.accel_x)
            new_accel_y_data.append(dp.accel_y)
            new_accel_z_data.append(dp.accel_z)

            new_gyro_x_data.append(dp.gyro_x)
            new_gyro_y_data.append(dp.gyro_y)
            new_gyro_z_data.append(dp.gyro_z)

        x = np.append(x, new_x_data)[-NUMBER_OF_DATA_POINTS:]

        accel_x_y = np.append(accel_x_y, new_accel_x_data)[-NUMBER_OF_DATA_POINTS:]
        accel_y_y = np.append(accel_y_y, new_accel_y_data)[-NUMBER_OF_DATA_POINTS:]
        accel_z_y = np.append(accel_z_y, new_accel_z_data)[-NUMBER_OF_DATA_POINTS:]

        gyro_x_y = np.append(gyro_x_y, new_gyro_x_data)[-NUMBER_OF_DATA_POINTS:]
        gyro_y_y = np.append(gyro_y_y, new_gyro_y_data)[-NUMBER_OF_DATA_POINTS:]
        gyro_z_y = np.append(gyro_z_y, new_gyro_z_data)[-NUMBER_OF_DATA_POINTS:]

        min_x = min(x, default=0)
        max_x = max(x, default=10)

        min_accel_y = min(accel_x_y + accel_y_y + accel_z_y)
        max_accel_y = max(accel_x_y + accel_y_y + accel_z_y)

        accel_delta = max((max_accel_y - min_accel_y) * (PLOT_MARGIN / 100), 0.5)

        min_accel_y -= accel_delta
        max_accel_y += accel_delta

        min_gyro_y = min(gyro_x_y + gyro_y_y + gyro_z_y)
        max_gyro_y = max(gyro_x_y + gyro_y_y + gyro_z_y)

        gyro_delta = max((max_gyro_y - min_gyro_y) * (PLOT_MARGIN / 100), 10)

        min_gyro_y -= gyro_delta
        max_gyro_y += gyro_delta

        self.accel_plots.set_xlim(min_x, max_x)
        self.accel_plots.set_ylim(min_accel_y, max_accel_y)

        self.gyro_plots.set_xlim(min_x, max_x)
        self.gyro_plots.set_ylim(min_gyro_y, max_gyro_y)

        self.accel_x_plot.set_data(x, accel_x_y)
        self.accel_y_plot.set_data(x, accel_y_y)
        self.accel_z_plot.set_data(x, accel_z_y)

        self.gyro_x_plot.set_data(x, gyro_x_y)
        self.gyro_y_plot.set_data(x, gyro_y_y)
        self.gyro_z_plot.set_data(x, gyro_z_y)

        return self.accel_x_plot, self.accel_y_plot, self.accel_z_plot, self.gyro_x_plot, self.gyro_y_plot, self.gyro_z_plot

    def plot(self):
        self.init_plots()
        self.animation = FuncAnimation(self.figure, self.animate, blit=False, interval=PLOT_UPDATE_INTERVAL)
        plt.show()


class SerialSender(object):
    def __init__(self, serial_q: mp.Queue):
        self.data_queue = serial_q

    def process(self):
        pass


if __name__ == '__main__':
    try:
        plot_queue = mp.Queue()
        serial_queue = mp.Queue()

        ard = Nano33BLE(plot_queue, serial_queue)
        plotter = Plotter(plot_queue)
        serial = SerialSender(serial_queue)

        data_p = mp.Process(target=ard.process)
        plot_p = mp.Process(target=plotter.plot)
        serial_p = mp.Process(target=serial.process)

        data_p.start()
        plot_p.start()
        serial_p.start()

        data_p.join()
        plot_p.join()
        serial_p.join()
    except KeyboardInterrupt:
        print('\nReceived Keyboard Interrupt')
    finally:
        print('Program finished')
