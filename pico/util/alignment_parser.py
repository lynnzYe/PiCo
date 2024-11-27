"""
@author: Bmois
@brief: Parser for hmm and match txt files, generated from Nakamura et. al.'s symbolic music alignment tool

Purpose: obtain alignment data to model tempo/ioi
"""
from dataclasses import dataclass, asdict

import matplotlib.pyplot as plt
import matplotlib.cm as cm
import mido
from jams.eval import tempo
from sympy.physics.units import velocity

from pico.pneno.interpolator import IOI_PLACEHOLDER
from pico.pneno.pneno_seq import extract_pneno_pitches_from_midi, create_pneno_seq_from_midi_file, PnenoSeq, \
    create_pneno_seq_from_midi, PnenoPitch, convert_abs_to_delta_time, convert_onsets_to_ioi
from pico.logger import logger
from pico.util.midi_util import pitch_name_to_midi, ticks_to_seconds, seconds_to_ticks, midi_to_pitch_name, \
    midi_list_to_midi, note_to_midi


@dataclass
class ScoreNote:
    id: str
    score_time: float
    bar: int
    staff: int
    voice: int
    sub_voice: int
    order: int
    event_type: str
    duration: float
    pitch: str
    note_type: str
    chord: list[str]


class ScoreParser:
    def __init__(self):
        self.notes = dict[str, ScoreNote]()  # (note_id, ScoreNote)
        self.tqpn = 0
        self.version = ''
        self.sorted_notes = []

    def _parse_line(self, line):
        parts = line.strip().split("\t")
        line = line.replace('\n', '')
        if 'TPQN' in line:
            self.tqpn = int(line.strip(': ')[-1])
            return
        elif 'Fmt3xVersion' in line:
            self.version = line.strip(': ')[-1]
            return
        elif '//' in line:
            print("\x1B[34m[Info]\033[0m ", line)
            return

        # Parse the basic attributes
        score_time = float(parts[0])  # Score beat
        bar = int(parts[1])  # Bar number
        staff = int(parts[2])  # Staff number
        voice = int(parts[3])  # Voice number
        sub_voice = int(parts[4])  # Sub-voice number
        order = int(parts[5])  # Order
        event_type = parts[6]  # Event type
        duration = float(parts[7])  # Duration
        num_notes = int(parts[8])  # Number of notes in the chord

        # Parse the pitches, note types, and note IDs
        pitches = parts[9:9 + num_notes]
        note_types = parts[9 + num_notes:9 + 2 * num_notes]
        note_ids = parts[9 + 2 * num_notes:9 + 3 * num_notes]

        # Store each note by its note ID for easy access
        for i in range(num_notes):
            self.notes[note_ids[i]] = ScoreNote(
                id=note_ids[i],
                score_time=score_time,
                bar=bar,
                staff=staff,
                voice=voice,
                sub_voice=sub_voice,
                order=order,
                event_type=event_type,
                duration=duration,
                pitch=pitches[i],
                note_type=note_types[i],
                chord=note_ids  # Store all note IDs in the chord
            )
        self.sorted_notes.append(note_ids)

    def parse_file(self, filepath):
        with open(filepath, "r") as file:
            for line in file:
                self._parse_line(line)

    def get_note_by_id(self, note_id):
        """Retrieve a note by its ID."""
        return self.notes.get(note_id, None)

    def get_attr_by_id(self, note_id, attr):
        if note_id not in self.notes.keys():
            return None
        if attr not in self.notes[note_id].keys():
            raise KeyError("Matcher found unknown key")
        return self.notes[note_id].get(attr, None)

    def get_notes_in_chord(self, note_id):
        """Retrieve all notes in the same chord as the given note ID."""
        note = self.get_note_by_id(note_id)
        if note:
            return [self.get_note_by_id(nid) for nid in note['chord']]
        return None

    def to_json(self):
        return {key: asdict(value) for key, value in self.notes.items()}


@dataclass
class MissingNote:
    score_beat: int
    note_id: str


@dataclass
class MatchNote:
    id: str
    onset_time: float
    offset_time: float
    pitch: str  # spelled pitch
    onset_velocity: int
    offset_velocity: int
    channel: int
    match_status: str
    score_time: float
    score_note_id: str  # If matched, the score note ID is provided
    error_index: int
    skip_index: str


