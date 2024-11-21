import mido


def array_choice(hint, arr_len):
    while True:
        try:
            in_choice = int(input(hint))
            if 0 <= in_choice < arr_len:
                return in_choice
            else:
                print("Invalid input. Please input a valid number between 0 and ", arr_len - 1)
        except Exception:
            print("Invalid input. Please input a valid number between 0 and ", arr_len - 1)


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
    input_choice = array_choice('', len(input_list))
    print("=============================")
    print("Please choose an output device (If you see FluidSynth virtual port, plz choose this one.)")
    for i, e in enumerate(output_list):
        print(i, ': ', e)
    output_choice = array_choice('', len(output_list))
    return [input_list[input_choice], output_list[output_choice]]


def ticks_to_seconds(ticks, tempo, ticks_per_beat):
    return (ticks * tempo) / (ticks_per_beat * 1_000_000)


def seconds_to_ticks(seconds, tempo, ticks_per_beat):
    return seconds * (ticks_per_beat * 1_000_000) / tempo


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