class ImageToolError(Exception):
    """Base class of all errors in this package."""


class ConfigError(ImageToolError):
    """A setting is missing or a value is invalid."""


class OptionError(ImageToolError, ValueError):
    """An unknown format, size, quality, style, task or language, or an empty prompt."""


class InputError(ImageToolError):
    """The input image is missing, empty, too large or not a PNG or JPG."""


class ModelError(ImageToolError):
    """The model server did not answer, or the answer was unusable."""