class MatchParser:
    def __init__(self):
        self.notes = dict[str, MatchNote]()  # (note_id, MatchNote)
        self.score_map = dict[str, MatchNote]()
        self.ordered_notes = []  # note id
        self.extra_notes = []  # note id
        self.matched_notes = []  # note id
        self.missing_notes = []  # List of MissingNote
        self.score = ''
        self.perf = ''
        self.fmt3x = ''
        self.version = ''

    def _parse_line(self, line):
        # Check if the line starts with //Missing
        line = line.replace('\n', '')
        if line.startswith("//Missing"):
            # Example: //Missing 330 P1-4-42
            parts = line.split('')
            miss_note = MissingNote(parts[1], parts[2])
            self.missing_notes.append(miss_note)
            return
        elif line.startswith(('//Version')):
            self.version = line.split(': ')[-1]
            return
        elif line.startswith('// Score'):
            self.score = line.split(': ')[-1]
            return
        elif line.startswith('// Perfm'):
            self.perf = line.split(': ')[-1]
            return
        elif line.startswith('// fmt3x:'):
            self.fmt3x = line.split(': ')[-1]
            return
        elif '//' in line:
            print("\x1B[34m[Info]\033[0m ", line)
            return
        else:
            # Split regular lines by tab and parse the attributes
            parts = line.strip().split("\t")
            try:
                note = MatchNote(id=parts[0],
                                 onset_time=float(parts[1]),
                                 offset_time=float(parts[2]),
                                 pitch=parts[3],
                                 onset_velocity=int(parts[4]),
                                 offset_velocity=int(parts[5]),
                                 channel=int(parts[6]),
                                 match_status=parts[7],
                                 score_time=float(parts[8]),
                                 score_note_id=parts[9],
                                 error_index=int(parts[10]),
                                 skip_index=parts[11],
                                 )
                if parts[9] == '*':
                    self.extra_notes.append(note.id)
                else:
                    # Store the note in the dictionary indexed by onset_time (ID)
                    self.matched_notes.append(note.id)
                self.notes[note.id] = note
                self.ordered_notes.append(note.id)
            except ValueError:
                print("A Match File is expected. Format error.")

    def parse_file(self, filepath):
        with open(filepath, "r") as file:
            for line in file:
                self._parse_line(line)
        for _, value in self.notes.items():
            self.score_map[value.score_note_id] = value

    def count_aligned_midi(self):
        if not self.matched_notes:
            print("\x1B[33m[Warning]\033[0m No match file provided")
            return 0.0
        matched_count = 0
        for e in self.matched_notes:
            note = self.notes[e]
            if note.score_note_id != '*' and note.error_index == 0:
                matched_count += 1
        return matched_count

    def to_json(self):
        return {key: asdict(value) for key, value in self.notes.items()}

    def to_midi(self, fpath, matched_only=True):
        midi = mido.MidiFile()
        track = mido.MidiTrack()
        midi.tracks.append(track)
        tempo = 500000  # Default 120 bpm - microseconds per beat
        ticks_per_beat = midi.ticks_per_beat
        if matched_only:
            noteid_list = self.matched_notes
        else:
            noteid_list = self.ordered_notes

        # Create absolute-time based MIDI events, then sort and convert to delta time
        midi_list = []
        for nid in noteid_list:
            note = self.notes[nid]
            midi_list.append(
                mido.Message(type='note_on', note=pitch_name_to_midi(note.pitch),
                             velocity=note.onset_velocity, channel=note.channel,
                             time=seconds_to_ticks(seconds=note.onset_time, tempo=tempo, ticks_per_beat=ticks_per_beat)
                             ))
            midi_list.append(
                mido.Message(type='note_off', note=pitch_name_to_midi(note.pitch),
                             velocity=note.onset_velocity, channel=note.channel,
                             time=seconds_to_ticks(seconds=note.offset_time, tempo=tempo, ticks_per_beat=ticks_per_beat)
                             ))
        midi_list.sort(key=lambda e: (e.time, e.note))
        convert_abs_to_delta_time(midi_list)
        for e in midi_list:
            track.append(e)
        midi.save(fpath)


