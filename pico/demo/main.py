import argparse
import os.path

import mido
import time

from pico.demo.util.mimo import MiMo, NoteEvent
from pico.logger import logger
from pico.demo.util.synthesizer import Fluidx
import pico.demo.music.music_seq as mur
from pico.util.midi_util import choose_midi_input


def create_synthesizer(sf_path):
    return Fluidx(sf_path)


def build_mimo():
    in_device, out_device = choose_midi_input()
    mimo = MiMo(in_device, out_device)
    mimo.add_note_seq(mur.schubert_142_3)
    return mimo


def create_interactive_sessino(sf_path):
    assert os.path.exists(sf_path)
    synthesizer = create_synthesizer(sf_path)
    time.sleep(1)

    mimo = build_mimo()
    logger.info("The interactive demo is about to start.")
    # input("\n\n[Press enter to start]")
    mimo.start_realtime_capture()

    try:
        input('[Press enter again to stop]\n')
    finally:
        logger.info("Stopping interactive demo...")
        mimo.stop()
        synthesizer.stop()


def test_main():
    sf_path = 'data/piano.sf2'
    create_interactive_sessino(sf_path)


def main():
    parser = argparse.ArgumentParser(
        description='Piano Conductor - Proof of Concept. '
                    'This can be thought of as a reimplementation of Max Matthews\'s radio baton in python,'
                    'replacing the drum sensor with MIDI keyboard input.'
    )
    # Adding arguments
    logger.warn("Currently, demos only support predetermined array of pitches"
                " (which can be edited in music.py). Only --sf_path will be used.")
    parser.add_argument('--sf_path', type=str, required=True, help="Path to the sound font")
    parser.add_argument('--midi_path', type=str, required=False, help="Path to the MIDI file")
    args = parser.parse_args()

    create_interactive_sessino(sf_path=args.sf_path)


if __name__ == '__main__':
    # test_main()
    main()
