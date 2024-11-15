"""
Play Next Note Seq
"""
import mido
import time


class PnenoPitch:
    def __init__(self, pitch, velocity, onset, offset):
        self.pitch = pitch
        self.velocity = velocity
        self.onset = onset
        self.offset = offset


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
    def __init__(self, pneno_seq: list[PnenoCluster] = None, bpm=60):
        if pneno_seq is None:
            pneno_seq = []
        self.bpm = bpm
        self.seq = pneno_seq

        self.cursor = 0

    def get_next_seq(self):
        if self.cursor >= len(self.seq) - 1:
            return None
        return self.seq[self.cursor + 1]


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

    tempo = []
    melody_noteon = []
    melody_noteoff = []
    acc_noteon = []
    acc_noteoff = []

    if len(midi.tracks) == 3:
        tempo = parse_midi_track_tempo(midi.tracks[0])
        melody_track = midi.tracks[1]
        acc_track = midi.tracks[2]  # For aligned Pneno segments
    else:
        melody_track = midi.tracks[0]
        acc_track = midi.tracks[1]  # For aligned Pneno segments

    # Convert to absolute time
    for track in midi.tracks:
        absolute_time = 0
        for msg in track:
            absolute_time += msg.time
            msg.time = absolute_time

    melody_onsets = []

    for msg in melody_track:
        if msg.type == 'set_tempo':
            tempo.append(msg.tempo)
        elif msg.type == 'note_on' and msg.velocity > 0:  # Only consider note_on messages with non-zero velocity
            melody_noteon.append(msg)
            melody_onsets.append(msg.time)
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            melody_noteoff.append(msg)

    acc_sequences = []  # List of lists to store sequences
    current_sequence = []
    onset_index = 0

    for msg in acc_track:
        if msg.type == 'note_on' and msg.velocity > 0:
            acc_noteon.append(msg)
            # Append note to the current sequence if it's before the next melody onset
            if onset_index < len(melody_onsets) and msg.time <= melody_onsets[onset_index]:
                current_sequence.append(msg)
            else:
                # Append the current sequence and start a new one when we reach the next onset
                acc_sequences.append(current_sequence)
                current_sequence = [msg]
                onset_index += 1
                # Prevent out-of-bounds indexing for melody_onsets
                if onset_index >= len(melody_onsets):
                    break

        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            acc_noteoff.append(msg)

    return melody_noteon, acc_noteon,


def play_noteon_midi_seq(midi_seq, output_port_name, default_vel=80):
    play_mid_seq = []
    for m in midi_seq:
        play_mid_seq.append(mido.Message('note_on', note=m.note, velocity=default_vel, time=m.time))
        play_mid_seq.append(mido.Message('note_off', note=m.note, velocity=default_vel, time=10))
    with mido.open_output(output_port_name) as output:
        start_time = time.time()
        for msg in play_mid_seq:
            # Wait for the specified delta time
            time.sleep(msg.time)
            # Send the message to the output
            output.send(msg)
            print(f"Sent: {msg} at {time.time() - start_time:.2f}s")


if __name__ == '__main__':
    create_pneno_seq('/Users/kurono/Desktop/pneno_demo.mid')
