import numpy as np
import logging
from datetime import datetime, date
import functions.strategy.similitudes as sim
import functions.analysis.outcome_analysis as o_a
import sys
sys.path.append('E:/')
import nicpy.nehMisc as nM

class GridSearch:

    def __init__(self, parameter_vectors, perc_limit = 0.5):

        # self.initial_logging()
        self.parameter_vectors = parameter_vectors
        self.parameters = list(parameter_vectors.keys())
        # self.parameters_can_be_negative = []
        self.perc_limit = perc_limit

        self.all_indexers = []      # All of the indexers for accessing the results array
        self.extr_indexers = []     # Results array indices of extrema
        self.min_max = 'None'       # Starts as 'None' to indicate no max or min yet found

        # Lists to store the history of an auto optimisation
        self.auto_optimised_vectorisations = []
        self.auto_optimised_extrema_param_sets = []
        self.auto_optimised_extrema = []
        self.auto_optimised_parameter_percent_changes = []

        # Determine which parameters are vectorised for searching over (array with one element is still considered 'vectorised')
        # and check that adequate parameter vectors or equivalence/constant value have been provided for each parameter
        self.vectorised_parameters = []
        self.nonvectorised_parameters = []
        for parameter in self.parameters:
            if parameter not in parameter_vectors.keys():
                raise Exception('Vector or equivalence/constant value for {} not specified.'.format(parameter))
            if type(parameter_vectors[parameter]) in [list, np.ndarray]:
                if len(parameter_vectors[parameter]) < 0: raise Exception('Empty array specified for parameter {}.'.format(parameter))
                self.vectorised_parameters.append(parameter)
            else:
                # if type(parameter_vectors[parameter]) == str and parameter_vectors[parameter] not in self.parameters + ['on', 'off']:
                #     raise Exception('Invalid equivalence condition for parameter {}.'.format(parameter))
                self.nonvectorised_parameters.append(parameter)
        # Rearrange the full list of parameters to be vectorised -> nonvectorised
        self.parameters = self.vectorised_parameters + self.nonvectorised_parameters

        # Determine parameter types based on input parameter_vectors
        self.parameter_types = {}
        for parameter in self.parameters:
            this_vec = self.parameter_vectors[parameter]
            if type(this_vec) == str:
                if this_vec in self.vectorised_parameters:
                    self.parameter_types[parameter] = type(self.parameter_vectors[this_vec][0])
                else:
                    self.parameter_types[parameter] = str
            elif type(this_vec) == float:
                self.parameter_types[parameter] = float
            elif type(this_vec) == int:
                self.parameter_types[parameter] = int
            elif type(this_vec) == date:
                self.parameter_types[parameter] = int
            elif type(this_vec) == dict:
                self.parameter_types[parameter] = dict
            else:
                self.parameter_types[parameter] = type(this_vec[0])


        # Initialise empty results array
        self.results = np.array([])
        self.generate_empty_results_array()


    # def initial_logging(self):
    #
    #     file_name = '{}.log'.format(nM.get_YYYYMMDDHHMMSS_string(datetime.now(),'-',';'))
    #     stream_h = logging.StreamHandler()
    #     file_h = logging.FileHandler('{0}/{1}'.format( ,file_name))
    #     stream_h.setLevel('INFO')
    #     logging.basicConfig(level = logging.DEBUG, format='%(asctime)s [] []',
    #                         handlers = [file_h, stream_h])
    #     logging.degbug('Inputs: / /')

    def generate_empty_results_array(self):

        search_shape = []
        for parameter in self.parameters:
            if parameter in self.vectorised_parameters:
                search_shape.append(len(self.parameter_vectors[parameter]))
        self.results = np.zeros(search_shape)

    def calculate(self, data_file, current_cycle = -1, total_cycles = -1):

        parameter_combos, results_indexers = self.get_complete_parameter_combos()
        start_time = datetime.now()
        for i, combo in enumerate(parameter_combos):
            # Generate the parameter dictionary
            param_set = dict(zip(self.parameters, combo))

            # Perform the current parametrisation of the algorithm
            trades, liquid_cash_history, ticker_data, BAH_data = sim.test_strategy(data_file, param_set)
            res = o_a.analyse_trades(trades, liquid_cash_history, ticker_data, param_set, BAH_data)

            # Add the resulting metric to the results array
            self.results[tuple(results_indexers[i])] = res['net_profit']

            elapsed = (datetime.now() - start_time).total_seconds() / 60
            remaining = elapsed / (i + 1) * (len(parameter_combos) - i)
            if current_cycle == -1:
                print('Calculating error grid point {}/{}. Time elapsed: {} mins, Predicted remaining time: {} mins'.format(i + 1, len(parameter_combos), elapsed, remaining))
            else:
                print('Calculating error grid point {}/{}, cycle {}/{}. Time elapsed this cycle: {} mins, Predicted remaining time this cycle: {} mins'.format(i + 1, len(parameter_combos), current_cycle+1, total_cycles, elapsed, remaining))

        return self.results


    def get_global_extremum(self, min_max):

        # Find the global min or max
        if min_max == 'min':
            extr = np.amin(self.results)
        elif min_max == 'max':
            extr = np.amax(self.results)
        else:
            raise Exception('get_global_extremum input must be a string of either \'min\' or \'max\'.')

        # Generate a list of the results indexers pointing to the (possibly non-unique) global extremum
        self.extr_indexers = []
        for i, arr in enumerate(np.where(extr == self.results)):
            if i == 0:
                for el in arr:
                    self.extr_indexers.append([el])
            else:
                for j, el in enumerate(arr):
                    self.extr_indexers[j].append(el)

        if len(self.extr_indexers) > 1:
            logging.warning('Found multiple positions of the global results extremum.')
        self.min_max = min_max

        return extr, self.extr_indexers


    def auto_optimise(self, BTD, direction, cycles, minmax):

        self.auto_optimised_vectorisations = []
        self.auto_optimised_extrema_param_sets = []
        self.auto_optimised_extrema = []
        self.auto_optimised_parameter_percent_changes = []

        for cycle in range(cycles):

            # Update the parameter vectorisation and the results grid, unless it is the first cycle
            if cycle>0:
                self.parameter_vectors = self.suggest_refined_vectorisation()
                self.generate_empty_results_array()
            if len(self.auto_optimised_extrema_param_sets)>=2:
                self.auto_optimised_parameter_percent_changes.append(self.get_parameter_percent_changes())

            # Perform the search over the current grid
            self.calculate(BTD, direction, current_cycle=cycle, total_cycles=cycles)

            # Get the minimum and its index (reject non-uniques)
            the_extr, extr_indexers = self.get_global_extremum(minmax)
            self.auto_optimised_vectorisations.append(self.parameter_vectors)
            self.auto_optimised_extrema_param_sets.append(self.indexers2params(extr_indexers)[0])
            self.auto_optimised_extrema.append(the_extr)

    def get_parameter_percent_changes(self):

        if len(self.auto_optimised_extrema_param_sets)<2:
            raise Exception('Cannot calculate a percentage change as have not yet finished two grid search functions.')
        else:
            perc_changes = {}
            for parameter in self.vectorised_parameters:
                perc_changes[parameter] =abs((self.auto_optimised_extrema_param_sets[-1][parameter]-self.auto_optimised_extrema_param_sets[2][parameter])/self.auto_optimised_extrema_param_sets[-2][parameter]*100)

        return perc_changes

    def suggest_refined_vectorisation(self):

        if len(self.extr_indexers) == 0:
            raise Exception('No extremum has yet been found.')

        extr_indexer = self.extr_indexers[0]

        if len(self.extr_indexers) > 1:
            logging.warning('Non-unique extremum was found - defaulting to the first of these:\n'
                            '{}'.format(self.indexers2params(extr_indexer)))

        # Initialise then populate a dictionary of refined parameter vectors
        refined_parameter_vectors = {}
        for i, parameter in enumerate(self.vectorised_parameters):

            # If the parameter is changing slowly or not at all, can fix its value for subsequent grids
            if len(self.auto_optimised_parameter_percent_changes)>1 and len(self.parameter_vectors[parameter])>1:
                if self.auto_optimised_parameter_percent_changes[-1][parameter]<self.perc_limit and self.auto_optimised_parameter_percent_changes[-2][paramter]<self.perc_limit:
                    logging.info('Parameter \'{}\' changed by less than {}% for two consecutive cycles, so it was fixed after cycle {} of {} total '
                                 'auto_optimise cycles.'.format(parameter, self.perc_limit, this_cycle-1, total_cycles))
                    self.paramter_vectors[parameter] = np.array([self.auto_optimised_extrema_param_sets[-1][parameter]])

            param_type = self.parameter_types[parameter]
            param_vecs = self.parameter_vectors[parameter]

            # If the parameter was specified as a single entry array it will remain unchanged
            if len(param_vecs) == 1:
                refined_parameter_vectors[parameter] = self.parameter_vectors[parameter]
                logging.warning('Parameter \'{}\' was specified as a single entry array, so it will remain unchanged.'.format(parameter))

            # If the extremum indexer was on a boundary for the current parameter, shift the search space in the direction of the boundary
            # and keep the same number of search points (or if 2 points only, increases to 3 points)
            else:
                if extr_indexer[i] == 0:
                    ave_delta = (param_vecs[-1] - param_vecs[0]) / (len(param_vecs) - 1)
                    rpv = [param_vecs[0], param_vecs[0] + (param_vecs[1] - param_vecs[0]) / 2]
                    while len(rpv) < len(param_vecs) or len(rpv) <= 2: rpv.insert(0, rpv[0] - ave_delta)
                    refined_parameter_vectors[parameter] = np.array(rpv)
                elif extr_indexer[i] == len(param_vecs)-1:
                    ave_delta = (param_vecs[-1] - param_vecs[0]) / (len(param_vecs) - 1)
                    rpv = [param_vecs[-1] - (param_vecs[-1] - param_vecs[-2]) / 2, param_vecs[-1]]
                    while len(rpv) < len(param_vecs) or len(rpv) <= 2: rpv.append(rpv[-1] + ave_delta)
                    refined_parameter_vectors[parameter] = np.array(rpv)

                # Otherwise, treat the adjacent indexers as the new boundaries, and generate the same number of test values as previously but with a smaller delta and more points
                else:
                    refined_parameter_vectors[parameter] = np.linspace(param_vecs[extr_indexer[i]-1], param_vecs[extr_indexer[i]+1], min(len(param_vecs)+1,5))

                # If parameter type is integer, need to round the above results, and remove any zeros
                if np.issubdtype(param_type, np.integer):
                    refined_parameter_vectors[parameter] = np.round(refined_parameter_vectors[parameter]).astype(int)
                    refined_parameter_vectors[parameter] = refined_parameter_vectors[parameter][np.where(refined_parameter_vectors[parameter]!=0)]

                # Remove any negatives if they are not valid
                if not self.parameters_can_be_negative[parameter]:
                    refined_parameter_vectors[parameter] = refined_parameter_vectors[parameter][np.where(refined_parameter_vectors[parameter]>=0)]

                # Remove any duplicates
                refined_parameter_vectors[parameter] = np.unique(refined_parameter_vectors[parameter])

                # If there are fewer than three after this process, add more
                if len(refined_parameter_vectors[parameter])>1:
                    delta = refined_parameter_vectors[parameter][-1]-refined_parameter_vectors[parameter][-2]
                else:
                    delta = 1
                while len(refined_parameter_vectors[parameter])<4:
                    last = refined_parameter_vectors[parameter][-1]
                    refined_parameter_vectors[parameter] = np.concatenate([refined_parameter_vectors[parameter], np.array([last+delta])], axis=0)


        # Nonvectorised parameters remain the same (those which refer to vectorised parameters will change to match these)
        for parameter in self.nonvectorised_parameters:
            refined_parameter_vectors[parameter] = self.parameter_vectors[parameter]

        return refined_parameter_vectors


    def indexers2params(self, indexers):

        parameter_sets = []
        for indexer in indexers:
            combo = []
            for i, index in enumerate(indexer):
                parameter = self.parameters[i]
                # The indexer parameters are vectorised, so get the parameter value at 'index'
                combo.append(self.parameter_vectors[parameter][index])
            for parameter in self.nonvectorised_parameters:
                # If the parameter tracks another vectorised parameter, set it equal to the tracked parameter in this combo
                if self.parameter_vectors[parameter] in self.vectorised_parameters:
                    reference_vectorised_parameter = self.parameter_vectors[parameter]
                    reference_index = self.vectorised_parameters.index(reference_vectorised_parameter)
                    combo.append(combo[reference_index])
                # If the parameter is a constant, simply add that constant
                else:
                    combo.append(self.parameter_vectors[parameter])
            parameter_set = dict(zip(self.parameters, combo))
            parameter_sets.append(parameter_set)

        return parameter_sets


    def params2indexers(self, parameter_sets):

        indexers = []
        for this_set in parameter_sets:
            indexer = []
            for parameter in this_set:
                # If the parameter is vectorised, get the array index of the appropriate value in the parameter set
                if parameter in self.vectorised_parameters:
                    parameter_value = this_set[parameter]
                    indexer.append(np.where(self.parameter_vectors[parameter]==parameter_value)[0][0])
                # If the parameter is a constant or tracks another vectorised parameter, it is not represented in the index

            indexers.append(indexer)

        return indexers


    def get_complete_parameter_combos(self):

        # Get the parameter combos excluding the non-vectorised quantities
        n_vectorised_params = len(self.vectorised_parameters)
        parameter_combos, indexers = self.get_vectorised_parameter_combos(n_vectorised_params - 1)

        # Add the nonvectorised parameters to the current combo (either a constant or the same as another parameter which was vectorised)
        for combo in parameter_combos:
            for parameter in self.nonvectorised_parameters:
                # If the parameter tracks another vectorised parameter, set it equal to the tracked parameter in this combo
                if self.parameter_vectors[parameter] in self.vectorised_parameters:
                    reference_vectorised_parameter = self.parameter_vectors[parameter]
                    reference_index = self.vectorised_parameters.index(reference_vectorised_parameter)
                    combo.append(combo[reference_index])
                # If the parameter is a constant, simply add that constant
                else:
                    combo.append(self.parameter_vectors[parameter])

        # Confirm that the number of parameter combos is the same as the number of results entries
        if len(parameter_combos) != self.results.size:
            raise Exception('Wrong number of parameter combos were calculated.')

        self.all_indexers = indexers

        return parameter_combos, indexers


    def get_vectorised_parameter_combos(self, i_param):

        # Get the current parameter to add to the lower dimensional results
        this_param = self.vectorised_parameters[i_param]

        # Get the lower dimensional results
        if i_param == 0:
            lower_combo_list, lower_indexer_list = [[]], [[]]
        else:
            lower_combo_list, lower_indexer_list = self.get_vectorised_parameter_combos(i_param - 1)

        # Generate the new combo list
        new_combo_list, new_indexer_list = [], []
        for c, combo in enumerate(lower_combo_list):
            for index, value in enumerate(self.parameter_vectors[this_param]):
                new_combo_list.append(combo + [value])
                new_indexer_list.append(lower_indexer_list[c] + [index])

        return new_combo_list, new_indexer_list