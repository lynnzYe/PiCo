import argparse
import logging
import os
import time

import pico.mono_pico.music.music_seq
from pico.logger import logger
from pico.mono_pico.util.synthesizer import Fluidx
from pico.pico import PiCo
from pico.mono_pico.mono_pico import MonoPiCo
from pico.pneno.interpolator import IFPSpeedInterpolator, parse_ifp_performance_ioi, DMAVelocityInterpolator
from pico.pneno.pneno_seq import create_pneno_seq_from_midi_file
from pico.pneno.pneno_system import PnenoSystem
from pico.util.midi_util import choose_midi_input, array_choice

modes = ['Play a sequence of notes', 'Play a complete score']


def choose_pico_mode():
    print("\nPlease choose a mode:")
    for i, e in enumerate(modes):
        print(f"{i + 1}: {e}")
    return array_choice(1, len(modes) + 1, '')


def create_pico_system(in_port, out_port, mode, **kwargs) -> PiCo or None:
    """
    Factory function for creating Piano Conductor systems
    :param in_port:   MIDI input port name
    :param out_port:  MIDI output port name
    :param mode:
    :return:
    """
    if mode == 1:
        return MonoPiCo(input_port_name=in_port, output_port_name=out_port)
    elif mode == 2:
        # speed_interpolator = DMYSpeedInterpolator()
        speed_interpolator = IFPSpeedInterpolator()
        if kwargs.get('ref_sess') is not None:
            score_ioi, tplt_ioi = parse_ifp_performance_ioi(kwargs.get('ref_sess'))
            speed_interpolator.load_template(score_ioi, tplt_ioi)
        if kwargs.get('interpolate_velocity'):
            vel_interpolator = DMAVelocityInterpolator()
        else:
            vel_interpolator = None
        return PnenoSystem(input_port_name=in_port, output_port_name=out_port, velocity_interpolator=vel_interpolator,
                           speed_interpolator=speed_interpolator, session_save_path=kwargs.get('session_save_path'))
    else:
        raise Exception(f"Unknown mode: {mode}")


def create_score(mode, score_path=None):
    if mode == 1:
        scores = pico.mono_pico.music.music_seq.scores
        piece_names = scores.keys()
        choice = array_choice(0, len(piece_names))
        return scores[piece_names[choice]]
    elif mode == 2:
        os.path.exists(score_path)
        return create_pneno_seq_from_midi_file(score_path)


def start_interactive_session(sf_path, score_path=None, **kwargs):
    assert os.path.exists(sf_path)
    synthesizer = Fluidx(sf_path, listen_chnl=[0, 1])
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
        description='Piano Conductor - Proof of Concept Demo'
    )
    # Adding arguments
    parser.add_argument('--sf_path', type=str, required=True, help="Path to the sound font")
    parser.add_argument('--midi_path', type=str, required=False, help="Path to a MIDI file")
    parser.add_argument('--sess_save_path', type=str, required=False,
                        help='If provided, performance will be saved at the given path')
    parser.add_argument('--ref_sess', type=str, required=False,
                        help="Path to a performance.pkl file as a reference for tempo prediction")
    parser.add_argument('--interpolate_velocity', action='store_true', required=False,
                        help="Path to a performance.pkl file as a reference for tempo prediction")
    args = parser.parse_args()

    logger.set_level(logging.INFO)
    start_interactive_session(sf_path=args.sf_path,
                              score_path=args.midi_path,
                              session_save_path=args.sess_save_path,
                              ref_sess=args.ref_sess,
                              interpolate_velocity=args.interpolate_velocity)


def debug_main():
    logger.set_level(logging.DEBUG)
    # sf_path = '/Users/kurono/Documents/github/PiCo/pico/data/kss.sf2'
    sf_path = '/Users/kurono/Documents/github/PiCo/pico/data/piano.sf2'
    # score_path = '/Users/kurono/Desktop/pneno_hrwz.mid'
    score_path = '/Users/kurono/Desktop/sutekidane.mid'
    sess_save_path = None
    # sess_save_path = '/Users/kurono/Desktop'
    ref_sess = None
    # ref_sess = '/Users/kurono/Desktop/perf_data.pkl'
    start_interactive_session(sf_path=sf_path,
                              score_path=score_path,
                              session_save_path=sess_save_path,
                              ref_sess=ref_sess,
                              interpolate_velocity=True)


if __name__ == '__main__':
    # debug_main()
    main()

# TODO @Bmois:
#  1. Rhythm game: play piano conductor with exact same speed (DmyVelocityInterpolator),
#           then calculate IOI ratio deviation to score the performance! It will be a fun game!
#       - additional feature: history data, and see where you often miss!
#  2. Ritardando practice! select a q in [2,3], then craft the IOI to reflect that tempo change!
