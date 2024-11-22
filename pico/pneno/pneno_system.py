import logging
import os.path
import threading

import mido
import pickle
from collections import deque
from threading import Thread, Timer
import time
import sched

from pico.logger import logger
from pico.pneno.interpolator import DMYSpeedInterpolator, DMAVelocityInterpolator, IFPSpeedInterpolator, \
    SpeedInterpolator, VelocityInterpolator
from pico.pneno.pneno_seq import PnenoSegment, PnenoSeq, is_note_on, is_note_off, create_pneno_seq_from_midi_file
from pico.util.midi_util import choose_midi_input
from pico.pico import PiCo

scheduler = sched.scheduler(time.time, time.sleep)


class PnoSegBinder:
    """
    Creates a binding between touch inputs and pneno segments
    - add(key, sgmt): register a PnenoSegment with a given key
    - pop(key): pop the registered PnenoSegment
    """

    def __init__(self):
        self.binding = {}
        self.noteon_status = {}

    def add(self, key, sgmt: PnenoSegment or None):
        self.binding[key] = sgmt

    def add_noteon(self, pitch, midi: mido.Message):
        self.noteon_status[pitch] = midi

    def has_noteon(self, pitch):
        if pitch in self.noteon_status.keys():
            return True
        return False

    def pop_noteon(self, pitch):
        if pitch in self.noteon_status:
            self.noteon_status.pop(pitch)

    def pop_binding(self, key):
        return self.binding.pop(key)

    def pop_by_midi(self, signal: mido.Message):
        if is_note_off(signal):
            if signal.note not in self.binding.keys():
                logger.warn("No Pneno Segment found for key", signal.note)
                return None
            return self.binding.pop(signal.note)
        logger.warn("Cannot retrive PnenooSegment by note-on events")
        return None

    def add_midi_binding(self, signal: mido.Message, sgmt: PnenoSegment or None):
        if is_note_on(signal):
            self.add(signal.note, sgmt)
        else:
            logger.warn("Note-off events cannot serve as the key.")

    def nullify_midi_binding(self, signal: mido.Message):
        if is_note_on(signal):
            self.add(signal, None)
        else:
            logger.warn("Note-off events cannot serve as the key.")


