import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np
import multiprocessing as mp



# initializing empty values
# for x and y co-ordinates
xdata, ydata = [], []


# animation function
def animate(i, line):
    # t is a parameter which varies
    # with the frame number
    t = 0.1 * i

    # x, y values to be plotted
    x = t * np.sin(t)
    y = t * np.cos(t)

    # appending values to the previously
    # empty x and y data holders
    xdata.append(x)
    ydata.append(y)
    line.set_data(xdata, ydata)

    return line,


def plot():
    # creating a blank window
    # for the animation
    fig = plt.figure()
    axis = plt.axes(xlim=(-50, 50),
                    ylim=(-50, 50))

    line, = axis.plot([], [], lw=2)

    # calling the animation function
    anim = animation.FuncAnimation(fig, animate,
                                   fargs=(line, ))
    plt.show()


if __name__ == '__main__':
    try:
        plot_p = mp.Process(target=plot)

        plot_p.start()

        plot_p.join()
    except KeyboardInterrupt:
        print('\nReceived Keyboard Interrupt')
    finally:
        print('Program finished')
