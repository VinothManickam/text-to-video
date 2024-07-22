from flask import Flask, request, jsonify, send_file
from PIL import ImageFont, ImageDraw, Image
from gtts import gTTS
from moviepy.editor import ImageSequenceClip, AudioFileClip
from pydub import AudioSegment
import colorsys
import numpy as np
import os
import uuid
import logging
import traceback

# Configure logging to write to a file
logging.basicConfig(filename='app.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')

# Variables for customization
TEXT_SPEED = 24  # frames per second
TEXT_COLOR = (255, 255, 255)
FONT_PATH = "arial.ttf"  # Path to .ttf font file (change this to your font file)
FONT_SIZE = 180
BACKGROUND_SPEED = 0.8  # Background color change speed (lower value means slower)
TIMING_ADJUSTMENT = -0.3  # Adjusts the duration of each word in the video
START_BG_COLOR = "#000000"  # Start color in HEX
END_BG_COLOR = "#6638f0"  # End color in HEX
VIDEO_SIZE = (1920, 1080)  # width, height

def get_ffmpeg_path():
    return r"C:\Users\hp\ffmpeg\ffmpeg-master-latest-win64-gpl-shared\bin\ffmpeg.exe"

# Function to convert HEX color to RGB
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

# interpolate color
def interpolate_color(start_color, end_color, progress):
    start_color = hex_to_rgb(start_color)
    end_color = hex_to_rgb(end_color)

    start_h, start_s, start_v = colorsys.rgb_to_hsv(
        start_color[0] / 255, start_color[1] / 255, start_color[2] / 255
    )
    end_h, end_s, end_v = colorsys.rgb_to_hsv(
        end_color[0] / 255, end_color[1] / 255, end_color[2] / 255
    )

    interpolated_h = start_h + (end_h - start_h) * progress
    interpolated_s = start_s + (end_s - start_s) * progress
    interpolated_v = start_v + (end_v - start_v) * progress

    r, g, b = colorsys.hsv_to_rgb(interpolated_h, interpolated_s, interpolated_v)

    return int(r * 255), int(g * 255), int(b * 255)

def text_to_video(textfile, outputfile):
    with open(textfile, "r") as f:
        lines = f.read()

    words = lines.split()
    images = []
    durations = []

    fnt = ImageFont.truetype(FONT_PATH, FONT_SIZE)

    # Generate speech for the whole text and save as a temporary file
    tts = gTTS(text=lines, lang="en")
    tts.save("temp.mp3")

    # Measure the speech duration using pydub
    full_audio = AudioSegment.from_file("temp.mp3", ffmpeg=get_ffmpeg_path())
    full_audio_duration = len(full_audio) / 1000  # duration in seconds
    avg_word_duration = full_audio_duration / len(words)  # average duration per word

    durations.append(avg_word_duration + TIMING_ADJUSTMENT)  # Adjust frame duration based on average word duration and timing adjustment

    for i, word in enumerate(words):
        # Calculate text size and position only once per word
        text_bbox = fnt.getbbox(word)  # Get bounding box of the text
        text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]  # Calculate width and height from bounding box
        position = ((VIDEO_SIZE[0] - text_width) / 2, (VIDEO_SIZE[1] - text_height) / 2)

        # Calculate background color based on word index and total number of words
        background_progress = i / len(words)
        background_color = interpolate_color(START_BG_COLOR, END_BG_COLOR, background_progress)

        img = Image.new("RGB", VIDEO_SIZE, color=background_color)  # Set background color
        d = ImageDraw.Draw(img)
        d.text(position, word, font=fnt, fill=TEXT_COLOR)

        images.append(np.array(img))
        durations.append(avg_word_duration)  # Set frame duration based on average word duration

    audioclip = AudioFileClip("temp.mp3")
    clip = ImageSequenceClip(images, durations=durations)
    clip = clip.set_audio(audioclip)

    clip.fps = TEXT_SPEED
    clip.write_videofile(outputfile, codec="libx264")

    # Remove the temporary file
    os.remove("temp.mp3")

app = Flask(__name__)

@app.route('/generate-video', methods=['GET'])
def generate_video():
    text = request.args.get('text')
    if not text:
        app.logger.error('Text parameter is missing')
        return jsonify({"error": "Text parameter is required"}), 400

    try:
        # Save the text to a temporary file
        text_filename = f"{uuid.uuid4()}.txt"
        with open(text_filename, "w") as f:
            f.write(text)

        # Generate a unique output file name
        output_filename = 'output.mp4'

        # Call the text_to_video function
        text_to_video(text_filename, output_filename)

        # Remove the temporary text file
        os.remove(text_filename)

        # Send the generated video file
        return send_file(output_filename, mimetype='video/mp4', as_attachment=True, download_name=output_filename)

    except Exception as e:
        app.logger.error(f'Failed to generate video: {str(e)}')
        app.logger.error(traceback.format_exc())
        return jsonify({"error": "Failed to generate video"}), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
