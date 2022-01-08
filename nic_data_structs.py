from datetime import datetime
from inspect import signature
from pathlib import Path
import pickle, heapq, numbers
import numpy as np
import pandas as pd


class CacheDict:

    def __init__(self, func, persist_directory=None, persist_filename = None, initial_keys=(), persist_lifetime_hours=10**10):

        self.func = func
        self.func_name = str(func).split(' ')[1]
        self.n_func_args = len(signature(func).parameters)
        self.cache_dict = {}

        # If the persist_filename exists, load it
        self.persist_filepath = None
        if persist_filename and persist_directory:
            self.persist_filepath = Path(persist_directory) / persist_filename
            if Path(self.persist_filepath).exists():

                persist_load = pickle.load(open(str(self.persist_filepath), 'rb'))
                persist_CacheDict = persist_load['CacheDict']
                save_datetime = persist_load['save_datetime']
                # If the save_datetime is less than persist_lifetime_hours ago, and the func details match, load the old cache_dict
                if (datetime.now()-save_datetime).total_seconds()/60/60 < persist_lifetime_hours:
                    if persist_CacheDict.func == self.func and persist_CacheDict.n_func_args == self.n_func_args and persist_CacheDict.func_name == self.func_name:
                        self.cache_dict = persist_CacheDict.cache_dict

        if len(initial_keys) > 0:
            for key in initial_keys:
                self._check_key(key)
                key_str = tuple(str(el) for el in key)
                self.cache_dict[key_str] = self.func(*key)
            if self.persist_filepath:
                pickle.dump({'CacheDict': self, 'save_datetime': datetime.now()}, open(str(self.persist_filepath), 'wb'))

    def _check_key(self, key):
        er = 'All keys must be tuples of length equal to number of parameters in the' \
             'function whose result is being cached.\n For {} this is {} arguments.'.format(self.func_name, self.n_func_args)
        if not isinstance(key, tuple): raise Exception(er)
        elif len(key) != self.n_func_args: raise Exception(er)

    def get_key_value(self, key):
        self._check_key(key)
        key_str = tuple(str(el) for el in key)
        if key_str in self.cache_dict.keys():
            return self.cache_dict[key_str]
        else:
            self.cache_dict[key_str] = self.func(*key)
            # Update the persisted CacheDict if an update occurs
            if self.persist_filepath:
                # First create the directory if it doesn't yet exist
                if not self.persist_filepath.parent.exists():
                    self.persist_filepath.parent.mkdir()
                pickle.dump({'CacheDict': self, 'save_datetime': datetime.now()}, open(str(self.persist_filepath), 'wb'))
            return self.cache_dict[key_str]

    def force_key_value(self, key, value):
        self._check_key(key)
        if key in self.cache_dict.keys():
            raise Exception('\'{}\' is already a key in the CacheDict; must explicitly delete it first with delete_key method'.format(key))
        else:
            self.cache_dict[key] = value
            # Update the persisted CacheDict if an update occurs
            if self.persist_filepath:
                pickle.dump({'CacheDict': self, 'save_datetime': datetime.now()}, open(str(self.persist_filepath), 'wb'))

    def delete_key(self, key):
        self._check_key(key)
        if key in self.cache_dict.keys():
            del self.cache_dict[key]
            # Update the persisted CacheDict if an update occurs
            if self.persist_filepath:
                pickle.dump({'CacheDict': self, 'save_datetime': datetime.now()}, open(str(self.persist_filepath), 'wb'))
        else:
            raise Exception('\'{}\' is not already in the cache.'.format(key))


class PriorityQueue:
    def __init__(self):
        self.elements = []

    def empty(self):
        return len(self.elements) == 0

    def put(self, item, priority):
        heapq.heappush(self.elements, (priority, item))

    def get(self):
        return heapq.heappop(self.elements)[1]


