import pyaudio, playsound
import wave
from datetime import datetime, timedelta

from gtts import gTTS
import os
import pyttsx3

def play_wav(wav_file):
    CHUNK = 256
    wf = wave.open(wav_file, 'rb')
    p = pyaudio.PyAudio()
    stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True)
    data = wf.readframes(CHUNK)
    while str(data) != 'b\'\'':
        stream.write(data)
        data = wf.readframes(CHUNK)
    stream.stop_stream()
    stream.close()
    p.terminate()


# p = pyaudio.PyAudio()
# info = p.get_host_api_info_by_index(0)
# numdevices = info.get('deviceCount')
# for i in range(0, numdevices):
#     if (p.get_device_info_by_host_api_device_index(0, i).get('maxOutputChannels')) > 0:
#         print("Input Device id ", i, " - ", p.get_device_info_by_host_api_device_index(0, i).get('name'))

class TextToSpeech:

    def __init__(self, logger, recheck_google_minutes=5):
        # Initially assume availability of Google TTS (requires internet)
        self.google_TTS_available = True
        # If google is inaccessible, record the time so it can be checked again after recheck_google_duration
        self.recheck_google_minutes = recheck_google_minutes
        self.last_checked_google_time = None
        self.pyttsx3engine = None
        #self.say('Initialised text-to-speech.')
        self._logger=logger

    def say(self, text):
        if self.last_checked_google_time and not self.google_TTS_available:
            if datetime.now() - self.last_checked_google_time > timedelta(minutes=self.recheck_google_minutes):
                self.google_TTS_available = True

        if self.google_TTS_available:
            try:
                self.last_checked_google_time = datetime.now()
                self._google_TTS(text)
                self._logger.debug('Used Google TTS to say "{}"'.format(text))
            except:
                self.google_TTS_available = False

        if not self.google_TTS_available:
            try:
                self._pyttsx3(text)
                self._logger.debug('Used pyttsx3 TTS to say "{}"'.format(text))
            except:
                self._logger.debug('Google TTS and pyttsx3 both failed to say text "{}"'.format(text))


    def _google_TTS(self, text):
        tts = gTTS(text=text, lang='en', slow=False)
        tts.save('temp.mp3')
        playsound.playsound('temp.mp3', True)
        os.remove('temp.mp3')

    def _pyttsx3(self, text):
        if not self.pyttsx3engine:
            self.pyttsx3engine = pyttsx3.init()
            self.pyttsx3engine.setProperty('rate', 200)
            self.pyttsx3engine.setProperty('volume', 1)
            voices = self.pyttsx3engine.getProperty('voices')
            if len(voices)<1: raise Exception('No system voices available for pyttsx3 to use.')
            elif len(voices)>1: self.pyttsx3engine.setProperty('voice', voices[1].id)
            else: self.pyttsx3engine.setProperty('voice', voices[0].id)
        self.pyttsx3engine.say(text)
        self.pyttsx3engine.runAndWait()





if __name__ == '__main__':
    play_wav(r'E:\dev\python_projects\automate\data\beep3.wav')
    tts = TextToSpeech(0.5)
    tts.say('Hello there! I am a computer.')
    # from playsound import playsound
    #
    # playsound(r'E:\dev\python_projects\automate\data\beep3.mp3')