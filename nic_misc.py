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

from nicpy import nic_str

def mkdir_if_DNE(directory):
    """
    Creates a new directory (lowest level all the way up to final nested folder).
    :param directory: pathlib.Path object representing new directory
    :return: None
    """

    if not isinstance(directory, Path):
        raise Exception('Input should be a pathlib.Path object.')

    folders_to_create = []
    ancestor = directory
    while ancestor != Path(directory.anchor) and not ancestor.exists():
        folders_to_create.append(ancestor.stem)
        ancestor = ancestor.parent
    for folder in reversed(folders_to_create):
        ancestor = ancestor/folder
        ancestor.mkdir()

def exponential_MA(datetimes, data, tau):
    """
    Exponential moving average.
    :param datetimes: Datetimes
    :param data: Numerical data to smooth
    :param tau: Smoothing parameter
    :return:
    """

    if tau <= 0:
        raise Exception('tau smoothing parameter must be positive.')
    datetimes, data = list(datetimes), list(data)
    if len(datetimes) != len(data):
        raise Exception('Must input equal length datetimes and data vectors.')
    smoothed = [data[0]]
    for i in range(1, len(datetimes)):
        time_delta_seconds = (datetimes[i]-datetimes[i-1]).total_seconds()
        if time_delta_seconds <= 0:
            raise Exception('Datetimes must be strictly increasing.')
        w = np.exp(-time_delta_seconds/60/60/24/tau)
        smoothed.append(w*smoothed[-1]+(1-w)*data[i])

    return smoothed

def txt_vectors_to_df(txts_directory, separator_char, ignore_empty=False):
    """
    # Creates a DataFrame from a series of text files, with each file as a column.
    :param txts_directory: Directory in which to search for .txt files
    :param separator_char: Value separation character e.g. ',' , '/' , ';'
    :param ignore_empty: Exclude empty values found in the .txt lists
    :return:
    """
    files = os.listdir(str(txts_directory))
    text_file_paths = [Path(txts_directory) / file for file in files if  # '~$' files are temporary Office files present when the main file is opened
                             ((Path(txts_directory) / file).suffix == '.txt') and ('~$' not in str(Path(txts_directory) / file))]
    data_dict = {}
    max_len = 0
    for file_path in text_file_paths:
        file = open(str(file_path), 'r')
        data_name = file_path.stem
        file_text = file.read()
        data_dict[data_name] = file_text.split(separator_char)
        if ignore_empty:
            data_dict[data_name] = [el for el in data_dict[data_name] if el != '']
        if len(data_dict[data_name]) > max_len:
            max_len = len(data_dict[data_name])

    # Append empty strings to any lists which are shorter than the max_len
    for k, v in data_dict.items():
        this_len = len(v)
        if max_len - this_len > 0:
            for _ in range(max_len - this_len):
                v.append('')

    return pd.DataFrame(data_dict)

# TODO: test this, move to a logging helpers file?
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


def business_date_shift(business_date_reference, business_day_delta, country_string):

    # Convert days delta to years delta to get approximate range of necessary holidays data
    now_year = business_date_reference.year
    years_delta = int(np.ceil(abs(business_day_delta/365)))
    years_list = list(range(now_year-years_delta, now_year+years_delta+1))

    # TODO: need to add holidays data control for more countries and states
    if country_string == 'AU':
        country_holidays = holidays.AU(years=years_list)
    elif country_string == 'UK':
        country_holidays = holidays.UK(years=years_list)
    elif country_string == 'US':
        country_holidays = holidays.US(years=years_list)
    else:
        raise Exception('Unknown country string, cannot get holiday data.')

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
    """
    Easily and succinctly exclude combinations of conditions from a DataFrame.
    :param df: DataFrame
    :param exclude_combos: a list of dicts, each being a combo to exclude
    :return: DataFrame without the specified rows
    """
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


# For a DataFrame assumed to be pre-sorted by the given column, return the row index with the greatest value in that
# column but lower than specified value.
# e.g. for getting the most recent data as of 'now' in a historical time series
# lowest_idx is an index before which the greatest value is already known not to be
def df_latest_row(df: pd.DataFrame, column: str, less_than_value, lowest_idx=None):

    # If the first idx is unavailable or has value actually >= less than value, error
    if lowest_idx:
        if lowest_idx > df.shape[0]-1:
            raise Exception('Bad lowest_idx - out of bounds.')
        if df[column].iat[lowest_idx] >= less_than_value:
            raise Exception('Bad lowest_idx - value >= less_than_value.')

    # If df is empty, return None
    if df.empty:
        return None

    idx = lowest_idx if lowest_idx else 0

    # If the first idx is >= less_than_value, return None
    if df[column].iat[idx] >= less_than_value:
        return None

    while df[column].iat[idx] < less_than_value:
        idx += 1
    return idx-1


# Check if two datetimes occur on the same weekend
def same_weekend(dt1, dt2):
    if not isinstance(dt1, datetime) or not isinstance(dt2, datetime):
        raise TypeError('dt1 and dt2 must both be datetimes, but instead received types {} and {}.'.format(type(dt1), type(dt2)))
    weekend_days = [5, 6]
    if dt1.weekday() in weekend_days and dt2.weekday() in weekend_days:
        if abs(dt1-dt2) < timedelta(days=2):
            return True
    return False

