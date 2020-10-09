from datetime import datetime, date, timedelta
import logging
import businesstime as bt
import pandas as pd
import numpy as np
import os
from pathlib import Path
import heapq
import pyautogui
import time
from nicpy import nic_str
# from android.storage import app_storage_path, primary_external_storage_path, secondary_external_storage_path

class PriorityQueue:
    def __init__(self):
        self.elements = []

    def empty(self):
        return len(self.elements) == 0

    def put(self, item, priority):
        heapq.heappush(self.elements, (priority, item))

    def get(self):
        return heapq.heappop(self.elements)[1]


# Creates a nested new directory
def mkdir_if_DNE(directory):

    if not isinstance(directory, Path): raise Exception('Input should be a pathlib.Path object.')

    folders_to_create = []
    ancestor = directory
    while ancestor != Path(directory.anchor) and not ancestor.exists():
        folders_to_create.append(ancestor.stem)
        ancestor = ancestor.parent
    for folder in reversed(folders_to_create):
        ancestor = ancestor/folder
        ancestor.mkdir()


def exponential_MA(datetimes, data, tau):

    datetimes, data = list(datetimes), list(data)
    if not same_shape([datetimes, data]): raise Exception('Must input congruent datetimes and data vectors.')
    smoothed = [data[0]]
    for i in range(1, len(datetimes)):
        w = np.exp(-(datetimes[i]-datetimes[i-1]).total_seconds()/60/60/24/tau)
        smoothed.append(w*smoothed[-1]+(1-w)*data[i])

    return smoothed


# Check lengths/sizes of all the lists/arrays/dataframes in a list are the same
def same_shape(list_of_lists):
    if type(list_of_lists) != list: raise Exception('Must input a list of lists/arrays/DataFrames.')
    if len(list_of_lists) < 2: raise Exception('Must input a list of multiple lists/arrays/DataFrames (can mix arrays with DataFrames, but not lists with the others).')
    first_type = type(list_of_lists[0])
    if first_type == list:
        first_shape = len(list_of_lists[0])
    elif first_type in [np.ndarray, pd.core.frame.DataFrame]:
        first_shape = list_of_lists[0].shape
        if len(first_shape) == 1: first_shape = (first_shape[0], 1)
    else:
        raise Exception('Can only check lists with other lists, or arrays/DataFrames with each other, but found a \'{}\'.'.format(type(first_type)))

    for el in list_of_lists[1:]:
        if first_type == list:
            if type(el) != list: raise Exception('Can only check lists with other lists, or arrays/DataFrames with each other.')
            if len(el) != first_shape: return False
        if first_type in [np.ndarray, pd.core.frame.DataFrame]:
            if type(el) not in [np.ndarray, pd.core.frame.DataFrame]: raise Exception('Can only check lists with other lists, or arrays/DataFrames with each other.')
            new_shape = el.shape
            if len(new_shape) == 1: new_shape = (new_shape[0], 1)
            if new_shape != first_shape: return False

    return True



