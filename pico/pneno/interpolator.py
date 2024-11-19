from sympy import numer

from pico.pneno.pneno_seq import PnenoSeq
from pico.logger import logger


class DMYSpeedInterpolator:
    def interpolate(self):
        return 1.0


class IFPSpeedInterpolator:
    """
    Reference: https://www.cs.tufts.edu/~jacob/250aui/ifp-performance-template.pdf
    """

    def __init__(self, wh=1.0, wp=.25, wt=.5, window_size=5, note_seq: PnenoSeq = None):
        self.wh = wh
        self.wp = wp
        self.wt = wt
        self.w_size = window_size
        self.ioi_list = []
        self.bpm_ratio_history = [1.0]
        if note_seq is not None:
            self.build_ioi_list(note_seq)
        self.cursor = 1

    def interpolate_current_speed(self, curr_ioi):
        if not self.ioi_list:
            logger.warn("IOI list is empty! cannot interpolate properly.")
            return 1.0
        if self.cursor >= len(self.ioi_list):
            logger.warn("IOI cursor exceeds list len! This is a bug.")
            return 1.0
        input_ioi_ratio = curr_ioi / self.ioi_list[self.cursor]

        bpm__1 = self.bpm_ratio_history[-1] if len(self.bpm_ratio_history) == 1 else 1.0
        bpm__2 = self.bpm_ratio_history[-2] if len(self.bpm_ratio_history) == 2 else 1.0
        sum_size = min(len(self.bpm_ratio_history), self.w_size)

        bpm_ratio = ((self.wt * input_ioi_ratio + self.wh * (
                1 / sum_size * sum(self.bpm_ratio_history[-sum_size:])))
                     * 1 / (self.wt + self.wh) * (bpm__1 / bpm__2) ** self.wp)
        self.bpm_ratio_history.append(bpm_ratio)
        self.cursor += 1
        return bpm_ratio

    def is_end(self):
        return self.cursor == len(self.ioi_list)

    def build_ioi_list(self, note_seq: PnenoSeq):
        """
        Build tempo for
        :param note_seq:
        :return:
        """
        self.ioi_list = []
        curr_onset = note_seq.seq[0].onset
        for i, e in enumerate(note_seq.seq):
            self.ioi_list.append(e.onset - curr_onset)
            curr_onset = e.onset

    def load_ioi_list(self, ioi_list: list[float]):
        self.ioi_list = ioi_list


class DMAVelocityInterpolator:
    """Decaying Moving Average Interpolator"""

    def __init__(self, alpha=0.5, decay=0.8):
        self.alpha = alpha
        self.decay = decay
        self._past_vel = None

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
