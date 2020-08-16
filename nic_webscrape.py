import json, requests, bs4
import pandas as pd
from datetime import datetime, timedelta
from definitions import OPENWEATHER_API_KEY
import nic_misc as nm

# Gets weather data for past 5 days as well as
class WeatherData:

    # Updated when new data collected by get_all_weather_data()
    data_collected_machine_time = None
    data_collected_most_recent_utc_time = None
    data_collected_most_recent_local_time = None
    utc_time_delta = None


    def __init__(self, location_town = '', location_country = '', location_latlon = ()):

        self.location_town      = location_town                         # Set inputs to instance variables
        self.location_country   = location_country
        self.location_latlon    = location_latlon
        self.check_inputs()

        self.retrieved_data = self.get_all_weather_data()
        self.processed_data, self.processed_data_dict = self.process_all_weather_data()


    def check_inputs(self):

        # Check types
        if not (isinstance(self.location_town, str) and
                isinstance(self.location_country, str) and isinstance(self.location_latlon, tuple)):
            raise Exception('location_town, location_country and location_latlon must be of types string, string and tuple, respectively.')

        # Check location argument combination
        if self.location_town and self.location_latlon:
            raise Exception('Cannot specify location latlon and town at the same time.')
        if self.location_country and not self.location_town:
            raise Exception('Cannot specify location country without a town.')

        # Check latlon input tuple length and values
        if self.location_latlon:
            if len(self.location_latlon) != 2:
                raise Exception('location_latlon must be a tuple of length 2 (-90 <= latitude <= 90, -180 <= longitude <= 180).')
            if not -90 <= self.location_latlon[0] <= 90 or not -180 <= self.location_latlon[1] <= 180:
                raise Exception('location_latlon must be a tuple of length 2 (-90 <= latitude <= 90, -180 <= longitude <= 180).')

        if self.location_town:
            # Get or check the input country code
            if self.location_country:
                self.location_country = get_check_country_code(self.location_country)
            # Warning about ambiguous city
            else:
                print('WARNING: Town but no country specified - check that town retrieved is the one expected - e.g. London, CA vs. London, GB.')


    def get_all_weather_data(self):

        retrieved_data = {'future': {}, 'historical': {}}

        # If a town was specified...
        if self.location_town:
            # ... if country code specified, join it to the town
            loc = ','.join([self.location_town, self.location_country]) if self.location_country else self.location_town
            # ... first call just to get lat, lon to pass to a onecall call
            url = 'http://api.openweathermap.org/data/2.5/weather?q={}&APPID={}'.format(loc, OPENWEATHER_API_KEY)
            response = requests.get(url)
            try: response.raise_for_status()
            except: raise Exception(response.content)
            initial_data = json.loads(response.text)
            self.location_latlon = (initial_data['coord']['lat'], initial_data['coord']['lon'])
            # ... and also get country code if not already specified, alerting user to which country was chosen
            if not self.location_country:
                self.location_country = initial_data['sys']['country']
                print('WARNING: As no country was specified, automaticaly found data for '
                      'specified town {} in country {}.'.format(self.location_town, self.location_country))

        # Use the lat, lon for onecall call (current and future data)
        url = 'https://api.openweathermap.org/data/2.5/onecall?lat={}&lon={}&appid={}'.format(self.location_latlon[0], self.location_latlon[1], OPENWEATHER_API_KEY)
        response = requests.get(url)
        try: response.raise_for_status()
        except: raise Exception(response.content)
        retrieved_data['future'] = json.loads(response.text)

        # Use the lat, lon for timemachine call (historical data)
        for days_back in [1, 2, 3, 4, 5]:
            time = int(datetime.timestamp(datetime.now() - timedelta(days = days_back)))
            url = 'https://api.openweathermap.org/data/2.5/onecall/timemachine?lat={}&lon={}&dt={}&appid={}'.format(self.location_latlon[0], self.location_latlon[1], time, OPENWEATHER_API_KEY)
            response = requests.get(url)
            try: response.raise_for_status()
            except: raise Exception(response.content)
            retrieved_data['historical'][days_back] = json.loads(response.text)

        self.data_collected_machine_time = datetime.now()
        self.data_collected_most_recent_utc_time = datetime.utcfromtimestamp(retrieved_data['future']['current']['dt'])
        self.data_collected_most_recent_local_time = datetime.utcfromtimestamp(retrieved_data['future']['current']['dt'] + retrieved_data['future']['timezone_offset'])
        self.utc_time_delta = self.data_collected_most_recent_local_time - self.data_collected_most_recent_utc_time

        return retrieved_data


    # Processes the weather data into a chronological DataFrame form
    def process_all_weather_data(self):

        # Columns to extract (dicts mapping original data label to final DataFrame column label)
        cols_historical_hourly = {}
        for i in self.retrieved_data['historical'].keys():
            for el in self.retrieved_data['historical'][i]['hourly']:
                for key in el.keys():
                    cols_historical_hourly[key] = nm.to_pascal_case(key)

        cols_future_current = {el: nm.to_pascal_case(el) for el in self.retrieved_data['future']['current'].keys()}

        cols_future_hourly = {}
        for el in self.retrieved_data['future']['hourly']:
            for key in el.keys():
                cols_future_hourly[key] = nm.to_pascal_case(key)

        cols_future_daily = {}
        for el in self.retrieved_data['future']['daily']:
            for key in el.keys():
                cols_future_daily[key] = nm.to_pascal_case(key)

        all_cols = list(set(list(cols_historical_hourly.keys()) +
                            list(cols_future_current.keys())    +
                            list(cols_future_hourly.keys())     +
                            list(cols_future_daily.keys())))#      +
                           # ['HistoricalTodayForecast']))

        # Initialise dictionary for processed data
        processed_data_dict = {col: [] for col in all_cols}

        # Add the historical-hourly data
        for days_back in reversed(list(self.retrieved_data['historical'].keys())):
            for i in range(len(self.retrieved_data['historical'][days_back]['hourly'])):
                for k in all_cols:
                    if k in self.retrieved_data['historical'][days_back]['hourly'][i].keys():
                        v = self.retrieved_data['historical'][days_back]['hourly'][i][k]
                    else:
                        v = 'N/A'
                    if k == 'weather' and type(v) == list:
                        processed_data_dict[k].append(nm.to_pascal_case(v[0]['description']))
                    elif k == 'rain' and type(v) == dict:
                        processed_data_dict[k].append(list(v.values())[0])
                    # elif k == 'HistoricalTodayForecast':
                    #     processed_data_dict[k].append('Historical')
                    else:
                        processed_data_dict[k].append(v)

        # Add the current and future-hourly data
        for i in range(len(self.retrieved_data['future']['hourly'])):

            # The current data always occurs between i == 0 and i == 1 future-hourly data times
            if i == 1:
                for k in all_cols:
                    if k in self.retrieved_data['future']['current'].keys():
                        v = self.retrieved_data['future']['current'][k]
                    else:
                        v = 'N/A'
                    if k == 'weather':
                        processed_data_dict[k].append(nm.to_pascal_case(v[0]['description']))
                    elif k == 'rain' and type(v) == dict:
                        processed_data_dict[k].append(list(v.values())[0])
                    # elif k == 'HistoricalTodayForecast':
                    #     processed_data_dict[k].append('Today')
                    else:
                        processed_data_dict[k].append(v)

            for k in all_cols:
                if k in self.retrieved_data['future']['hourly'][i].keys():
                    v = self.retrieved_data['future']['hourly'][i][k]
                else:
                    v = 'N/A'
                if k == 'weather' and v != 'N/A':
                    processed_data_dict[k].append(nm.to_pascal_case(v[0]['description']))
                elif k == 'rain' and type(v) == dict:
                    processed_data_dict[k].append(list(v.values())[0])
                # elif k == 'HistoricalTodayForecast':
                #     # TODO: 'Today' is tomorrow
                #     if timestamps_are_same_day_in_local_time(self.retrieved_data['future']['hourly'][i]['dt'], self.retrieved_data['future']['current']['dt'], self.utc_time_delta):
                #         processed_data_dict[k].append('Today')
                #     else:
                #         processed_data_dict[k].append('Forecast')
                else:
                    processed_data_dict[k].append(v)

        # Add the future-daily data
        for i in range(len(self.retrieved_data['future']['daily'])):
            # Only need the future-daily data occurring after the future-hourly data ends
            if self.retrieved_data['future']['daily'][i]['dt'] > self.retrieved_data['future']['hourly'][-1]['dt']:
                for k in all_cols:
                    if k in self.retrieved_data['future']['daily'][i].keys():
                        v = self.retrieved_data['future']['daily'][i][k]
                    else:
                        v = 'N/A'
                    if k == 'weather' and v != 'N/A':
                        processed_data_dict[k].append(nm.to_pascal_case(v[0]['description']))
                    elif k == 'rain' and type(v) == dict:
                        processed_data_dict[k].append(list(v.values())[0])
                    # elif k == 'HistoricalTodayForecast':
                    #     processed_data_dict[k].append('Forecast')
                    else:
                        processed_data_dict[k].append(v)

        # Check that all the lists are the same length
        list_lengths = {col: len(processed_data_dict[col]) for col in all_cols}
        if not all([el == list(list_lengths.values())[0] for el in list_lengths.values()]):
            raise Exception('Not all lists of processed data are the same length, so cannot build chronological DataFrame of all retrieved data types.')

        # Make a DataFrame from the dict of lists and if not, warn the user that the code is suboptimal
        # and perform the reorder in the DataFrame (hopefully can be avoided above)
        processed_data_df = pd.DataFrame.from_dict(processed_data_dict)
        # processed_data_df['dt'] = processed_data_df['dt'].apply(lambda x: datetime.utcfromtimestamp(x) + self.utc_time_delta)

        # Check that the times are all in the correct order
        if sorted(processed_data_df['dt'].to_list()) != processed_data_df['dt'].to_list():
            print('WARNING: Data was not appended in flawless chronological order, so a DataFrame sort_values call is necessary (suboptimal code speed!)')
            processed_data_df.sort_values(by = 'dt')

        # TODO: rename columns
        return processed_data_df, processed_data_dict


