from PIL import Image, ImageDraw, ImageFont
import numpy as np
from pathlib import Path
from datetime import datetime
import nicpy.nic_misc as nm
from nicpy.definitions import FFMPEG_FILEPATH
import subprocess
import os

# import multiprocessing as mp

# Convert Image.getdata() data to RGB array
def RGB_image_data_to_array(image_data, size):

    r, g, b = [el[0] for el in image_data], [el[1] for el in image_data], [el[2] for el in image_data]
    the_order = 'F'
    data_array_r = np.reshape(r, size, order=the_order)
    data_array_g = np.reshape(g, size, order=the_order)
    data_array_b = np.reshape(b, size, order=the_order)
    return np.array([data_array_r, data_array_g, data_array_b])


# Pixelation based on mean colour
# TODO: add comments
def pixelate_mean_colour(original_image, new_pixels_x):
    data = original_image.getdata()
    original_size = data.size
    data_array = RGB_image_data_to_array(data, original_size)

    original_pixels_per_new_pixel = int(np.floor(data.size[0] / new_pixels_x))
    last_x_pixel_longer = data.size[0] % original_pixels_per_new_pixel != 0
    # x_remainder = data.size[0] % original_pixels_per_new_pixel
    # y_remainder = data.size[1] % original_pixels_per_new_pixel
    new_pixels_y = int(np.floor(data.size[1] / original_pixels_per_new_pixel))
    last_y_pixel_longer = data.size[1] % original_pixels_per_new_pixel != 0
    new_image = Image.new('RGB', (new_pixels_x, new_pixels_y))

    recon = Image.new('RGB', original_size)
    reconstruct_old_image = []
    for y in range(data.size[1]):
        for x in range(data.size[0]):
            reconstruct_old_image.append((data_array[0, x, y], data_array[1, x, y], data_array[2, x, y]))
    recon.putdata(reconstruct_old_image)
    recon.show()
    new_data = []

    unused_pixels_y = data.size[1]
    for y in range(new_pixels_y):
        if y == new_pixels_y-1 and last_y_pixel_longer:
            y_range = range(data.size[1]-unused_pixels_y, data.size[1])
        else:
            y_range = range(data.size[1]-unused_pixels_y, data.size[1]-unused_pixels_y+original_pixels_per_new_pixel)

        unused_pixels_x = data.size[0]
        for x in range(new_pixels_x):
            print(y,x)
            if x == new_pixels_x - 1 and last_x_pixel_longer:
                x_range = range(data.size[0] - unused_pixels_x, data.size[0])
            else:
                x_range = range(data.size[0] - unused_pixels_x, data.size[0] - unused_pixels_x + original_pixels_per_new_pixel)

            mean_R = int(np.round(np.mean(data_array[0, x_range[0]:x_range[-1], y_range[0]:y_range[-1]])))
            mean_G = int(np.round(np.mean(data_array[1, x_range[0]:x_range[-1], y_range[0]:y_range[-1]])))
            mean_B = int(np.round(np.mean(data_array[2, x_range[0]:x_range[-1], y_range[0]:y_range[-1]])))

            new_data.append((mean_R, mean_G, mean_B))
            unused_pixels_x -= len(x_range)
        unused_pixels_y -= len(y_range)

    new_image.putdata(new_data)
    new_image.show()
    return new_image


# def pixelate_corner_colour(original_image):
#     a=2

# def RGB_combine_similar_colour_regions(original_image, colour_diff_metric_tol, search_method = 'LRUD'):
#
#     if colour_diff_metric_tol > np.sqrt((255-0)**2*3):
#         raise Exception('tol must be less than ~441.672955...')
#
#     # Convert image data to a 3D array of RGB values
#     data = original_image.getdata()
#     original_size = data.size
#     data_array = RGB_image_data_to_array(data)
#
#     # Maintain a map of regions filled in
#     filled_map = np.zeros([data_array.shape[1], data_array.shape[2]])
#
#     # Spiral inward?
#     # LRUD scan
#     first_unfinished_row = 0
#     for y in range(data_array.shape[2]):
#         for x in range(data_array.shape[1]):
#             if filled_map[x, y] == 1:
#                 break
#             else:
#                 # Find region
#                 for Y in range(first_unfinished_row, data_array.shape[2])
#                 filled_map[x, y] = 1
#         # Check if a new row has been finished
#         if filled_map[:, first_unfinished_row].all():
#             first_unfinished_row = y+1

