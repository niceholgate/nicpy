from datetime import datetime
from inspect import signature
class CacheDict:

    def __init__(self, func, initial_keys=[]):

        self.func = func
        self.func_name = str(func).split(' ')[1]
        self.n_func_args = len(signature(func).parameters)
        self.cache_dict = {}
        for key in initial_keys:
            self.check_key(key)
            self.cache_dict[key] = self.func(*key)

    def check_key(self, key):
        er = 'All keys must be tuples of length equal to number of parameters in the' \
             'function whose result is being cached.\n For {} this is {} arguments.'.format(self.func_name, self.n_func_args)
        if not isinstance(key, tuple): raise Exception(er)
        elif len(key) != self.n_func_args: raise Exception(er)

    def get_key_value(self, key):
        self.check_key(key)
        if key in self.cache_dict.keys():
            return self.cache_dict[key]
        else:
            self.cache_dict[key] = self.func(*key)
            return self.cache_dict[key]

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

if __name__=='__main__':
    long_func_cache = CacheDict(long_func)
    t1=datetime.now()
    a=long_func_cache.get_key_value((1000000,))
    dt1=(datetime.now()-t1).total_seconds()

    t2 = datetime.now()
    b=long_func_cache.get_key_value((1000000,))
    dt2 = (datetime.now() - t2).total_seconds()