class PnenoSystem(PiCo):
    """
    The "play-next-note" system: captures real-time input signals and bind them with ordered PnenoSegments
    """
    listening = False  # whether to start realtime midi monitoring/listening
    pno_seq: PnenoSeq
    seg_binder: PnoSegBinder

    def __init__(self, input_port_name, output_port_name, pno_seq=None, history_size=1500, clean_intv=5,
                 session_save_path=None,
                 speed_interpolator: SpeedInterpolator = None, velocity_interpolator: VelocityInterpolator = None):
        """

        :param input_port_name:
        :param output_port_name:
        :param pno_seq:   predetermined orderedsequence of PnenoSegments. No async support.
        :param history_size:
        :param clean_intv:
        :param session_save_path:  if provided (save folder), full performance will be saved as a pkl file
        :param speed_interpolator:
        :param velocity_interpolator
        """
        self.input_port = mido.open_input(input_port_name)
        self.output_port = mido.open_output(output_port_name)

        self.speed_interpolator = speed_interpolator if speed_interpolator else DMYSpeedInterpolator()
        self.velocity_interpolator = velocity_interpolator if velocity_interpolator else DMAVelocityInterpolator()

        if pno_seq is None:
            self.pno_seq = PnenoSeq()
        else:
            self.pno_seq = pno_seq
        self.seg_binder = PnoSegBinder()
        self.session_save_path = session_save_path
        self.history = deque(maxlen=history_size if not self.session_save_path else None)
        self.clean_intv = clean_intv

        self.listening = True
        self.running_event = None
        self.midi_scheduler = None
        self.capture_thread = None
        self.cleaner = None

        self._stopped = False
        self._prev_time = 0

    def load_score(self, score):
        assert type(score) == PnenoSeq
        self.pno_seq = score
        self.speed_interpolator.load_score(self.pno_seq.to_ioi_list())

    def start_realtime_capture(self):
        if self.listening:
            self.running_event = threading.Event()  # Event to control thread termination
            self.capture_thread = threading.Thread(target=self.listen)
            self.midi_scheduler = threading.Thread(target=self.run_midi_scheduler)
            self.cleaner = Timer(self.clean_intv, self.clean_history) if not self.session_save_path else None

            self.running_event.set()  # Set the event to start the thread
            self.capture_thread.start()
            self.midi_scheduler.start()
            self.cleaner.start() if not self.session_save_path else None
            logger.info("Pneno System started! Press any MIDI key to continue...")
        else:
            logger.warn("PnenoSystem is not listening to you.")

    def listen(self):
        while self.running_event.is_set():
            if not self.listening or self.input_port is None:
                break
            try:
                for msg in self.input_port.iter_pending():
                    if not self.running_event.is_set():
                        break
                    logger.debug('Received input:', msg)
                    sgmt = self.get_sgmt(msg)
                    self.play_sgmt(sgmt, msg)
                    self.history.append((time.time(), msg, sgmt))
                time.sleep(0.00001)  # Tiny sleep to prevent blocking

            except (EOFError, OSError) as e:
                # Handle port closing or other IO errors
                logger.debug(f"Port error during listen: {e}")
                # break
            # except Exception as e:
            #     logger.error(f"Unexpected error in listen loop: {e}")
            # break

    def stop(self):
        if self._stopped:
            return
        logger.info("Stopping Pneno...")
        self.listening = False
        self.running_event.clear()  # Signal the thread to stop

        # Close the input port first to interrupt any blocking receive
        if self.input_port is not None:
            self.input_port.close()
            logger.debug("MIDI input port closed.")
            self.input_port = None

        if self.midi_scheduler and self.midi_scheduler.is_alive():
            self.midi_scheduler.join(timeout=1.0)
            if self.midi_scheduler.is_alive():
                logger.warn("Midi scheduler thread didn't stop gracefully within timeout")
            else:
                logger.debug("Midi scheduler stopped.")
            self.midi_scheduler = None

        # Now wait for the capture thread to finish
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2.0)  # Add timeout to prevent hanging
            if self.capture_thread.is_alive():
                logger.warn("Capture thread didn't stop gracefully within timeout")
            else:
                logger.debug("Realtime capture stopped.")
            self.capture_thread = None

        # Stop the cleaner timer
        if self.cleaner and self.cleaner.is_alive():
            self.cleaner.cancel()
            logger.debug("Cleaner timer stopped.")
            self.cleaner = None

        #  Close the output port
        if self.output_port is not None:
            self.output_port.close()
            logger.debug("MIDI output port closed.")
            self.output_port = None

        # If a path is provided, write the performance data
        self.save_performance_data()
        self._prev_time = 0
        self._stopped = True

    def run_midi_scheduler(self):
        while self.listening:
            if scheduler.queue:
                scheduler.run(blocking=False)
            time.sleep(0.01)

    def express_midi_seq(self, midi_seq: list[mido.Message], speed_scale_factor=1.0, default_velocity=60):
        """
        :param midi_seq:
        :return: list of midi seq (in absolute time) with updated expressive params
            - midi seq in absolute time
        """
        expressive_seq = midi_seq.copy()
        for e in expressive_seq:
            e.time *= speed_scale_factor
            e.velocity = default_velocity
        return expressive_seq

    def schedule_midi_seq(self, midi_seq):
        if not self.midi_scheduler.is_alive():
            logger.warn("Midi scheduler not started!")
            return
        for e in midi_seq:
            e.channel = 0
            scheduler.enter(self.pno_seq.ticks_to_seconds(e.time), 1, self.output_port.send, (e,))

    def get_sgmt(self, m: mido.Message):
        sgmt = None
        if self.pno_seq.empty():
            logger.warn("Empty note sequence. You need to register a Pneno Sequence (PnenoSeq) to perform")
            return None
        elif self.pno_seq.is_end():
            # End of performance reached
            return None
        if is_note_on(m):
            sgmt = self.pno_seq.get_next_sgmt()
            self.seg_binder.add_midi_binding(m, sgmt)
        return sgmt

    def play_sgmt(self, sgmt: PnenoSegment, midi: mido.Message):
        if sgmt is None and is_note_off(midi):
            seg = self.seg_binder.pop_by_midi(midi)
            if seg is None:
                return  # note-on already terminated by another touch signal
            key_midi_off = mido.Message(type='note_off', note=seg.key.pitch, channel=0, velocity=midi.velocity,
                                        time=0)
            self.output_port.send(key_midi_off)
            self.seg_binder.pop_noteon(seg.key.pitch)
            if not self.seg_binder.noteon_status and self.pno_seq.is_end():
                # Reached end of performance
                logger.info("You have completed the performance. Bravo!")
                # self.listening = False
                # self.running_event.clear()
                logger.info("You may now exit by pressing [Enter]")
        if is_note_on(midi):
            # Apply input midi velocity to sgmt key
            if sgmt is None:
                logger.debug("Received empty sgmt with note-on")
                return
            elif self.seg_binder.has_noteon(sgmt.key.pitch):
                key_mid = self.seg_binder.noteon_status[sgmt.key.pitch]
                self.seg_binder.add_midi_binding(key_mid, None)
                end_midi = mido.Message(type='note_off', note=sgmt.key.pitch, channel=0, velocity=midi.velocity,
                                        time=0)
                self.output_port.send(end_midi)

            self.seg_binder.add_noteon(sgmt.key.pitch, midi)  # always update current noteon with the latest midi
            key_midi = mido.Message(type='note_on', note=sgmt.key.pitch, channel=0, velocity=midi.velocity, time=0)
            logger.debug("Sending:", midi)
            self.output_port.send(key_midi)

            curr_ioi = self.pno_seq.seconds_to_ticks(time.time() - self._prev_time) if self._prev_time != 0 else 1
            logger.debug('Current ioi:', curr_ioi, 'midi time:', midi.time, 'prev time:', self._prev_time)
            midi_seq = self.express_midi_seq(
                sgmt.to_midi_seq(use_absolute_time=True, include_key=False, start_from_zero=True),
                speed_scale_factor=self.speed_interpolator.interpolate(curr_ioi),
                default_velocity=self.velocity_interpolator.interpolate(midi.velocity))
            self.schedule_midi_seq(midi_seq)
            self._prev_time = time.time()

    def add_note_seq(self, pitch_arr: list[int]):
        logger.info('Appended note list: ', pitch_arr)
        self.noteseq.append_list(pitch_arr)

    def clean_history(self):
        current_time = time.time()
        count = 0
        while self.history and current_time - self.history[0][0] > 5:
            self.history.popleft()
            count += 1
        logger.debug("+Cleaned", count, 'history')
        self.cleaner = Timer(self.clean_intv, self.clean_history)  # Restart timer
        self.cleaner.start()

    def save_performance_data(self):
        if self.session_save_path:
            save_path = f'{self.session_save_path}/perf_data.pkl'
            fname_add = 0
            data = {
                "ticks_per_beat": self.pno_seq.ticks_per_beat,
                "tempo": self.pno_seq.tempo,
                "pred_velocity": repr(self.velocity_interpolator),
                "pred_speed": repr(self.speed_interpolator),
                "performance": self.history,
            }
            if os.path.exists(f'{self.session_save_path}/perf_data.pkl'):
                logger.warn("Existing performance data exist")
                while os.path.exists(f'{self.session_save_path}/perf_data_{fname_add}.pkl'):
                    fname_add += 1
                save_path = f'{self.session_save_path}/perf_data_{fname_add}.pkl'
            with open(save_path, 'wb') as f:
                pickle.dump(data, f)
                print('Performance history saved to:', save_path)


def start_interactive_session(midi_path):
    pneno_seq = create_pneno_seq_from_midi_file(midi_path)
    inp, oup = choose_midi_input()
    pno = PnenoSystem(inp, oup, pno_seq=pneno_seq)
    pno.start_realtime_capture()
    time.sleep(0.5)
    logger.info("Press [Enter] to stop")
    input('')
    pno.stop()


def main():
    midi_path = '/Users/kurono/Desktop/pneno_demo.mid'
    # start_interactive_session(midi_path)

    # perf = '/Users/kurono/Desktop/perf_data.pkl'
    # pno_seq = create_pneno_seq_from_midi(midi_path)
    # print(parse_ifp_performance_ioi(perf, pno_seq.seconds_to_ticks))


if __name__ == '__main__':
    logger.set_level(logging.DEBUG)
    main()

# TODO @Bmois:
#  [done] 1. solve same-note on off debug
#  2. real-time tempo estimation
#  3. record performance data save as rehearsal data for tempo estimation
