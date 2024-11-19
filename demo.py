import argparse
import logging
import os
import time

import pico.mono_pico.music.music_seq
from pico.logger import logger
from pico.mono_pico.util.synthesizer import Fluidx
from pico.pico import PiCo
from pico.mono_pico.mono_pico import MonoPiCo
from pico.pneno.pneno_seq import PnenoSeq, create_pneno_seq_from_midi
from pico.pneno.pneno_system import PnenoSystem
from pico.util.midi_util import choose_midi_input, array_choice

modes = ['Play a sequence of notes', 'Play a complete score']


def choose_pico_mode():
    print("\nPlease choose a mode:")
    for i, e in enumerate(modes):
        print(f"{i}: {e}")
    return array_choice('', len(modes))


def create_pico_system(in_port, out_port, mode) -> PiCo or None:
    """
    Factory function for creating Piano Conductor systems
    :param in_port:   MIDI input port name
    :param out_port:  MIDI output port name
    :param mode:
    :return:
    """
    if mode == 0:
        return MonoPiCo(input_port_name=in_port, output_port_name=out_port)
    elif mode == 1:
        return PnenoSystem(input_port_name=in_port, output_port_name=out_port)
    else:
        logger.warn("Unknown mode:", mode)
    return None


def create_score(mode, score_path=None):
    if mode == 0:
        return pico.mono_pico.music.music_seq.schubert_142_3
    elif mode == 1:
        os.path.exists(score_path)
        return create_pneno_seq_from_midi(score_path)


def start_interactive_session(sf_path, score_path=None):
    """

    :param sf_path:
    :param score_path:
    :return:
    """
    assert os.path.exists(sf_path)
    synthesizer = Fluidx(sf_path)
    time.sleep(0.5)

    in_port, out_port = choose_midi_input()
    mode = choose_pico_mode()
    pico = create_pico_system(in_port=in_port, out_port=out_port, mode=mode)
    score = create_score(mode, score_path)
    pico.load_score(score)
    pico.start_realtime_capture()

    input("\nPress [Enter] to stop\n")
    pico.stop()
    synthesizer.stop()


def main():
    parser = argparse.ArgumentParser(
        description='Piano Conductor - Proof of Concept Demo, '
                    'Idea similar to Radio Baton by Max Matthews'
    )
    # Adding arguments
    parser.add_argument('--sf_path', type=str, required=True, help="Path to the sound font")
    parser.add_argument('--midi_path', type=str, required=False, help="Path to a MIDI file")
    args = parser.parse_args()

    start_interactive_session(sf_path=args.sf_path, score_path=args.midi_path)


def debug_main():
    sf_path = '/Users/kurono/Documents/github/PiCo/pico/data/kss.sf2'
    score_path = '/Users/kurono/Desktop/pneno_demo.mid'
    start_interactive_session(sf_path=sf_path, score_path=score_path)


if __name__ == '__main__':
    logger.set_level(logging.INFO)
    debug_main()
    # main()

# TODO @Bmois: accept MIDI input and convert to pneno MIDI (separate anchor MIDI events from segments)
