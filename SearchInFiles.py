import os
import string
import win32com.client
from pathlib import Path
from pptx import Presentation
from datetime import datetime

import shutil
import subprocess
import sys

import nic_misc
import nic_str
import nic_data_structs
import ppt_utils
import pdf_utils
import OCR_utils
from definitions import POPPLER_BIN_PATH, TESSERACT_EXE_FILEPATH
import itertools

# TODO: Add Word, Excel, CSV, images etc.
# TODO: search image files for text

# TODO: make use of the temp directory for all temp images and pdfs etc


class SearchInFiles:

    known_types = {
        'plaintext'     : ['.py', '.txt', '.log', '.bat', '.java'],
        'fancytext'     : ['.pdf', '.docx'],
        'spreadsheet'   : ['.xlsx', '.csv'],
        'presentation'  : ['.pptx'],
        'images'        : ['.jpg', '.png', '.bmp', '.tif', '.tiff']
    }
    data_categories = list(known_types.keys())
    all_known_types = set(itertools.chain.from_iterable(known_types.values()))

    def __init__(self, search_root_directory, search_strings, requested_types = None, output_directory = None, case_sensitive=False, whole_phrase_only=True, allow_OCR=True, search_in_doc_images=False):

        self.check_inputs(search_root_directory=search_root_directory, search_strings=search_strings,
                          requested_types=requested_types, output_directory=output_directory, case_sensitive=case_sensitive,
                          whole_phrase_only=whole_phrase_only, allow_OCR=allow_OCR, search_in_doc_images=search_in_doc_images)

        self.output_directory = Path(output_directory) if output_directory == '' else Path(search_root_directory).parent / 'file_search_outputs'
        self.temp_directory = Path(search_root_directory).parent / 'file_search_temp'
        for directory in [self.output_directory, self.temp_directory]:
            if not directory.exists(): directory.mkdir()

        self.parameters = {
            'search_root_directory'  :   search_root_directory,
            'search_strings'         :   search_strings,
            'requested_types'        :   requested_types,
            'case_sensitive'         :   case_sensitive,
            'whole_phrase_only'      :   whole_phrase_only,
            'allow_OCR'              :   allow_OCR,
            'search_in_doc_images'   :   search_in_doc_images
        }

        candidate_file_paths, files_to_search_inside = self.find_all_file_paths()               # Get all the file paths of known file types in the search_root_directory,
                                                                                                # and the ones to search inside according to requested types
        self.results = {'candidate_file_paths'      :   candidate_file_paths,
                        'files_to_search_inside'    :   files_to_search_inside,         # \/ Preallocation for info about files which are found to contain keywords \/
                        'containing_file_paths'     :   {search_string : {cat: {} for cat in self.data_categories} for search_string in self.parameters['search_strings']},
                        'failed_file_paths'         :   {cat: {} for cat in self.data_categories},  # Preallocation for files which could not be loaded or read and reasons why
                                                                                                    # \/ Preallocation for lists of pdf reading steps used for each pdf file
                        'pdf_reading_steps'         :   {pdf_fp:[] for pdf_fp in files_to_search_inside['fancytext'] if Path(pdf_fp).suffix=='.pdf'},
                        'file_slide_sizes'          :   {}}                                         # Preallocation for sizes of each presentation file's slides

        self.search_in_plaintexts()       # Get all the file paths of requested type which contain the requested text
        # self.search_in_fancytexts()         # i.e. populate self.results['containing_file_paths']
        # self.search_in_spreadsheets()
        self.search_in_presentations()

        self.print_search_results()

    @staticmethod
    def check_inputs(search_root_directory, search_strings, requested_types, output_directory, case_sensitive,
                     whole_phrase_only, allow_OCR, search_in_doc_images):

        # search_root_directory is a string and must exist
        if not isinstance(search_root_directory, str):
            raise Exception('search_root_directory must be entered as a string of an extant directory (in which to search all subdirectories for files).')
        if search_root_directory == '' or not Path(search_root_directory).exists():
            raise Exception('search_root_directory must be an extant directory (in which to search all subdirectories for files).')

        # Cannot search in a drive as there can be no parent directory in which to make temp folder or output folder
        if Path(search_root_directory).drive == Path(search_root_directory):
            raise Exception('Cannot search in a drive root e.g. \'C:/\', because temporary files are stored by default in a folder in the search_root_directory parent folder.')

        # search_strings must be a list of strings
        if not nic_data_structs.is_list_of(str, search_strings):
            raise Exception('search_strings must be a list of strings (or a single string in a list).')

        # Check that requested_types is a list of strings and that all the requested_types are known by the class
        if not nic_data_structs.is_list_of(str, requested_types):
            raise Exception('search_strings must be a list of strings (or a single string in a list).')
        types_not_known = [rt for rt in requested_types if rt not in SearchInFiles.all_known_types]
        if types_not_known: raise Exception('The following requested file types are not known by the class: {}'.format(types_not_known))

        # If an output_directory was specified, check that it exists
        if output_directory != None:
            if not Path(output_directory).exists():
                raise Exception('Specified output_directory must exist (or set to default empty string and a default output folder will be created in the parent of the search_root_directory).')

            # Outputs folder must be outside the search directory or else error
            descend = Path(output_directory)
            while descend != Path(output_directory).drive:
                if descend == Path(search_root_directory):
                    raise Exception('The specified output_directory must not be within the search_root_directory.')
                descend = descend.parent

        # Check that binary parameters are all booleans
        if not all([type(parameter) == bool for parameter in [case_sensitive, whole_phrase_only, allow_OCR, search_in_doc_images]]):
            raise Exception('The following input parameters must all be booleans: {}'.format([case_sensitive, whole_phrase_only, allow_OCR, search_in_doc_images]))

        # If allow_OCR set True, need to verify accessability of Tesseract
        if allow_OCR:
            reqs = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'])
            installed_packages = [r.decode().split('==')[0] for r in reqs.split()]
            if 'pytesseract' not in installed_packages:
                raise Exception('allow_OCR (Optical Character Recognition) has been requested, but the \'pytesseract\' package is not installed.\n'
                                'Install with \'pip install pytesseract\'.')
            if 'tesseract.exe' not in TESSERACT_EXE_FILEPATH or not Path(TESSERACT_EXE_FILEPATH).exists():
                raise Exception('allow_OCR (Optical Character Recognition) has been requested, but the TESSERACT_EXE_FILEPATH has not been set correctly.\n'
                                'Install Tesseract (https://github.com/UB-Mannheim/tesseract/wiki) and then set the TESSERACT_EXE_FILEPATH variable in definitions.py to the \'tesseract.exe\' filepath.')
            if Path(POPPLER_BIN_PATH).stem != 'bin' or not Path(POPPLER_BIN_PATH).exists() or 'poppler' not in POPPLER_BIN_PATH:
                raise Exception('allow_OCR (Optical Character Recognition) has been requested, but the poppler_bin_path has not been set correctly.\n'
                                'Install Poppler (http://blog.alivate.com.au/poppler-windows/) and then set the poppler_bin_path variable in definitions.py to the installed Poppler /bin/ subdirectory.')

        # Cannot request search_in_doc_images without OCR being allowed
        if search_in_doc_images and not allow_OCR:
            raise Exception('Cannot request to search inside document images (search_in_doc_images=True) without OCR being allowed (allow_OCR=True).')

        # Cannot request search in image files without OCR being allowed
        image_file_types_requested = [rt for rt in requested_types if rt not in SearchInFiles.known_types['images']]
        if image_file_types_requested and not allow_OCR:
            raise Exception('Cannot search in the requested image file types ({}) without OCR being allowed (allow_OCR=True).'.format(image_file_types_requested))

    def find_all_file_paths(self):

        directories = [x[0] for x in os.walk(str(self.parameters['search_root_directory']))]
        candidate_file_paths = []
        for directory in directories:
            files = os.listdir(str(directory))
            candidate_file_paths += [Path(directory) / file for file in files if            # '~$' files are temporary Office files present when the main file is opened
                                     ((Path(directory) / file).suffix in self.all_known_types) and ('~$' not in str(Path(directory) / file))]

        files_to_search_inside = {}
        for cat in self.known_types.keys():
            this_cat_requested_types = [el for el in self.parameters['requested_types'] if el in self.known_types[cat]] if self.parameters['requested_types'] else self.known_types[cat]
            files_to_search_inside[cat] = [str(p) for p in candidate_file_paths if p.suffix in this_cat_requested_types]

        return candidate_file_paths, files_to_search_inside

    def search_in_fancytexts(self):

        for index_file, file_path in enumerate(self.results['files_to_search_inside']['fancytext']):
            if Path(file_path).suffix == '.pdf':
                self.search_in_pdfs(file_path)

            elif Path(file_path).suffix == '.docx':
                self.search_in_docxs(file_path)

    def search_in_pdfs(self, file_path):

        # Read the text with tika and parse into individual pages with BeautifulSoup
        # TODO: test with 1 page pdf
        pages = pdf_utils.tika_read()

        # If the file contains 4 or more consecutive symbols, it is probably encrypted
        file_probably_encrypted = False
        for page_text in pages:
            if page_text is None or pdf_utils.is_probably_encrypted(page_text, n_consecutive_symbols=4):
                file_probably_encrypted = True
                break

        # 1. If probably encrypted and OCR allowed, analyse the pages with Tesseract OCR (Optical Character Recognition)
        if file_probably_encrypted and self.parameters['allow_OCR']:
            self.results['pdf_reading_steps'][file_path].append('encrypted: used page OCR')
            page_image_filepaths = OCR_utils.pdf_pages_to_images(file_path, self.temp_directory, 'jpg')      # Convert pdf pages to image files and save list of their filepaths
            for i, image_fp in enumerate(page_image_filepaths):                  # Use OCR on each page to get a text string for each
                page_text = OCR_utils.image_to_text(image_fp, language = 'eng')
                for search_string in self.parameters['search_strings']:
                    line_numbers = nic_str.count_text_occurrences(page_text, search_string, self.parameters['case_sensitive'], self.parameters['whole_phrase_only'], get_line_numbers=True)
                    if len(line_numbers) > 0:
                        if str(file_path) not in list(self.results['containing_file_paths'][search_string]['fancytext'].keys()):
                            self.results['containing_file_paths'][search_string]['fancytext'][str(file_path)] = {}
                        self.results['containing_file_paths'][search_string]['fancytext'][str(file_path)]['page '+str(i+1)] = line_numbers
            # Delete the temporary image files created
            if page_image_filepaths:
                for fp in page_image_filepaths: os.remove(fp)
        # 2. If probably encrypted but cannot use OCR, add to failed file paths store
        elif file_probably_encrypted and not self.parameters['allow_OCR']:
            self.results['failed_file_paths']['fancytext'][(str(file_path))] = 'File appears to be encrypted and OCR has not been allowed/is not available.'
            self.results['pdf_reading_steps'][file_path].append('encrypted: OCR not allowed')
        # 3. If probably not encrypted, analyse the tika text of each page
        else:
            self.results['pdf_reading_steps'][file_path].append('unencrypted: analyse tika text')
            for i, page_text in enumerate(pages):
                for search_string in self.parameters['search_strings']:
                    line_numbers = nic_str.count_text_occurrences(page_text, search_string, self.parameters['case_sensitive'], self.parameters['whole_phrase_only'], get_line_numbers=True)
                    if len(line_numbers) > 0:
                        if str(file_path) not in list(self.results['containing_file_paths'][search_string]['fancytext'].keys()):
                            self.results['containing_file_paths'][search_string]['fancytext'][str(file_path)] = {}
                        self.results['containing_file_paths'][search_string]['fancytext'][str(file_path)]['page '+str(i+1)] = line_numbers

            # Check if the pdf has any images - if desired, these can be analysed separately with OCR (not needed in encrypted case)
            if self.parameters['search_in_doc_images'] and self.parameters['allow_OCR']:
                self.results['pdf_reading_steps'][file_path].append('unencrypted: search in images')
                n_images, saved_image_filepaths = pdf_utils.count_extract_pdf_images(file_path, save_images = True)
                if n_images > 0:
                    for j, image_fp in enumerate(saved_image_filepaths):
                        image_text = OCR_utils.image_to_text(image_fp, language='eng')
                        for search_string in self.parameters['search_strings']:
                            occurrences = nic_str.count_text_occurrences(image_text, search_string, self.parameters['case_sensitive'], self.parameters['whole_phrase_only'])
                            if occurrences > 0:
                                page_number = Path(file_path).stem.split('_page_')[-1]
                                if str(file_path) not in list(self.results['containing_file_paths'][search_string]['fancytext'].keys()):
                                    self.results['containing_file_paths'][search_string]['fancytext'][str(file_path)] = {}
                                self.results['containing_file_paths'][search_string]['fancytext'][str(file_path)]['image {} on page {}'.format(j+1, page_number)] = '{} occurrences'.format(occurrences)

    # TODO: docx
    # def search_in_docxs(self, file_path):
    #
    #     # Check text ala pptx
    #
    #     # If requested, extract images and check

    def search_in_plaintexts(self):

        for index_file, file_path in enumerate(self.results['files_to_search_inside']['plaintext']):
            file = open(str(file_path), 'r')
            try:
                file_text = file.read()
            except:
                self.results['failed_file_paths']['plaintext'][str(file_path)] = 'Could not read file.'
                continue
            print('Searching in plaintext file {} of {}...'.format(index_file + 1, len(self.results['files_to_search_inside']['plaintext'])))
            for search_string in self.parameters['search_strings']:
                line_numbers = nic_str.count_text_occurrences(file_text, search_string, self.parameters['case_sensitive'], self.parameters['whole_phrase_only'], get_line_numbers=True)
                if len(line_numbers)>0:
                    self.results['containing_file_paths'][search_string]['plaintext'][str(file_path)] = line_numbers

    def search_in_presentations(self):

        ppt_instance, slide_counter = win32com.client.Dispatch('PowerPoint.Application'), 0
        for index_file, file_path in enumerate(self.results['files_to_search_inside']['presentation']):
            print('Searching in presentation file {} of {}...'.format(index_file+1, len(self.results['files_to_search_inside']['presentation'])))
            read_only, has_title, window = False, False, False
            prs = ppt_instance.Presentations.open(file_path, read_only, has_title, window)
            self.results['file_slide_sizes'][file_path] = (prs.PageSetup.SlideWidth, prs.PageSetup.SlideHeight)

            for index_slide, Slide in enumerate(prs.Slides):
                for index_shape, Shape in enumerate(Slide.Shapes):
                    slide_string = 'Slide ' + str(index_slide + 1)
                    object_string = 'Object ' + str(index_shape + 1)
                    if Shape.HasTextFrame:
                        if Shape.TextFrame.HasText:
                            paragraphs_specialchars_removed = [p.Text for p in Shape.TextFrame.TextRange.Paragraphs() if (p.Text !='\r')]
                            for index_paragraph, Paragraph in enumerate(paragraphs_specialchars_removed):
                                for search_string in self.parameters['search_strings']:
                                    occurrences = nic_str.count_text_occurrences(Paragraph, search_string, self.parameters['case_sensitive'], self.parameters['whole_phrase_only'])
                                    if occurrences > 0:
                                        slide_counter += 1
                                        if str(file_path) not in list(self.results['containing_file_paths'][search_string]['presentation'].keys()):
                                            self.results['containing_file_paths'][search_string]['presentation'][str(file_path)] = {}
                                        paragraph_string = 'Paragraph ' + str(index_paragraph + 1)
                                        occurrences_string = str(occurrences) + ' occurrence' if occurrences == 1 else str(occurrences) + ' occurrences'
                                        combined_string = object_string + ', ' + paragraph_string + ', ' + occurrences_string
                                        if slide_string in list(self.results['containing_file_paths'][search_string]['presentation'][str(file_path)].keys()):
                                            self.results['containing_file_paths'][search_string]['presentation'][str(file_path)][slide_string].append(combined_string)
                                        else:
                                            self.results['containing_file_paths'][search_string]['presentation'][str(file_path)][slide_string] = [combined_string]
                    if Shape.Type in [3, 21, 28, 11, 13] and self.parameters['search_in_doc_images'] and self.parameters['allow_OCR']:
                        img_fp = str(self.temp_directory/'{}_{}_{}.jpg'.format(str(Path(file_path).stem).replace('.',''), slide_string, object_string))
                        Shape.Export(img_fp, 3)
                        try:
                            image_text = OCR_utils.image_to_text(img_fp, language='eng')
                        except:
                            image_text = ''
                        for search_string in self.parameters['search_strings']:
                            occurrences = nic_str.count_text_occurrences(image_text, search_string, self.parameters['case_sensitive'], self.parameters['whole_phrase_only'])
                            occurrences_string = str(occurrences) + ' occurrence' if occurrences == 1 else str(occurrences) + ' occurrences'
                            combined_string = object_string + ' (image), ' + occurrences_string
                            if occurrences > 0:
                                if str(file_path) not in list(self.results['containing_file_paths'][search_string]['presentation'].keys()):
                                    self.results['containing_file_paths'][search_string]['presentation'][str(file_path)] = {}
                                if slide_string in list(self.results['containing_file_paths'][search_string]['presentation'][str(file_path)].keys()):
                                    self.results['containing_file_paths'][search_string]['presentation'][str(file_path)][slide_string].append(combined_string)
                                else:
                                    self.results['containing_file_paths'][search_string]['presentation'][str(file_path)][slide_string] = [combined_string]
                        os.remove(img_fp)

    def print_search_results(self):

        for cat in self.known_types.keys():
            this_cat_files_with_keywords = []
            for search_string in self.parameters['search_strings']:
                this_cat_files_with_keywords += list(self.results['containing_file_paths'][search_string][cat].keys())
            this_cat_files_with_keywords = list(set(this_cat_files_with_keywords))
            print('The following candidate {} files were found to contain requested keywords '
                  '(case_sensitive={}, whole_phrase_only={}):'.format(cat, self.parameters['case_sensitive'], self.parameters['whole_phrase_only']))
            if not this_cat_files_with_keywords: print('     None')
            for file in this_cat_files_with_keywords: print('     ' + file)

    def presentation_output(self, output_directory):

        files_slides_data = {}
        for search_string in self.results['containing_file_paths'].keys():
            for file_path in self.results['containing_file_paths'][search_string]['presentation'].keys():
                for slide_string in self.results['containing_file_paths'][search_string]['presentation'][str(file_path)].keys():
                    index_slide = nic_misc.ints_in_str(slide_string)-1
                    paragraph_occurrences = [nic_misc.ints_in_str(descriptor.split(',')[2]) for descriptor in self.results['containing_file_paths'][search_string]['presentation'][str(file_path)][slide_string]]
                    occurrences = sum(paragraph_occurrences)
                    if file_path not in files_slides_data.keys():
                        files_slides_data[file_path] = {index_slide : {search_string : occurrences}}
                    else:
                        if index_slide not in files_slides_data[file_path].keys():
                            files_slides_data[file_path][index_slide] = {search_string : occurrences}
                        elif search_string not in files_slides_data[file_path][index_slide].keys():
                            files_slides_data[file_path][index_slide][search_string] = occurrences
        files_slides_messages = {file_path:[] for file_path in files_slides_data.keys()}
        for file_path in files_slides_data.keys():
            for index_slide in files_slides_data[file_path].keys():
                message = '~~~~~~~~~~~\n'
                message += 'Keyword search was completed with case_sensitive={} and whole_phrase_only={}.\n'.format(self.parameters['case_sensitive'], self.parameters['whole_phrase_only'])
                message += 'Searched in: {}\n'.format(self.search_root_directory)
                message += 'Searched for: {}\n'.format(self.parameters['search_strings'])
                message += 'This is slide {} of file {}.\n'.format(index_slide+1, file_path)
                for search_string in files_slides_data[file_path][index_slide].keys():
                    occurrences = files_slides_data[file_path][index_slide][search_string]
                    message += 'It contains {} occurrences of search string \'{}\'.\n'.format(str(occurrences), search_string)
                message += '~~~~~~~~~~~\n'

                files_slides_messages[file_path].append((index_slide, message))
        ppt_utils.grab_slides(files_slides_messages, self.results['file_slide_sizes'], output_directory)

    def pdf_output(self, output_directory):
        output_directory = Path(output_directory)
        if not output_directory.exists(): output_directory.mkdir()
        dt_string = nic_misc.get_YYYYMMDDHHMMSS_string(datetime.now(), '-', '_')
        output_filepath = Path(output_directory) / 'keyword_results_combined_pdf_{}_{}.pdf'.format(self.parameters['search_strings'], dt_string)

        component_filepaths_and_pages = {}
        for search_string in self.results['containing_file_paths'].keys():
            for file_path in self.results['containing_file_paths'][search_string]['fancytext'].keys():
                if file_path not in component_filepaths_and_pages.keys(): component_filepaths_and_pages[file_path] = []
                for page_string in self.results['containing_file_paths'][search_string]['fancytext'][file_path]:
                    component_filepaths_and_pages[file_path].append(nic_misc.ints_in_str(page_string))
        pdf_utils.merge_pdfs(component_filepaths_and_pages, output_filepath)





if __name__=='__main__':

    search = SearchInFiles(search_root_directory=r'C:\dev\nicpy\test\test_data', search_strings=['No insert'],
                           case_sensitive=True, whole_phrase_only=True, search_in_doc_images=False)

    # search.pdf_output(r'E:\nicpy\Projects\automate\data\output')
    # search.presentation_output(r'E:\nicpy\Projects\automate\output')

