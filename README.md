# PiCo

AKA: Piano Conductor





## Background

The ideas of "air instruments" (e.g. air guitar) and conducting systems are not new. Many projects have explored this
idea, such as _Guitar Hero, Piano Genie, Radio Baton_, and others.

I want to take this further and create an "air piano". I envision a future where the technical challenges of piano
playing becomes less of a barrier for both amateurs and professionals to express their interpretations of musical
compositions.

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
[[2]](https://archives.ismir.net/ismir2019/paper/000105.pdf),
[[3]](https://arxiv.org/abs/2208.14867),
[[4]](https://arxiv.org/pdf/2306.06040),
[[5]](https://archives.ismir.net/ismir2023/paper/000069.pdf)
[[6]](https://arxiv.org/pdf/2406.14850)

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

I am looking for collaborators! If you are interested, please reach out to me!

# Reference

[1] Sageev Oore, Ian Simon, Sander Dieleman, Douglas Eck, and Karen Simonyan. 2020. This time with feeling: Learning
expressive musical performance. Neural Computing and Applications 32, (2020), 955–967.
[2] Akira Maezawa, Kazuhiko Yamamoto, and Takuya Fujishima. 2019. Rendering Music Performance With Interpretation
Variations Using Conditional Variational RNN. In International Society for Music Information Retrieval Conference.
Retrieved from https://api.semanticscholar.org/CorpusID:208334557
[3] Seungyeon Rhyu, Sarah Kim, and Kyogu Lee. 2022. Sketching the Expression: Flexible Rendering of Expressive Piano
Performance with Self-Supervised Learning. Retrieved from https://arxiv.org/abs/2208.14867
[4] Jingjing Tang, Geraint Wiggins, and Gyorgy Fazekas. 2023. Reconstructing Human Expressiveness in Piano Performances
with a Transformer Network. Retrieved from https://arxiv.org/abs/2306.06040
[5] Ilya Borovik and Vladimir Viro. 2023. ScorePerformer: Expressive Piano Performance Rendering with Fine-Grained
Control. In Proceedings of the 24th International Society for Music Information Retrieval Conference (ISMIR). Retrieved
from https://archives.ismir.net/ismir2023/paper/000069.pdf
[6] Huan Zhang, Shreyan Chowdhury, Carlos Eduardo Cancino-Chacón, Jinhua Liang, Simon Dixon, and Gerhard Widmer. 2024.
DExter: Learning and Controlling Performance Expression with Diffusion Models. Retrieved
from https://arxiv.org/abs/2406.14850


