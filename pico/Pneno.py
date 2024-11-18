"""
Play Next Note Seq
"""
from os import times

import mido
import time

from dask.array import absolute

from pico.logger import logger


class PnenoPitch:
    def __init__(self, pitch, velocity, onset, offset, chnl=0):
        self.pitch = pitch
        self.velocity = velocity
        self.onset = onset  # absolute time
        self.offset = offset  # absolute time
        self.chnl = chnl

    def __repr__(self):
        return (f"Note(onset={self.onset}, offset={self.offset}, pitch={self.pitch}, "
                f"velocity={self.velocity}, channel={self.chnl})")

    def to_midi_events(self):
        return [mido.Message(type='note_on', note=self.pitch, channel=self.chnl, velocity=self.velocity,
                             time=self.onset),
                mido.Message(type='note_off', note=self.pitch, channel=self.chnl, velocity=0,
                             time=self.offset)]


def convert_abs_to_delta_time(midi_list: list[mido.Message]):
    """
    Convert absolute time to delta time [In Place]

    :param midi_list:
    :return:
    """
    curr_time = 0
    midi_list.sort(key=lambda e: e.time)
    for i in range(len(midi_list)):
        new_time = midi_list[i].time
        assert curr_time <= midi_list[i].time
        midi_list[i].time -= curr_time
        curr_time = new_time


def shift_segment_time(key_onset, segment: list[PnenoPitch]):
    for e in segment:
        assert e.onset >= key_onset
        assert e.offset >= key_onset
        e.onset -= key_onset
        e.offset -= key_onset
    return segment


def shift_midi_time(key_onset, events: list[mido.Message]):
    for e in events:
        e.time -= key_onset


class PnenoSegment:
    def __init__(self, key: PnenoPitch, segment: list[PnenoPitch]):
        """

        :param key:
        :param segment: Pneno segment, starting from current key MIDI till the next key MIDI
        """
        self.onset = key.onset
        self.key = key
        self.key.offset -= self.onset
        self.key.onset -= self.onset  # Always the first note in a segment
        self.sgmt = shift_segment_time(key_onset=self.onset, segment=segment)

    # def query(key): return False
    def to_midi_seq(self, use_absolute_time=False):
        """
        Convert list of PnenoNotes to Midi Messages
        :param use_absolute_time:
        :return:
            1.  sequence of sorted mido.Message (by time)
                - if not use_absolute_time, the first note will start with time = 0.
                    To use it in PnenoSeq, you probably need to compensate the timeshift using self.onset
                - if use_absolute_time, the first note will be the absolute start time
            2.  the absolute time of the last event in this sequence
         -
        """
        events = self.key.to_midi_events()
        for e in self.sgmt:
            events.extend(e.to_midi_events())
        events.sort(key=lambda event: event.time)
        if not use_absolute_time:
            convert_abs_to_delta_time(events)
            return events
        for i in range(len(events)):
            events[i].time += self.onset
        return events


class PnenoSeq:
    def __init__(self, segment_list: list[PnenoSegment] = None, bpm=60):
        if segment_list is None:
            segment_list = []
        self.bpm = bpm
        self.seq = segment_list

        self.cursor = 0

    def __getitem__(self, index):
        return self.seq[index]

    def append(self, pneno_sgmt: PnenoSegment):
        assert pneno_sgmt is not None
        self.seq.append(pneno_sgmt)

    def extend(self, pneno_seq: list[PnenoSegment]):
        assert pneno_seq is not None
        self.seq.extend(pneno_seq)

    def reset_cursor(self):
        self.cursor = 0

    def clean(self):
        self.reset_cursor()
        self.seq = []
        self.bpm = 60

    def get_next_sgmt(self):
        if self.cursor >= len(self.seq) - 1:
            return None
        return self.seq[self.cursor + 1]

    def to_midi_seq(self, use_absolute_time=False):
        events = []
        prev_end_abs_time = 0
        for e in self.seq:
            assert prev_end_abs_time <= e.onset
            seg_events = e.to_midi_seq(use_absolute_time=True)
            events.extend(seg_events)
        if not use_absolute_time:
            convert_abs_to_delta_time(events)
        return events


