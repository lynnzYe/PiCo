import pytest
from pico.pneno.pneno_seq import *


@pytest.mark.parametrize("midi_list, num_notes", [
    ([mido.Message(type="note_on", note=60, velocity=60, time=1, channel=1),
      mido.Message(type="note_off", note=60, velocity=60, time=1, channel=1),
      mido.Message(type="note_on", note=61, velocity=60, time=1, channel=1),
      mido.Message(type="note_off", note=61, velocity=60, time=1, channel=1),
      ], 2),
])
def test_extract_pneno_notes(midi_list: [mido.Message], num_notes):
    notes, tempo_chgs = extract_pneno_notes_from_track(midi_list)
    assert len(notes) == num_notes
