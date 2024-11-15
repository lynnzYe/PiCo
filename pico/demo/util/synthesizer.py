import fluidsynth
import threading
import time
from pico.demo.util.bmois_logger import logger


class Fluidx:
    fs = None  # fluidsynth instance

    def __init__(self, sf_path=None, sr=44100.0, gain=1.0):
        self.fs = fluidsynth.Synth(samplerate=sr, gain=gain)
        self.fs.start()

        if sf_path is not None:
            logger.debug("Loading soundfont:", sf_path)
        self.load_sf(sf_path)

    def __del__(self):
        self.stop()

    def stop(self):
        if self.fs:
            self.fs.delete()
            self.fs = None
            logger.debug("Fluidx synthesizer stopped and resources released.")

    def load_sf(self, sf_path):
        sfid = self.fs.sfload(sf_path)
        self.fs.program_select(0, sfid, 0, 0)

    def noteon(self, chan, key, vel):
        return self.fs.noteon(chan, key, vel)

    def noteoff(self, chan, key, vel):
        return self.fs.noteoff(chan, key, vel)

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
    fs.noteon(0, 60, 100)
    fs.noteon(0, 64, 100)
    fs.noteon(0, 67, 100)
    input("End?")


if __name__ == '__main__':
    main()
