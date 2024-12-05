# Piano Conductor 
a.k.a. PiCo

Create artful piano performances by tapping. Unleash your creative potential with minimal technical distractions.

## Installation

```shell
conda create -n pico python=3.11 -y
conda activate pico
pip install -r requirements.txt
pip install -e .
```

## Proof-of-Concept Interactive Demo

You will need these for the demo:

- a connected MIDI device
- [fluidsynth](https://www.fluidsynth.org/download/)
- a piano soundfont (The [Piano Collection-SF4u](https://drive.google.com/file/d/1UpggAFKqgrcjWweZJNAQspuT9zo-hotJ/view)
  soundfont is
  recommended)

### Arguments

- Required:
    - `sf_path`: you need to provide a soundfont path to use this demo.
- Optional:
    - `midi_path`: only used in `Mode 2` This is the musical score you want to perform through this system.
    - `sess_save_path`: provide a path to save the interactive session.
    - `ref_sess`: provide hints for the system to track your tempo using a past session data.
    - `interpolate_velocity`: adding this flag will ask the system to interpolate MIDI velocity for the accompaniment
      part.

### Example

```shell
python demo.py \
  # Required args
  --sf_path=PATH_TO_SOUNDFONT \
  
  # Optional args
  --midi_path=PATH_TO_MIDI_FILE \  
  --sess_save_path=PATH_TO_SAVE_FILE \  
  --ref_sess=PATH_TO_REF_FILE \
  --interpolate_velocity  #
  
```

### Example Session

```text
=============================
Please choose an input device
0 :  Roland Digital Piano
> 0
=============================
Please choose an output device (If you see FluidSynth virtual port, plz choose this one.)
0 :  Roland Digital Piano
1 :  FluidSynth virtual port (81308)
> 1

Please choose a mode:
1: Play a sequence of notes
2: Play a complete score
> 2

Press [Enter] to stop
[Info] Pneno System started! Press any MIDI key to continue...

```

### Common Problems

"Couldn't find the FluidSynth library"

- Please refer to this
  stackoverflow [link](https://stackoverflow.com/questions/62478717/importerrorcouldnt-find-the-fluidsynth-library)
  for more information
- For MacOS users: You may need to append it to DYLD_LIBRARY_PATH

---

## More Information

### How to Interact?

Press any key on the MIDI device. Your {onset, offset, velocity} information will be applied to a predetermined note
sequence one by one, synthesized using the provided soundfont.

Pressing a certain pitch won't do any help. Only the note-on/note-off signal is useful. Therefore, it can be extended to
other interfaces, such as a pressure-sensitive desk/glove.

It is a proof of concept for Piano Conductor—reconstruct a complete expressive performance from timing and dynamic
information only, so that you can artfully play the piano anytime anywhere without significant practice

### About Different Modes of Interaction

This demo contains two modes of interation:

1. Play a sequence of notes
    - A predetermined sequence of notes will be played as you tap (any MIDI note-on/note-off signals)
    - You can add new scores by modifying `music_seq.py`
2. Play a complete score **[New]**
    - "Perform" the complete score by tapping a part of the score (e.g. melody line). The missing
      notes are synthesized with velocity and timing inferred from your input.

### About saving your interactive session

You can provide a `--sess_save_path` to save your demo session. After obtaining the `perf_data.pkl` file, The
performance can be synthesized by calling `perf_file_to_midi(...)` from `midi_util.py`

## Background

The ideas of "air instruments" (e.g. air guitar) and conducting systems are not new. Many projects have explored this
idea, such as _[Radio Baton](https://ccrma.stanford.edu/radiobaton/), [Guitar Hero](https://en.wikipedia.org/wiki/Guitar_Hero),
[iFP](https://www.cs.tufts.edu/~jacob/250aui/ifp-performance-template.pdf), [Piano Genie](https://imaginary.github.io/piano-genie/), [Virtual Conductor](https://www.youtube.com/watch?v=fEXOWFmA8KA&t=2s&ab_channel=HausderMusik)_, and many others.

I want to take this further and create an "air piano", where an intelligent system helps pianists of all skill levels
express their interpretations of musical compositions. 

As early as in the 1970s, Max Matthews came up with the idea of "radio baton". Since the pitch information is explicitly
encoded in most musical scores, one can ask computers to memorize it, leaving the performer to focus on controlling the
rhythm, speed, volume, pattern, and timbre of the sound.

With recent advancements in artificial intelligence, I am motivated to dream bigger. Instead of having users to
manipulate all the expressive parameters at once, which can be overwhelming, why not have AI infer the appropriate
expressive parameters from the main contour that users provide?

## Musical Rationale

Have you ever felt that you have so much to express, but your piano technique holds you back from fully realizing it?
Well, this is a challenge even for world-renowned pianists. Experienced pianists still struggle with challenging, yet
breathtakingly beautiful pieces. Some may possess extraordinary musicality but lack the early childhood training that
builds perfect technique, while others may suffer from conditions like severe tendinitis or aging. Unexpected events can
also make it physically difficult to express oneself fully through music.

For less experienced pianists, much of their practice time is probably spent focusing on correcting mistakes, which
often requires hundreds of hours to eliminate wrong notes. During performance, their attention can be consumed by simply
playing the right notes, leaving little room to express their true artistic intentions. I also believe that too much
effort is spent on mastering the technical aspects of this difficult instrument. While technique is essential for
realizing our expressive goals, the ultimate aim of a musical performance should be to communicate emotion and connect
with others.

My goal is to lower the technical barriers to piano playing, allowing both amateurs and professionals to focus more on
artistic expression. By doing so, we can foster deeper connections between individuals and cultivate a culture of
understanding through music.

## Technical Rationale

Modeling expressiveness in piano performance is a topic that has received growing attention from scholars, such as
[[1]](https://magenta.tensorflow.org/performance-rnn),
[[2]](https://archives.ismir.net/ismir2019/paper/000112.pdf),
[[3]](https://archives.ismir.net/ismir2019/paper/000105.pdf),
[[4]](https://arxiv.org/abs/2208.14867),
[[5]](https://arxiv.org/pdf/2306.06040),
[[6]](https://archives.ismir.net/ismir2023/paper/000069.pdf)
[[7]](https://arxiv.org/pdf/2406.14850)

Interestingly, however, most research in the area of controllable expressive performance generation has used "mid-level
perceptual features"[6] (articulation, performance style, dynamic) as input, rather than directly conditioning on
incomplete performances created by humans. There are several reasons for investigating conditioning on incomplete human
performances. First, it "permits" users to directly control the timing, articulation, pitch, and timbre of individual
notes in the performance, allowing for much more intimacy and fine-grained control. This level of intimacy and control
is essential for building real-time piano conducting systems with minimal loss in artistic control and a sense of
ownership/autonomy. Additionally, by closely conditioning on the users' performance, deep learning models may better
understand what the user wants, as it is difficult to accurately describe one's expressive intentions without
demonstrating them on the keyboard. Thirdly, evidences shows that this approach is highly feasible. For example,
pianists often utilize common performance strategies, such as shaping according to the main melody line and lowering the
volume of accompanying passages. Signs of success have been demonstrated in the
[Masked Expressiveness](https://github.com/bmoist/maskedExpressiveness/) project. By learning the strategies, deep
learning models have the potential to make educated guesses about the user's expressive intentions, although it could
still benefit from incorporating additional information, such as rehearsal data and other mid-level perceptual features.
Moreover, once the model has learned these common patterns in performance, it may also help us understand how pianists
organize and realize their expressive intentions.

---

People may have a vision of how their performances should sound, but is spending countless hours practicing every day
for each new piece the only way to bring that vision to life?

Is it possible to play the piano anywhere, anytime, without compromising the joy and artistry of the performance?

Can technology and machine learning serve as wings for human imagination and expression?

## Notice:

I am looking for collaborators! If you are interested, please reach out to me! Contact information can be found on my
[personal website](https://lynnzye.github.io).

# Reference

[1] Sageev Oore, Ian Simon, Sander Dieleman, Douglas Eck, and Karen Simonyan. 2020. This time with feeling: Learning
expressive musical performance. Neural Computing and Applications 32, (2020), 955–967.

[2] Dasaem Jeong, Taegyun Kwon, Yoojin Kim, Kyogu Lee, and Juhan Nam. 2019. VirtuosoNet: A Hierarchical RNN-based System
for
Modeling Expressive Piano Performance. In International Society for Music Information Retrieval Conference. Retrieved
from
https://api.semanticscholar.org/CorpusID:208334424

[3] Akira Maezawa, Kazuhiko Yamamoto, and Takuya Fujishima. 2019. Rendering Music Performance With Interpretation
Variations Using Conditional Variational RNN. In International Society for Music Information Retrieval Conference.
Retrieved from https://api.semanticscholar.org/CorpusID:208334557

[4] Seungyeon Rhyu, Sarah Kim, and Kyogu Lee. 2022. Sketching the Expression: Flexible Rendering of Expressive Piano
Performance with Self-Supervised Learning. Retrieved from https://arxiv.org/abs/2208.14867

[5] Jingjing Tang, Geraint Wiggins, and Gyorgy Fazekas. 2023. Reconstructing Human Expressiveness in Piano Performances
with a Transformer Network. Retrieved from https://arxiv.org/abs/2306.06040

[6] Ilya Borovik and Vladimir Viro. 2023. ScorePerformer: Expressive Piano Performance Rendering with Fine-Grained
Control. In Proceedings of the 24th International Society for Music Information Retrieval Conference (ISMIR). Retrieved
from https://archives.ismir.net/ismir2023/paper/000069.pdf

[7] Huan Zhang, Shreyan Chowdhury, Carlos Eduardo Cancino-Chacón, Jinhua Liang, Simon Dixon, and Gerhard Widmer. 2024.
DExter: Learning and Controlling Performance Expression with Diffusion Models. Retrieved
from https://arxiv.org/abs/2406.14850