# Reduce unique colours by bucketing them
# TODO: add comments
def RGB_colours_bucket(original_image, div_fac):

    # Convert image data to a 3D array of RGB values
    data = original_image.getdata()
    original_size = data.size
    data_array = RGB_image_data_to_array(data, original_size)

    # TODO: parallelise
    for j in range(data_array.shape[1]):
        print([j])
        for k in range(data_array.shape[2]):
            dominant_colour_index = np.argmax(data_array[:, j, k])
            if dominant_colour_index == 0:
                other_index1, other_index2 = 1, 2
            elif dominant_colour_index == 1:
                other_index1, other_index2 = 0, 2
            elif dominant_colour_index == 2:
                other_index1, other_index2 = 0, 1
            dominant_colour = data_array[dominant_colour_index, j, k]
            other_colour1, other_colour2 = data_array[other_index1, j, k], data_array[other_index2, j, k]
            for i in range(data_array.shape[0]):
                data_array[i, j, k] = int(np.round(np.round(data_array[i, j, k]/div_fac)*div_fac))
            # enhance the dominant colour, more if the RGB is too dark grey
            very_dark = data_array[0, j, k]<60 and data_array[1, j, k]<60 and data_array[2, j, k]<60
            if very_dark:
                data_array[dominant_colour_index, j, k] = int(dominant_colour + (255 - dominant_colour) / 6)
                data_array[other_index1, j, k] = int(other_colour1 + (255 - other_colour1) / 12)
                data_array[other_index2, j, k] = int(other_colour2 + (255 - other_colour2) / 12)
            else:
                data_array[dominant_colour_index, j, k] = int(dominant_colour+(255-dominant_colour)/12)
                data_array[other_index1, j, k] = int(other_colour1 + (255 - other_colour1) / 24)
                data_array[other_index2, j, k] = int(other_colour2 + (255 - other_colour2) / 24)
    recon = Image.new('RGB', original_size)
    reconstruct_old_image = []
    for y in range(data.size[1]):
        for x in range(data.size[0]):
            reconstruct_old_image.append((data_array[0, x, y], data_array[1, x, y], data_array[2, x, y]))
    recon.putdata(reconstruct_old_image)
    recon.show()

    return recon

