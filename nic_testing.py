from unittest.mock import Mock

class PickableMock(Mock):
    def __reduce__(self):
        return (Mock, ())

def set_up_mock_from_object(obj):
    mock_object = PickableMock()
    for prop in dir(obj):
        if prop[0] != '_':
            mock_object.__dict__[prop] = obj.__getattribute__(prop)

    # make sure str() usage matches that of the original object
    mock_object.__str__ = PickableMock()
    mock_object.__str__.return_value = str(obj)
    return mock_object


