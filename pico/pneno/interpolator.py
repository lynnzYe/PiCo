import os.path

from pico.logger import logger

from abc import abstractmethod
from scipy import stats
import pickle

from pico.util.midi_util import seconds_to_ticks

# Because there are no notes before the first pitch, it does not have an IOI. This is a placeholder
# 1 to prevent zero division, also serves as the scaling factor: 1.0
IOI_PLACEHOLDER = 1


class SpeedInterpolator:
    @abstractmethod
    def load_score(self, score):
        pass

    @abstractmethod
    def interpolate(self, curr_ioi):
        pass

    @abstractmethod
    def __repr__(self):
        return "SpeedInterpolator()"


class DMYSpeedInterpolator(SpeedInterpolator):
    def load_score(self, score=None):
        pass

    def interpolate(self, curr_ioi=None):
        return 1.0

    def __repr__(self):
        return "DMYSpeedInterpolator()"


class IFPSpeedInterpolator(SpeedInterpolator):
    """
    Reference: https://www.cs.tufts.edu/~jacob/250aui/ifp-performance-template.pdf

    This class mainly works with inter-onset intervals (IOI) and its ratios.
    """

    def __init__(self, wh=.8, wp=.3, wt=.6, window_size=5,
                 score_ioi: list[float] = None, template_ioi: list[float] = None):
        """
        :param wh: how stable the predicted tempo will be
        :param wp: how responsive
        :param wt: how much influence from the template
        :param window_size:
        :param score_ioi:  first element should always be 1 as a placeholder for the first tempo prediction
        :param template_ioi:    first element should always be 1 as a placeholder for the first tempo prediction
        """
        self.wh = wh
        self.wp = wp
        self.wt = wt
        self.w_size = window_size
        self.score_ioi_list = []  # the first element is the ioi between note[0] and note[1]
        self.user_bpm_history = []  # as ratio
        self.pred_bpm_history = []  # as ratio (store predicted bpm for future reference)
        self.tplt_bpm_history = []  # borrowing the term "performance template" from the iFP paper
        if score_ioi is not None:
            assert 0 not in score_ioi and score_ioi[0] == IOI_PLACEHOLDER
            self.score_ioi_list = score_ioi
        if template_ioi is not None:
            self.load_template(score_ioi, template_ioi) and template_ioi[0] == IOI_PLACEHOLDER
        self.cursor = 0

    def __repr__(self):
        return (f"IFPSpeedInterpolator(wh={self.wh}, wp={self.wp}, wt={self.wt}, "
                f"window_size={self.w_size}, ..)")

    def interpolate(self, curr_ioi):
        """
        Ideal case: interpolate based on the following IOI
        P1 - P2 - P3 - P4
           a    b    c
        Use `a` to predict P1's bpm.

        However, during demo, `a` can only be known after P2 is performed.

        Therefore, we will have 2 modes of interpolation:
        1. real-time prediction
            - used past bpm as current bpm -> which of course does not work quite well.
        2. template-based prediction
            - use template bpm as current bpm

        use a' to predict P2's speed
        [a, b, c]
        :param curr_ioi:
        :return:
        """
        if not self.score_ioi_list:
            logger.warn("IOI list is empty! cannot interpolate properly.")
            return 1.0
        if self.cursor == len(self.score_ioi_list) - 1:
            # TODO @Bmois: Because there are no subsequent notes to compute IOI, use the last performed BPM to predict
            return self.user_bpm_history[-1]
        if self.cursor >= len(self.score_ioi_list):
            logger.warn("IOI cursor exceeds list len! This is a bug.")
            return 1.0
        curr_bpm = self.score_ioi_list[self.cursor] / curr_ioi  # bpm should be inversely proportionate to IOI
        if self.cursor == 0 and self.tplt_bpm_history:
            curr_bpm = self.tplt_bpm_history[0]

        bpm__1 = self.user_bpm_history[-1] if len(self.user_bpm_history) >= 1 else 1.0
        bpm__2 = self.user_bpm_history[-2] if len(self.user_bpm_history) >= 2 else 1.0
        tplt_bpm = self.tplt_bpm_history[self.cursor + 1] if self.tplt_bpm_history else 1.0
        sum_size = min(len(self.user_bpm_history), self.w_size) if self.user_bpm_history else 1
        bpm_sum = sum(self.user_bpm_history[-sum_size:]) if self.user_bpm_history else 1
        avg_bpm = bpm_sum / sum_size

        pred_bpm_ratio = ((self.wt * tplt_bpm + self.wh * avg_bpm)
                          * 1 / (self.wt + self.wh) * (bpm__1 / bpm__2) ** self.wp)
        self.user_bpm_history.append(curr_bpm)
        self.pred_bpm_history.append(pred_bpm_ratio)
        self.cursor += 1
        logger.debug("current bpm:", curr_bpm)
        logger.debug("bpm history:", self.user_bpm_history)
        logger.debug("predicted bpm:", pred_bpm_ratio)
        return 1 / pred_bpm_ratio  # Ratio to be multiplied with onsets

    def load_score(self, score_ioi_list: list[float]):
        assert 0 not in score_ioi_list and score_ioi_list[0] == IOI_PLACEHOLDER
        if self.tplt_bpm_history:
            assert len(self.tplt_bpm_history) == len(score_ioi_list)
        self.score_ioi_list = score_ioi_list

    def load_template(self, score_ioi_list, template_ioi):
        if template_ioi is None or score_ioi_list is None:
            logger.warn("Require both score ioi and template ioi to load template")
            return
        self.load_score(score_ioi_list)
        assert 0 not in template_ioi and template_ioi[0] == IOI_PLACEHOLDER
        tplt_bpm_history = []
        for i, e in enumerate(template_ioi):
            tplt_bpm_history.append(self.score_ioi_list[i] / e)  # Bpm is inversely proportionate to IOI
        self.tplt_bpm_history = tplt_bpm_history

    def is_end(self):
        return self.cursor == len(self.score_ioi_list)


