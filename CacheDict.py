from datetime import datetime
from inspect import signature
from pathlib import Path
import pickle
from definitions import DATA_PERSIST_DIRECTORY

class CacheDict:

    def __init__(self, func, initial_keys=[], persist_filename = '', persist_lifetime_hours=None):

        self.func = func
        self.func_name = str(func).split(' ')[1]
        self.n_func_args = len(signature(func).parameters)
        self.cache_dict = {}

        # If the persist_filename exists, load it
        self.persist_filepath = Path(DATA_PERSIST_DIRECTORY)/persist_filename
        if Path(self.persist_filepath).exists():
            persist_load = pickle.load(open(self.persist_filepath, 'rb'))
            persist_CacheDict = persist_load['CacheDict']
            save_datetime = persist_load['save_datetime']
            # If the save_datetime is more than persist_lifetime_hours ago, and the func details match, load the old cache_dict
            if (datetime.now()-save_datetime).total_seconds()/60/60 < persist_lifetime_hours:
                if persist_CacheDict.func == self.func and persist_CacheDict.n_func_args == self.n_func_args and persist_CacheDict.func_name == self.func_name:
                    self.cache_dict = persist_CacheDict.cache_dict

        for key in initial_keys:
            self.check_key(key)
            key_str = tuple(str(el) for el in key)
            self.cache_dict[key_str] = self.func(*key)


    def check_key(self, key):
        er = 'All keys must be tuples of length equal to number of parameters in the' \
             'function whose result is being cached.\n For {} this is {} arguments.'.format(self.func_name, self.n_func_args)
        if not isinstance(key, tuple): raise Exception(er)
        elif len(key) != self.n_func_args: raise Exception(er)

    def get_key_value(self, key):
        self.check_key(key)
        key_str = tuple(str(el) for el in key)
        if key_str in self.cache_dict.keys():
            return self.cache_dict[key_str]
        else:
            self.cache_dict[key_str] = self.func(*key)
            # Update the persisted CacheDict if an update occurs
            if self.persist_filepath:
                pickle.dump({'CacheDict':self, 'save_datetime':datetime.now()}, open(self.persist_filepath, 'wb'))
            return self.cache_dict[key_str]

    def force_key_value(self, key, value):
        self.check_key(key)
        if key in self.cache_dict.keys():
            raise Exception('\'{}\' is already a key in the CacheDict; must explicitly delete it first with delete_key method'.format(key))
        else:
            self.cache_dict[key] = value

    def delete_key(self, key):
        self.check_key(key)
        if key in self.cache_dict.keys():
            del self.cache_dict[key]
        else:
            raise Exception('\'{}\' is not already in the cache.'.format(key))

def long_func(n):
    result = 0
    while n>1:
        result += n**2
        n -= 1
    return result

# Example showing speedup due to caching
if __name__=='__main__':
    long_func_cache = CacheDict(long_func)
    t1=datetime.now()
    a=long_func_cache.get_key_value((1000000,))
    dt1=(datetime.now()-t1).total_seconds()

    t2 = datetime.now()
    b=long_func_cache.get_key_value((1000000,))
    dt2 = (datetime.now() - t2).total_seconds()