# TODO: add comments
def add_text_line_to_image(original_image, text, text_center,
                            text_size=80,
                            text_box_pixel_width = 5,
                            RGBA=(255,255,255,255),
                            text_background_RGBA = (0,0,0,0),
                            text_box_RGBA = (0,0,0,0),
                            rot_degrees=0,
                            font_name = 'Arial',
                            show_result = False,
                            save_result = False):

    try:
        font = ImageFont.truetype(r'C:\Windows\Fonts\{}.ttf'.format(font_name), size=text_size)  # Choose the text font
    except:
        print('Could not get requested font from \'C:\Windows\Fonts\' - reverting to default font.')
        font = ImageFont.load_default()
    text_size = font.getsize(text)
    text_box_border_offset = 20
    text_box_pixels = (text_size[0]+text_box_border_offset*2, text_size[1]+text_box_border_offset*2)

    try:
        if type(original_image)==str: base = original_image.convert('RGBA')  # Get an original image with alpha
        else: base = original_image.convert('RGBA')
    except:
        raise Exception('Failed to open or convert the input original image.')

    txt = Image.new('RGBA', text_box_pixels)                    # New layer for text to be written on
    draw_context = ImageDraw.Draw(txt)                          # Get a drawing context

    if text_box_RGBA[3]>0:
        txt_corners = [(0, 0),(0,txt.size[1]),(txt.size[0],txt.size[1]),(txt.size[0],0),(0,0)]
        draw_context.line(txt_corners, fill=text_box_RGBA, width=text_box_pixel_width, joint='curve')        # Draw border around non-alpha text layer (text box)
        # draw_context.ellipse([(txt.size[0]/2-10, txt.size[1]/2-10), (txt.size[0]/2+10, txt.size[1]/2+10)], fill=(255,0,0,255))# Draw a central ellipse

    coords = (np.round(text_box_pixels[0]/2-text_size[0]/2), np.round(text_box_pixels[1]/2-text_size[1]/2))
    draw_context.text(coords, text, font=font, fill=(255,0,0,255))                 # Write the text
    txt = RGBA_image_colA_to_colB(txt, (0, 0, 0), text_background_RGBA)
    txt_rot = txt.rotate(rot_degrees, expand=1).convert('RGBA')
    txt_rot = RGBA_image_colA_to_colB(txt_rot, (0,0,0), (0,0,0,0))
    txt_rot = RGBA_image_colA_to_colB(txt_rot, (255, 0, 0), (RGBA[0], RGBA[1], RGBA[2], RGBA[3]))
    #rotated_size = (txt.size[0]*np.sin(rot_degrees*np.pi/180)+txt.size[1]*np.cos(rot_degrees*np.pi/180), txt.size[0]*np.cos(rot_degrees*np.pi/180)+txt.size[1]*np.sin(rot_degrees*np.pi/180))
    # print(rotated_size)
    text_upper_left = (int(np.round(text_center[0]-txt_rot.size[0]/2)), int(np.round(text_center[1]-txt_rot.size[1]/2)))
    base.paste(txt_rot, text_upper_left, txt_rot)

    # Output new file with timestamp to original directory and display it
    timestamp_string = nm.get_YYYYMMDDHHMMSS_string(datetime.now(), '-', '_')
    new_image_fp = str(Path(original_file_path).parent / (Path(original_file_path).stem+'_'+timestamp_string+Path(original_file_path).suffix))
    file_type = Path(original_file_path).suffix[1:].upper()
    if file_type == 'JPG': file_type = 'JPEG'
    base = base.convert('RGB')
    if save_result: base.save(new_image_fp, file_type)
    if show_result: base.show()
    return new_image_fp, base


# Select a colour A and change it to colour B throughout whole image
def RGBA_image_colA_to_colB(image, colA, colB):
    data = image.getdata()
    new_data = []
    for item in data:
        if abs(item[0]-colA[0])<250 and abs(item[1] - colA[1])<250 and abs(item[2] - colA[2])<250:
            new_data.append((colB[0], colB[1], colB[2], colB[3]))
        else:
            new_data.append(item)
    image.putdata(new_data)
    return image


# Calls ffmpeg to make a video from the frames (video goes to the frames directory by default)
# Assumes that, for example, 541 frames are named as 'frame_00000.format' to 'frame_00541.format'
def frames_to_video(frames_directory, video_name_with_format = 'video.avi', image_format = 'png', fps = 20):

    # Delete the video file if it already exists
    if (frames_directory / video_name_with_format).exists(): os.remove(str(frames_directory / video_name_with_format))
    fps = str(int(fps))     # Floors non-int fps and converts to string as required
    subprocess.run([FFMPEG_FILEPATH, '-framerate', fps,
                    '-i', str(frames_directory/'frame_%05d.{}'.format(image_format)),
                    str(frames_directory/video_name_with_format)])



if __name__ == '__main__':

    # Colour bucketing and pixelation example
    original_file_path = r'F:\Nick\Pictures\vivi\105040270_289965975381877_4524177727143924866_n.jpg'
    # original_file_path = r'F:\Nick\Pictures\birdsNbugs\5\46952284_10210251585804874_8255541787091795968_o.jpg'
    original_image = Image.open(original_file_path)
    # add_text_line_to_image(original_image, text='Hello there!', RGBA=(255,0,0,255), text_size = 120, text_center = (700, 1100), text_background_RGBA=(0,255,0,100), text_box_RGBA=(0,0,255,255), rot_degrees=-30)
    pre_pixelated = pixelate_mean_colour(original_image, 600)
    bucketed = RGB_colours_bucket(pre_pixelated, 200)
    pixelated = pixelate_mean_colour(bucketed, 100)
    pixelated.save('a.bmp')