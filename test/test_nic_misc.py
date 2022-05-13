import pytest
import pandas as pd
from datetime import datetime
from pathlib import Path
import os
import shutil

from nic_testing import check_raises
from nicpy.nic_misc import (mkdir_if_DNE,
                            df_latest_row,
                            df_exclude_combos,
                            exponential_MA,
                            txt_vectors_to_df,
                            business_date_shift)

def test_mkdir_if_DNE():
    """
    Test the mkdir_if_DNE() function.
    """
    cwd = Path.cwd()
    create = cwd / 'test_dir' / 'nested_test_dir'
    assert not create.exists() and not create.parent.exists()
    mkdir_if_DNE(create)
    assert create.exists() and create.parent.exists()
    os.rmdir(create)
    assert not create.exists() and create.parent.exists()
    os.rmdir(create.parent)
    assert not create.exists() and not create.parent.exists()

def test_exponential_MA():
    """
    Test the exponential_MA() function.
    """

    # Failure if times and data are not the same length
    dt = [datetime(2020, 1, 1), datetime(2020, 1, 2)]
    data = [4.6, 7.8, 10.1]
    tau = 0.5
    check_raises(Exception, 'Must input equal length datetimes and data vectors.', exponential_MA, dt, data, tau)

    # Failure if times are not sequential
    dt = [datetime(2020, 1, 1), datetime(2020, 1, 3), datetime(2020, 1, 2)]
    check_raises(Exception, 'Datetimes must be strictly increasing.', exponential_MA, dt, data, tau)

    dt = [datetime(2020, 1, 1), datetime(2020, 1, 3), datetime(2020, 1, 3)]
    check_raises(Exception, 'Datetimes must be strictly increasing.', exponential_MA, dt, data, tau)

    # Failure if tau is not positive
    dt = [datetime(2020, 1, 1), datetime(2020, 1, 2), datetime(2020, 1, 3)]
    tau = -0.5
    check_raises(Exception, 'tau smoothing parameter must be positive.', exponential_MA, dt, data, tau)

    tau = 0
    check_raises(Exception, 'tau smoothing parameter must be positive.', exponential_MA, dt, data, tau)



    # Check result same length as input data
    tau = 0.5
    smoothed = exponential_MA(dt, data, 0.5)
    assert len(smoothed) == len(dt)

def test_txt_vectors_to_df():
    """
    Test the txt_vectors_to_df() function.
    """
    separator_char = ','

    # Create some text files to test
    cwd = Path.cwd()
    temp_dir = cwd / 'temp_txt'
    mkdir_if_DNE(temp_dir)
    for num in [3, 4, 5]:
        f = open(temp_dir / '{}.txt'.format(num), 'w+')
        for i in range(num):
            f.write(str(i) + separator_char)
        f.close()

    # If ignoring empty, the final commas in above files are ignored
    df = txt_vectors_to_df(temp_dir, separator_char, ignore_empty=True)
    assert df.shape == (5, 3)
    assert list(df.columns) == ['3', '4', '5']
    assert df['3'].equals(pd.Series(['0', '1', '2', '', '']))
    assert df['4'].equals(pd.Series(['0', '1', '2', '3', '']))
    assert df['5'].equals(pd.Series(['0', '1', '2', '3', '4']))

    # Otherwise the DataFrame should be one row longer
    df = txt_vectors_to_df(temp_dir, separator_char, ignore_empty=False)
    assert df.shape == (6, 3)
    assert list(df.columns) == ['3', '4', '5']
    assert df['3'].equals(pd.Series(['0', '1', '2', '', '', '']))
    assert df['4'].equals(pd.Series(['0', '1', '2', '3', '', '']))
    assert df['5'].equals(pd.Series(['0', '1', '2', '3', '4', '']))

    # Delete the files
    shutil.rmtree(temp_dir)

def test_business_date_shift():

    # Fails if reference date is not a business date

    # Fails if unknown country string

    # Correct result intra-week with no public holidays
    monday = datetime(2022, 1, 24)
    assert business_date_shift(monday, 3, 'US') == datetime(2022, 1, 27)

    # Correct result for known weekend without any public holidays
    assert business_date_shift(monday, 5, 'US') == datetime(2022, 1, 31)

    # Correct result for known public holiday (Monday 4th July 2022)
    monday = datetime(2022, 6, 27)
    assert business_date_shift(monday, 5, 'US') == datetime(2022, 7, 5)



def test_df_exclude_combos():
    """
    Test the df_exclude_combos() function.
    """
    # Create some test data
    df = pd.DataFrame({'Weather': ['Cloudy', 'Sunny', 'Sunny', 'Sunny', 'Cloudy'],
                       'Temp': [10, 20, 30, 25, 22]})

    # Testing with single conditions
    df_excluded = df_exclude_combos(df, [{'Weather': ['==', 'Cloudy']}])
    assert df_excluded.equals(df[df['Weather']!='Cloudy'])
    assert df_excluded.shape[0] == 3

    # Testing with two conditions (and)
    df_excluded = df_exclude_combos(df, [{'Weather': ['==', 'Cloudy'], 'Temp': ['<', 15]}])
    assert df_excluded.equals(df[~((df['Temp'] < 15) & (df['Weather'] == 'Cloudy'))])
    assert df_excluded.shape[0] == 4

    df_excluded = df_exclude_combos(df, [{'Weather': ['==', 'Cloudy'], 'Temp': 10}])
    assert df_excluded.equals(df[~((df['Temp'] == 10) & (df['Weather'] == 'Cloudy'))])
    assert df_excluded.shape[0] == 4

    # Testing with three conditions (and + or)
    df_excluded = df_exclude_combos(df, [{'Weather': ['==', 'Cloudy'], 'Temp': 10},
                                         {'Weather': ['==', 'Sunny']}])
    assert df_excluded.shape[0] == 1

def test_df_latest_row():
    """
    Test the df_latest_row() function.
    """

    # Data to test on
    df = pd.DataFrame(
        {'Time': [datetime(2020, 10, 11), datetime(2020, 10, 13), datetime(2020, 10, 19), datetime(2020, 10, 21)],
         'Value': [6, 2, 4, 2]})

    # If less_than_value between indices, should return the lower index
    less_than_value = datetime(2020, 10, 15)
    idx = df_latest_row(df, 'Time', less_than_value)
    assert idx == 1

    # If less_than_value matches an index, should return the index before
    less_than_value = datetime(2020, 10, 21)
    idx = df_latest_row(df, 'Time', less_than_value)
    assert idx == 2

    # If less_than_value matches an index and we correctly know a lowest_index, should get same result as above
    idx = df_latest_row(df, 'Time', less_than_value, 0)
    assert idx == 2
    idx = df_latest_row(df, 'Time', less_than_value, 1)
    assert idx == 2
    idx = df_latest_row(df, 'Time', less_than_value, 2)
    assert idx == 2

    # If time ordering value at lowest_idx >= the less_than_value, should raise exception
    with pytest.raises(Exception) as excinfo:
        idx = df_latest_row(df, 'Time', less_than_value, 3)
    assert 'Bad lowest_idx - value >= less_than_value.' == str(excinfo.value)

    # If time lowest_idx out of bounds, should raise exception
    with pytest.raises(Exception) as excinfo:
        idx = df_latest_row(df, 'Time', less_than_value, 4)
    assert 'Bad lowest_idx - out of bounds.' == str(excinfo.value)
