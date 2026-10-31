class OmiliaError(Exception):
    pass

class DatasetNotFoundError(OmiliaError):
    pass

class JSONDatasetError(OmiliaError):
    pass

class IncorrectDataError(OmiliaError):
    pass
