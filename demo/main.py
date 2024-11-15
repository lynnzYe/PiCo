import argparse
from turtledemo.penrose import start

import mido
import time
import threading

from demo.util.mimo import MiMo, NoteEvent
from demo.util.bmois_logger import logger
from demo.util.synthesizer import Fluidx
import demo.music.music_seq as mur


def array_choice(hint, arr_len):
    while True:
        try:
            in_choice = int(input(hint))
            if 0 <= in_choice <= arr_len:
                return in_choice
        except ValueError:
            print("Invalid input. Please input a valid number between 0 and ", arr_len)


def choose_midi_input():
    logger.info("Available MIDI input devices:")
    input_list = mido.get_input_names()
    output_list = mido.get_output_names()
    if len(input_list) == 0 or len(output_list) == 0:
        raise RuntimeError("No MIDI input/output device found.")
        return [], []
    for i, e in enumerate(input_list):
        print(i, ': ', e)
    input_choice = array_choice('Choose an input device.', len(input_list))
    for i, e in enumerate(output_list):
        print(i, ': ', e)
    output_choice = array_choice('Choose an input device.', len(output_list))
    return [input_list[input_choice], output_list[output_choice]]


def create_synthesizer(sf_path):
    global synthesizer_instance
    synthesizer_instance = Fluidx(sf_path)
    while True:
        time.sleep(1)


def run_mimo():
    in_device, out_device = choose_midi_input()
    mimo = MiMo(in_device, out_device)
    mimo.add_note_seq(mur.schubert_142_3)
    mimo.start_realtime_capture()


def create_interactive_sessino(sf_path):
    thread = threading.Thread(target=lambda: create_synthesizer(sf_path))
    thread.start()
    time.sleep(1)

    run_mimo()

    input('end?')
    thread.join()


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
    logger.warn("Currently, demo are available only with predetermined array of pitches"
                " (which can be modified and created in the music.py file.\nOnly --sf_path will be used.")
    parser.add_argument('--sf_path', type=str, required=False, help="Path to the sound font")
    parser.add_argument('--midi_path', type=str, required=False, help="Path to the MIDI file")
    args = parser.parse_args()

    create_interactive_sessino(sf_path=args.sf_path)


if __name__ == '__main__':
    # test_main()
    main()
