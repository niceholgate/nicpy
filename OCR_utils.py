from PIL import Image
from pdf2image import convert_from_path
import pytesseract
import numpy as np
from fpdf import FPDF
from pathlib import Path

from definitions import POPPLER_BIN_PATH, TESSERACT_EXE_FILEPATH
pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE_FILEPATH

def pdf_pages_to_images(PDF_file_path, image_directory, image_format, compression_factor = 1):
    PDF_directory = Path(PDF_file_path).parent
    PDF_name_folder = str(Path(PDF_file_path).stem)+'_page_images'
    pages = convert_from_path(PDF_file_path, 500, poppler_path=POPPLER_BIN_PATH)

    # Compress the images
    if compression_factor > 1:
        for i in range(len(pages)):
            s = pages[i].size
            pages[i] = pages[i].resize((int(np.round(s[0]/compression_factor)), int(np.round(s[1]/compression_factor))), Image.ANTIALIAS)

    # Iterate through all the pages stored above and save as image files
    if not (PDF_directory / PDF_name_folder).exists(): (PDF_directory / PDF_name_folder).mkdir()
    image_filepaths = []
    for i, page in enumerate(pages):
        filename = 'page_' + str(i+1) + '.'+image_format.lower()
        page.save(str(Path(image_directory)/filename), image_format.upper())
        image_filepaths.append(str(Path(image_directory)/filename))

    return image_filepaths


def image_to_text(image_filepath, language = 'eng'):

    page_image = Image.open(image_filepath)
    try:
        image_to_osd = pytesseract.image_to_osd(page_image)
        orientation = int(np.round(float(image_to_osd.split('Orientation in degrees')[1].split(':')[1].split('\n')[0].strip())))
        if orientation == 180:
            page_image = page_image.rotate(orientation)
    except:
        pass
    try:
        page_string = pytesseract.image_to_string(page_image, lang=language, timeout=5)
        page_string = page_string.replace('-\n', '')
    except RuntimeError as timeout_error:
        page_string = 'pytesseract timeout after 5 seconds'

    return page_string


def image_to_pdf(image_file_path):
    image_directory = Path(image_file_path).parent
    image_name = str(Path(image_file_path).stem)
    page_image = Image.open(image_file_path)
    image_to_pdf = pytesseract.image_to_pdf_or_hocr(page_image, extension='pdf')
    with open(str(image_directory/(image_name+'.pdf')), 'w+b') as f:
        f.write(image_to_pdf)  # pdf type is bytes by default
        print('Successfully wrote {}'.format(str(image_directory/(image_name+'.pdf'))))

    return str(image_directory/(image_name+'.pdf'))


def images_to_pdf(image_file_paths, output_file_path=''):

    cover = Image.open(image_file_paths[0])
    width, height = cover.size
    first_image_directory = Path(image_file_paths[0]).parent
    first_image_name = str(Path(image_file_paths[0]).stem)

    pdf = FPDF(unit="pt", format=[width, height])

    for fp in image_file_paths:
        pdf.add_page()
        pdf.image(fp, 0, 0)

    if output_file_path == '':
        output_file_path = str(first_image_directory/(first_image_name+'.pdf'))
    pdf.output(output_file_path, 'F')

    return output_file_path

#TODO: finish this
def image_table_to_df(image_file_path):

    page_image = Image.open(image_file_path)

    # Get verbose data including boxes, confidences, line and page numbers
    image_to_data_df = pytesseract.image_to_data(page_image, output_type='data.frame')


if __name__=='__main__':
    PDF_file_path = "E:/nicpy/Projects/automate/data/pdf/3.2.7_VXFIBER Ltd UK  March Bank.pdf"
    # poppler_path = r"E:\nicpy\Projects\automate\poppler-0.68.0_x86\poppler-0.68.0\bin"
    # # pdf_pages_to_images(PDF_file_path, poppler_path)
    # image_file_path = r'E:\nicpy\Projects\automate\data\img20200518_10034946_page_images\page_1.jpg'
    # s2=image_to_text(image_file_path, language = 'eng')

    image_file_paths = pdf_pages_to_images(PDF_file_path)
    new_pdf_filepath = images_to_pdf(image_file_paths)

# Other capabilities:
# Get bounding box estimates
# image_to_boxes = pytesseract.image_to_boxes(page_image)
# Get information about orientation and script detection
# image_to_osd = pytesseract.image_to_osd(page_image)
# Get HOCR output
# image_to_hocr = pytesseract.image_to_pdf_or_hocr(page_image, extension='hocr')


# # Open a text file in append mode so that all contents of all images are added to the same file
# f = open("output_text2.txt", "a")
#
# # Finally, write the processed text to the file.
# f.write(page_string_mod)
#
# # Close the file after writing all the text.
# f.close()