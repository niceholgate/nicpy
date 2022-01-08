import pytest
import pandas as pd
from datetime import datetime
from nicpy.nic_misc import df_latest_row, df_exclude_combos
from nic_webscrape import WeatherData
import yfinance as yf

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