def logging_setup(logger_name, base_directory, file_base):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    # create file handler which logs even debug messages
    file_name = '{}_{}.log'.format('ass_log', nic_str.get_YYYYMMDDHHMMSS_string(datetime.now(), '-', ';'))
    fh = logging.FileHandler(str(base_directory / 'logs' / file_name))
    fh.setLevel(logging.DEBUG)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    # create formatter and add it to the handlers
    formatter = logging.Formatter(u'[%(asctime)s] [%(threadName)s] [%(levelname)s] [%(lineno)d:%(filename)s(%(process)d)] - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

def business_date_shift(business_date_reference, business_day_delta):

    business_time = bt.BusinessTime(weekends=[5,6])

    # Check that business day reference is a date, a bussiness day, and business_day_delta is an integer
    if not isinstance(business_date_reference, date):
        raise Exception('Reference must be a datetime.date object.')
    if not business_time.isbusinessday(business_date_reference):
        raise Exception('Reference must be a business day.')
    if not isinstance(business_day_delta, int):
        raise Exception('Delta must be an integer.')

    signed_one = 1 if business_day_delta >= 0 else -1
    business_days_elapsed = 0
    new_date = business_date_reference
    while business_days_elapsed<abs(business_day_delta):
        new_date += timedelta(days=signed_one)
        if business_time.isbusinessday(new_date):
            business_days_elapsed += 1

    return new_date

def txt_vectors_to_df(txts_directory, separator_char):
    files = os.listdir(str(txts_directory))
    text_file_paths = [Path(txts_directory) / file for file in files if  # '~$' files are temporary Office files present when the main file is opened
                             ((Path(txts_directory) / file).suffix == '.txt') and ('~$' not in str(Path(txts_directory) / file))]
    data_dict = {}
    for file_path in text_file_paths:
        file = open(str(file_path), 'r')
        data_name = file_path.stem
        file_text = file.read()
        data_dict[data_name] = file_text.split(separator_char)
    data_df = pd.DataFrame(data_dict)

    return data_df

# Tests that an object is a list and that it only contains only the specified element type
def is_list_of(test_element_type, test_list):
    if not isinstance(test_list, list): return False
    if not all([type(el) == test_element_type for el in test_list]): return False
    return True

def distance(distance_type, coords1, coords2):
    distance_types = ['euclidian', 'octile', 'manhattan']
    if distance_type not in distance_types:
        raise Exception('Unknown distance type requested, must be from among: {}'.format(distance_types))
    elif distance_type == 'euclidian': # TODO: how much faster is a sqrt approximation?
        squares = [(coord1 - coord2)**2 for coord1, coord2 in zip(coords1, coords2)]
        return np.sqrt(sum(squares))
    elif distance_type == 'octile':
        dx, dy = abs(coords1[0]-coords2[0]), abs(coords1[1]-coords2[1])
        return abs(dx-dy) + np.sqrt(2)*min(dx, dy)
    elif distance_type == 'manhattan':
        deltas = [abs(coord1 - coord2) for coord1, coord2 in zip(coords1, coords2)]
        return sum(deltas)

def look_busy():
    time.sleep(5)
    pixel_center = [int(el/2) for el in pyautogui.size()]
    for i in range(10**100):
        direction = int(np.random.rand()*4)
        if direction == 0:
            pyautogui.move(100+int(np.random.rand()*300), -40+80*np.random.rand(), duration=0.2+2*np.random.rand())              # right\
            time.sleep(0.2+int(np.random.rand()*10))
        if direction == 1:
            pyautogui.move(-40+80*np.random.rand(), 100+int(np.random.rand()*300), duration=0.2+2*np.random.rand())              # down
            time.sleep(0.2 + int(np.random.rand() * 10))
        if direction == 2:
            pyautogui.move(-(100+int(np.random.rand()*300)), -40+80*np.random.rand(), duration=0.2+2*np.random.rand())           # left
            time.sleep(0.2 + int(np.random.rand() * 10))
        if direction == 3:
            pyautogui.move(-40+80*np.random.rand(), -(100 + int(np.random.rand() * 300)), duration=0.2+2*np.random.rand())   # up
            time.sleep(0.2 + int(np.random.rand() * 10))
        if abs(pyautogui.position()[0]-pyautogui.size()[0])<20 or abs(pyautogui.position()[1]-pyautogui.size()[1])<20:
            pyautogui.moveTo(pixel_center[0], pixel_center[1], duration=1+2*np.random.rand()) # reset if close to screen edge
            time.sleep(0.2 + int(np.random.rand() * 10))

# def cut_paste_all_files(from_dir = '', to_dir = '', preset = ''):
#
#     # If known preset specified, set the from_dir and to_dir accordingly
#     known_presets = {'phone': {'from_dir': '', 'to_dir': ''}}
#     print(app_storage_path)
#     print(primary_external_storage_path)
#     print(secondary_external_storage_path)
#     # p = Path('This PC\Moto G (5)\Samsung SD card\DCIM\Camera')
#     # Check
#
#
# cut_paste_all_files()