def create_match_midi_map(match_info: MatchParser, performance: mido.MidiFile):
    """

    :param match_info:
    :param performance:
    :return:
    """
    assert len(performance.tracks) <= 2
    perf_notes, perf_bpms = extract_pneno_pitches_from_midi(performance, combine=True)
    # Make sure pitches are in ascending order when the onsets are the same
    perf_notes.sort(key=lambda pneno_pitch: (pneno_pitch.onset, pneno_pitch.pitch))
    perf_bpms.sort(key=lambda midi: midi.time)

    if len(match_info.notes) != len(perf_notes):
        raise Exception(f"Unequal note events between "
                        f"MIDI ({len(perf_notes)}) and match info ({len(match_info.notes)})!")
    for i, e in enumerate(match_info.ordered_notes):
        pitch = pitch_name_to_midi(match_info.notes[e].pitch)
        assert pitch == perf_notes[i].pitch
        perf_notes[i].id = e
    return perf_notes, perf_bpms


def create_fmt3x_mapping(score_info: ScoreParser, pno_pitches, onsets):
    """
    Update pno_pitches's ID in place
    :param score_info:
    :param pno_pitches:
    :param onsets:
    :return:
    """
    score_cursor = 0
    curr_perf_onset = pno_pitches[0].onset
    # Logic: match each onset groups
    for i, e in enumerate(pno_pitches):
        if curr_perf_onset != onsets[i]:
            curr_perf_onset = onsets[i]
            score_cursor += 1
        score_notes = score_info.sorted_notes[score_cursor]
        for note in score_notes:
            if pitch_name_to_midi(score_info.notes[note].pitch) == e.pitch:
                e.id = score_info.notes[note].id
                continue
        if e.id is None:
            # Each loop must create an exact mapping.
            logger.error("Found unmatched note: ", e)
    return pno_pitches


def create_fmt3x_map_from_midi(score_info: ScoreParser, score: mido.MidiFile):
    """
    :param score_info:
    :param score:
    :return:
    """
    assert len(score.tracks) <= 2
    perf_notes, perf_bpms = extract_pneno_pitches_from_midi(score, combine=True)
    perf_notes.sort(key=lambda pneno_pitch: pneno_pitch.onset)
    perf_bpms.sort(key=lambda midi: midi.time)
    assert len(score_info.notes) == len(perf_notes)

    perf_notes = create_fmt3x_mapping(score_info, perf_notes, [e.onset for e in perf_notes])
    return perf_notes, perf_bpms


def create_fmt3x_map_from_pnoseq(score_info: ScoreParser, pno_seq: PnenoSeq):
    """
    :param score_info:
    :param pno_seq:
    :return:
    """
    notes, onsets = pno_seq.flatten()
    assert len(score_info.notes) == len(notes)
    sorted_notes = sorted(zip(notes, onsets), key=lambda x: x[1])
    notes, onsets = zip(*sorted_notes)
    notes = list(notes)
    onsets = list(onsets)
    create_fmt3x_mapping(score_info, pno_pitches=notes, onsets=onsets)
    # debug, _ = pno_seq.flatten()
    # for e in debug:
    #     assert e.id is not None


"""
NEED PerformedPnenoSeq:
 - list of PerformedPnenoSegment
 - calculates IOI ratio for key pitches
 - then calculate IOI for sgmt pitches. (omit negative onsets)

result: [key IOI], [sgmt IOI]
"""


def calculate_perf_ioi(pno_seq: PnenoSeq, score_info: ScoreParser, match_info: MatchParser):
    # Obtain performed key pitches & aligned segments
    perf_key_onsets = []
    key_sgmt_ioi = []
    if len(match_info.matched_notes) != len(score_info.notes):
        logger.warn("Imperfect alignment. IOI calculation may be influenced. Alignment rate:",
                    len(match_info.matched_notes) / len(score_info.notes))
    for e in pno_seq.seq:
        sgmt_onsets = []
        assert e.key.id is not None
        key_onset = match_info.score_map[e.key.id].onset_time
        perf_key_onsets.append(key_onset)
        for j, note in enumerate(e.sgmt):
            sgmt_pitch_onset = match_info.score_map[note.id].onset_time - key_onset
            if sgmt_pitch_onset < 0:
                logger.debug(f"Segment {j}'s onset is earlier than key onset.")
                sgmt_pitch_onset = 0
            sgmt_onsets.append(sgmt_pitch_onset)

        key_sgmt_ioi.append(convert_onsets_to_ioi(sgmt_onsets))

    return convert_onsets_to_ioi(perf_key_onsets), key_sgmt_ioi


