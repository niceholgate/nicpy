import fitz
from pathlib import Path
from PyPDF2 import PdfFileMerger, PdfFileReader, PdfFileWriter
import OCR_utils
import os
from PIL import Image
import string
from tika import parser
from io import StringIO
from bs4 import BeautifulSoup
import nicpy.nic_misc as nm
import nicpy.nic_pic as np


def merge_pdfs(input_filepaths_and_pages, output_filepath):

    if not isinstance(input_filepaths_and_pages, dict):
        raise Exception('input_filepaths_and_pages must be a dictionary with keys as pdf file paths and values as ordered lists of their pages to include.')
    if Path(output_filepath).suffix != '.pdf':
        raise Exception('Must specify a \'.pdf\' file extension for output_filepath.')
    output = PdfFileWriter()

    for i, fp in enumerate(input_filepaths_and_pages.keys()):
        file = PdfFileReader(open(fp, "rb"))
        if max(input_filepaths_and_pages[fp]) > file.numPages:
            raise Exception('A non-existent page number was requested for file {} which is {} pages long.'.format(fp, file.numPages))

        for j, page_n in enumerate(input_filepaths_and_pages[fp]):
            # Get the current page to be added to the combined document
            this_page = file.getPage(page_n)
            # If first page, get the size of pages to use in this document
            if i==0 and j==0:
                width = float(this_page.mediaBox[2])
            # Otherwise, scale the subsequent page to match
            else:
                width2 = float(this_page.mediaBox[2])
                scale_fac = width/width2
                this_page.scale(scale_fac, scale_fac)
            output.addPage(this_page)

    outputStream = open(output_filepath, "wb")
    output.write(outputStream)
    outputStream.close()


def decode_pdf(pdf_filepath, image_directory,image_format='PNG'):

    if Path(pdf_filepath).suffix != '.pdf':
        raise Exception('Must specify a \'.pdf\' file extension for input pdf_filepath.')
    image_filepaths = OCR_utils.pdf_pages_to_images(pdf_filepath, image_directory, image_format=image_format)

    output = PdfFileWriter()
    pdf_page_fps = []
    for image_fp in image_filepaths:
        pdf_page_fps.append(OCR_utils.image_to_pdf(image_fp))   # Create a pdf from the image
        file = PdfFileReader(open(pdf_page_fps[-1], "rb"))           # Open the image's pdf
        output.addPage(file.getPage(0))                         # Add the page to the new document

    new_filepath = str(Path(pdf_filepath).parent / (Path(pdf_filepath).stem + '_decoded' + Path(pdf_filepath).suffix))
    outputStream = open(new_filepath, "wb")
    output.write(outputStream)
    outputStream.close()

    # Delete the temporary image files created
    if image_filepaths:
        for fp in image_filepaths: os.remove(fp)

    return new_filepath




# Detects if some parsed file text is likely to be encrypted (appears as gibberish and requires the file to instead be read as an image by a text recogniser)
def is_probably_encrypted(file_contents_string, n_consecutive_symbols=4):

    # Does it contain n consecutive symbols?
    contains_consecutive_symbols = False
    for i in range(len(file_contents_string) - n_consecutive_symbols + 1):
        portion = file_contents_string[i:i+n_consecutive_symbols]
        for i, char in enumerate(portion):
            if char not in string.punctuation+'�':
                break
            if i == len(portion)-1: contains_consecutive_symbols = True

    # Does it contain any common small words?
    contains_small_words = False
    small_words = ['an', 'the', 'of', 'for', 'from', 'to', 'on', 'in', 'can', 'is', 'be', 'good', 'bad']
    for word in small_words:
        occurrences = nm.count_text_occurrences(file_contents_string, word, case_sensitive=False, whole_phrase_only=True, get_line_numbers=False)
        if occurrences > 0:
            contains_small_words = True
            break

    if contains_consecutive_symbols or (not contains_small_words): return True
    return False


