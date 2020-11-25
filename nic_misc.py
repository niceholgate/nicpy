from datetime import datetime, date, timedelta
import logging
import businesstime as bt
import pandas as pd
import numpy as np
import os
from pathlib import Path
import pyautogui
import time
import holidays
import numbers
import yfinance as yf
from nic_webscrape import WeatherData

from nicpy import nic_str


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


# Exponential moving average
def exponential_MA(datetimes, data, tau):

    datetimes, data = list(datetimes), list(data)
    if not same_shape([datetimes, data]): raise Exception('Must input congruent datetimes and data vectors.')
    smoothed = [data[0]]
    for i in range(1, len(datetimes)):
        w = np.exp(-(datetimes[i]-datetimes[i-1]).total_seconds()/60/60/24/tau)
        smoothed.append(w*smoothed[-1]+(1-w)*data[i])

    return smoothed


# Creates a DataFrame from a series of text files, with each file as a column
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


# TODO: need to add holidays data control for more countries and states
def business_date_shift(business_date_reference, business_day_delta, country_string):

    # Convert days delta to years delta to get approximate range of necessary holidays data
    now_year = business_date_reference.year
    years_delta = np.ceil(abs(business_day_delta/365))
    years_list = list(range(now_year-years_delta, now_year+years_delta+1))
    if country_string == 'US': country_holidays = holidays.US(years=years_list)

    business_time = bt.BusinessTime(weekends=[5, 6], holidays=country_holidays)

    # Check that business day reference is a date, a business day, and business_day_delta is an integer
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


# Moves the mouse forever, with a 5 second delay to permit selection of a new window etc. Cancel with ctrl+c.
def look_busy():
    time.sleep(5)
    pixel_center = [int(el/2) for el in pyautogui.size()]
    london_still_reeks = True
    while london_still_reeks:
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

# Easily and succinctly exclude combinations of conditions from a DataFrame
# exclude_combos is a list of dicts, each being a combo to exclude
def df_exclude_combos(df, exclude_combos):
    filter_combos = pd.Series([False]*df.shape[0], index=df.index)
    for combo in exclude_combos:
        filter_this_combo = pd.Series([True]*df.shape[0], index=df.index)
        for key, value in combo.items():
            if key not in df.columns:
                raise Exception('Column {} is not in the DataFrame'.format(key))

            # If list of length 2 check for >, <, <=, >= operators in first column
            if isinstance(value, list):
                if len(value) == 2:
                    if value[0] == '>' and isinstance(value[1], numbers.Number):
                        filter_this_combo = filter_this_combo * (df[key] > value[1])
                    elif value[0] == '<':
                        filter_this_combo = filter_this_combo * (df[key] < value[1])
                    elif value[0] == '<=':
                        filter_this_combo = filter_this_combo * (df[key] <= value[1])
                    elif value[0] == '>=':
                        filter_this_combo = filter_this_combo * (df[key] >= value[1])
                    else:
                        filter_this_combo = filter_this_combo * (df[key] == value[1])
            # If NaN check isnull
            elif pd.isnull(value):
                filter_this_combo = filter_this_combo * (df[key].isnull())
            # All others checks equality
            else:
                filter_this_combo = filter_this_combo * (df[key] == value)
        # OR operation - cumulative exclusions
        filter_combos = filter_combos + filter_this_combo
    return df[~filter_combos]

if __name__ == '__main__':
    # Testing df_exclude_combos()
    df_numerical = yf.Ticker("MSFT").history()
    df_mixed = WeatherData('Perth').processed_data
    # exclude_combos = [{'WindDeg': 250, 'Weather': 'ClearSky'}]
    # df_excluded = df_exclude_combos(df_mixed, exclude_combos)
    # other_df_excluded = df_mixed[~((df_mixed['WindDeg'] == 250) & (df_mixed['Weather'] == 'ClearSky'))]
    df_mixed['DateTime'][4] = float('NaN')
    exclude_combos_with_range = [{'WindDeg': ['<=', 200]},
                                 {'Weather': 'ClearSky', 'Pressure': ['<', 1010]},
                                 {'DateTime': float('NaN')}]
    df_excluded = df_exclude_combos(df_mixed, exclude_combos_with_range)
    a=2

