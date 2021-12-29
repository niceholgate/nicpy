import json, requests, bs4
import pandas as pd
from datetime import datetime, timedelta
from definitions import OPENWEATHER_API_KEY
import matplotlib.pyplot as plt
import matplotlib.patches as ptc
import nic_str as ns
import nic_plot
from nicpy.nic_data_structs import CacheDict
from pathlib import Path

# Gets weather data for past 5 days as well as
class WeatherData:

    # Updated when new data collected by get_all_weather_data()
    data_collected_machine_time = None
    data_collected_most_recent_utc_time = None
    data_collected_most_recent_local_time = None
    utc_time_delta = None
    unix_utc_to_local = None

    legend_bbox_to_anchor = (0, 0)

    def __init__(self, location_town = '', location_country = '', location_latlon = ()):

        self.location_town      = location_town.title()                         # Set inputs to instance variables
        self.location_country   = location_country.title()
        self.location_latlon    = location_latlon
        self._check_inputs()

        self.retrieved_data = self._get_all_weather_data()
        self.processed_data = self._process_all_weather_data()

    def _check_inputs(self):

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
            if self.location_country: self.location_country = get_check_country_code(self.location_country)[1]
            # Warning about ambiguous city
            else: print('WARNING: Town but no country specified - check that town retrieved is the one expected - e.g. London, CA vs. London, GB.')

    def _get_all_weather_data(self):

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
                self.location_country = get_check_country_code(initial_data['sys']['country'])[1]
                print('WARNING: As no country was specified, automatically found data for '
                      'specified town {} in country {}.'.format(self.location_town, self.location_country))

        # Use the lat, lon for onecall call (current and future data)
        url = 'https://api.openweathermap.org/data/2.5/onecall?lat={}&lon={}&appid={}'.format(self.location_latlon[0], self.location_latlon[1], OPENWEATHER_API_KEY)
        response = requests.get(url)
        try: response.raise_for_status()
        except: raise Exception(response.content)
        retrieved_data['future'] = json.loads(response.text)

        # Use the lat, lon for timemachine call (historical data)
        for days_back in [0, 1, 2, 3, 4, 5]:
            time = int(retrieved_data['future']['current']['dt'] - timedelta(days = days_back).total_seconds())
            url = 'https://api.openweathermap.org/data/2.5/onecall/timemachine?lat={}&lon={}&dt={}&appid={}'.format(self.location_latlon[0], self.location_latlon[1], time, OPENWEATHER_API_KEY)
            response = requests.get(url)
            try: response.raise_for_status()
            except: raise Exception(response.content)
            retrieved_data['historical'][days_back] = json.loads(response.text)

        self.data_collected_machine_time = datetime.now()
        self.data_collected_most_recent_utc_time = datetime.utcfromtimestamp(retrieved_data['future']['current']['dt'])
        self.data_collected_most_recent_local_time = datetime.utcfromtimestamp(retrieved_data['future']['current']['dt'] + retrieved_data['future']['timezone_offset'])
        self.utc_time_delta = self.data_collected_most_recent_local_time - self.data_collected_most_recent_utc_time
        self.unix_utc_to_local = lambda x: datetime.utcfromtimestamp(x) + self.utc_time_delta

        return retrieved_data

    # Processes the weather data into a chronological DataFrame form
    def _process_all_weather_data(self):

        # Columns to extract to a processed DataFrame
        all_cols = []
        for i in self.retrieved_data['historical'].keys():
            for el in self.retrieved_data['historical'][i]['hourly']:
                for key in el.keys():
                    if key not in all_cols: all_cols.append(key)

        for key in self.retrieved_data['future']['current'].keys():
            if key not in all_cols: all_cols.append(key)

        for el in self.retrieved_data['future']['hourly']:
            for key in el.keys():
                if key not in all_cols: all_cols.append(key)

        for el in self.retrieved_data['future']['daily']:
            for key in el.keys():
                if key not in all_cols: all_cols.append(key)

        # Initialise dictionary for processed data
        processed_data_dict = {col: [] for col in all_cols}

        # Add the historical-hourly data
        for days_back in reversed(list(self.retrieved_data['historical'].keys())):
            for i in range(len(self.retrieved_data['historical'][days_back]['hourly'])):
                for k in all_cols:
                    if k in self.retrieved_data['historical'][days_back]['hourly'][i].keys(): v = self.retrieved_data['historical'][days_back]['hourly'][i][k]
                    else: v = 'N/A'
                    if k == 'weather' and type(v) == list: processed_data_dict[k].append(ns.to_pascal_case(v[0]['description']))
                    elif k in ['rain', 'snow'] and type(v) == dict:
                        if len(v.values()) > 0:
                            processed_data_dict[k].append(list(v.values())[0])
                        else:
                            processed_data_dict[k].append('N/A')
                    else: processed_data_dict[k].append(v)

        # Add the current and future-hourly data
        for i in range(len(self.retrieved_data['future']['hourly'])):

            # The current data always occurs between i == 0 and i == 1 future-hourly data times
            if i == 1:
                for k in all_cols:
                    if k in self.retrieved_data['future']['current'].keys(): v = self.retrieved_data['future']['current'][k]
                    else: v = 'N/A'
                    if k == 'weather': processed_data_dict[k].append(ns.to_pascal_case(v[0]['description']))
                    elif k in ['rain', 'snow'] and type(v) == dict:
                        if len(v.values()) > 0:
                            processed_data_dict[k].append(list(v.values())[0])
                        else:
                            processed_data_dict[k].append('N/A')
                    else: processed_data_dict[k].append(v)

            for k in all_cols:
                if k in self.retrieved_data['future']['hourly'][i].keys(): v = self.retrieved_data['future']['hourly'][i][k]
                else: v = 'N/A'
                if k == 'weather' and v != 'N/A': processed_data_dict[k].append(ns.to_pascal_case(v[0]['description']))
                elif k in ['rain', 'snow'] and type(v) == dict:
                    if len(v.values()) > 0:
                        processed_data_dict[k].append(list(v.values())[0])
                    else:
                        processed_data_dict[k].append('N/A')
                else: processed_data_dict[k].append(v)

        # Add the future-daily data
        for i in range(len(self.retrieved_data['future']['daily'])):
            # Only need the future-daily data occurring after the future-hourly data ends
            if self.retrieved_data['future']['daily'][i]['dt'] > self.retrieved_data['future']['hourly'][-1]['dt']:
                for k in all_cols:
                    if k in self.retrieved_data['future']['daily'][i].keys(): v = self.retrieved_data['future']['daily'][i][k]
                    else: v = 'N/A'
                    if k == 'weather' and v != 'N/A': processed_data_dict[k].append(ns.to_pascal_case(v[0]['description']))
                    elif k in ['rain', 'snow'] and type(v) == dict:
                        if len(v.values()) > 0:
                            processed_data_dict[k].append(list(v.values())[0])
                        else:
                            processed_data_dict[k].append('N/A')
                    else: processed_data_dict[k].append(v)

        # Check that all the lists are the same length
        list_lengths = {col: len(processed_data_dict[col]) for col in all_cols}
        if not all([el == list(list_lengths.values())[0] for el in list_lengths.values()]):
            raise Exception('Not all lists of processed data are the same length, so cannot build chronological DataFrame of all retrieved data types.')

        # Make a DataFrame from the dict of lists and if not, warn the user that the code is suboptimal
        # and perform the reorder in the DataFrame (hopefully can be avoided above)
        processed_data_df = pd.DataFrame.from_dict(processed_data_dict)
        if sorted(processed_data_df['dt'].to_list()) != processed_data_df['dt'].to_list():
            print('WARNING: Data was not appended in flawless chronological order, so a DataFrame sort_values call is necessary (suboptimal code speed!)')
            processed_data_df.sort_values(by = 'dt')

        # Create a new column for local time and rename the columns to use PascalCase
        processed_data_df['dt_local'] = processed_data_df['dt'].apply(self.unix_utc_to_local)
        processed_data_df.rename(columns=ns.to_pascal_case, inplace=True)
        processed_data_df.rename(columns={'Temp': 'TempK',
                                          'FeelsLike': 'FeelsLikeK',
                                          'Dt': 'DateTime',
                                          'DtLocal': 'DateTimeLocal',
                                          'Uvi': 'UVI',
                                          'Pop': 'PoP'}, inplace=True)

        # Create TempC/TempF and FeelsLikeC/FeelsLikeF columns
        processed_data_df['TempC'] = processed_data_df['TempK'].apply(lambda x: {el: x[el]-273.15 for el in x.keys()} if isinstance(x, dict) else x-273.15)
        processed_data_df['TempF'] = processed_data_df['TempC'].apply(lambda x: {el: x[el]*9/5+32 for el in x.keys()} if isinstance(x, dict) else x*9/5+32)
        processed_data_df['FeelsLikeC'] = processed_data_df['FeelsLikeK'].apply(lambda x: {el: x[el] - 273.15 for el in x.keys()} if isinstance(x, dict) else x - 273.15)
        processed_data_df['FeelsLikeF'] = processed_data_df['FeelsLikeC'].apply(lambda x: {el: x[el] * 9 / 5 + 32 for el in x.keys()} if isinstance(x, dict) else x * 9 / 5 + 32)

        return processed_data_df

    def plot_future(self, temp_scale, show_time_now=True, show_days_background=True):

        today_date = self.data_collected_most_recent_local_time.date()
        for i in range(self.processed_data.shape[0]):
            if self.processed_data['DateTimeLocal'].iloc[i].date() == today_date:
                first_today_index = i
                break

        dict_indices = [i for i in range(self.processed_data.shape[0]) if type(self.processed_data['Temp' + temp_scale.upper()].iloc[i]) == dict]
        first_date, last_date = self.processed_data['DateTimeLocal'].iloc[0].date(), self.processed_data['DateTimeLocal'].iloc[dict_indices[-1]].date()
        temp_window = self.processed_data.iloc[first_today_index:dict_indices[0]]
        other_window = self.processed_data.iloc[first_today_index:]

        fig = plt.figure(figsize=(20,10))

        # Temp, feels_like
        ax1 = fig.add_subplot(411)
        ax1.plot(temp_window['DateTimeLocal'], temp_window['Temp' + temp_scale.upper()], 'mo-', label='Temperature ({})'.format(temp_scale.upper()))
        ax1.plot(temp_window['DateTimeLocal'], temp_window['FeelsLike' + temp_scale.upper()], 'gs-', label='Feels-like temperature ({})'.format(temp_scale.upper()))
        dict_times, dict_mins, dict_maxs = [], [], []
        for i in dict_indices:
            ax1.plot([self.processed_data['DateTimeLocal'].iloc[i], self.processed_data['DateTimeLocal'].iloc[i]],
                     [self.processed_data['Temp' + temp_scale.upper()].iloc[i]['min'], self.processed_data['Temp' + temp_scale.upper()].iloc[i]['max']], c=[0.6, 0.6, 0.6], zorder=10)
            dict_times.append(self.processed_data['DateTimeLocal'].iloc[i])
            dict_maxs.append(self.processed_data['Temp' + temp_scale.upper()].iloc[i]['max'])
            dict_mins.append(self.processed_data['Temp' + temp_scale.upper()].iloc[i]['min'])
        ax1.scatter(dict_times, dict_maxs, c='r', marker='^', zorder=11, label='Daily max ({})'.format(temp_scale.upper()))
        ax1.scatter(dict_times, dict_mins, c='b', marker='v', zorder=12, label='Daily min ({})'.format(temp_scale.upper()))
        ax1.legend(loc='upper right',   framealpha=0.5)
        self._lock_axes_limits(ax1)
        if show_time_now: self._show_time_now(ax1)
        if show_days_background: self._show_days_background(ax1, first_date, last_date)
        nic_plot.nic_standard_axes(ax1, xlabel='Time', ylabel='Temp ({})'.format(temp_scale.upper()))

        # Humidity, clouds
        ax2 = fig.add_subplot(412)
        ax2.plot(other_window['DateTimeLocal'], other_window['Humidity'], 'bo-', zorder=200, label='Humidity (%)')
        ax2.plot(other_window['DateTimeLocal'], other_window['Clouds'], 'cs-', zorder=201, label='Clouds (%)')
        ax2.legend(loc='upper right', framealpha=0.5)
        self._lock_axes_limits(ax2)
        if show_time_now: self._show_time_now(ax2)
        if show_days_background: self._show_days_background(ax2, first_date, last_date)
        nic_plot.nic_standard_axes(ax2, ylabel='Humidity/Clouds (%)')

        # Wind speed, wind direction
        ax3 = fig.add_subplot(413)
        windspeed = ax3.plot(other_window['DateTimeLocal'], other_window['WindSpeed'], 'gs-', zorder=202, label='Wind speed (m/s)')
        nic_plot.nic_standard_axes(ax3, ylabel='Wind speed\n(m/s)', ylabelcolor='g')
        ax4 = ax3.twinx()
        winddir = ax4.plot(other_window['DateTimeLocal'], other_window['WindDeg'], 'r^-', zorder=203, label='Wind direction (deg)')
        self._lock_axes_limits(ax4)
        if show_time_now: self._show_time_now(ax4)
        if show_days_background: self._show_days_background(ax3, first_date, last_date)
        nic_plot.nic_standard_axes(ax4, ylabel='Wind direction\n(deg)', ylabelcolor='r')
        ax4.legend(windspeed + winddir, [l.get_label() for l in (windspeed + winddir)], loc='upper right',   framealpha=0.5)

        # Rain, snow, pop, weather
        ax5 = fig.add_subplot(414)
        l = {}
        if 'PoP' in other_window.columns:
            not_NA_pop = other_window[other_window['PoP'] != 'N/A']
            if not not_NA_pop.empty:
                l['PoP'] = ax5.plot(not_NA_pop['DateTimeLocal'], not_NA_pop['PoP'], 'mv:', zorder=210, label='Chance of precipitation (%)')
        nic_plot.nic_standard_axes(ax5, xlabel='Time', ylabel='Chance of precipitation\n(%)', ylabelcolor='m')

        ax6 = ax5.twinx()
        if 'Rain' in other_window.columns and other_window['Rain'].shape[0] > 0:
            not_NA_rain = other_window[other_window['Rain'] != 'N/A']
            if not not_NA_rain.empty:
                l['Rain'] = ax6.plot(not_NA_rain['DateTimeLocal'], not_NA_rain['Rain'], 'co-', zorder=201, label='Rain (mm)')
        if 'Snow' in other_window.columns and other_window['Snow'].shape[0] > 0:
            not_NA_snow = other_window[other_window['Snow'] != 'N/A']
            if not not_NA_snow.empty:
                l['Snow '] = ax6.plot(not_NA_snow['DateTimeLocal'], not_NA_snow['Snow'], 'bs-', zorder=202, label='Snow (mm)')
        self._lock_axes_limits(ax6)
        if show_days_background: self._show_days_background(ax5, first_date, last_date)
        if show_time_now: self._show_time_now(ax6)
        self._show_qualitative(ax6, self.data_collected_most_recent_local_time, last_date)
        nic_plot.nic_standard_axes(ax6, xlabel='Time', ylabel='Rain/Snow\n(mm)', ylabelcolor='b')
        if l: ax5.legend([line[0] for line in l.values()], [el.get_label() for el in [line[0] for line in l.values()]], loc='upper right',   framealpha=0.5)

        plt.suptitle('Forecast weather data for {}, {}\n(lat={}, lon={})'.format(wd.location_town, wd.location_country, wd.location_latlon[0], wd.location_latlon[1]), fontsize=14, fontweight='bold')

    def plot_today(self, temp_scale, show_time_now=True, show_days_background=True):
        today_date = self.data_collected_most_recent_local_time.date()
        first_date, last_date = today_date, today_date + timedelta(days=1)
        first_today_index, last_tomorrow_index = None, None
        for i in range(self.processed_data.shape[0]):
            if self.processed_data['DateTimeLocal'].iloc[i].date() == today_date and not first_today_index:
                first_today_index = i
            if self.processed_data['DateTimeLocal'].iloc[i].date() == today_date+timedelta(days=2):
                last_tomorrow_index = i-1
                break
        window = self.processed_data.iloc[first_today_index:last_tomorrow_index + 1]

        fig = plt.figure(figsize=(20,10))

        # Temp, feels_like
        ax1 = fig.add_subplot(411)
        ax1.plot(window['DateTimeLocal'], window['Temp'+temp_scale.upper()], 'mo-', zorder=200, label='Temperature ({})'.format(temp_scale.upper()))
        ax1.plot(window['DateTimeLocal'], window['FeelsLike'+temp_scale.upper()], 'gs-', zorder=201, label = 'Feels-like temperature ({})'.format(temp_scale.upper()))
        ax1.legend(loc='upper right',   framealpha=0.5)
        self._lock_axes_limits(ax1)
        if show_time_now: self._show_time_now(ax1)
        if show_days_background: self._show_days_background(ax1, first_date, last_date)
        nic_plot.nic_standard_axes(ax1, ylabel='Temp\n({})'.format(temp_scale.upper()))

        # Humidity, clouds
        ax2 = fig.add_subplot(412)
        ax2.plot(window['DateTimeLocal'], window['Humidity'], 'bo-', zorder=200, label='Humidity (%)')
        ax2.plot(window['DateTimeLocal'], window['Clouds'], 'cs-', zorder=201, label='Clouds (%)')
        ax2.legend(loc='upper right',   framealpha=0.5)
        self._lock_axes_limits(ax2)
        if show_time_now: self._show_time_now(ax2)
        if show_days_background: self._show_days_background(ax2, first_date, last_date)
        nic_plot.nic_standard_axes(ax2, ylabel='Humidity/Clouds\n(%)')

        # Wind speed, wind direction
        ax3 = fig.add_subplot(413)
        windspeed = ax3.plot(window['DateTimeLocal'], window['WindSpeed'], 'gs-', zorder=202, label='Wind speed (m/s)')
        nic_plot.nic_standard_axes(ax3, ylabel='Wind speed\n(m/s)', ylabelcolor='g')
        ax4 = ax3.twinx()
        winddir = ax4.plot(window['DateTimeLocal'], window['WindDeg'], 'r^-', zorder=203, label='Wind direction (deg)')
        self._lock_axes_limits(ax4)
        if show_time_now: self._show_time_now(ax4)
        if show_days_background: self._show_days_background(ax3, first_date, last_date)
        nic_plot.nic_standard_axes(ax4, ylabel='Wind direction\n(deg)', ylabelcolor='r')
        ax4.legend(windspeed + winddir, [l.get_label() for l in (windspeed + winddir)], loc='upper right',   framealpha=0.5)

        # Rain, snow, pop, weather
        ax5 = fig.add_subplot(414)
        l={}
        if 'PoP' in window.columns:
            not_NA_pop = window[window['PoP'] != 'N/A']
            if not not_NA_pop.empty:
                l['PoP']=ax5.plot(not_NA_pop['DateTimeLocal'], not_NA_pop['PoP'], 'mv:', zorder=210, label='Chance of precipitation (%)')
        nic_plot.nic_standard_axes(ax5, xlabel='Time', ylabel='Chance of precipitation\n(%)', ylabelcolor='m')
        if show_days_background: self._show_days_background(ax5, first_date, last_date)
        ax6 = ax5.twinx()
        if 'Rain' in window.columns and window['Rain'].shape[0] > 0:
            not_NA_rain = window[window['Rain'] != 'N/A']
            if not not_NA_rain.empty:
                l['Rain']=ax6.plot(not_NA_rain['DateTimeLocal'], not_NA_rain['Rain'], 'co-', zorder=201, label='Rain (mm)')
        if 'Snow' in window.columns and window['Snow'].shape[0] > 0:
            not_NA_snow = window[window['Snow'] != 'N/A']
            if not not_NA_snow.empty:
                l['Snow ']=ax6.plot(not_NA_snow['DateTimeLocal'], not_NA_snow['Snow'], 'bs-', zorder=202, label='Snow (mm)')
        self._show_qualitative(ax6, first_date, last_date)
        self._lock_axes_limits(ax6)
        if show_time_now: self._show_time_now(ax6)
        nic_plot.nic_standard_axes(ax6, xlabel='Time', ylabel='Rain/Snow\n(mm)', ylabelcolor='b')
        if l: ax5.legend([line[0] for line in l.values()], [el.get_label() for el in [line[0] for line in l.values()]], loc='upper right',   framealpha=0.5)

        plt.suptitle('Today\'s weather data for {}, {}\n(lat={}, lon={})'.format(wd.location_town, wd.location_country, wd.location_latlon[0], wd.location_latlon[1]), fontsize=14, fontweight='bold')

    def plot_all(self, temp_scale, show_time_now=True, show_days_background=True):

        today_date = self.data_collected_most_recent_local_time.date()
        dict_indices = [i for i in range(self.processed_data.shape[0]) if type(self.processed_data['Temp' + temp_scale.upper()].iloc[i]) == dict]
        first_date, last_date = self.processed_data['DateTimeLocal'].iloc[0].date(), self.processed_data['DateTimeLocal'].iloc[dict_indices[-1]].date()
        temp_window = self.processed_data.iloc[:dict_indices[0]]

        fig = plt.figure(figsize=(20,10))

        # Temp, feels_like
        ax1 = fig.add_subplot(411)
        dict_indices = [i for i in range(self.processed_data.shape[0]) if type(self.processed_data['Temp' + temp_scale.upper()].iloc[i]) == dict]

        ax1.plot(temp_window['DateTimeLocal'], temp_window['Temp' + temp_scale.upper()], 'mo-', label='Temperature ({})'.format(temp_scale.upper()))
        ax1.plot(temp_window['DateTimeLocal'], temp_window['FeelsLike' + temp_scale.upper()], 'gs-', label='Feels-like temperature ({})'.format(temp_scale.upper()))
        dict_times, dict_mins, dict_maxs = [], [], []
        for i in dict_indices:
            ax1.plot([self.processed_data['DateTimeLocal'].iloc[i], self.processed_data['DateTimeLocal'].iloc[i]],
                     [self.processed_data['Temp' + temp_scale.upper()].iloc[i]['min'], self.processed_data['Temp' + temp_scale.upper()].iloc[i]['max']], c=[0.6, 0.6, 0.6], zorder=10)
            dict_times.append(self.processed_data['DateTimeLocal'].iloc[i])
            dict_maxs.append(self.processed_data['Temp' + temp_scale.upper()].iloc[i]['max'])
            dict_mins.append(self.processed_data['Temp' + temp_scale.upper()].iloc[i]['min'])
        ax1.scatter(dict_times, dict_maxs, c='r', marker='^', zorder=11, label='Daily max ({})'.format(temp_scale.upper()))
        ax1.scatter(dict_times, dict_mins, c='b', marker='v', zorder=12, label='Daily min ({})'.format(temp_scale.upper()))
        ax1.legend(loc='upper right',   framealpha=0.5)
        self._lock_axes_limits(ax1)
        if show_time_now: self._show_time_now(ax1)
        if show_days_background: self._show_days_background(ax1, first_date, last_date)
        nic_plot.nic_standard_axes(ax1, xlabel='Time', ylabel='Temp\n({})'.format(temp_scale.upper()))

        # Humidity, clouds
        ax2 = fig.add_subplot(412)
        ax2.plot(self.processed_data['DateTimeLocal'], self.processed_data['Humidity'], 'bo-', zorder=200, label='Humidity (%)')
        ax2.plot(self.processed_data['DateTimeLocal'], self.processed_data['Clouds'], 'cs-', zorder=201, label='Clouds (%)')
        ax2.legend(loc='upper right',   framealpha=0.5)
        self._lock_axes_limits(ax2)
        if show_time_now: self._show_time_now(ax2)
        if show_days_background: self._show_days_background(ax2, first_date, last_date)
        nic_plot.nic_standard_axes(ax2, ylabel='Humidity/Clouds\n(%)')

        # Wind speed, wind direction
        ax3 = fig.add_subplot(413)
        windspeed = ax3.plot(self.processed_data['DateTimeLocal'], self.processed_data['WindSpeed'], 'gs-', zorder=202, label='Wind speed (m/s)')
        nic_plot.nic_standard_axes(ax3, ylabel='Wind speed\n(m/s)', ylabelcolor='g')
        ax4 = ax3.twinx()
        winddir = ax4.plot(self.processed_data['DateTimeLocal'], self.processed_data['WindDeg'], 'r^-', zorder=203, label='Wind direction (deg)')
        self._lock_axes_limits(ax4)
        if show_time_now: self._show_time_now(ax4)
        if show_days_background: self._show_days_background(ax3, first_date, last_date)
        nic_plot.nic_standard_axes(ax4, ylabel='Wind direction\n(deg)', ylabelcolor='r')
        ax4.legend(windspeed + winddir, [l.get_label() for l in (windspeed + winddir)], loc='upper right',   framealpha=0.5)

        # Rain, snow, pop, weather
        ax5 = fig.add_subplot(414)
        l = {}
        if 'PoP' in self.processed_data.columns:
            not_NA_pop = self.processed_data[self.processed_data['PoP'] != 'N/A']
            if not not_NA_pop.empty:
                l['PoP'] = ax5.plot(not_NA_pop['DateTimeLocal'], not_NA_pop['PoP'], 'mv:', zorder=210, label='Chance of precipitation (%)')
        nic_plot.nic_standard_axes(ax5, xlabel='Time', ylabel='Chance of precipitation\n(%)', ylabelcolor='m')
        if show_days_background: self._show_days_background(ax5, first_date, last_date)

        ax6 = ax5.twinx()
        if 'Rain' in self.processed_data.columns and self.processed_data['Rain'].shape[0] > 0:
            not_NA_rain = self.processed_data[self.processed_data['Rain'] != 'N/A']
            if not not_NA_rain.empty:
                l['Rain'] = ax6.plot(not_NA_rain['DateTimeLocal'], not_NA_rain['Rain'], 'co-', zorder=201, label='Rain (mm)')
        if 'Snow' in self.processed_data.columns and self.processed_data['Snow'].shape[0] > 0:
            not_NA_snow = self.processed_data[self.processed_data['Snow'] != 'N/A']
            if not not_NA_snow.empty:
                l['Snow '] = ax6.plot(not_NA_snow['DateTimeLocal'], not_NA_snow['Snow'], 'bs-', zorder=202, label='Snow (mm)')
        self._lock_axes_limits(ax6)
        if show_time_now: self._show_time_now(ax6)
        nic_plot.nic_standard_axes(ax6, xlabel='Time', ylabel='Rain/Snow\n(mm)', ylabelcolor='b')
        if l: ax5.legend([line[0] for line in l.values()], [el.get_label() for el in [line[0] for line in l.values()]], loc='upper right',   framealpha=0.5)

        plt.suptitle('All weather data for {}, {}\n(lat={}, lon={})'.format(wd.location_town, wd.location_country, wd.location_latlon[0], wd.location_latlon[1]), fontsize=14, fontweight='bold')



    def _lock_axes_limits(self, ax):
        ax.set_xlim(ax.get_xlim())
        ax.set_ylim(ax.get_ylim())

    def _show_time_now(self, ax):
        plt.plot([self.data_collected_most_recent_local_time, self.data_collected_most_recent_local_time], [-1000,1000], linestyle='--', c='g', linewidth=1.5, zorder=100)
        plt.text(self.data_collected_most_recent_local_time, ax.get_ylim()[0] + (ax.get_ylim()[1] - ax.get_ylim()[0]) / 15, '  Time now:\n  {}'.format(self.data_collected_most_recent_local_time.strftime('%d-%m-%Y %H:%M:%S')), color='g', zorder=501, weight='bold')

    @staticmethod
    def _show_days_background(ax, first_date, last_date):
        date = first_date
        counter = 0
        while date <= last_date:
            if counter % 2 == 1: ax.add_patch(ptc.Rectangle([date, -100], timedelta(days=1), 1000, color=[0.9, 0.9, 0.9], zorder=1))
            date += timedelta(days=1)
            counter += 1

    def _show_qualitative(self, ax, first_date, last_date):
        times, quals = [], []
        data_on_ax = self.processed_data[(self.processed_data['DateTimeLocal']>pd.Timestamp(first_date)) & (self.processed_data['DateTimeLocal']<pd.Timestamp(last_date))]
        data_on_ax.reset_index(inplace=True, drop=True)
        for i, row in data_on_ax.iterrows():
            if i == 0:
                times.append(row['DateTimeLocal'])
                quals.append(row['Weather'])
            else:
                if quals[-1] != row['Weather']:
                    times.append(row['DateTimeLocal'])
                    quals.append(row['Weather'])
        for t, q in zip(times, quals):
            ax.text(t, ax.get_ylim()[0] + (ax.get_ylim()[1] - ax.get_ylim()[0]) / 15 * 14,
                     ' {}'.format(q), color='r', zorder=502, weight='bold', rotation = 90, size=6)


