import fluidsynth
import threading
import time
from pico.logger import logger


class Fluidx:
    fs = None  # fluidsynth instance

    def __init__(self, sf_path=None, sr=44100.0, gain=1.0, listen_chnl=None):
        if listen_chnl is None:
            listen_chnl = [0]
        self.fs = fluidsynth.Synth(samplerate=sr, gain=gain)
        self.fs.start()

        if sf_path is not None:
            logger.debug("Loading soundfont:", sf_path)
        self.load_sf(sf_path, channels=listen_chnl)

    def __del__(self):
        self.stop()

    def stop(self):
        if self.fs:
            self.fs.delete()
            self.fs = None
            logger.debug("Fluidx synthesizer stopped and resources released.")

    def load_sf(self, sf_path, channels=None):
        if channels == None:
            channels = [0]
        sfid = self.fs.sfload(sf_path)
        for c in channels:
            self.fs.program_select(c, sfid, 0, 0)

    def noteon(self, chan, key, vel):
        return self.fs.noteon(chan, key, vel)

    def noteoff(self, chan, key):
        return self.fs.noteoff(chan, key)

    def release_all(self, chan=0):
        self.fs.all_notes_off(chan)


def main():
    """
    Toy example using Fluidx (pyFluidSynth)
    :return:
    """
    soundfont_path = '../data/piano.sf2'
    fs = Fluidx(soundfont_path)
    # input("Start?")
    fs.noteon(0, 60, 60)
    fs.noteon(0, 64, 60)
    fs.noteon(0, 67, 60)
    time.sleep(1)
    fs.noteoff(0, 60)
    fs.noteoff(0, 64)
    fs.noteoff(0, 67)

    while True:
        input("Release all current noteon?")
        fs.release_all(0)


if __name__ == '__main__':
    main()
