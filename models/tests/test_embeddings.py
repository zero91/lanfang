from __future__ import division
from __future__ import print_function
from __future__ import absolute_import
import unittest
import logging
import tempfile
import os
import numpy as np
from jpyutils.models import Embeddings
from jpyutils import utils

class TestEmbeddings(unittest.TestCase):
    def setUp(self):
        self.__embeddings = Embeddings()

    def test_load(self):
        utils.utilities.get_logger()
        with self.assertRaises(ValueError):
            self.__embeddings.load("test", 300)
        word2id, word_embeddings = self.__embeddings.load("glove.6B", 50)
        self.assertEqual(word_embeddings.shape[0], len(word2id))
        self.assertEqual(word_embeddings.shape[1], 50)

        word2id, word_embeddings = self.__embeddings.load("glove.6B", 50, id_shift=3)
        self.assertEqual(word_embeddings.shape[0], len(word2id) + 3)
        self.assertEqual(word_embeddings.shape[1], 50)

    def test_generate(self):
        random_embeddings = self.__embeddings.generate((3, 50))
        self.assertEqual(random_embeddings.shape, (3, 50))
        norm = np.linalg.norm(random_embeddings, axis=1)
        self.assertEqual(norm.shape, (3,))
        for elem in norm:
            self.assertAlmostEqual(elem, 1.0)

    def tearDown(self):
        pass

if __name__ == "__main__":
    unittest.main()
