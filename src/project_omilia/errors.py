class OmiliaError(Exception):
    pass

class DatasetNotFoundError(OmiliaError):
    pass

class IncorrectDataError(OmiliaError):
    pass