# Checks that an input string is either a valid country code or a country name
# with a matching country code, returning the code in either case
def get_check_country_code(country_or_code, bespoke_code_edits={}):

    # If the locally saved table has not been downloaded for 24 hours, download it again
    def wikipedia_table2df_weather():
        return wikipedia_table2df('ISO_3166-1_alpha-2', [2])['2']
    country_code_cache_dict = CacheDict(wikipedia_table2df, persist_filename = 'get_check_country_code.dat', persist_lifetime_hours=24)
    # country_codes_df = wikipedia_table2df('ISO_3166-1_alpha-2', [2])['2']
    country_codes_df = country_code_cache_dict.get_key_value(('ISO_3166-1_alpha-2',[2],False))['2']

    # Check the table
    expected_cols = ['CODE', 'COUNTRY NAME (USING TITLE CASE)', 'YEAR', 'CCTLD', 'ISO 3166-2', 'NOTES']
    for col in expected_cols:
        if col not in country_codes_df.columns:
            raise Exception('Unexpected country codes reference table retrieved from Wikipedia.')
    if country_codes_df.shape[0] < 200:
        raise Exception('Unexpected country codes reference table retrieved from Wikipedia.')

    country_or_code_upper = country_or_code.upper()
    if country_codes_df[country_codes_df.CODE == country_or_code].shape[0] == 1:
        return country_or_code_upper, country_codes_df[country_codes_df.CODE == country_or_code]['COUNTRY NAME (USING TITLE CASE)'].iloc[0].title()
    else:
        for country in country_codes_df['COUNTRY NAME (USING TITLE CASE)']:
            if country.upper() == country_or_code_upper or country.upper() in country_or_code_upper or country_or_code_upper in country.upper():
                table_code = country_codes_df[country_codes_df['COUNTRY NAME (USING TITLE CASE)'] == country]['CODE'].iloc[0]
                if table_code in bespoke_code_edits.keys(): return bespoke_code_edits[table_code], country.title()
                else: return table_code, country.title()
        return country_or_code, country_or_code
        # raise Exception('Invalid country or country code requested: {}'.format(country_or_code))

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
            df_rows = row_labels if row_labels and len(row_labels) == len(rows) else list(range(len(rows)))
            dfs[title] = pd.DataFrame(rows, index=df_rows, columns=df_cols)

    return dfs

