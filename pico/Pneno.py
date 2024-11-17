"""
Play Next Note Seq
"""
import mido
import time

import note_seq
from anyio import current_time
from dask.array import absolute
from jams.eval import tempo
from mir_eval.display import pitch


class PnenoPitch:
    def __init__(self, pitch, velocity, onset, offset, chnl=0):
        self.pitch = pitch
        self.velocity = velocity
        self.onset = onset
        self.offset = offset
        self.chnl = chnl

    def __repr__(self):
        return (f"Note(onset={self.onset}, offset={self.offset}, pitch={self.pitch}, "
                f"velocity={self.velocity}, channel={self.chnl})")


class PnenoCluster:
    def __init__(self, key: PnenoPitch, segment: list[PnenoPitch]):
        """

        :param key:
        :param segment: Pneno segment, starting from current key MIDI till the next key MIDI
        """
        self.key = key
        self.seg = segment

        # def query(key): return False


class PnenoSeq:
    def __init__(self, cluster_seq: list[PnenoCluster] = None, bpm=60):
        if cluster_seq is None:
            cluster_seq = []
        self.bpm = bpm
        self.seq = cluster_seq

        self.cursor = 0

    def append(self, pneno_cluster: PnenoCluster):
        assert pneno_cluster is not None
        self.seq.append(pneno_cluster)

    def extend(self, pneno_seq: list[PnenoCluster]):
        assert pneno_seq is not None
        self.seq.extend(pneno_seq)

    def reset_cursor(self):
        self.cursor = 0

    def clean(self):
        self.reset_cursor()
        self.seq = []
        self.bpm = 60

    def get_next_cluster(self):
        if self.cursor >= len(self.seq) - 1:
            return None
        return self.seq[self.cursor + 1]


def extract_pneno_notes(midi: mido.MidiFile):
    """
    Link note on and note off to create a PnenoPitch object
    :param midi:
    :return:
    """
    # tqb = midi.ticks_per_beat
    track_notes = []
    tempo_changes = []
    for tr in midi.tracks:
        notes = []
        tempo_chg = []
        active_notes = {}
        absolute_time = 0
        for msg in tr:
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
        tempo_changes.append(tempo_chg)
        track_notes.append(notes)

    return track_notes, tempo_changes


def parse_midi_track_tempo(track):
    tempo = []
    for msg in track:
        if msg.type == 'set_tempo':
            tempo.append(msg.tempo)
    return tempo


def create_pneno_seq(midi_path):
    """

    :param midi_path:
        - one track for the main melody
        - one track for the aligned notes
    :return:
    """
    midi = mido.MidiFile(midi_path)
    if len(midi.tracks) not in [2, 3]:
        raise ValueError("Currently MIDI file must have at least two tracks (melody and accompaniment)")
    track_notes, tempo_changes = extract_pneno_notes(midi)

    # tempo = tempo_changes[0]  # TODO @Bmois check for multiple tempo changes
    if len(midi.tracks) == 3:
        melody_track = track_notes[1]
        acc_track = track_notes[2]  # For aligned Pneno segments
    else:
        melody_track = track_notes[0]
        acc_track = track_notes[1]

    melody_onsets = []

    for note in melody_track:
        melody_onsets.append(note.onset)

    acc_sequences = []  # List of lists to store sequences
    current_acc_sequence = []
    onset_index = 1

    for note in acc_track:
        # Append note to the current sequence if it's before the next melody onset
        if onset_index < len(melody_onsets) and note.onset < melody_onsets[onset_index]:
            current_acc_sequence.append(note)
        else:
            # Append the current sequence and start a new one when we reach the next onset
            acc_sequences.append(current_acc_sequence)
            current_acc_sequence = [note]
            onset_index += 1
            # Prevent out-of-bounds indexing for melody_onsets
            if onset_index >= len(melody_onsets):
                break

    assert len(melody_track) == len(acc_sequences)
    pneno_seq = PnenoSeq()
    for i in range(len(melody_track)):
        pneno_seq.append(PnenoCluster(key=melody_track[i], segment=acc_sequences[i]))
    return pneno_seq


def play_noteon_midi_seq(midi_seq, output_port_name, default_vel=80, chnl=0):
    """

    :param midi_seq: Array of MIDI events with absolute time.
    :param output_port_name:
    :param default_vel:
    :return:
    """
    midi_seq.sort(key=lambda event: event.time)
    with mido.open_output(output_port_name) as output:
        last_time = midi_seq[0].time
        for msg in midi_seq:
            delay = (msg.time - last_time) / 500
            time.sleep(delay)
            msg.velocity = default_vel
            msg.channel = chnl
            output.send(msg)
            last_time = msg.time


if __name__ == '__main__':
    print(mido.get_output_names())
    melody, acc = create_pneno_seq('/Users/kurono/Desktop/pneno_demo.mid')

    for i in range(len(acc)):
        play_noteon_midi_seq(acc[i], output_port_name=mido.get_output_names()[0])
        time.sleep(0.3)