# Using just the shared columns in two DataFrames, finds full matches. If there are duplicates in the matching columns for each DF,
# rows always match one-to-one (this is not the behaviour of a normal merge).
class RowMatcher:

    def __init__(self, df1, df2, df1_name='df1', df2_name='df2', shared_cols=None, tolerances={}):
        # Set DataFrames, names, suffixes, tolerances
        self.df1, self.df2, self.df1_name, self.df2_name = df1, df2, df1_name, df2_name
        self.suffixes = ['_' + df1_name, '_' + df2_name]
        self.tolerances = tolerances

        # Get all the shared columns and reduce to just specified ones (if any and if they are all valid)
        self.shared_cols = [col for col in df1.columns if col in df2.columns]
        if len(self.shared_cols) == 0:
            raise Exception('There are no shared columns between the two DataFrames.')
        if shared_cols and isinstance(shared_cols, list):
            for col in shared_cols:
                if col not in self.shared_cols:
                    raise Exception('The specified shared column "{}" does not exist in both of the DataFrames.'.format(col))
            self.shared_cols = shared_cols

        # Check that the specified tolerances are for numeric shared_cols
        for tol_name, tol_val in tolerances.items():
            if tol_name not in self.shared_cols:
                raise Exception('The tolerance for "{}" is not among the shared columns for matching.'.format(tol_name))
            if not isinstance(tol_val, numbers.Number):
                raise Exception('The tolerance for "{}" has a non-numeric value ({}).'.format(tol_name, tol_val))
            if not isinstance(df1[tol_name].iloc[0], numbers.Number):
                raise Exception('"{}" is a non-numeric field and cannot have a tolerance assigned.'.format(tol_name, tol_val))

        # Initialise matches containers
        self.full_matches, self.unmatched_df1, self.unmatched_df2 = None, None, None
        self.partial_matches = {col: None for col in self.shared_cols}

        self._get_full_matches()
        for mismatch_col in self.shared_cols:
            self._get_partial_matches(mismatch_col)

    def _get_full_matches(self):
        # Ignoring numeric field tolerances, find the full_matches and the not-full-matches (partials/unmatched)
        self.full_matches, self.unmatched_df1, self.unmatched_df2 = RowMatcher.get_matches(self.df1, self.df2, self.shared_cols, self.suffixes)

        # Check if any of the remaining mismatches are actually full matches when specified tolerances on the numeric fields are considered
        for mismatch_col, tol_val in self.tolerances.items():
            # Reduce to common columns except mismatch_col
            shared_cols_excl = [col for col in self.shared_cols if col != mismatch_col]

            # Find which rows have started to match if ignoring mismatch_col
            partial_matches = self.get_matches(self.unmatched_df1, self.unmatched_df2, shared_cols_excl, self.suffixes)[0]

            # If for any partial_matches the two values of mismatch_col are sufficiently close, add them to the full_matches and remove them from the unmatched
            if not partial_matches.empty:
                partial_matches['ERROR'] = partial_matches.apply(lambda x: abs(x[mismatch_col+self.suffixes[0]]-x[mismatch_col+self.suffixes[1]]), axis=1)
                new_full_matches_1 = partial_matches[partial_matches['ERROR'] < tol_val].rename(columns={mismatch_col+self.suffixes[0]: mismatch_col})
                new_full_matches_2 = partial_matches[partial_matches['ERROR'] < tol_val].rename(columns={mismatch_col+self.suffixes[1]: mismatch_col})
                if not new_full_matches_1.empty:
                    self.full_matches = pd.concat([self.full_matches, new_full_matches_1[self.full_matches.columns]]).reset_index(drop=True)
                    self.unmatched_df1 = self.keep_right_df_uniques_with_duplicates(new_full_matches_1, self.unmatched_df1)
                    self.unmatched_df2 = self.keep_right_df_uniques_with_duplicates(new_full_matches_2, self.unmatched_df2)

    def _get_partial_matches(self, mismatch_col):
        # Alphabetically ordered columns expected for partial mismatch output table (exclude the mismatch_col)
        ordered_cols = sorted(set(self.unmatched_df1.columns.to_list()+self.unmatched_df2.columns.to_list()+[mismatch_col+self.suffixes[0], mismatch_col+self.suffixes[1]]))
        ordered_cols = [col for col in ordered_cols if col != mismatch_col]

        # Reduce to common columns except mismatch_col and find which rows have started to match
        shared_cols_excl = [col for col in self.shared_cols if col != mismatch_col]

        self.partial_matches[mismatch_col], self.unmatched_df1, self.unmatched_df2 = \
            self.get_matches(self.unmatched_df1, self.unmatched_df2, shared_cols_excl, self.suffixes)

        # Check if any of the remaining mismatches are actually partial matches when specified tolerances on the numeric fields are considered
        for mismatch_col2, tol_val2 in self.tolerances.items():
            # Reduce to common columns except mismatch_col
            shared_cols_excl = [col for col in self.shared_cols if col not in [mismatch_col, mismatch_col2]]

            # Find which rows have started to match if ignoring mismatch_col
            partial_matches = self.get_matches(self.unmatched_df1, self.unmatched_df2, shared_cols_excl, self.suffixes)[0]

            # If for any partial_matches the two values of mismatch_col are sufficiently close, add them to the full_matches and remove them from the unmatched
            if partial_matches is not None:
                if not partial_matches.empty:
                    partial_matches['ERROR'] = partial_matches.apply(lambda x: abs(x[mismatch_col2 + self.suffixes[0]] - x[mismatch_col2 + self.suffixes[1]]), axis=1)
                    new_partial_matches_1 = partial_matches[partial_matches['ERROR'] < tol_val2].rename(columns={mismatch_col2 + self.suffixes[0]: mismatch_col2})
                    new_partial_matches_2 = partial_matches[partial_matches['ERROR'] < tol_val2].rename(columns={mismatch_col2 + self.suffixes[1]: mismatch_col2})
                    if not new_partial_matches_1.empty:
                        self.partial_matches[mismatch_col] = pd.concat([self.partial_matches[mismatch_col], new_partial_matches_1[self.partial_matches[mismatch_col].columns]]).reset_index(drop=True)
                        self.unmatched_df1 = self.keep_right_df_uniques_with_duplicates(new_partial_matches_1, self.unmatched_df1)
                        self.unmatched_df2 = self.keep_right_df_uniques_with_duplicates(new_partial_matches_2, self.unmatched_df2)

        # Ensure null DataFrame has same columns as a non-empty one would
        if self.partial_matches[mismatch_col] is None:
            self.partial_matches[mismatch_col] = pd.DataFrame(columns=ordered_cols)


    @staticmethod
    def get_matches(df1, df2, on, suffixes):
        check_type_and_shape(suffixes, list, 2)

        # Check for duplicates in the matching criteria
        df1_dups_flags, df2_dups_flags = df1.duplicated(keep=False, subset=on), df2.duplicated(keep=False, subset=on)

        # Default to empty matches
        matches = None

        # Get matches for non-duplicated
        df1_not_dups, df2_not_dups = df1[~df1_dups_flags], df2[~df2_dups_flags]
        if not df1_not_dups.empty and not df2_not_dups.empty:
            matches = df1_not_dups.merge(df2_not_dups, how='inner', on=on, validate='one_to_one', suffixes=suffixes)
            # Find which rows remain unmatched in each set
            df1, df2 = RowMatcher.keep_right_df_uniques(matches, df1), RowMatcher.keep_right_df_uniques(matches, df2)

        # Get matches between dups in 1 and all remaining in 2, and which rows remain unmatched in each set
        df1_dups_flags = df1.duplicated(keep=False, subset=on)
        df1_dups, df1_not_dups = df1[df1_dups_flags], df1[~df1_dups_flags]
        if not df1_dups.empty and not df2.empty:
            new_matches, df1_dups, df2 = RowMatcher.get_matches_with_duplicates(df1_dups, df2, on, suffixes)
            if len(new_matches)>0:
                matches = pd.concat(new_matches) if matches is None else pd.concat([matches] + new_matches)
                df1 = pd.concat([df1_not_dups, df1_dups])

        # Get matches between dups in 2 and all remaining in 1, and which rows remain unmatched in each set
        df2_dups_flags = df2.duplicated(keep=False, subset=on)
        df2_dups, df2_not_dups = df2[df2_dups_flags], df2[~df2_dups_flags]
        if not df2_dups.empty and not df1.empty:
            new_matches, df1, df2_dups = RowMatcher.get_matches_with_duplicates(df1, df2_dups, on, suffixes)
            if len(new_matches)>0:
                matches = pd.concat(new_matches) if matches is None else pd.concat([matches] + new_matches)
                df2 = pd.concat([df2_not_dups, df2_dups])

        if matches is not None:
            matches.reset_index(drop=True)

        return matches, df1, df2

    # Gets matches reliably even if there are duplicates in the shared_cols (each duplicate can only match once)
    # Scales poorly with size, so should call twice with alternate duplicate filtering
    @staticmethod
    def get_matches_with_duplicates(df1, df2, shared_cols, suffixes):
        check_type_and_shape(suffixes, list, 2)
        matched_indices1, matched_indices2, matches = [], [], []
        for i1, row1 in df1.iterrows():
            for i2, row2 in df2.iterrows():
                if i1 not in matched_indices1 and i2 not in matched_indices2:
                    match = pd.DataFrame(row1).T.merge(pd.DataFrame(row2).T, how='inner', on=shared_cols, suffixes=suffixes)
                    if not match.empty:
                        matched_indices1.append(i1)
                        matched_indices2.append(i2)
                        matches.append(match)
        return matches, df1.drop(index=matched_indices1), df2.drop(index=matched_indices2)

    @staticmethod
    def keep_right_df_uniques(left_df, right_df, on=None):
        merge_outer = left_df.merge(right_df, how='outer', indicator=True, on=on)
        right_uniques = merge_outer[merge_outer['_merge'] == 'right_only'].drop(columns=['_merge'])
        return right_uniques[right_df.columns]

    @staticmethod
    def keep_right_df_uniques_with_duplicates(left_df, right_df, on=None):
        matched_indicesL, matched_indicesR = [], []
        for iL, rowL in left_df.iterrows():
            for iR, rowR in right_df.iterrows():
                if iL not in matched_indicesL and iR not in matched_indicesR:
                    match = pd.DataFrame(rowL).T.merge(pd.DataFrame(rowR).T, how='inner', on=on)
                    if not match.empty:
                        matched_indicesL.append(iL)
                        matched_indicesR.append(iR)
        return right_df.drop(index=matched_indicesR)

