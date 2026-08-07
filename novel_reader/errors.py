class NovelReaderError(Exception):
    """Erro esperado e apresentável ao usuário."""


class UnsupportedSourceError(NovelReaderError):
    pass


class DownloadError(NovelReaderError):
    pass


class ParseError(NovelReaderError):
    pass


class AccessRestrictedError(NovelReaderError):
    pass
