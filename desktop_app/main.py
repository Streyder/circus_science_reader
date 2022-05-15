import os
import struct
import time
import asyncio
import pandas as pd
from bleak import BleakClient, discover
from plotly.subplots import make_subplots

ACCEL_STRING_UUID = 'fc0a2501-af4b-4c14-b795-a49e9f7e6b84'

MAXIMUM_RUNTIME = 600  # in s

DRAW_PLOTS = True
PLOT_UPDATE_INTERVAL = 5  # in s

CSV_FILE_PATH = "out.csv"

gyro_x_name = "gyro_x"
gyro_y_name = "gyro_y"
gyro_z_name = "gyro_z"

accel_x_name = "accel_x"
accel_y_name = "accel_y"
accel_z_name = "accel_z"


class Nano33BLE(object):
    def __init__(self):

        self.df = pd.DataFrame()

        if os.path.exists(CSV_FILE_PATH):
            os.remove(CSV_FILE_PATH)

        self.df[gyro_x_name] = list()
        self.df[gyro_y_name] = list()
        self.df[gyro_z_name] = list()

        self.df[accel_x_name] = list()
        self.df[accel_y_name] = list()
        self.df[accel_z_name] = list()

        self.last_plot_update_time = time.perf_counter()

        self.plot_figure = None

        if DRAW_PLOTS:
            self.init_plots()

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

        self.df = pd.concat([self.df, new_df], ignore_index=True)

        self.df.to_csv(CSV_FILE_PATH)

        if not DRAW_PLOTS:
            return

        if (time.perf_counter() - self.last_plot_update_time) > PLOT_UPDATE_INTERVAL:
            self.update_plots()
            self.last_plot_update_time = time.perf_counter()

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

    def init_plots(self):
        self.plot_figure = make_subplots(rows=2, cols=1, subplot_titles=("Acceleration", "Gyro"))

        self.plot_figure['layout']['xaxis']['title'] = 'Sample #'
        self.plot_figure['layout']['xaxis2']['title'] = 'Sample #'
        self.plot_figure['layout']['yaxis']['title'] = 'Acceleration in [G]'
        self.plot_figure['layout']['yaxis2']['title'] = 'Gyro in [deg/s]'

        self.plot_figure.add_scatter(
            y=self.df[accel_x_name],
            mode="lines",
            name="Accel X",
            row=1, col=1
        )

        self.plot_figure.add_scatter(
            y=self.df[accel_y_name],
            mode="lines",
            name="Accel Y",
            row=1, col=1
        )

        self.plot_figure.add_scatter(
            y=self.df[accel_z_name],
            mode="lines",
            name="Accel Z",
            row=1, col=1
        )

        self.plot_figure.add_scatter(
            y=self.df[gyro_x_name],
            mode="lines",
            name="Gyro X",
            row=2, col=1
        )

        self.plot_figure.add_scatter(
            y=self.df[gyro_y_name],
            mode="lines",
            name="Gyro Y",
            row=2, col=1
        )

        self.plot_figure.add_scatter(
            y=self.df[gyro_z_name],
            mode="lines",
            name="Gyro Z",
            row=2, col=1
        )

        self.plot_figure.update_layout(title_text="Nano Sense BLE Data")

    def update_plots(self):
        self.plot_figure.data[0]["y"] = self.df[accel_x_name]
        self.plot_figure.data[1]["y"] = self.df[accel_y_name]
        self.plot_figure.data[2]["y"] = self.df[accel_z_name]

        self.plot_figure.data[3]["y"] = self.df[gyro_x_name]
        self.plot_figure.data[4]["y"] = self.df[gyro_y_name]
        self.plot_figure.data[5]["y"] = self.df[gyro_z_name]
        self.plot_figure.show()


loop = asyncio.get_event_loop()
try:
    ard = Nano33BLE()
    loop.run_until_complete(ard.gather_data())
except KeyboardInterrupt:
    print('\nReceived Keyboard Interrupt')
finally:
    print('Program finished')
