import numpy as np
from scipy.stats import norm
import matplotlib.pyplot as plt


class NormalDist:

    def __init__(self, samples):
        self.samples = samples
        self.mean = np.mean(samples)
        self.std = np.std(samples)

    def add_sample(self, sample):
        self.samples.append(sample)
        self.mean = (self.mean*(len(self.samples)-1)+sample)/len(self.samples)
        self.std = np.std(self.samples)

    def remove_sample(self, sample_index):
        self.mean = (self.mean*len(self.samples) - self.samples[sample_index]) / (len(self.samples)-1)
        self.samples.pop(sample_index)
        self.std = np.std(self.samples)

    def get_upper_tail_critical_value(self, fraction_above):
        crit = norm.ppf(1 - fraction_above, loc=self.mean, scale=self.std)
        return crit

    def in_upper_tail(self, test, fraction_above):
        crit = self.get_upper_tail_critical_value(fraction_above)
        return True if test > crit else False

    def get_lower_tail_critical_value(self, fraction_below):
        crit = norm.ppf(fraction_below, loc=self.mean, scale=self.std)
        return crit

    def in_lower_tail(self, test, fraction_below):
        crit = self.get_lower_tail_critical_value(fraction_below)
        return True if test < crit else False

    def dist_plot(self, test, fraction_above, just_dist=False):
        xs = np.linspace(self.mean - 6 * self.std, self.mean + 6 * self.std, 200)
        dist = [np.exp(-(1 / 2) * ((x - self.mean) / self.std) ** 2) / (self.std * np.sqrt(2 * np.pi)) for x in xs]
        if not just_dist: plt.figure()
        plt.plot(xs, dist)  # plot the distribution
        if not just_dist:
            crit = norm.ppf(1 - fraction_above, loc=self.mean, scale=self.std)
            plt.plot([0, 0], [0, 1], '--k')  # plot x = 0
            plt.plot([self.mean, self.mean], [0, 1], ':k')  # plot x = mean
            plt.plot([crit, crit], [0, 1], '--r')  # plot x = crit
            plt.plot([test, test], [0, 1], '--b')  # plot x = test
            plt.scatter(self.samples, [0.5] * len(self.samples))
            plt.legend(['dist', '0', 'mean', 'crit', 'test'])