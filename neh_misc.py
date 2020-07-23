from datetime import datetime, date, timedelta
import logging
import businesstime as bt
import pandas as pd
import numpy as np
import requests
import bs4
import string
from pathlib import Path
# from android.storage import app_storage_path, primary_external_storage_path, secondary_external_storage_path

# Get all of the integers in a string
def ints_in_str(string):
    return int(''.join(x for x in string if x.isdigit()))

def get_YYYYMMDDHHMMSS_string(datetime, connector1, connector2):

    YYYY, month, day = str(datetime.year), str(datetime.month), str(datetime.day)
    hours, mins, secs = str(datetime.hour), str(datetime.minute), str(datetime.second)
    MM = month if len(month) == 2 else '0' + month
    DD = day if len(day) == 2 else '0' + day
    hh = hours if len(hours) == 2 else '0' + hours
    mm = mins if len(mins) == 2 else '0' + mins
    ss = secs if len(secs) == 2 else '0' + secs

    return connector1.join([YYYY, MM, DD]) + ' ' + connector2.join([hh, mm, ss])


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


def get_parameter_string(parameters):

    parameter_string = '_'.join([parameter+'='+str(parameters[parameter]) for parameter in parameters.keys()])

    return parameter_string


def logging_setup(base_directory):
    file_name = '{}_{}.log'.format(today_date, get_YYYYMMDDHHMMSS_string(datetime.now(), '-', ';'))
    stream_h = logging.StreamHandler()
    file_h = logging.FileHandler("{0}/{1}".format(base_directory + '/logs', file_name))
    stream_h.setLevel('INFO')
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s [%(threadName)s] [%(levelname)s]  %(message)s",
                        handlers=[file_h, stream_h])


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

# TODO: option to save to xlsx
# TODO: https://en.wikipedia.org/wiki/New_York_City borough as a multiindex dataframe
def wikipedia_table2df(wikipedia_URL, table_indices = 'all', can_clip_data = False):

    # If only an article title URL portion was given, assume it is from English language wikipedia
    if 'https://' not in wikipedia_URL:
        wikipedia_URL.replace(' ','_')
        wikipedia_URL = 'https://en.wikipedia.org/wiki/' + wikipedia_URL

    # Get the webpage data
    res = requests.get(wikipedia_URL)
    res.raise_for_status()

    # Find the tables
    soup = bs4.BeautifulSoup(res.text, 'html.parser')
    tables = soup.findAll('table')
    if table_indices == 'all':
        table_indices = list(range(len(tables)))
    if type(table_indices) != list:
        raise Exception('Can only specify which table_indices to download as a list or \'all\'.')

    dfs = {}
    for table_index in table_indices:
        row_labels = []
        col_labels = []
        title = str(table_index)        # default title is just the list index of the table as pulled by request
        if table_index<len(tables):
            table = tables[table_index]
            rows = []

            for i, this_row in enumerate(table.find_all('tr')):
                # Get the row elements (td)
                row_elems = this_row.find_all('td')

                # And the row labels (th)
                labels = this_row.find_all('th')

                # If there is a single label but no data entries in the first row, it is the table title
                if len(labels)==1 and not row_elems and i==0:
                    title = labels[0].text.strip().upper()
                    if len(title)>25: title = title[:25]
                # If there is a single label but not data entries in a subsequent row, treat it as a single element
                elif len(labels)==1 and not row_elems and i>0:
                    rows.append([labels[0].text.strip().upper()])
                # If there are multiple labels and no no data entries, they are column labels (if not yet filled)
                elif len(labels) > 1 and not row_elems and not col_labels:
                    col_labels = [label.text.strip().upper() for label in labels]
                # If there is a single row label and some row elements, add the label to the row labels
                elif len(labels) == 1 and row_elems:
                    row_labels.append(labels[0].text.strip().upper())
                    # Also, if the col_labels are one more than a labelled row, remove the first of them (because it is just a redundant classifier for the column labels)
                    if len(col_labels)==len(row_elems)+1:
                        col_labels.pop(0)
                # If there are elements, add them as a row, unless there is only one, is at the bottom of the table, and has no label when the others did have labels
                if row_elems and not (i==len(table.find_all('tr'))-1 and not labels and len(row_labels)>0):
                    rows.append([elem.text.strip() for elem in row_elems])

            # Get the max row length
            max_row_length = max([len(row) for row in rows])

            # If any rows are shorter than the max row, append None until all rows have the max elements
            for row in rows:
                while len(row) < max_row_length:
                    row.append(None)

            # Can only use the column labels if there is one per column
            df_cols = col_labels if len(col_labels) == len(rows[0]) else [str(i) for i in range(len(rows[0]))]

            # Can only use the row labels if there is one per row
            df_rows = row_labels if row_labels and len(row_labels)==len(rows) else list(range(len(rows)))
            dfs[title] = pd.DataFrame(rows, index = df_rows, columns = df_cols)

    return dfs

def count_text_occurrences(text, search_string, case_sensitive, whole_phrase_only, get_line_numbers = False):
    search_in_string = text if case_sensitive else text.upper()
    search_string_test = search_string if case_sensitive else search_string.upper()
    line_numbers = []
    if len(search_string) == len(search_in_string):
        occurrences = 1 if search_in_string == search_string_test else 0
    elif len(search_string) > len(text):
        occurrences = 0
    elif len(search_string) < len(text):
        occurrences = 0
        for i in range(len(search_in_string) - len(search_string) + 1):
            # TODO: check this is searching the whole paragraph
            text_portion = search_in_string[i:i + len(search_string)]
            if whole_phrase_only:
                if text_portion == search_string_test:
                    if (i == 0) and (text[i + len(search_string_test)] in (string.whitespace + string.punctuation)):
                        occurrences += 1
                        if get_line_numbers:
                            if not line_numbers:
                                line_numbers = [text[:i].count('\n')+1]
                            else:
                                line_numbers.append(line_numbers[-1]+text[last_i+len(search_string)-1:i].count('\n'))
                            last_i = i

                    elif (i == len(text) - len(search_string)) and (text[i - 1] in (string.whitespace + string.punctuation)):
                        occurrences += 1
                        if get_line_numbers:
                            if not line_numbers:
                                line_numbers = [text[:i].count('\n')+1]
                            else:
                                line_numbers.append(line_numbers[-1]+text[last_i+len(search_string)-1:i].count('\n'))
                            last_i = i

                    elif (i > 0) and (i < len(text) - len(search_string)):
                        if (text[i - 1] in (string.whitespace + string.punctuation)) and (text[i + len(search_string_test)] in (string.whitespace + string.punctuation)):
                            occurrences += 1
                            if get_line_numbers:
                                if not line_numbers:
                                    line_numbers = [text[:i].count('\n') + 1]
                                else:
                                    line_numbers.append(line_numbers[-1] + text[last_i + len(search_string) - 1:i].count('\n'))
                                last_i = i
            else:
                if text_portion == search_string_test:
                    occurrences += 1
                    if get_line_numbers:
                        if not line_numbers:
                            line_numbers = [text[:i].count('\n') + 1]
                        else:
                            line_numbers.append(line_numbers[-1] + text[last_i + len(search_string) - 1:i].count('\n'))
                        last_i = i

    if get_line_numbers: return line_numbers
    return occurrences


def txt_vectors_to_df(txts_directory, separator_char):
    files = os.listdir(str(txts_directory))
    text_file_paths += [Path(txts_directory) / file for file in files if  # '~$' files are temporary Office files present when the main file is opened
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