import mido
from mido import Message
import Mode
import numpy as np

import json


class Note:

    def __init__(self, pitch: int, time=1/4):

        """
        usage:
            note1 = Note(0)
            note2 = Note(2,1/8)

        :param pitch: int               # 預設採用七聲音階系統 0~6代表一個八度的7個音 7~13代表下一個八度的7個音
        :param time: float              # 4分音符為1/4, 8分音符為1/8, 依此類推

        """

        self.pitch = pitch
        self.time = time

    def __repr__(self):
        return "{\"note\": [%d, %.3f]}" % (self.pitch, self.time)


class Chord(Note):
    def __init__(self, *args: Note):
        """
        usage:
            Chord(Note(0),Note(2),Note(4))

        放在同一個Chord裡的音符會一起被播放，一起結束
        :param args: tuple of Note      #
        """
        super(Note, self).__init__()
        self.pitch = args[0].pitch
        self.time = args[0].time
        self.chord = list(args)

    def __repr__(self):
        return self.chord.__str__().replace("(", "[").replace(")", "]")


class Bar:
    def __init__(self, notes=None, key="C", mode=Mode.major, octave=4, tempo=75, time_sign=(4, 4)):

        """
        init a Bar object (小節物件)

        usage:
            bar1 = Bar(Note(0), Note(1), Note(2), Note(0, 1/8))
            bar2 = Bar([Chord(Note(0), Note(2), Note(4)), Note(0, 1/8), key="E", mode=mode.minor, octave=4)


        :param notes:       list                        # Note/Chord 的 list
        :param key:         string                      # 調(主音)
        :param mode:        dict                        # 音階系統(調式) ex. mode.major:大調, mode.minor:小調
        :param octave:      int                         # 第幾個八度
        :param tempo:       int                         # 速度(bpm)
        :param time_sign:   (x,y)                       # 拍號，每小節有x拍，以y分音符為1拍

        """

        self.key = key
        self.key_dict = {"C": 0, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}
        self.octave = octave
        self.tempo = tempo
        self.time_sign = time_sign
        self.time_constant = 72000                      # 時間常數，換算midi每個tick的時間用的

        self.mode = mode

        if type(notes) is list:
            self.notes = notes
        elif notes is None:
            self.notes = []
        else:
            raise TypeError("Bar(x): input x must be a list of Note. your type(x) is %s" % type(notes))

        # TODO: init by json

    def to_128_pitch(self, note: Note):

        """
        根據傳入的Note之相對pitch，計算出對應的128絕對pitch

        usage:
            bar.to_128_pitch(Note(0))

        :param note: Note
        :return: int

        """
        midi_128_pitch = self.mode[note.pitch] + 12 * self.octave + self.key_dict[self.key]
        return midi_128_pitch

    def to_time(self, note: Note):

        """
        根據傳入的Note之相對時間長度，計算出對應midi的時間長度

        usage:
            bar.to_time(Note(0,1/8))

        :param note:
        :return:

        """

        time = int(self.time_constant / self.tempo * note.time)
        # TODO: adjust time
        return time

    def append(self, note: Note):
        self.notes.append(note)
        return

    def pop(self)->Note:
        return self.notes.pop()

    def to_json(self):

        k = {"key": self.key,
             "key_dict":self.key_dict,
             "octave":self.octave,
             "tempo":self.tempo,
             "time_signature":self.time_sign,
             "time_constant":self.time_constant,
             "mode": self.mode,
             "notes": "to_be_replace"
             }

        return json.dumps(k).replace("\"to_be_replace\"", self.notes.__repr__())

    def to_array(self, min_note_unit=1/16):
        """
        根據bar資訊，產生對應的 numpy array

        :param min_note_unit:
        :return: np.array in shape(pitch, time, feature)
        """

        unit_note_time = 1 / self.time_sign[1]
        note_per_bar = self.time_sign[0]

        total_time_per_bar = unit_note_time * note_per_bar
        array_length_per_bar = int(total_time_per_bar / min_note_unit)
        array = np.zeros((128, array_length_per_bar, 2))

        cursor = 0

        for note in self.notes:

            if type(note) is Note:

                length = int(note.time/min_note_unit)

                # melody feature matrix in [:,:,0]
                array[self.to_128_pitch(note), cursor:cursor+length, 0] = 1

                # onset feature matrix in [:,:,1]
                array[self.to_128_pitch(note), cursor, 1] = 1

                cursor += length

            if type(note) is Chord:

                length = int(note.time / min_note_unit)

                for chord_note in note.chord:

                    # melody feature matrix in [:,:,0]
                    array[self.to_128_pitch(chord_note), cursor:cursor + length, 0] = 1

                    # onset feature matrix in [:,:,1]
                    array[self.to_128_pitch(chord_note), cursor, 1] = 1

                cursor += length

        return array


class Tab(Bar):

    def __init__(self, *args: Bar):
        super(Tab, self).__init__()
        self.bars = list(args)

        try:
            self.key = args[0].key
            self.key_dict = args[0].key_dict
            self.octave = args[0].octave
            self.tempo = args[0].tempo
            self.time_sign = args[0].time_sign

        except IndexError:
            pass

    def to_array(self, min_note_unit=1/16):

        array = np.zeros((128, 0, 2))

        for bar in self.bars:
            array = np.concatenate((array, bar.to_array()), axis=1)
        return array

    def to_json(self):

        string_list = list()

        for bar in self.bars:
            string_list.append(bar.to_json())

        return "["+",".join(string_list)+"]"

    def append(self, bar: Bar):
        self.bars.append(bar)
        return

    def pop(self):
        return self.bars.pop()



class MidiTrack(mido.MidiTrack):

    def append_bar(self, bar):
        if type(bar) is Bar:
            self._append_bar(bar)

        elif type(bar) is Tab:
            for tab_bar in bar.bars:
                self._append_bar(tab_bar)


    def _append_bar(self, bar: Bar):
        for note in bar.notes:

            if type(note) is Note:

                pitch = bar.to_128_pitch(note)
                time = bar.to_time(note)
                print(pitch, time, note)

                self.append(Message('note_on', note=pitch, velocity=64, time=0))
                self.append(Message('note_off', note=pitch, velocity=64, time=time))

            elif type(note) is Chord:

                pitch = 0
                time = bar.to_time(note)
                print(bar.to_128_pitch(note), time, note)

                for chord_note in note.chord:
                    pitch = bar.to_128_pitch(chord_note)
                    self.append(Message('note_on', note=pitch, velocity=64, time=0))

                self.append(Message('note_off', note=pitch, velocity=64, time=time))

                for chord_note in reversed(note.chord[:-1]):
                    pitch = bar.to_128_pitch(chord_note)
                    self.append(Message('note_off', note=pitch, velocity=64, time=0))

            # TODO: Volume control
            # TODO: time shift
            # TODO: independent end time for notes in chord
            # TODO: Program change

        return


