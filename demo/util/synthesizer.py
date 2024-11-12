import fluidsynth


class Fluidx:
    fs = None  # fluidsynth instance

    def __init__(self, sf_path=None, sr=44100.0, gain=1.0):
        self.fs = fluidsynth.Synth(samplerate=sr, gain=gain)
        self.fs.start()

        if sf_path is not None:
            print("Loading soundfont:", sf_path)
            self.load_sf(sf_path)

    def __del__(self):
        self.fs.delete()

    def load_sf(self, sf_path):
        sfid = self.fs.sfload(sf_path)
        self.fs.program_select(0, sfid, 0, 0)

    def noteon(self, chan, key, vel):
        return self.fs.noteon(chan, key, vel)


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