def extract_pneno_notes_from_track(midi_track: mido.MidiTrack or list[mido.Message]):
    """

    :param midi_track:
    :return:
    """
    notes = []
    tempo_chg = []
    active_notes = {}
    absolute_time = 0

    for msg in midi_track:
        absolute_time += msg.time
        if msg.type == 'set_tempo':
            tempo_chg.append(msg)
        elif msg.type == 'note_on' and msg.velocity > 0:
            key = (msg.note, msg.channel)
            if key in active_notes:
                onset_time, velocity = active_notes.pop(key)
                notes.append(
                    PnenoPitch(pitch=msg.note, velocity=msg.velocity, onset=onset_time, offset=absolute_time,
                               chnl=msg.channel))
            active_notes[key] = (absolute_time, msg.velocity)
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            key = (msg.note, msg.channel)
            if key in active_notes:
                onset_time, velocity = active_notes.pop(key)
                notes.append(
                    PnenoPitch(pitch=msg.note, velocity=velocity, onset=onset_time, offset=absolute_time,
                               chnl=msg.channel))
    # Close any remaining notes
    for (pitch, channel), (onset_time, velocity) in active_notes.items():
        notes.append(PnenoPitch(pitch=pitch, velocity=velocity, onset=onset_time, offset=absolute_time,
                                chnl=channel))
    return notes, tempo_chg


def extract_pneno_notes_from_midi(midi: mido.MidiFile):
    """
    Link note on and note off to create a PnenoPitch object
    :param midi:
    :return:
    """
    # tqb = midi.ticks_per_beat
    track_notes = []
    tempo_changes = []
    for tr in midi.tracks:
        notes, tempo_chgs = extract_pneno_notes_from_track(tr)
        track_notes.append(notes)
        tempo_changes.append(tempo_chgs)

    return track_notes, tempo_changes


def parse_midi_track_tempo(track):
    tempo = []
    for msg in track:
        if msg.type == 'set_tempo':
            tempo.append(msg.tempo)
    return tempo


def create_pneno_seq_from_midi(midi_path):
    """
    :param midi_path:
        - one track for the main melody
        - one track for the aligned notes
    :return:
    """
    midi = mido.MidiFile(midi_path)
    if len(midi.tracks) not in [2, 3]:
        raise ValueError("Currently MIDI file must have at least two tracks (melody and accompaniment)")
    track_notes, tempo_changes = extract_pneno_notes_from_midi(midi)

    # tempo = tempo_changes[0]  # TODO @Bmois check for multiple tempo changes
    if len(midi.tracks) == 3:
        melody_track = track_notes[1]
        acc_track = track_notes[2]  # For aligned Pneno segments
    else:
        melody_track = track_notes[0]
        acc_track = track_notes[1]

    return create_pneno_seq(melody_track, acc_track)


def create_pneno_seq(melody_track, acc_track):
    melody_track.sort(key=lambda e: e.onset)
    acc_track.sort(key=lambda e: e.onset)
    melody_onsets = []

    for note in melody_track:
        melody_onsets.append(note.onset)

    acc_sequences = []  # List of lists to store sequences
    current_acc_sequence = []
    onset_index = 1

    for i, note in enumerate(acc_track):
        # Append note to the current sequence if it's before the next melody onset
        if onset_index == len(melody_onsets):
            current_acc_sequence.append(note)
            acc_sequences.append(current_acc_sequence)
            break
        elif onset_index < len(melody_onsets) and note.onset < melody_onsets[onset_index]:
            current_acc_sequence.append(note)
        else:
            # Append the current sequence and start a new one when we reach the next onset
            acc_sequences.append(current_acc_sequence)
            current_acc_sequence = [note]
            onset_index += 1
            # Prevent out-of-bounds indexing for melody_onsets
            if onset_index > len(melody_onsets):
                break

    assert len(melody_track) == len(acc_sequences)
    pneno_seq = PnenoSeq()
    for i in range(len(melody_track)):
        pneno_seq.append(PnenoSegment(key=melody_track[i], segment=acc_sequences[i]))
    return pneno_seq


def play_midi_seq(midi_seq, output_port_name, default_vel=80, chnl=0, absolute_time=False, tempo_scaling=400):
    """

    :param midi_seq: Array of MIDI events with absolute time.
    :param output_port_name:
    :param default_vel:
    :param chnl:
    :param absolute_time:
    :param tempo_scaling
    :return:
    """
    if absolute_time:
        midi_seq.sort(key=lambda event: event.time)
    with mido.open_output(output_port_name) as output:
        last_time = midi_seq[0].time
        for msg in midi_seq:
            if absolute_time:
                delay = (msg.time - last_time) / tempo_scaling
            else:
                delay = msg.time / tempo_scaling
                logger.debug("Delay is", delay)
            assert delay >= 0
            time.sleep(delay)
            msg.velocity = default_vel
            msg.channel = chnl
            output.send(msg)
            last_time = msg.time


if __name__ == '__main__':
    print(mido.get_output_names())
    pneno_seq = create_pneno_seq_from_midi('/Users/kurono/Desktop/pneno_demo.mid')
    play_midi_seq(pneno_seq.to_midi_seq(use_absolute_time=False), output_port_name=mido.get_output_names()[0])

    # for i in range(len(acc)):
    #     play_noteon_midi_seq(acc[i], output_port_name=mido.get_output_names()[0])
    #     time.sleep(0.3)
