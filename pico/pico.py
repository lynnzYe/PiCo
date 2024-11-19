from abc import abstractmethod


class PiCo:
    @abstractmethod
    def load_score(self, score):
        pass

    @abstractmethod
    def listen(self):
        pass

    @abstractmethod
    def start_realtime_capture(self):
        pass

    @abstractmethod
    def stop(self):
        pass