class MIDIAlignmentParser:
    """
    Build a mapping between MIDI files and alignment information
    Both fmt3x and match files are required.
    """

    def __init__(self, fmt3x_file: str, match_file: str, score_midi: str, perf_midi: str):
        self.score_info = ScoreParser()
        self.score_info.parse_file(fmt3x_file)
        self.match_info = MatchParser()
        self.match_info.parse_file(match_file)
        self.score = mido.MidiFile(score_midi)
        self.perf = mido.MidiFile(perf_midi)
        self.perf_data = []
        self.pneno_seq = PnenoSeq()
        self._create_mapping()

    def _create_mapping(self):
        assert self.perf is not None and self.score is not None
        assert self.score_info is not None and self.match_info is not None

        self.perf_data, _ = create_match_midi_map(self.match_info, self.perf)
        self.pneno_seq = create_pneno_seq_from_midi(self.score)
        create_fmt3x_map_from_pnoseq(self.score_info, self.pneno_seq)

    def calculate_performed_pno_ioi_ratio(self):
        score_key_ioi_list = [self.pneno_seq.ticks_to_seconds(e - IOI_PLACEHOLDER) for e in
                              self.pneno_seq.to_ioi_list()]
        score_sgmt_ioi_list = []
        for e in self.pneno_seq.seq:
            onsets = [p.onset for p in e.sgmt]
            ioi = convert_onsets_to_ioi(onsets)
            score_sgmt_ioi_list.append([self.pneno_seq.ticks_to_seconds(i) for i in ioi])

        key_ioi_list, sgmt_ioi_list = calculate_perf_ioi(self.pneno_seq, self.score_info, self.match_info)

        # Calculate key IOI ratio:
        key_ioi_ratio = []
        for i, e in enumerate(key_ioi_list):
            key_ioi_ratio.append(e / score_key_ioi_list[i] if e != 0 else 1)

        # Calculate segment IOI ratio:
        sgmt_ioi_ratio = []
        for i, sgmt in enumerate(sgmt_ioi_list):
            sgmt_ratio = []
            for j, p in enumerate(sgmt):
                sgmt_ratio.append(p / score_sgmt_ioi_list[i][j] if score_sgmt_ioi_list[i][j] != 0 else 1)
            sgmt_ioi_ratio.append(sgmt_ratio)

        assert len(key_ioi_ratio) == len(score_key_ioi_list) == len(sgmt_ioi_ratio)
        return key_ioi_ratio, sgmt_ioi_ratio

    def get_performed_key_notes(self):
        keys = [e.key.id for e in self.pneno_seq]
        return [self.match_info.score_map[e] for e in keys]

    def to_pneno_midi(self, fpath: str):
        """
        Convert performance to MIDI used for PnenoSeq extraction
        :param fpath:
        :return:
        """
        out_midi = []
        midi = mido.MidiFile()
        main = mido.MidiTrack()
        acc = mido.MidiTrack()
        midi.tracks.append(main)
        midi.tracks.append(acc)
        tempo = 500000  # Default 120 bpm - microseconds per beat
        ticks_per_beat = midi.ticks_per_beat

        # Create absolute-time based MIDI events, then sort and convert to delta time
        key_midi_list = []
        acc_midi_list = []

        for sgmt in self.pneno_seq:
            key_note = self.match_info.score_map[sgmt.key.id]
            key_midi_list.extend(
                note_to_midi(pitch=pitch_name_to_midi(key_note.pitch), velocity=key_note.onset_velocity,
                             channel=key_note.channel,
                             onset=seconds_to_ticks(seconds=key_note.onset_time, tempo=tempo,
                                                    ticks_per_beat=ticks_per_beat),
                             offset=seconds_to_ticks(seconds=key_note.offset_time, tempo=tempo,
                                                     ticks_per_beat=ticks_per_beat)))
            sgmt_notes = [self.match_info.score_map[e.id] for e in sgmt.sgmt]
            for e in sgmt_notes:
                acc_midi_list.extend(
                    note_to_midi(pitch=pitch_name_to_midi(e.pitch), velocity=e.onset_velocity, channel=e.channel,
                                 onset=seconds_to_ticks(seconds=e.onset_time, tempo=tempo,
                                                        ticks_per_beat=ticks_per_beat),
                                 offset=seconds_to_ticks(seconds=e.offset_time, tempo=tempo,
                                                         ticks_per_beat=ticks_per_beat)))
        key_midi_list.sort(key=lambda e: (e.time, e.note))
        acc_midi_list.sort(key=lambda e: (e.time, e.note))
        convert_abs_to_delta_time(key_midi_list)
        convert_abs_to_delta_time(acc_midi_list)
        for e in key_midi_list:
            main.append(e)
        for e in acc_midi_list:
            acc.append(e)
        midi.save(fpath)


