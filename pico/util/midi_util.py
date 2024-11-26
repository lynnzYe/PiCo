import mido
import os
import pickle


def is_note_on(m: mido.Message):
    return m.type == 'note_on' and m.velocity > 0


def is_note_off(m: mido.Message):
    return m.type == 'note_off' or (m.type == 'note_on' and m.velocity == 0)


def is_note(m: mido.Message):
    return is_note_on(m) or is_note_off(m)


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


def array_choice(arr_begin, arr_end, hint=''):
    while True:
        try:
            in_choice = int(input(hint))
            if arr_begin <= in_choice < arr_end:
                return in_choice
            else:
                print(f"Invalid input. Please input a valid number between {arr_begin} and {arr_end - 1}")
        except Exception:
            print(f"Invalid input. Please input a valid number between {arr_begin} and {arr_end - 1}")


def choose_midi_input():
    # logger.info("Available MIDI input devices:")
    input_list = mido.get_input_names()
    output_list = mido.get_output_names()
    if len(input_list) == 0 or len(output_list) == 0:
        raise RuntimeError("No MIDI input/output device found.")
    print("=============================")
    print("Please choose an input device")
    for i, e in enumerate(input_list):
        print(i, ': ', e)
    input_choice = array_choice(0, len(input_list), '')
    print("=============================")
    print("Please choose an output device (If you see FluidSynth virtual port, plz choose this one.)")
    for i, e in enumerate(output_list):
        print(i, ': ', e)
    output_choice = array_choice(0, len(output_list), '')
    return [input_list[input_choice], output_list[output_choice]]


def ticks_to_seconds(ticks, tempo=500_000, ticks_per_beat=480):
    return (ticks * tempo) / (ticks_per_beat * 1_000_000)


def seconds_to_ticks(seconds, tempo=500_000, ticks_per_beat=480):
    return int(round(seconds * (ticks_per_beat * 1_000_000) / tempo))


def midi_to_pitch_name(midi: int, all_sharp=True):
    midi_map = {
        0: 'C',
        2: 'D',
        4: 'E',
        5: 'F',
        7: 'G',
        9: 'A',
        11: 'B',
    }
    assert midi >= 0
    octave = midi // 12 - 1  # C4 = 60
    base = midi % 12
    if base in midi_map.keys():
        return f"{midi_map[base]}{octave}"
    # Now determine flat or sharp
    if all_sharp:
        return f"{midi_map[base - 1]}#{octave}"
    else:
        return f"{midi_map[base + 1]}b{octave}"


def pitch_name_to_midi(pname: str):
    note_map = {
        'C': 0,
        'D': 2,
        'E': 4,
        'F': 5,
        'G': 7,
        'A': 9,
        'B': 11
    }
    base = pname[0].upper()
    acc = None
    if len(pname) > 2:
        assert pname[1] in '#b'
        acc = pname[1]
        octave = int(pname[2:])
    else:
        octave = int(pname[1:])
    semitone = note_map[base]
    if acc:
        semitone += 1 if acc == '#' else - 1
    return (12 * (octave + 1)) + semitone


def midi_list_to_midi(midi_list: list[mido.Message], ticks_per_beat=480):
    midi = mido.MidiFile()
    track = mido.MidiTrack()
    midi.tracks.append(track)
    midi.ticks_per_beat = ticks_per_beat
    for e in midi_list:
        track.append(e)
    return midi


def note_to_midi(pitch, velocity, onset, offset, channel):
    mlist = [mido.Message(type='note_on', note=pitch, velocity=velocity, channel=channel, time=onset),
             mido.Message(type='note_off', note=pitch, velocity=velocity, channel=channel, time=offset)]
    return mlist


def perf_file_to_midi(perf_file, save_path=None):
    """
    :param perf_file:  perf_data.pkl
    :param save_path:
    :return:
    """
    if perf_file is None:
        return None, None
    assert os.path.exists(perf_file)
    with open(perf_file, 'rb') as f:
        data = pickle.load(f)

    # deque of (time, msg, sgmt)
    ticks_per_beat = data['ticks_per_beat']
    tempo = data['tempo']
    start_time = data['start_time']
    perf_seq = data['performance']

    # Flatten performance sequence
    # ( time, performned MIDI, mapped PnenoSegment, synthesized MIDI)
    midi_list = []
    midi_noteon_map = {}
    for e in perf_seq:
        midi = e[1]
        midi.time = seconds_to_ticks(e[0] - start_time, tempo, ticks_per_beat)
        if e[2] is not None:
            midi_noteon_map[midi.note] = e[2].key.pitch
            midi.note = e[2].key.pitch
            midi_list.append(e[1])
            assert e[3] is not None
            for mid in e[3]:
                mid.time += midi.time
                mid.channel = 1  # Append acc part to another track
                mid.time = int(mid.time)
            midi_list.extend(e[3])
        else:
            pitch = midi_noteon_map.pop(midi.note)
            midi.note = pitch
            midi_list.append(midi)

    convert_abs_to_delta_time(midi_list)

    midi_file = midi_list_to_midi(midi_list)
    if save_path:
        midi_file.save(save_path)
    return midi_file


def main():
    perf_file_to_midi('/Users/kurono/Desktop/perf_data.pkl', save_path='/Users/kurono/Desktop/thz.mid')


if __name__ == '__main__':
    main()
