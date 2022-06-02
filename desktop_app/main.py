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
from datetime import datetime
import math
import mplcyberpunk  # noqa: we use these cyberpunk theme below, import is required
import websockets
from websockets import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed


BLE_DATA_UUID = 'fc0a2501-af4b-4c14-b795-a49e9f7e6b84'

MAXIMUM_RUNTIME = 600  # in s
PLOT_UPDATE_INTERVAL = 100  # in ms
PLOT_MARGIN = 10  # in %
S_BETWEEN_DATAPOINTS = 1 / 119.6  # We acquire data with ~119hz
TIME_PLOTTED = 10  # in seconds
NUMBER_OF_DATA_POINTS = int(math.floor(TIME_PLOTTED / S_BETWEEN_DATAPOINTS))

SAVE_ANIMATION = False
PATH_TO_ANIMATION_FILE = "animation.mp4"


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
        self.datetime_started = datetime.utcnow()

    def callback_data(self, _, data):
        floats = deque()
        while len(data) > 0:
            floats.append(struct.unpack("f", data[0:4])[0])
            del data[0:4]

        for i in range(0, len(floats), 6):
            dp = DataPoint(self.current_datapoint * S_BETWEEN_DATAPOINTS,
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

                        self.datetime_started = datetime.utcnow()

                        await client.start_notify(BLE_DATA_UUID, self.callback_data)

                        await asyncio.sleep(MAXIMUM_RUNTIME)

                        seconds = (datetime.utcnow() - self.datetime_started).total_seconds()
                        print(f"Acquired {self.current_datapoint} datapoints in {seconds}s for a average frequency of {self.current_datapoint / seconds}Hz")

                        await client.stop_notify(BLE_DATA_UUID)

    def process(self):
        asyncio.run(self.gather_data())


class Plotter(object):
    def __init__(self, dq: mp.Queue):
        self.data_queue = dq

        self.figure = None
        self.axes = None
        self.animation = None

        self.accel_x_plot = None
        self.accel_y_plot = None
        self.accel_z_plot = None

        self.gyro_x_plot = None
        self.gyro_y_plot = None
        self.gyro_z_plot = None

        self.accel_x_line = None
        self.accel_y_line = None
        self.accel_z_line = None

        self.gyro_x_line = None
        self.gyro_y_line = None
        self.gyro_z_line = None

    def init_plots(self):
        self.figure, self.axes = plt.subplots(nrows=2, ncols=3, figsize=(15, 10))
        self.figure.tight_layout(pad=3)

        self.accel_x_plot = self.axes[0, 0]
        self.accel_y_plot = self.axes[0, 1]
        self.accel_z_plot = self.axes[0, 2]
        self.gyro_x_plot = self.axes[1, 0]
        self.gyro_y_plot = self.axes[1, 1]
        self.gyro_z_plot = self.axes[1, 2]

        self.accel_x_plot.set_title("X")
        self.accel_x_plot.set_xlabel("Time [s]")
        self.accel_x_plot.set_ylabel("Acceleration [G]")
        self.accel_x_plot.set_xlim(0, NUMBER_OF_DATA_POINTS)
        self.accel_x_plot.set_ylim(-2, 2)

        self.accel_y_plot.set_title("Y")
        self.accel_y_plot.set_xlabel("Time [s]")
        self.accel_y_plot.set_ylabel("Acceleration [G]")
        self.accel_y_plot.set_xlim(0, NUMBER_OF_DATA_POINTS)
        self.accel_y_plot.set_ylim(-2, 2)

        self.accel_z_plot.set_title("Z")
        self.accel_z_plot.set_xlabel("Time [s]")
        self.accel_z_plot.set_ylabel("Acceleration [G]")
        self.accel_z_plot.set_xlim(0, NUMBER_OF_DATA_POINTS)
        self.accel_z_plot.set_ylim(-2, 2)

        # self.gyro_plots_x.set_title("Gyro X")
        self.gyro_x_plot.set_xlabel("Time [s]")
        self.gyro_x_plot.set_ylabel("Position")
        self.gyro_x_plot.set_xlim(0, NUMBER_OF_DATA_POINTS)
        self.gyro_x_plot.set_ylim(-100, 100)

        # self.gyro_plots_y.set_title("Gyro Y")
        self.gyro_y_plot.set_xlabel("Time [s]")
        self.gyro_y_plot.set_ylabel("Position")
        self.gyro_y_plot.set_xlim(0, NUMBER_OF_DATA_POINTS)
        self.gyro_y_plot.set_ylim(-100, 100)

        # self.gyro_plots_z.set_title("Gyro Z")
        self.gyro_z_plot.set_xlabel("Time [s]")
        self.gyro_z_plot.set_ylabel("Position")
        self.gyro_z_plot.set_xlim(0, NUMBER_OF_DATA_POINTS)
        self.gyro_z_plot.set_ylim(-100, 100)

        self.accel_x_line, = self.accel_x_plot.plot([], [], label="Accel X", color='cyan')
        self.accel_y_line, = self.accel_y_plot.plot([], [], label="Accel Y", color='magenta')
        self.accel_z_line, = self.accel_z_plot.plot([], [], label="Accel Z", color='yellow')

        self.gyro_x_line, = self.gyro_x_plot.plot([], [], label="Gyro X", color='cyan')
        self.gyro_y_line, = self.gyro_y_plot.plot([], [], label="Gyro Y", color='magenta')
        self.gyro_z_line, = self.gyro_z_plot.plot([], [], label="Gyro Z", color='yellow')

        # self.figure.legend()

    def animate(self, frame: int):  # noqa: frame is never used but required for the animation function
        accel_x_y = self.accel_x_line.get_ydata()
        accel_y_y = self.accel_y_line.get_ydata()
        accel_z_y = self.accel_z_line.get_ydata()

        gyro_x_y = self.gyro_x_line.get_ydata()
        gyro_y_y = self.gyro_y_line.get_ydata()
        gyro_z_y = self.gyro_z_line.get_ydata()

        x = self.accel_x_line.get_xdata()

        new_data: Deque[DataPoint] = deque()

        while True:
            try:
                new_data.append(self.data_queue.get(False))

            except Empty:
                break

        if len(new_data) == 0:
            return self.accel_x_line, self.accel_y_line, self.accel_z_line, self.gyro_x_line, self.gyro_y_line, self.gyro_z_line

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

        # Set Plot limits. This "zooms" the plot correctly
        self.accel_x_plot.set_xlim(min_x, max_x)  # noqa: We are aware this looks duplicate but its easy this way
        self.accel_y_plot.set_xlim(min_x, max_x)
        self.accel_z_plot.set_xlim(min_x, max_x)
        self.accel_x_plot.set_ylim(min_accel_y, max_accel_y)
        self.accel_y_plot.set_ylim(min_accel_y, max_accel_y)
        self.accel_z_plot.set_ylim(min_accel_y, max_accel_y)

        self.gyro_x_plot.set_xlim(min_x, max_x)  # noqa: We are aware this looks duplicate but its easy this way
        self.gyro_y_plot.set_xlim(min_x, max_x)
        self.gyro_z_plot.set_xlim(min_x, max_x)
        self.gyro_x_plot.set_ylim(min_gyro_y, max_gyro_y)
        self.gyro_y_plot.set_ylim(min_gyro_y, max_gyro_y)
        self.gyro_z_plot.set_ylim(min_gyro_y, max_gyro_y)

        # Set line data. This updates the actual plot lines
        self.accel_x_line.set_data(x, accel_x_y)
        self.accel_y_line.set_data(x, accel_y_y)
        self.accel_z_line.set_data(x, accel_z_y)

        self.gyro_x_line.set_data(x, gyro_x_y)
        self.gyro_y_line.set_data(x, gyro_y_y)
        self.gyro_z_line.set_data(x, gyro_z_y)

        return self.accel_x_line, self.accel_y_line, self.accel_z_line, self.gyro_x_line, self.gyro_y_line, self.gyro_z_line

    def plot(self):
        plt.style.use('cyberpunk')
        self.init_plots()
        self.animation = FuncAnimation(self.figure, self.animate, blit=True, interval=PLOT_UPDATE_INTERVAL)
        plt.show()


class WebsocketServer(object):
    def __init__(self, serial_q: mp.Queue):
        self.data_queue = serial_q

    async def ws_handler(self, ws: WebSocketServerProtocol, uri: str) -> None:
        print(f"{datetime.utcnow()}: {ws.remote_address} connected and wants some data")

        try:
            async for message in ws:
                print(f"Received Message: {message}")
                new_data: Deque[DataPoint] = deque()

                while True:
                    try:
                        new_data.append(self.data_queue.get(False))

                    except Empty:
                        break

                try:
                    data_to_send: DataPoint = new_data[-1]
                    await ws.send(f"{data_to_send.gyro_x:.3f};{data_to_send.gyro_y:.3f};{data_to_send.gyro_z:.3f};{data_to_send.accel_x:.3f};{data_to_send.accel_y:.3f};{data_to_send.accel_z:.3f}")
                except:
                    await ws.send(f"0.000;0.000;0.000;0.000;0.000;0.000")
        except ConnectionClosed:
            print("Connection was closed violently, but we survived!")

    def process(self):
        start_server = websockets.serve(self.ws_handler, "localhost", 4000)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(start_server)
        loop.run_forever()


if __name__ == '__main__':
    try:
        plot_queue = mp.Queue()
        serial_queue = mp.Queue()

        ard = Nano33BLE(plot_queue, serial_queue)
        plotter = Plotter(plot_queue)
        websocket_server = WebsocketServer(serial_queue)

        data_p = mp.Process(target=ard.process)
        plot_p = mp.Process(target=plotter.plot)
        websocket_p = mp.Process(target=websocket_server.process)

        data_p.start()
        plot_p.start()
        websocket_p.start()

        data_p.join()
        websocket_p.join()
    except KeyboardInterrupt:
        print('\nReceived Keyboard Interrupt')
    finally:
        if SAVE_ANIMATION:
            plotter.animation.save(PATH_TO_ANIMATION_FILE)  # noqa: Plotter is never undefined or we dont get here anways
        print('Program finished')
