import string

# Get all of the integers in a string
def ints_in_str(string):
    return int(''.join(x for x in string if x.isdigit()))


def get_YYYYMMDDHHMMSS_string(datetime, connector1, connector2):

    YYYY, month, day = str(datetime.year), str(datetime.month), str(datetime.day)
    hours, mins, secs = str(datetime.hour), str(datetime.minute), str(datetime.second)
    MM = month if len(month) == 2 else '0' + month
    DD = day if len(day) == 2 else '0' + day
    hh = hours if len(hours) == 2 else '0' + hours
    mm = mins if len(mins) == 2 else '0' + mins
    ss = secs if len(secs) == 2 else '0' + secs

    return connector1.join([YYYY, MM, DD]) + ' ' + connector2.join([hh, mm, ss])


def get_parameter_string(parameters):

    parameter_string = '_'.join([parameter+'='+str(parameters[parameter]) for parameter in parameters.keys()])

    return parameter_string

# temp backup copy
# def count_text_occurrences(text, search_string, case_sensitive, whole_phrase_only, get_line_numbers = False):
#     search_in_string = text if case_sensitive else text.upper()
#     search_string_test = search_string if case_sensitive else search_string.upper()
#     line_numbers = []
#     if len(search_string) == len(search_in_string):
#         occurrences = 1 if search_in_string == search_string_test else 0
#     elif len(search_string) > len(text):
#         occurrences = 0
#     elif len(search_string) < len(text):
#         occurrences = 0
#         for i in range(len(search_in_string) - len(search_string) + 1):
#             # TODO: check this is searching the whole paragraph
#             text_portion = search_in_string[i:i + len(search_string)]
#             if whole_phrase_only:
#                 if text_portion == search_string_test:
#                     if (i == 0) and (text[i + len(search_string_test)] in (string.whitespace + string.punctuation)):
#                         occurrences += 1
#                         if get_line_numbers:
#                             if not line_numbers:
#                                 line_numbers = [text[:i].count('\n')+1]
#                             else:
#                                 line_numbers.append(line_numbers[-1]+text[last_i+len(search_string)-1:i].count('\n'))
#                             last_i = i
#
#                     elif (i == len(text) - len(search_string)) and (text[i - 1] in (string.whitespace + string.punctuation)):
#                         occurrences += 1
#                         if get_line_numbers:
#                             if not line_numbers:
#                                 line_numbers = [text[:i].count('\n')+1]
#                             else:
#                                 line_numbers.append(line_numbers[-1]+text[last_i+len(search_string)-1:i].count('\n'))
#                             last_i = i
#
#                     elif (i > 0) and (i < len(text) - len(search_string)):
#                         if (text[i - 1] in (string.whitespace + string.punctuation)) and (text[i + len(search_string_test)] in (string.whitespace + string.punctuation)):
#                             occurrences += 1
#                             if get_line_numbers:
#                                 if not line_numbers:
#                                     line_numbers = [text[:i].count('\n') + 1]
#                                 else:
#                                     line_numbers.append(line_numbers[-1] + text[last_i + len(search_string) - 1:i].count('\n'))
#                                 last_i = i
#             else:
#                 if text_portion == search_string_test:
#                     occurrences += 1
#                     if get_line_numbers:
#                         if not line_numbers:
#                             line_numbers = [text[:i].count('\n') + 1]
#                         else:
#                             line_numbers.append(line_numbers[-1] + text[last_i + len(search_string) - 1:i].count('\n'))
#                         last_i = i
#
#     if get_line_numbers: return line_numbers
#     return occurrences

def count_text_occurrences(text, search_string, case_sensitive, whole_phrase_only, get_line_numbers = False):
    search_in_string = text if case_sensitive else text.upper()
    search_string_test = search_string if case_sensitive else search_string.upper()
    line_numbers = []
    if len(search_string) == len(search_in_string):
        occurrences = 1 if search_in_string == search_string_test else 0
        line_numbers = [1]
    elif len(search_string) > len(text):
        occurrences = 0
    elif len(search_string) < len(text):
        occurrences = 0
        for i in range(len(search_in_string) - len(search_string) + 1):
            # TODO: check this is searching the whole paragraph
            text_portion = search_in_string[i:i + len(search_string)]
            if whole_phrase_only:
                if text_portion == search_string_test:
                    if (i == 0) and (text[i + len(search_string_test)] in (string.whitespace + string.punctuation)):
                        occurrences += 1
                        if get_line_numbers:
                            line_numbers, last_i = _get_line_numbers(line_numbers, text, i, last_i, search_string)

                    elif (i == len(text) - len(search_string)) and (text[i - 1] in (string.whitespace + string.punctuation)):
                        occurrences += 1
                        if get_line_numbers:
                            line_numbers, last_i = _get_line_numbers(line_numbers, text, i, last_i, search_string)

                    elif (i > 0) and (i < len(text) - len(search_string)):
                        if (text[i - 1] in (string.whitespace + string.punctuation)) and (text[i + len(search_string_test)] in (string.whitespace + string.punctuation)):
                            occurrences += 1
                            if get_line_numbers:
                                line_numbers, last_i = _get_line_numbers(line_numbers, text, i, last_i, search_string)
            else:
                if text_portion == search_string_test:
                    occurrences += 1
                    if get_line_numbers:
                        line_numbers, last_i = _get_line_numbers(line_numbers, text, i, last_i, search_string)

    if get_line_numbers: return line_numbers
    return occurrences

def _get_line_numbers(line_numbers, text, i, last_i, search_string):
    if not line_numbers:
        line_numbers = [text[:i].count('\n') + 1]
    else:
        line_numbers.append(line_numbers[-1] + text[last_i + len(search_string) - 1:i].count('\n'))
    last_i = i
    return line_numbers, last_i

def to_pascal_case(original_string):
    modified_string = original_string.replace('_', ' ')
    modified_string = modified_string.title().replace(' ', '')
    return modified_string



