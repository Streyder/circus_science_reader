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
        self.animation = None

        # Plot init
        self.figure, self.axes = plt.subplots(2)

        self.accel_plots = self.axes[0, 0]
        self.gyro_plots = self.axes[0, 1]

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

        plt.legend()

        self.accel_x_plot = self.accel_plots.plot([], [], label="Accel X")
        self.accel_y_plot = self.accel_plots.plot([], [], label="Accel Y")
        self.accel_z_plot = self.accel_plots.plot([], [], label="Accel Z")

        self.gyro_x_plot = self.gyro_plots.plot([], [], label="Gyro X")
        self.gyro_y_plot = self.gyro_plots.plot([], [], label="Gyro Y")
        self.gyro_z_plot = self.gyro_plots.plot([], [], label="Gyro Z")

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
                new_data.append(plot_queue.get(False))

            except Empty:
                break

        for dp in new_data:
            dp: DataPoint

            x = np.append(x, dp.timestamp)

            accel_x_y = np.append(accel_x_y, dp.accel_x)[-NUMBER_OF_DATA_POINTS:]
            accel_y_y = np.append(accel_y_y, dp.accel_y)[-NUMBER_OF_DATA_POINTS:]
            accel_z_y = np.append(accel_z_y, dp.accel_z)[-NUMBER_OF_DATA_POINTS:]

            gyro_x_y = np.append(gyro_x_y, dp.gyro_x)[-NUMBER_OF_DATA_POINTS:]
            gyro_y_y = np.append(gyro_y_y, dp.gyro_y)[-NUMBER_OF_DATA_POINTS:]
            gyro_z_y = np.append(gyro_z_y, dp.gyro_z)[-NUMBER_OF_DATA_POINTS:]

        self.accel_x_plot.set_data(x, accel_x_y)
        self.accel_y_plot.set_data(x, accel_y_y)
        self.accel_z_plot.set_data(x, accel_z_y)

        self.gyro_x_plot.set_data(x, gyro_x_y)
        self.gyro_y_plot.set_data(x, gyro_y_y)
        self.gyro_z_plot.set_data(x, gyro_z_y)

        return self.accel_x_plot, self.accel_y_plot, self.accel_z_plot, self.gyro_x_plot, self.gyro_y_plot, self.gyro_z_plot

    def plot(self):
        self.animation = FuncAnimation(self.figure, self.animate, blit=True, interval=PLOT_UPDATE_INTERVAL)

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