def plot_bpm_ratio(bpm_ratio_list, time_list,
                   key_velocity_list=None, sgmt_bpm_ratio_list=None, sgmt_time_list=None, labels=None):
    plt.plot(time_list, bpm_ratio_list, color='gray', linestyle='-', linewidth=1, label='BPM Ratio')
    if key_velocity_list is not None:
        norm = plt.Normalize(min(key_velocity_list), max(key_velocity_list))
        colors = cm.viridis(norm(key_velocity_list))
        scatter = plt.scatter(time_list, bpm_ratio_list, c=colors, s=50, label='bpm ratio', edgecolor='k')
        plt.colorbar(scatter, label='Key Velocity')
    else:
        plt.scatter(time_list, bpm_ratio_list, color='blue', s=50, edgecolor='k')
    if sgmt_bpm_ratio_list is not None:
        for i, e in enumerate(sgmt_time_list):
            plt.plot(e, sgmt_bpm_ratio_list[i], color='gray', linestyle='--', linewidth=0.5)
            plt.scatter(e, sgmt_bpm_ratio_list[i], color='gray', linestyle='--', linewidth=0.5)

    if labels is not None:
        assert len(labels) == len(bpm_ratio_list)
        for t, v, label in zip(time_list, bpm_ratio_list, labels):
            plt.text(t, v, label, ha='right')

    plt.xlabel('Time/Onset')
    plt.ylabel('Ratio')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


def ftest_parsers():
    import json

    # Example usage:
    score_parser = ScoreParser()
    score_parser.parse_file("/Users/kurono/Desktop/AlignmentTool/data/schu_score_fmt3x.txt")
    print(json.dumps(score_parser.to_json(), indent=4))
    print('===================')

    match_parser = MatchParser()
    match_parser.parse_file("/Users/kurono/Desktop/AlignmentTool/data/hrwz_cut_match.txt")
    print(json.dumps(match_parser.to_json(), indent=4))
    print('===================')
    # match_parser.to_midi('/Users/kurono/Desktop/hello.mid')


def ftest_aligner():
    fmt3x_file = "/Users/kurono/Desktop/AlignmentTool/data/schu_score_fmt3x.txt"
    match_file = '/Users/kurono/Desktop/AlignmentTool/data/hrwz_cut_match.txt'
    # match_file = '/Users/kurono/Desktop/AlignmentTool/data/hrwz_norubato_match.txt'
    score_midi = '/Users/kurono/Desktop/schu_score.mid'
    perf_midi = '/Users/kurono/Desktop/AlignmentTool/data/hrwz_cut.mid'
    # perf_midi = '/Users/kurono/Desktop/hrwz_norubato.mid'

    align_parser = MIDIAlignmentParser(fmt3x_file=fmt3x_file,
                                       match_file=match_file,
                                       score_midi=score_midi,
                                       perf_midi=perf_midi)

    align_parser.to_pneno_midi('/Users/kurono/Desktop/testa.mid')

    # key_ioi_ratio, sgmt_ioi_ratio = align_parser.calculate_performed_pno_ioi_ratio()
    # key_onsets = align_parser.pneno_seq.to_onset_list()
    # key_labels = [midi_to_pitch_name(e, all_sharp=False) for e in align_parser.pneno_seq.to_pitch_list()]
    # key_velocity = [p.onset_velocity for p in align_parser.get_performed_key_notes()]
    #
    # key_bpm_ratio = [1 / e for e in key_ioi_ratio]
    # sgmt_bpm_ratio = [[1 / e for e in sgmt] for sgmt in sgmt_ioi_ratio]
    # sgmt_onsets = []
    # for e in align_parser.pneno_seq.seq:
    #     sgmt_onsets.append([ost.onset + e.onset for ost in e.sgmt])
    #
    # plot_bpm_ratio(bpm_ratio_list=key_bpm_ratio, time_list=key_onsets, key_velocity_list=key_velocity,
    #                labels=key_labels, sgmt_bpm_ratio_list=sgmt_bpm_ratio, sgmt_time_list=sgmt_onsets)


if __name__ == '__main__':
    # ftest_parsers()
    ftest_aligner()
