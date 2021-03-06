from lanfang.ai.engine import names
from lanfang.ai import utils
from lanfang.ai.engine.dataset import Dataset
from lanfang.ai.engine.model import Model
from lanfang.ai.engine.model import KerasModel
from lanfang.ai.engine.oracle import BaseOracle
from lanfang.ai.engine.oracle import KerasOracle
from lanfang.ai import dataset
from lanfang.ai import model

from lanfang.utils import func as _func

import inspect as _inspect


for dataset_class in _func.subclasses(Dataset):
  if _inspect.isabstract(dataset_class):
    continue
  Dataset.register(dataset_class)

for model_class in _func.subclasses(KerasModel):
  if _inspect.isabstract(model_class):
    continue
  Model.register(model_class)


__all__ = [_s for _s in dir() if not _s.startswith('_')]
