"""
Personal code for daily use.
============================
"""
import re
import warnings

# Make sure that DeprecationWarning within this package always gets printed
warnings.filterwarnings('always', category=DeprecationWarning,
                        module=r'^{0}\.'.format(re.escape(__name__)))

__version__ = "0.1.2dev"


from . import utils
from . import runner
from . import network
from . import mlutils

__all__ = ["utils", "runner", "network", "mlutils"]

#from . import datasets
#
#try:
#    from . import models
#    __all__ = ["datasets", "runner"]
#
#except Exception as e:
#    __all__ = ["models", "datasets", "runner"]