def timestamps_are_same_day_in_local_time(ts1, ts2, utc_time_delta):

    if isinstance(ts1, int): ts1 = datetime.utcfromtimestamp(ts1) + utc_time_delta
    if isinstance(ts2, int): ts2 = datetime.utcfromtimestamp(ts2) + utc_time_delta

    if ts1.date() == ts2.date():
        return True
    return False



if __name__ == '__main__':

    t1=datetime.now()
    a=get_check_country_code('Australia')
    dt1 = (datetime.now()-t1).total_seconds()

    t2 = datetime.now()
    b = get_check_country_code('Australia')
    dt2 = (datetime.now() - t2).total_seconds()

    t3 = datetime.now()
    c = get_check_country_code('Uzb')
    dt3 = (datetime.now() - t3).total_seconds()



    # wd = WeatherData('Perth')
    # wd.plot_today('c')
    # wd.plot_future('c')
    # wd.plot_all('c')
    # TODO: qualitative description on plot?
    # plt.scatter(wd.processed_data['dt_local'].iloc[:168], wd.processed_data['temp'].iloc[:168])

    # plt.scatter(wd.processed_data['dt_local'].iloc[:168], wd.processed_data['temp'].iloc[:168])
    # plt.figure()
    # plt.scatter(wd.processed_data['dt'].iloc[:168], wd.processed_data['temp'].iloc[:168])

    # Search for times in between 19th 1900h and 20th 1600h
    # wd.unix_utc_to_local(wd.retrieved_data['future']['current']['dt'])
    # wd.unix_utc_to_local(wd.retrieved_data['future']['minutely'][1]['dt'])
    # wd.unix_utc_to_local(wd.retrieved_data['future']['hourly'][0]['dt'])
    # wd.unix_utc_to_local(wd.retrieved_data['historical'][1]['current']['dt'])
    # wd.unix_utc_to_local(wd.retrieved_data['historical'][2]['hourly'][23]['dt'])