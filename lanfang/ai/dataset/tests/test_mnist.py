from lanfang.ai.dataset import mnist
from lanfang.ai.engine import names

import unittest
import os
import tensorflow as tf


class TestMnist(unittest.TestCase):
  def setUp(self):
    self._m_mnist = mnist.Mnist()

  def tearDown(self):
    pass

  def test_get_params(self):
    self.assertEqual(len(self._m_mnist.get_params()), 4);

  def test_artifacts(self):
    self.assertEqual(self._m_mnist.artifacts(), {})

  def test_preparse(self):
    save_dir = self._m_mnist.prepare()
    mnist_files = [
      "t10k-images-idx3-ubyte.gz",
      "train-images-idx3-ubyte.gz",
      "t10k-labels-idx1-ubyte.gz",
      "train-labels-idx1-ubyte.gz"
    ]
    for fname in mnist_files:
      self.assertTrue(os.path.isfile(os.path.join(save_dir, fname)))

  def test_get_padding(self):
    self.assertIsNone(self._m_mnist.get_padding())

  def test_read_parse(self):
    train_data = self._m_mnist.read(
        names.DataSplit.TRAIN,
        tf.estimator.ModeKeys.TRAIN)
    for i, (image, label) in enumerate(train_data):
      if i >= 10:
        break
      self.assertEqual(image.shape, (28, 28, 1))
      self.assertEqual(label.shape, ())
      self.assertEqual(image.dtype, tf.uint8)
      self.assertEqual(label.dtype, tf.uint8)
      features, labels = self._m_mnist.parse(
          tf.estimator.ModeKeys.TRAIN, image, label)
      parse_image = features[names.Image.IMAGE]
      parse_label = labels[names.Classification.LABEL]
      self.assertEqual(parse_image.shape, (28, 28, 1))
      self.assertEqual(parse_label.shape, ())
      self.assertEqual(parse_image.dtype, tf.float32)
      self.assertEqual(parse_label.dtype, tf.int32)