# Tests that an object is a list and that it contains only the specified element type
def is_list_of(test_element_type, test_list):
    if not isinstance(test_list, list): return False
    if not all([type(el) == test_element_type for el in test_list]): return False
    return True

# Verify type and shape of data variable in one line
def check_type_and_shape(variable, variable_type, variable_shape):
    if not isinstance(variable, variable_type):
        raise Exception('Input variable is not of expected type {}, but rather is of type {}.'.format(variable_type, type(variable)))
    if isinstance(variable, list):
        if len(variable) != variable_shape:
            raise Exception('List is not of expected length {}, but rather of length {}.'.format(variable_shape, len(variable)))
    else:
        if variable.shape != variable_shape:
            raise Exception('DataFrame/Array is not of expected shape {}, but rather of shape {}.'.format(variable_shape, variable.shape))

# Check lengths/sizes of all the lists/arrays/dataframes in a list are the same (can mix arrays with DataFrames, but not lists with the others)
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


def long_func(n):
    result = 0
    while n>1:
        result += n**2
        n -= 1
    return result


# Example showing speedup due to caching
if __name__=='__main__':
    long_func_cache = CacheDict(long_func, persist_filename='thing.dat', persist_lifetime_hours=1)
    t1=datetime.now()
    a=long_func_cache.get_key_value((1000000,))
    dt1=(datetime.now()-t1).total_seconds()

    t2 = datetime.now()
    b=long_func_cache.get_key_value((1000000,))
    dt2 = (datetime.now() - t2).total_seconds()

    # c = long_func_cache.get_key_value((140000,))

# Example showing matching with DataFrames
# df1 = pd.read_excel('match_test1a.xlsx')
# df2 = pd.read_excel('match_test1b.xlsx')
# matcher = RowMatcher(df1, df2, df1_name='one', df2_name='two', tolerances={'Price': 0.001})
# matcher2 = RowMatcher(df1, df2, df1_name='one', df2_name='two')

# if __name__=='__main__':
#     df1 = pd.read_excel('match_test3a.xlsx')
#     df2 = pd.read_excel('match_test3b.xlsx')
#     matcher = RowMatcher(df1, df2, df1_name='one', df2_name='two', tolerances={'Balance': 0.05, 'Interest Earned': 0.05})
#     matcher2 = RowMatcher(df1, df2, df1_name='one', df2_name='two')
#

