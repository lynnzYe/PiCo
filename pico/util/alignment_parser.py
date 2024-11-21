"""
@author: Bmois
@brief: Parser for hmm and match txt files, generated from Nakamura et. al.'s symbolic music alignment tool

Purpose: obtain alignment data to model tempo/ioi
"""
from dataclasses import dataclass, asdict
import mido

from pico.pneno.pneno_seq import extract_pneno_pitches_from_midi, create_pneno_seq_from_midi, PnenoSeq
from pico.logger import logger
from pico.util.midi_util import pitch_name_to_midi


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


class MatchFileParser:
    def __init__(self):
        self.notes = dict[str, MatchNote]()  # (note_id, MatchNote)
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


def create_match_midi_map(match_info: MatchFileParser, performance: mido.MidiFile):
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


def create_fmt3x_map_from_pnoseq(score_info: ScoreParser, pnoseq: PnenoSeq):
    """
    :param score_info:
    :param score_midi_path:
    :return:
    """
    notes, onsets = pnoseq.flatten()
    assert len(score_info.notes) == len(notes)
    sorted_notes = sorted(zip(notes, onsets), key=lambda x: x[1])
    notes, onsets = zip(*sorted_notes)
    notes = list(notes)
    onsets = list(onsets)
    create_fmt3x_mapping(score_info, pno_pitches=notes, onsets=onsets)
    debug, _ = pnoseq.flatten()
    for e in debug:
        assert e.id is not None
    return pnoseq


class MIDIAlignmentParser:
    """
    Build a mapping between MIDI files and alignment information
    Both fmt3x and match files are required.
    """

    def __init__(self, fmt3x_file: str, match_file: str, score_midi: str, perf_midi: str):
        self.score_info = ScoreParser()
        self.score_info.parse_file(fmt3x_file)
        self.match_info = MatchFileParser()
        self.match_info.parse_file(match_file)
        self.score = mido.MidiFile(score_midi)
        self.perf = mido.MidiFile(perf_midi)

    def _create_mapping(self):
        assert self.perf is not None and self.score is not None
        assert self.score_info is not None and self.match_info is not None


if __name__ == '__main__':
    import json

    # Example usage:
    score_parser = ScoreParser()
    score_parser.parse_file("/Users/kurono/Desktop/AlignmentTool/data/schu_score_fmt3x.txt")
    print(json.dumps(score_parser.to_json(), indent=4))
    print('===================')

    match_parser = MatchFileParser()
    match_parser.parse_file("/Users/kurono/Desktop/AlignmentTool/data/hrwz_cut_match.txt")
    print(json.dumps(match_parser.to_json(), indent=4))
    print('===================')

    # perf, perf_bpm = create_match_midi_map(match_info=match_parser,
    #                                        performance=mido.MidiFile(
    #                                            '/Users/kurono/Desktop/AlignmentTool/data/hrwz_cut.mid'))

    score, score_bpm = create_fmt3x_map_from_midi(score_info=score_parser,
                                                  score=mido.MidiFile(
                                                      '/Users/kurono/Desktop/AlignmentTool/data/schu_score.mid'))

    pnoseq = create_pneno_seq_from_midi('/Users/kurono/Desktop/schu_score.mid')
    create_fmt3x_map_from_pnoseq(score_info=score_parser, pnoseq=pnoseq)