# Checks that an input string is either a valid country code or a country name
# with a matching country code, returning the code in either case
def get_check_country_code(country_or_code):

    country_codes_df = wikipedia_table2df('ISO_3166-1_alpha-2', [2])['2']
    expected_cols = ['CODE', 'COUNTRY NAME (USING TITLE CASE)', 'YEAR', 'CCTLD', 'ISO 3166-2', 'NOTES']
    for col in expected_cols:
        if col not in country_codes_df.columns:
            raise Exception('Unexpected country codes reference table retrieved from Wikipedia.')
    if country_codes_df.shape[0] < 200:
        raise Exception('Unexpected country codes reference table retrieved from Wikipedia.')

    country_or_code = country_or_code.upper()
    if country_codes_df[country_codes_df.CODE == country_or_code].shape[0] == 1:
        return country_or_code
    else:
        for country in country_codes_df['COUNTRY NAME (USING TITLE CASE)']:
            if country.upper() == country_or_code:
                return country_codes_df[country_codes_df['COUNTRY NAME (USING TITLE CASE)'] == country]['CODE'].iloc[0]
        raise Exception('Invalid country or country code requested.')

# TODO: option to save to xlsx
# TODO: https://en.wikipedia.org/wiki/New_York_City borough as a multiindex dataframe
def wikipedia_table2df(wikipedia_URL, table_indices = 'all', can_clip_data = False):

    # If only an article title URL portion was given, assume it is from English language wikipedia
    if 'https://' not in wikipedia_URL:
        wikipedia_URL = 'https://en.wikipedia.org/wiki/' + wikipedia_URL.replace(' ','_')

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
        if table_index < len(tables):
            table = tables[table_index]
            rows = []

            for i, this_row in enumerate(table.find_all('tr')):
                # Get the row elements (td)
                row_elems = this_row.find_all('td')

                # And the row labels (th)
                labels = this_row.find_all('th')

                # If there is a single label but no data entries in the first row, it is the table title
                if len(labels) == 1 and not row_elems and i == 0:
                    title = labels[0].text.strip().upper()
                    if len(title) > 25: title = title[:25]
                # If there is a single label but not data entries in a subsequent row, treat it as a single element
                elif len(labels) == 1 and not row_elems and i > 0:
                    rows.append([labels[0].text.strip().upper()])
                # If there are multiple labels and no no data entries, they are column labels (if not yet filled)
                elif len(labels) > 1 and not row_elems and not col_labels:
                    col_labels = [label.text.strip().upper() for label in labels]
                # If there is a single row label and some row elements, add the label to the row labels
                elif len(labels) == 1 and row_elems:
                    row_labels.append(labels[0].text.strip().upper())
                    # Also, if the col_labels are one more than a labelled row, remove the first of them (because it is just a redundant classifier for the column labels)
                    if len(col_labels) == len(row_elems) + 1:
                        col_labels.pop(0)
                # If there are elements, add them as a row, unless there is only one, is at the bottom of the table, and has no label when the others did have labels
                if row_elems and not (i == len(table.find_all('tr')) - 1 and not labels and len(row_labels)>0):
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

def timestamps_are_same_day_in_local_time(ts1, ts2, utc_time_delta):

    if isinstance(ts1, int): ts1 = datetime.utcfromtimestamp(ts1) + utc_time_delta
    if isinstance(ts2, int): ts2 = datetime.utcfromtimestamp(ts2) + utc_time_delta

    if ts1.date() == ts2.date():
        return True
    return False



if __name__ == '__main__':
    wd = WeatherData('New York')

    import matplotlib.pyplot as plt
    plt.scatter(wd.processed_data['dt'].iloc[:168], wd.processed_data['temp'].iloc[:168])



