import argparse
import os.path

import mido
import time

from pico.demo.util.mimo import MiMo, NoteEvent
from pico.demo.util.bmois_logger import logger
from pico.demo.util.synthesizer import Fluidx
import pico.demo.music.music_seq as mur


def array_choice(hint, arr_len):
    while True:
        try:
            in_choice = int(input(hint))
            if 0 <= in_choice < arr_len:
                return in_choice
            else:
                print("Invalid input. Please input a valid number between 0 and ", arr_len - 1)
        except Exception:
            print("Invalid input. Please input a valid number between 0 and ", arr_len - 1)


def choose_midi_input():
    # logger.info("Available MIDI input devices:")
    input_list = mido.get_input_names()
    output_list = mido.get_output_names()
    if len(input_list) == 0 or len(output_list) == 0:
        raise RuntimeError("No MIDI input/output device found.")
    print("=============================")
    print("Please choose an input device")
    for i, e in enumerate(input_list):
        print(i, ': ', e)
    input_choice = array_choice('', len(input_list))
    print("=============================")
    print("Please choose an output device (you should be able to see FluidSynth virtual port. Choose this one plz.)")
    for i, e in enumerate(output_list):
        print(i, ': ', e)
    output_choice = array_choice('', len(output_list))
    return [input_list[input_choice], output_list[output_choice]]


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
    input("\n\n[Press enter to start]")
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