def parse_ifp_performance_ioi(perf_file):
    """
    :param perf_file:  perf_data.pkl
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
    perf_seq = data['performance']

    # Parse score IOI & performed IOI
    time_list = []
    score_ioi_list = []
    curr_tick = perf_seq[0][2].onset
    for e in perf_seq:
        if e[1].type == 'note_on':
            time_list.append(e[0])
            score_ioi_list.append(e[2].onset - curr_tick)
            curr_tick = e[2].onset
    score_ioi_list[0] = IOI_PLACEHOLDER  # For IFP
    curr_onset = time_list[0]
    tplt_ioi_list = [IOI_PLACEHOLDER]
    for i in range(1, len(time_list)):
        tplt_ioi_list.append(
            seconds_to_ticks(seconds=time_list[i] - curr_onset, tempo=tempo, ticks_per_beat=ticks_per_beat))
        curr_onset = time_list[i]
    return score_ioi_list, tplt_ioi_list


class VelocityInterpolator:
    @abstractmethod
    def interpolate(self, curr_vel):
        pass

    @abstractmethod
    def __repr__(self):
        pass


class DMAVelocityInterpolator(VelocityInterpolator):
    """Decaying Moving Average Interpolator"""

    def __init__(self, alpha=0.5, decay=0.8):
        self.alpha = alpha
        self.decay = decay
        self._past_vel = None

    def __repr__(self):
        return f"DMAVelocityInterpolator(alpha={self.alpha}, decay={self.decay}, .."

    def interpolate(self, curr_vel):
        if self._past_vel is None:
            self._past_vel = curr_vel * self.decay
            return int(self._past_vel)
        else:
            max_ret = self.decay * curr_vel
            return int(
                min(
                    self.alpha * self.decay * self._past_vel + (1 - self.alpha) * min(max_ret, self._past_vel),
                    max_ret
                )
            )


def main():
    # score_ioi = [20, 10, 10, 20, 20]
    # performed_ioi = [25, 15, 15, 18, 18]
    # ifp = IFPSpeedInterpolator(score_ioi_list=score_ioi, template_ioi=performed_ioi)

    midi_path = '/Users/kurono/Desktop/pneno_demo.mid'
    perf_data = '/Users/kurono/Desktop/perf_data.pkl'
    score_ioi, template_ioi = parse_ifp_performance_ioi(perf_data)
    # print(score_ioi)
    # print(template_ioi)

    ifp = IFPSpeedInterpolator(score_ioi=score_ioi, template_ioi=template_ioi)
    # ifp.load_template(template_ioi)

    for e in template_ioi:
        ifp.interpolate(e)
    print("Simple Scoring! how on-time did you play? What are your weak spots?")
    print(f'{sum(ifp.user_bpm_history) / len(ifp.user_bpm_history) * 100:.2f}%')
    print('Raw data:', ifp.user_bpm_history)


if __name__ == '__main__':
    main()
