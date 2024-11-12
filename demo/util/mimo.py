import logging

import mido
from collections import deque
from threading import Thread, Timer
import time
import copy

from util.bmois_logger import logger
import music.music_seq as music

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
    noteseq: NoteDeque  # predetermined list of pitches
    callback = None
    notebinder: NoteBinder

    def __init__(self, input_port_name, output_port_name, history_size=1500, clean_intv=5):
        # self.input_port = mido.open_input('A-Series Keyboard Keyboard')
        self.input_port = mido.open_input(input_port_name)
        self.output_port = mido.open_output(output_port_name)
        self.history = deque(maxlen=history_size)  # Adjust the size based on ticks and events per tick
        self.noteseq = NoteDeque()
        self.listening = True
        self.notebinder = NoteBinder()
        self.cleaner = Timer(clean_intv, self.clean_history)
        self.cleaner.start()
        # self.debug_timer = Timer(5, self.debug_queue)
        # self.debug_timer.start()

    def pneno(self, m: mido.messages.messages.Message):
        """
        Play next note in noteseq (call only once with noteon-noteoff pairs)
        :param m:
        :return:
        """
        if self.noteseq is None:
            return None
        pitch = 0
        if m.type == 'note_on' and m.velocity > 0:
            pitch = self.noteseq.pop()
            self.notebinder.add_event(m, pitch)
        else:
            pitch = self.notebinder.get(m)

        if pitch is None:
            return None
        return NoteEvent(m.type == 'note_on', pitch, m.velocity)

    def send_midi(self, note_event: NoteEvent):
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
        for m in self.input_port:
            logger.debug('listening:', m)
            self.transform_and_play(self.pneno, m)
            self.history.append((time.time(), m))

    def clean_history(self):
        # Prune outdated events
        self.add_note_seq(sheet)
        current_time = time.time()
        count = 0
        while self.history and current_time - self.history[0][0] > 5:
            self.history.popleft()
            count += 1
        logger.debug("+Cleaned", count)
        self.cleaner = Timer(5, self.clean_history)
        self.cleaner.start()

    # def debug_queue(self):
    #     logger.debug("+Hist len: ", len(self.history))
    #     # Restart the timer for the next debug
    #     self.debug_timer = Timer(5, self.debug_queue)
    #     self.debug_timer.start()

    def start_realtime_capture(self):
        if self.listening:
            capture_thread = Thread(target=self.listen, daemon=True)
            capture_thread.start()
        else:
            logger.warning("Mimo is not listening to you.")


def main():
    logger.info("MiMo Toy example")
    mimo = MiMo()
    # mimo.send_midi(NoteEvent(True, 60, 127))
    # time.sleep(2)
    # mimo.send_midi(NoteEvent(False, 60, 100))
    # mimo.add_note_seq(sheet)
    mimo.add_note_seq(sheet)
    mimo.start_realtime_capture()


if __name__ == '__main__':
    logger.set_level(logging.INFO)
    logger.info(mido.get_output_names())
    logger.info(mido.get_input_names())
    # main()

# 'FluidSynth virtual port (63328)'
