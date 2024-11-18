import logging
import threading

import mido
from collections import deque
from threading import Thread, Timer
import time
import sched

from joblib.testing import timeout

from pico.logger import logger
from pico.pneno.pneno_seq import PnenoSegment, PnenoSeq, is_note_on, is_note_off, create_pneno_seq_from_midi
from pico.util.midi_util import choose_midi_input

scheduler = sched.scheduler(time.time, time.sleep)


class PnoSegBinder:
    """
    Creates a binding between touch inputs and pneno segments
    - add(key, sgmt): register a PnenoSegment with a given key
    - pop(key): pop the registered PnenoSegment
    """

    def __init__(self):
        self.binding = {}

    def add(self, key, sgmt: PnenoSegment):
        self.binding[key] = sgmt

    def pop(self, key):
        return self.binding.pop(key)

    def get_by_midi(self, signal: mido.Message):
        if is_note_off(signal):
            return self.binding.pop(signal.note)
        logger.warn("Cannot retrive PnenooSegment by note-on events")
        return None

    def add_midi_binding(self, signal: mido.Message, sgmt: PnenoSegment):
        if signal.type == 'note_on' and signal.velocity > 0:
            self.add(signal.note, sgmt)
        else:
            logger.warn("Note-off events cannot serve as the key.")


class PnenoSystem:
    """
    The "play-next-note" system: captures real-time input signals and bind them with ordered PnenoSegments
    """
    listening = False  # whether to start realtime midi monitoring/listening
    pno_seq: PnenoSeq
    seg_binder: PnoSegBinder

    def __init__(self, input_port_name, output_port_name, pno_seq=None, history_size=1500, clean_intv=5):
        """

        :param input_port_name:
        :param output_port_name:
        :param pno_seq:   predetermined orderedsequence of PnenoSegments. No async support.
        :param history_size:
        :param clean_intv:
        """
        self.input_port = mido.open_input(input_port_name)
        self.output_port = mido.open_output(output_port_name)

        if pno_seq is None:
            self.pno_seq = PnenoSeq()
        else:
            self.pno_seq = pno_seq
        self.seg_binder = PnoSegBinder()
        self.history = deque(maxlen=history_size)  # Adjust the size based on ticks and events per tick
        self.clean_intv = clean_intv

        self.listening = True
        self.running_event = None
        self.midi_scheduler = None
        self.capture_thread = None
        self.cleaner = None

    def __del__(self):
        self.stop()

    def start_realtime_capture(self):
        if self.listening:
            self.running_event = threading.Event()  # Event to control thread termination
            self.capture_thread = threading.Thread(target=self.listen)
            self.midi_scheduler = threading.Thread(target=self.run_midi_scheduler)
            self.cleaner = Timer(self.clean_intv, self.clean_history)

            self.running_event.set()  # Set the event to start the thread
            self.capture_thread.start()
            self.midi_scheduler.start()
            self.cleaner.start()
        else:
            logger.warn("MiMo is not listening to you.")

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

        # Finally close the output port
        if self.output_port is not None:
            self.output_port.close()
            logger.debug("MIDI output port closed.")
            self.output_port = None

    def run_midi_scheduler(self):
        while self.listening:
            if scheduler.queue:
                scheduler.run(blocking=False)
            time.sleep(0.01)

    def schedule_midi_seq(self, midi_seq, scale_factor=1.0):
        if not self.midi_scheduler.is_alive():
            logger.warn("Midi scheduler not started!")
            return
        for e in midi_seq:
            scheduler.enter(self.pno_seq.ticks_to_seconds(e.time) * scale_factor, 1, self.output_port.send, (e,))

    def get_sgmt(self, m: mido.Message):
        sgmt = None
        if self.pno_seq.empty():
            logger.warn("Empty note sequence. You have completed the performance. Well done.")
        if is_note_on(m):
            sgmt = self.pno_seq.get_next_sgmt()
            self.seg_binder.add_midi_binding(m, sgmt)
        # else:
        #     sgmt = self.seg_binder.get_by_midi(m)
        if sgmt is None:
            return None
        return sgmt

    def interpolate_speed_scaling(self, n_history=5):
        """
        Given performance history, interpolate the current playback speed.
        :return:
        """
        return 1.0

    def play_sgmt(self, sgmt: PnenoSegment, midi: mido.Message):
        if sgmt is None and is_note_off(midi):
            seg = self.seg_binder.get_by_midi(midi)
            if seg is None:
                return
            key_midi_off = mido.Message(type='note_off', note=seg.key.pitch, channel=0, velocity=midi.velocity, time=0)
            self.output_port.send(key_midi_off)
        if is_note_on(midi):
            # Apply input midi velocity to sgmt key
            key_midi = mido.Message(type='note_on', note=sgmt.key.pitch, channel=0, velocity=midi.velocity, time=0)
            logger.debug("Sending:", midi)
            self.output_port.send(key_midi)

            midi_seq = sgmt.to_midi_seq(use_absolute_time=True, include_key=False, start_from_zero=True)
            self.schedule_midi_seq(midi_seq, self.interpolate_speed_scaling())

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
        self.cleaner = Timer(self.clean_intv, self.clean_history)
        self.cleaner.start()


def main():
    pneno_seq = create_pneno_seq_from_midi('/Users/kurono/Desktop/pneno_demo.mid')
    inp, oup = choose_midi_input()
    pno = PnenoSystem(inp, oup, pno_seq=pneno_seq)
    pno.start_realtime_capture()
    input("Press [Enter] to stop")
    pno.stop()


if __name__ == '__main__':
    logger.set_level(logging.DEBUG)
    main()


# TODO @Bmois: record performance data save as rehearsal data for tempo estimation