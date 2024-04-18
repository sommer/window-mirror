#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Copyright (C) 2024 Christoph Sommer <sommer@cms-labs.org>
#
# Documentation for this app is at https://github.com/sommer/window-mirror
#
# SPDX-License-Identifier: MIT
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

import argparse
import signal
from collections import namedtuple

import PySide6.QtWidgets
import Quartz
import Quartz.CoreGraphics

# react to Ctrl+C in terminal
signal.signal(signal.SIGINT, signal.SIG_DFL)


def get_window_id_by_app_name(app_name2):

    # create data structure to hold {app name, window title, window id}
    win = namedtuple('win', ['app_name', 'win_name', 'win_id'])
    wins = []

    # assemble list of all windows
    window_list = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID)
    for window in window_list:
        app_name = window['kCGWindowOwnerName']
        win_name = window.get('kCGWindowName', None)
        win_in = window['kCGWindowNumber']
        win_height = window['kCGWindowBounds']['Height']
        win_is_on_screen = window.get('kCGWindowIsOnscreen', False)

        # if not win_is_on_screen:
        #     continue

        if win_height < 32:
            continue

        if not win_name:
            continue

        if app_name in ['Dock', 'Window Server', 'Wallpaper']:
            continue

        if not app_name == app_name2:
            continue

        wins.append(win(app_name, win_name, win_in))

    if not wins:
        return None

    # sort by app name, then by window name
    wins.sort(key=lambda x: (x.app_name, x.win_name))

    # if more than one window, ask user to select one
    if len(wins) > 1:
        print(f'Multiple windows found for app name "{app_name2}":')
        for i, win in enumerate(wins):
            print(f'{i+1}: {win.win_name}')
        i = int(input('Enter window number: ')) - 1
    else:
        i = 0

    # get window id
    window_id = wins[i].win_id

    return window_id


parser = argparse.ArgumentParser(description='Mirror a window')
parser.add_argument('--app-name', '-a', type=str, help='Name of app to mirror')

args = parser.parse_args()

if not args.app_name:
    parser.print_help()
    exit(1)

preview_title = 'Mirrored Window (press q to close)'

app_name = args.app_name

window_id = get_window_id_by_app_name(app_name)
if not window_id:
    print(f'No window found. Exiting.')
    exit(1)

max_fps = 5


def icon_from_unicode(unicode_str):
    font = PySide6.QtGui.QFont('Arial', 128)
    metrics = PySide6.QtGui.QFontMetrics(font)
    rect = metrics.boundingRect(unicode_str)

    # create copy of rect with aspect ratio 1:1
    rect2 = rect
    rect2.setWidth(max(rect.width(), rect.height()))
    rect2.setHeight(max(rect.width(), rect.height()))

    pixmap = PySide6.QtGui.QPixmap(rect2.size())
    pixmap.fill(PySide6.QtGui.QColor('transparent'))
    painter = PySide6.QtGui.QPainter(pixmap)
    painter.setFont(font)

    # inverse rect coordinates
    rect = rect.translated(-rect.topLeft())

    painter.drawText(rect, PySide6.QtCore.Qt.AlignmentFlag.AlignCenter, unicode_str)
    painter.end()
    return pixmap


class MyApplication(PySide6.QtWidgets.QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        icon = icon_from_unicode('🪩')
        self.setWindowIcon(icon)

    def quit(self):
        super().quit()


class MyWindow(PySide6.QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Mirrored Window (press q to close)')
        self.setMinimumSize(320, 240)
        self.setCursor(PySide6.QtGui.QCursor(PySide6.QtCore.Qt.CursorShape.CrossCursor))

        # preferred size
        self.resize(640, 480)

        self.label = PySide6.QtWidgets.QLabel()
        # self.label.setScaledContents(True)
        self.setCentralWidget(self.label)

        # use a timer to update the image
        self.timer = PySide6.QtCore.QTimer()
        self.timer.timeout.connect(self.update_image)
        self.timer.start(1000//max_fps)

    def keyPressEvent(self, event):
        if event.key() == PySide6.QtCore.Qt.Key.Key_Q:
            self.close()
        elif event.key() == PySide6.QtCore.Qt.Key.Key_Escape:
            self.close()

    def update_image(self):

        # capture the window
        image = Quartz.CGWindowListCreateImage(Quartz.CGRectNull, Quartz.kCGWindowListOptionIncludingWindow, window_id, Quartz.kCGWindowImageBoundsIgnoreFraming)
        # img_width = CGImageGetWidth(image)
        img_height = Quartz.CGImageGetHeight(image)
        img_data_provider = Quartz.CGImageGetDataProvider(image)
        img_data = Quartz.CoreGraphics.CGDataProviderCopyData(img_data_provider)
        # bytes_per_row = Quartz.CGImageGetBytesPerRow(image)
        img_width = int(len(img_data) / img_height / 4)
        str_data = img_data.bytes().tobytes()

        image = PySide6.QtGui.QImage(str_data, img_width, img_height, PySide6.QtGui.QImage.Format_ARGB32)

        # scale the image to fit the window
        image = image.scaled(self.label.size(), PySide6.QtCore.Qt.AspectRatioMode.KeepAspectRatio, PySide6.QtCore.Qt.TransformationMode.SmoothTransformation)

        # center the image
        image = image.copy(image.width()//2 - self.label.width()//2, image.height()//2 - self.label.height()//2, self.label.width(), self.label.height())

        pixmap = PySide6.QtGui.QPixmap.fromImage(image)
        self.label.setPixmap(pixmap)


app = MyApplication([])

window = MyWindow()
window.show()

app.exec()
