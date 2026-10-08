class GeometryError(ValueError):
    code = "INVALID_GEOMETRY"
    status_code = 422

    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details or {}


class VersionConflict(GeometryError):
    code = "SCENE_VERSION_CONFLICT"
    status_code = 409


class InvalidFrame(GeometryError):
    code = "FRAME_VALIDATION_FAILED"

    def __init__(self, message, frame):
        super().__init__(message)
        self.frame = frame