def count_extract_pdf_images(pdf_file_path, save_images = False):
    doc, count, saved_image_filepaths = fitz.open(pdf_file_path), 0, []
    pdf_directory, pdf_name = Path(pdf_file_path).parent, str(Path(pdf_file_path).stem)
    for i in range(len(doc)):
        page = i+1
        for img in doc.getPageImageList(i):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)
            if pix.n < 5:  # this is GRAY or RGB
                # Mysterious plain black images are just 3 characters long if these replacements made
                if len(str(pix.samples).replace('\\','').replace('x','').replace('f','').replace('0','')) > 3:
                    count += 1
                    image_name = '{}_image_{}_page_{}.png'.format(pdf_name, count, page)
                    if save_images:
                        if not (pdf_directory / (pdf_name + '_images')).exists(): (pdf_directory / (pdf_name + '_images')).mkdir()
                        pix.writePNG(str(pdf_directory/(pdf_name+'_images')/image_name))
                        saved_image_filepaths.append(str(pdf_directory/(pdf_name+'_images')/image_name))
            else:  # CMYK: convert to RGB first
                pix1 = fitz.Pixmap(fitz.csRGB, pix)
                # Mysterious plain black images are just 3 characters long if these replacements made
                if len(str(pix1.samples).replace('\\', '').replace('x', '').replace('f', '').replace('0', '')) > 3:
                    count += 1
                    image_name = '{}_image_{}_page_{}.png'.format(pdf_name, count, page)
                    if save_images:
                        if not (pdf_directory/(pdf_name+'_images')).exists(): (pdf_directory/(pdf_name+'_images')).mkdir()
                        pix1.writePNG(str(pdf_directory/(pdf_name+'_images')/image_name))
                        saved_image_filepaths.append(str(pdf_directory / (pdf_name + '_images') / image_name))
                pix1 = None
            pix = None
    return count, saved_image_filepaths


def tika_read(pdf_file_path):
    pages, _buffer = [], StringIO()
    data = parser.from_file(pdf_file_path, xmlContent=True)
    xhtml_data = BeautifulSoup(data['content'], features="lxml")
    for content in xhtml_data.find_all('div', attrs={'class': 'page'}):
        _buffer.write(str(content))
        parsed_content = parser.from_buffer(_buffer.getvalue())
        _buffer.truncate()
        pages.append(parsed_content['content'])

    return pages

def remove_greyscale_watermark(PDF_file_path, to_black_upperbound, to_white_lowerbound,
                               compression_factor = 1,
                               replacement_watermark='',
                               replacement_watermark_font = 'Arial',
                               replacement_watermark_text_size=20,
                               replacement_watermark_colour=(50,50,50,255),
                               replacement_watermark_text_center = (200, 200),
                               replacement_watermark_rotation_angle=0,
                               output_file_path = '',
                               jpg_quality = 75):

    image_fps = OCR_utils.pdf_pages_to_images(PDF_file_path, str(Path(PDF_file_path).parent), 'BMP', compression_factor=compression_factor)
    mod_image_fps = []
    for image_fp in image_fps:
        im = Image.open(image_fp)
        pix, s = im.load(), im.size

        # Examine RGB of specified pixels
        # i_wm, j_wm = 1422, 3071
        # wm_grey = pix[i_wm - 1, j_wm - 1] #173
        # i_ol, j_ol = 1579, 2902
        # ol_grey = pix[i_ol - 1, j_ol - 1] #81

        # # Determine the most common RGBs
        # dict_of_colours = {}
        # for i in range(s[0]):
        #     for j in range(s[1]):
        #         col = pix[i, j]
        #         if col not in dict_of_colours.keys():
        #             dict_of_colours[col] = 1
        #         else:
        #             dict_of_colours[col] += 1
        # dict_of_colours = {k: v for k, v in sorted(dict_of_colours.items(), key=lambda item: item[1], reverse=True)}
        # len([tup for tup in dict_of_colours.keys() if tup[0]==tup[1] and tup[1]==tup[2]]) == len(dict_of_colours.keys()) # Check if all are greyscale

        for i in range(s[0]):
            for j in range(s[1]):
                col = pix[i, j]
                if col[0]>=to_white_lowerbound:
                    pix[i, j] = (255,255,255)
                elif col[0]<=to_black_upperbound:
                    pix[i, j] = (0, 0, 0)

        if replacement_watermark:
            fp, im=np.add_text_line_to_image(im, replacement_watermark, replacement_watermark_text_center,
                            text_size=replacement_watermark_text_size,
                            text_box_pixel_width = 0,
                            RGBA=replacement_watermark_colour,
                            text_background_RGBA = (0,0,0,0),
                            text_box_RGBA = (0,0,0,0),
                            rot_degrees=replacement_watermark_rotation_angle,
                            font_name = replacement_watermark_font,
                            show_result = False)


        im.save(image_fp[:-4]+'_mod.jpg', quality=jpg_quality)
        mod_image_fps.append(image_fp[:-4]+'_mod.jpg')

    OCR_utils.images_to_pdf(mod_image_fps, output_file_path=output_file_path)
    # Delete the temporary image files created
    if image_fps or mod_image_fps:
        for fp in image_fps+mod_image_fps: os.remove(fp)

