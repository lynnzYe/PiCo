import music21


class Score:
    score = None

    def __init__(self, xml_path):
        self.score = music21.converter.parseFile(xml_path)


def main():
    """
    Toy example usage of class Score
    :return:
    """
    score = Score("data/Schubert899.mxl")
    print("it is stream?", score.score.isStream)


if __name__ == '__main__':
    main()
