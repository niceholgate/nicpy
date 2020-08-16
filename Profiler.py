import cProfile
import io, os
from pathlib import Path
import pandas as pd
import numpy as np
import pstats
from datetime import datetime
from SearchInFiles import SearchInFiles
from nicpy.nic_misc import get_YYYYMMDDHHMMSS_string

class Profiler:
                    # See cProfile docs online for more details
    known_columns = ['N_CALLS',         # Number of calls
                     'T_TIME',          # Total time
                     'T_PER_CALL',      # Total time per call
                     'C_TIME',          # Cumulative time
                     'C_PER_CALL',      # Cumulative time per call
                     'FILE_DIR',        # Directory of file (if local code) or other function descriptor
                     'LINE_N',          # Line number (if local code)
                     'FUNCTION']        # Function name (if local code)

    def __init__(self, command_str, save_directory):
        self.command_string = command_str
        self.save_directory = save_directory

        self.command_start_time = datetime.now()
        start_time_str = get_YYYYMMDDHHMMSS_string(self.command_start_time, '-', '_')
        temp_data_str = 'Profiler_tempdata'+start_time_str
        cProfile.run(command_str, temp_data_str)
        self.command_end_time = datetime.now()
        self.__output_file_path = str(Path(save_directory)/'Profiler_{}_{}.csv'.format(start_time_str, command_str))

        # Process results to a string which can be output to an initial CSV, and save the CSV
        self.result = self.__process_raw_results(temp_data_str)

        # Delete the temporary raw results file
        if (Path.cwd()/temp_data_str).exists(): os.remove(str((Path.cwd()/temp_data_str)))


    def results_to_df(self, sort_by = 'C_TIME', ascending=False, string_exclusions = ['{', '<', 'Anaconda3','PyCharm'], overwrite_old_csv=False):

        if not self.__output_file_path:
            raise Exception('First need to call results_to_csv to generate a CSV from which the DataFrame can be built.')
        df = pd.read_csv(self.__output_file_path)

        # Rename to capitalised column labels in Profiler.known_columns
        df.rename(columns=dict(zip(list(df.columns), Profiler.known_columns)), inplace=True)

        # Sort by specified column, defaults to cumulative time
        if sort_by not in Profiler.known_columns: raise Exception('\'sort_by\' parameter must be a string from the following: '+ Profiler.known_columns)
        df.sort_values(by=sort_by, ascending=False, axis=0, inplace=True)

        if string_exclusions:
            df['EXCLUDE'] = df.apply(lambda x: check_multi_substrings(x['FILE_DIR'], string_exclusions), axis=1)
            df=df[df['EXCLUDE']==0]
            df.drop(columns=['EXCLUDE'], inplace=True)
            df.reset_index(drop=True, inplace=True)

        if overwrite_old_csv: df.to_csv(self.__output_file_path, index=False)

        return df

    def __process_raw_results(self, temp_data_str):
        result = io.StringIO()
        p = pstats.Stats(temp_data_str, stream=result).print_stats()
        result = result.getvalue()

        result = 'ncalls' + result.split('ncalls')[-1]  # Remove non-tabulated preamble

        result = '\n'.join([','.join(line.rstrip().split(None, 5)) for line in result.split('\n')])  # Replace whitespace separators with commas

        lines = result.split('\n')  # Separate filename, line number, and function name into separate columns (complicated)
        for i in range(len(lines)):
            bits = lines[i].split(':')
            if len(bits) > 2: bits = [':'.join(bits[0:2])] + bits[2:]  # (case where there was a ':' in the directory path which shouldn't have been split)
            lines[i] = ','.join(bits)
        result = '\n'.join(lines)
        lines = [','.join(line.split('(')) for line in result.split('\n')]
        for i in range(len(lines)): lines[i] = lines[i].replace(')', '')
        result = '\n'.join(lines)

        with open(self.__output_file_path, 'w+') as f:
            f.write(result)

        return result






def check_multi_substrings(string, substrings_list):

    for substr in substrings_list:
        if substr in string: return True
    return False


if __name__ == '__main__':
    directory = r'E:\nicpy\Projects\automate'
    strs = ['data', 'LiNe', 'The']
    cmd_str = 'SearchInFiles(search_root_directory=directory, search_strings=strs, case_sensitive=True, whole_word_only=True)'
    save_directory = str(Path.cwd())
    profiler = Profiler(cmd_str, save_directory)
    df = profiler.results_to_df(sort_by='C_TIME', ascending=False, overwrite_old_csv=True)