# TODO: Need to save .jpg instead of huge .bmp files
if __name__ == '__main__':
    # PDF_file_path = r'C:\Users\Nick\Desktop\wms\Scour Limited Mock 4 - Answer Pack - v1_0.pdf'
    # to_black_upperbound = 110
    # to_white_lowerbound = 160
    # remove_greyscale_watermark(PDF_file_path, to_black_upperbound, to_white_lowerbound,
    #                            replacement_watermark='', output_file_path=PDF_file_path[:-4]+'new.pdf', jpg_quality=60, compression_factor=2)

    for doc in ['Mock 5 - Answer Pack - v1_0',
                'Mock 5 - Exhibit 14 - v1_0',
                'Mock 5 - Exhibits 15 to 18 - v1_0',
                'Mock 5 - List of Exhs - v1_0',
                'Mock 6 - Answer Pack - v1_0',
                'Mock 6 - Exhibit 14 - v1_0',
                'Mock 6 - Exhibits 15 to 18 - v1_0',
                'Mock 6 - List of Exhibits and requirement - v1_0']:
        PDF_file_path = r'C:\Users\Nick\Desktop\docs\{}.pdf'.format(doc)
        to_black_upperbound = 110
        to_white_lowerbound = 160
        remove_greyscale_watermark(PDF_file_path, to_black_upperbound, to_white_lowerbound,
                                   replacement_watermark='', output_file_path=PDF_file_path[:-4] + 'new.pdf', jpg_quality=60, compression_factor=2)

# decode_pdf(r'E:\nicpy\Projects\automate\data\pdf\Scour Limited Mock 2 - Answer Pack - v1_0_Jia Li.pdf', r'E:\nicpy\Projects\automate\data\pdf',image_format='PNG')
# if __name__=='__main__':
#     pdf_file_path1  = r'D:\Sync\Writings\JofT\Holgate et al. - TURBO-18-1217.pdf'
#     pdf_file_path2  = r'E:\nicpy\Projects\automate\data\pdf\3.2.7_VXFIBER Ltd UK  March Bank.pdf'
#     pdf_file_path2_decoded = r'E:\nicpy\Projects\automate\data\pdf\3.2.7_VXFIBER Ltd UK  March Bank_decoded.pdf'
#     output_filepath = r'D:\Sync\Writings\JofT\1.pdf'
#     output_filepathd = r'D:\Sync\Writings\JofT\1d.pdf'
#     merge_pdfs({pdf_file_path1:[14,2],pdf_file_path2:[4,3]}, output_filepath)
#     merge_pdfs({pdf_file_path1: [14, 2], pdf_file_path2_decoded: [4, 3]}, output_filepathd)
