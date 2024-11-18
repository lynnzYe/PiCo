import logging
import threading

import mido
from collections import deque
from threading import Thread, Timer
import time
import copy

from nbclient.exceptions import timeout_err_msg

from pico.logger import logger
import pico.demo.music.music_seq as music

sheet = music.schubert_142_3

"""
I want to use the python lib "mido" to create a midi in, midi out class (MiMo). it should:
- listen and capture user midi input (velocity, onset, noteon noteoff etc.)
- keeps a record of historical input (memory size up till a threshold, lets say, 15 seconds)
- supports plugin (loading callback functions) and perform transformations on input midi with the callback
- allows midi scheduling (receive a sequence of midi, onset at future ticks, output them at the appropriate time)
- finally, it should contain a pointer to score positions in a musicxml file (so music21 is also a choice)

"""

"""
TODO:
- Now only one note-on can exist at any time for one pitch. 
    using two keys to represent the same pitch will cut short the first one, resulting in:
    | note-on -> note-on          -> note-off -> note-ff
        + converted to:
    | note-on -> note-off note-on -> note-off -> note-off 
"""


class NoteEvent:
    noteon: bool
    pitch: int
    velocity: int

    def __init__(self, noteon, pitch, velocity):
        self.noteon = noteon
        self.pitch = pitch
        self.velocity = velocity

    def __str__(self):
        return f"MidiEvent - Pitch: {self.pitch}, Velocity: {self.velocity}, NoteOn: {self.noteon}"


class NoteDeque:
    deque = None

    def __init__(self, array=None):
        if array is None:
            array = []
        self.deque = deque()
        self.set(array)

    def set(self, array: list[int]):
        if array:
            for e in array:
                self.deque.append(e)

    def append(self, pitch: int):
        assert type(pitch) == int()
        self.deque.append(pitch)

    def append_list(self, pitch_list: list[int]):
        self.deque.extend(pitch_list)

    def pitch(self):
        """
        Return the first element's pitch
        :return:
        """
        return self.deque[0]

    def pop(self):
        if self.deque:
            return self.deque.popleft()
        else:
            logger.error("Popping an empty NoteSeq!")
            return None

    def empty(self):
        return self.deque is None or len(self.deque) == 0

    def __str__(self):
        return str(list(self.deque))


class NoteBinder:
    """
    Creates a binding between input midi and intended midi (predetermined midi)

    """

    def __init__(self):
        self.binding = {}

    def add_event(self, m: mido.messages.messages.Message, pitch):
        """
        add a Midi event to storage, indexed by midi's pitch
        :param m: the midi event
        :param pitch: the predetermined pitch
        :return:
        """
        if m.type == 'note_on' and m.velocity > 0:
            self.binding[m.note] = pitch
        else:
            logger.warn("you shouldn't be adding a note off event!")

    def get(self, m: mido.messages.messages.Message):
        if m.type == 'note_off' or (m.type == 'note_on' and m.velocity == 0):
            return self.binding.pop(m.note)
        logger.warn("you shouldn't be getting a note on event!")
        return None


class MiMo:
    """
    MiMo: Midi in Midi out, or, Music in Music out
    """
    listening = False  # whether to start realtime midi monitoring/listening
    noteseq: 'NoteDeque'  # predetermined list of pitches
    callback = None
    notebinder: 'NoteBinder'

    def __init__(self, input_port_name, output_port_name, history_size=1500, clean_intv=5):
        self.input_port = mido.open_input(input_port_name)
        self.output_port = mido.open_output(output_port_name)
        self.history = deque(maxlen=history_size)  # Adjust the size based on ticks and events per tick
        self.noteseq = NoteDeque()
        self.listening = True
        self.running_event = threading.Event()  # Event to control thread termination
        self.notebinder = NoteBinder()
        self.clean_intv = clean_intv
        self.cleaner = None
        self.capture_thread = None

    def __del__(self):
        self.stop()

    def stop(self):
        # logger.info("Stopping MiMo...")
        self.listening = False
        self.running_event.clear()  # Signal the thread to stop

        # Close the input port first to interrupt any blocking receive
        if self.input_port is not None:
            self.input_port.close()
            logger.debug("MIDI input port closed.")
            self.input_port = None

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

    def pneno(self, m: mido.Message):
        if self.noteseq is None:
            return None
        pitch = 0
        if self.noteseq.empty():
            logger.warn("Empty note sequence. You have completed the performance. Well done.")
        if m.type == 'note_on' and m.velocity > 0:
            pitch = self.noteseq.pop()
            self.notebinder.add_event(m, pitch)
        else:
            pitch = self.notebinder.get(m)

        if pitch is None:
            return None
        return NoteEvent(m.type == 'note_on', pitch, m.velocity)

    def send_midi(self, note_event: 'NoteEvent'):
        if note_event:
            midi = mido.Message('note_on' if note_event.noteon else 'note_off',
                                note=note_event.pitch,
                                velocity=note_event.velocity)
            logger.debug("Sending:", midi)
            self.output_port.send(midi)

    def add_note_seq(self, pitch_arr: list[int]):
        logger.info('Appended note list: ', pitch_arr)
        self.noteseq.append_list(pitch_arr)

    def transform_and_play(self, func, mevent):
        if mevent:
            self.send_midi(func(mevent))

    def listen(self):
        while self.running_event.is_set():  # Continue while event is set
            if not self.listening or self.input_port is None:
                break  # Exit the loop if listening is turned off
            try:
                for msg in self.input_port.iter_pending():
                    if not self.running_event.is_set():
                        break
                    logger.debug('listening:', msg)
                    self.transform_and_play(self.pneno, msg)
                    self.history.append((time.time(), msg))
                time.sleep(0.001)

            except (EOFError, OSError) as e:
                # Handle port closing or other IO errors
                logger.debug(f"Port error during listen: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error in listen loop: {e}")
                break

    def clean_history(self):
        current_time = time.time()
        count = 0
        while self.history and current_time - self.history[0][0] > 5:
            self.history.popleft()
            count += 1
        logger.debug("+Cleaned", count)
        self.cleaner = Timer(self.clean_intv, self.clean_history)
        self.cleaner.start()

    def start_realtime_capture(self):
        if self.listening:
            self.running_event.set()  # Set the event to start the thread
            self.capture_thread = Thread(target=self.listen)
            self.capture_thread.start()
            self.cleaner = Timer(self.clean_intv, self.clean_history)
            self.cleaner.start()
        else:
            logger.warn("MiMo is not listening to you.")


def main():
    logger.info("MiMo Toy example")
    mimo = MiMo(mido.get_input_names()[0], mido.get_output_names()[-1])
    mimo.add_note_seq(sheet)
    mimo.start_realtime_capture()

    mimo.send_midi(NoteEvent(True, 60, 127))
    time.sleep(2)
    mimo.send_midi(NoteEvent(False, 60, 100))


if __name__ == '__main__':
    logger.set_level(logging.INFO)
    logger.info(mido.get_input_names())
    logger.info(mido.get_output_names())
    main()

# 'FluidSynth virtual port (63328)'
