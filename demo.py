import argparse
import logging
import os
import time

from jedi.debug import speed

import pico.mono_pico.music.music_seq
from pico.logger import logger
from pico.mono_pico.util.synthesizer import Fluidx
from pico.pico import PiCo
from pico.mono_pico.mono_pico import MonoPiCo
from pico.pneno.interpolator import IFPSpeedInterpolator, parse_ifp_performance_ioi, DMYSpeedInterpolator
from pico.pneno.pneno_seq import PnenoSeq, create_pneno_seq_from_midi
from pico.pneno.pneno_system import PnenoSystem
from pico.util.midi_util import choose_midi_input, array_choice

modes = ['Play a sequence of notes', 'Play a complete score']


def choose_pico_mode():
    print("\nPlease choose a mode:")
    for i, e in enumerate(modes):
        print(f"{i}: {e}")
    return array_choice('', len(modes))


def create_pico_system(in_port, out_port, mode, **kwargs) -> PiCo or None:
    """
    Factory function for creating Piano Conductor systems
    :param in_port:   MIDI input port name
    :param out_port:  MIDI output port name
    :param mode:
    :return:
    """
    if mode == 0:
        return MonoPiCo(input_port_name=in_port, output_port_name=out_port, **kwargs)
    elif mode == 1:
        # speed_interpolator = DMYSpeedInterpolator()
        speed_interpolator = IFPSpeedInterpolator()
        if kwargs.get('ref_perf') is not None:
            score_ioi, tplt_ioi = parse_ifp_performance_ioi(kwargs.get('ref_perf'))
            speed_interpolator.load_template(score_ioi, tplt_ioi)
        return PnenoSystem(input_port_name=in_port, output_port_name=out_port,
                           speed_interpolator=speed_interpolator, session_save_path=kwargs.get('session_save_path'))
    else:
        logger.warn("Unknown mode:", mode)
    return None


def create_score(mode, score_path=None):
    if mode == 0:
        return pico.mono_pico.music.music_seq.schubert_142_3
    elif mode == 1:
        os.path.exists(score_path)
        return create_pneno_seq_from_midi(score_path)


def start_interactive_session(sf_path, score_path=None, **kwargs):
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
    pico_system = create_pico_system(in_port=in_port, out_port=out_port, mode=mode, **kwargs)
    score = create_score(mode, score_path)
    pico_system.load_score(score)
    pico_system.start_realtime_capture()

    input("\nPress [Enter] to stop\n")
    pico_system.stop()
    synthesizer.stop()


def main():
    parser = argparse.ArgumentParser(
        description='Piano Conductor - Proof of Concept Demo, '
                    'Idea similar to Radio Baton by Max Matthews'
    )
    # Adding arguments
    parser.add_argument('--sf_path', type=str, required=True, help="Path to the sound font")
    parser.add_argument('--midi_path', type=str, required=False, help="Path to a MIDI file")
    parser.add_argument('--sess_save_path', type=str, required=False,
                        help='If provided, performance will be saved at the given path')
    parser.add_argument('--ref_perf', type=str, required=False,
                        help="Path to a performance.pkl file as a reference for tempo prediction")
    args = parser.parse_args()

    start_interactive_session(sf_path=args.sf_path, score_path=args.midi_path,
                              session_save_path=args.sess_save_path,
                              ref_perf=args.ref_perf)


def debug_main():
    logger.set_level(logging.DEBUG)
    # sf_path = '/Users/kurono/Documents/github/PiCo/pico/data/kss.sf2'
    sf_path = '/Users/kurono/Documents/github/PiCo/pico/data/piano.sf2'
    score_path = '/Users/kurono/Desktop/pneno_demo.mid'
    sess_save_path = None
    # sess_save_path = '/Users/kurono/Desktop'
    # ref_perf = None
    ref_perf = '/Users/kurono/Desktop/perf_data.pkl'
    start_interactive_session(sf_path=sf_path, score_path=score_path, session_save_path=sess_save_path,
                              ref_perf=ref_perf)


if __name__ == '__main__':
    logger.set_level(logging.INFO)
    debug_main()
    # main()

# TODO @Bmois:
#  1. accept MIDI input and convert to pneno MIDI (separate anchor MIDI events from segments)
#  2. Rhythm game: play piano conductor with exact same speed (DmyVelocityInterpolator),
#           then calculate IOI ratio deviation to score the performance! It will be a fun game!
#           (okay. so 17lianqin's automatic accompaniment may also achieve this, but only if no fluctuations...)
