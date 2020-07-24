#  Copyright (c) 2019-2020, RTE (https://www.rte-france.com)
#  See AUTHORS.txt
#  This Source Code Form is subject to the terms of the Apache License, version 2.0.
#  If a copy of the Apache License, version 2.0 was not distributed with this file, you can obtain one at http://www.apache.org/licenses/LICENSE-2.0.
#  SPDX-License-Identifier: Apache-2.0
#  This file is part of hadar-simulator, a python adequacy library for everyone.

import unittest

import numpy as np
import pandas as pd

from hadar.analyzer.result import Index, ResultAnalyzer, IntIndex
from hadar.optimizer.input import Production, Consumption, Study
from hadar.optimizer.output import OutputConsumption, OutputLink, OutputNode, OutputProduction, Result, OutputNetwork, \
    OutputStorage


class TestIndex(unittest.TestCase):

    def test_no_parameters(self):
        self.assertEqual(True, Index(column='i').all)

    def test_on_element(self):
        i = Index(column='i', index='fr')
        self.assertEqual(False, i.all)
        self.assertEqual(('fr',), i.index)

    def test_list_1(self):
        i = Index(column='i', index=['fr', 'be'])
        self.assertEqual(False, i.all)
        self.assertEqual(('fr', 'be'), i.index)

    def test_list_2(self):
        l = ['fr', 'be']
        i = Index(column='i', index=l)
        self.assertEqual(False, i.all)
        self.assertEqual(('fr', 'be'), i.index)

    def test_filter(self):
        i = Index(column='i', index=['fr', 'be'])
        df = pd.DataFrame(data={'i': ['it', 'fr', 'fr', 'be', 'de', 'it', 'be'],
                                'a': [0, 1, 2, 3, 4, 5, 6]})

        exp = pd.Series(data=[False, True, True, True, False, False, True], index=[0, 1, 2, 3, 4, 5, 6], name='i')

        pd.testing.assert_series_equal(exp, i.filter(df))


class TestIntIndex(unittest.TestCase):

    def test_range(self):
        i = IntIndex('i', index=slice(2, 6))
        self.assertEqual(False, i.all)
        self.assertEqual((2, 3, 4, 5), i.index)

    def test_list(self):
        i = IntIndex('i', index=[2, 6])
        self.assertEqual(False, i.all)
        self.assertEqual((2, 6), i.index)


class TestAnalyzer(unittest.TestCase):
    def setUp(self) -> None:
        self.study = Study(horizon=3, nb_scn=2)\
            .network()\
                .node('a')\
                    .consumption(cost=10 ** 3, quantity=[[120, 12, 12], [12, 120, 120]], name='load')\
                    .consumption(cost=10 ** 3, quantity=[[130, 13, 13], [13, 130, 130]], name='car')\
                    .production(cost=10, quantity=[[130, 13, 13], [13, 130, 130]], name='prod')\
                .node('b')\
                    .consumption(cost=10 ** 3, quantity=[[120, 12, 12], [12, 120, 120]], name='load')\
                    .production(cost=20, quantity=[[110, 11, 11], [11, 110, 110]], name='prod')\
                    .production(cost=20, quantity=[[120, 12, 12], [12, 120, 120]], name='nuclear') \
                    .storage(name='store', capacity=100, flow_in=10, flow_out=20,
                             cost_in=[[10, 1, 1], [1, 10, 10]], cost_out=[[20, 2, 2], [2, 20, 20]]) \
                .node('c')\
                .link(src='a', dest='b', quantity=[[110, 11, 11], [11, 110, 110]], cost=2)\
                .link(src='a', dest='c', quantity=[[120, 12, 12], [12, 120, 120]], cost=2)\
            .build()

        out = {
            'a': OutputNode(consumptions=[OutputConsumption(cost=np.ones((2, 3)) * 10 ** 3, quantity=[[20, 2, 2], [2, 20, 20]], name='load'),
                                          OutputConsumption(cost=np.ones((2, 3)) * 10 ** 3, quantity=[[30, 3, 3], [3, 30, 30]], name='car')],
                            productions=[OutputProduction(cost=np.ones((2, 3)) * 10, quantity=[[30, 3, 3], [3, 30, 30]], name='prod')],
                            storages=[],
                            links=[OutputLink(dest='b', quantity=[[10, 1, 1], [1, 10, 10]], cost=np.ones((2, 3)) * 2),
                                   OutputLink(dest='c', quantity=[[20, 2, 2], [2, 20, 20]], cost=np.ones((2, 3)) * 2)]),

            'b': OutputNode(consumptions=[OutputConsumption(cost=np.ones((2, 3)) * 10 ** 3, quantity=[[20, 2, 2], [2, 20, 20]], name='load')],
                            productions=[OutputProduction(cost=np.ones((2, 3)) * 20, quantity=[[10, 1, 1], [1, 10, 10]], name='prod'),
                                         OutputProduction(cost=np.ones((2, 3)) * 20, quantity=[[20, 2, 2], [2, 20, 20]], name='nuclear')],
                            storages=[OutputStorage(name='store', capacity=[[10, 1, 1], [1, 10, 10]],
                                                    flow_out=[[20, 2, 2], [2, 20, 20]],
                                                    flow_in=[[30, 3, 3], [3, 30, 30]])],
                            links=[])
        }

        self.result = Result(networks={'default': OutputNetwork(nodes=out)})

    def test_build_consumption(self):
        # Expected
        exp = pd.DataFrame(data={'cost': [10 ** 3] * 18,
                                 'asked': [120, 12, 12, 12, 120, 120, 130, 13, 13, 13, 130, 130, 120, 12, 12, 12, 120, 120],
                                 'given': [20, 2, 2, 2, 20, 20, 30, 3, 3, 3, 30, 30, 20, 2, 2, 2, 20, 20],
                                 'name': ['load'] * 6 + ['car'] * 6 + ['load'] * 6,
                                 'node': ['a'] * 12 + ['b'] * 6,
                                 'network': ['default'] * 18,
                                 't':   [0, 1, 2] * 6,
                                 'scn': [0, 0, 0, 1, 1, 1] * 3}, dtype=float)

        cons = ResultAnalyzer._build_consumption(self.study, self.result)

        pd.testing.assert_frame_equal(exp, cons)

    def test_build_production(self):
        # Expected
        exp = pd.DataFrame(data={'cost': [10] * 6 + [20] * 12,
                                 'avail': [130, 13, 13, 13, 130, 130, 110, 11, 11, 11, 110, 110, 120, 12, 12, 12, 120, 120],
                                 'used': [30, 3, 3, 3, 30, 30, 10, 1, 1, 1, 10, 10, 20, 2, 2, 2, 20, 20],
                                 'name': ['prod'] * 12 + ['nuclear'] * 6,
                                 'node': ['a'] * 6 + ['b'] * 12,
                                 'network': ['default'] * 18,
                                 't':   [0, 1, 2] * 6,
                                 'scn': [0, 0, 0, 1, 1, 1] * 3}, dtype=float)

        prod = ResultAnalyzer._build_production(self.study, self.result)

        pd.testing.assert_frame_equal(exp, prod)

    def test_build_storage(self):
        # Expected
        exp = pd.DataFrame(data={'max_capacity': [100] * 6,
                                 'capacity': [10, 1, 1, 1, 10, 10],
                                 'max_flow_in': [10] * 6,
                                 'flow_in': [30, 3, 3, 3, 30, 30],
                                 'max_flow_out': [20] * 6,
                                 'flow_out': [20, 2, 2, 2, 20, 20],
                                 'cost_in': [10, 1, 1, 1, 10, 10],
                                 'cost_out': [20, 2, 2, 2, 20, 20],
                                 'init_capacity': [0] * 6,
                                 'eff': [1] * 6,
                                 'name': ['store'] * 6,
                                 'node': ['b'] * 6,
                                 'network': ['default'] * 6,
                                 't': [0, 1, 2] * 2,
                                 'scn': [0, 0, 0, 1, 1, 1]}, dtype=float)

        stor = ResultAnalyzer._build_storage(self.study, self.result)
        pd.testing.assert_frame_equal(exp, stor, check_dtype=False)

    def test_build_link(self):
        # Expected
        exp = pd.DataFrame(data={'cost': [2] * 12,
                                 'avail': [110, 11, 11, 11, 110, 110, 120, 12, 12, 12, 120, 120],
                                 'used': [10, 1, 1, 1, 10, 10, 20, 2, 2, 2, 20, 20],
                                 'node': ['a'] * 12,
                                 'dest': ['b'] * 6 + ['c'] * 6,
                                 'network': ['default'] * 12,
                                 't':   [0, 1, 2] * 4,
                                 'scn': [0, 0, 0, 1, 1, 1] * 2}, dtype=float)

        link = ResultAnalyzer._build_link(self.study, self.result)

        pd.testing.assert_frame_equal(exp, link)

    def test_aggregate_cons(self):
        # Expected
        index = pd.Index(data=[0, 1, 2], dtype=float, name='t')
        exp_cons = pd.DataFrame(data={'asked': [120, 12, 12],
                                      'cost': [10 ** 3] * 3,
                                      'given': [20, 2, 2]}, dtype=float, index=index)

        # Test
        agg = ResultAnalyzer(study=self.study, result=self.result)
        cons = agg.network().scn(0).node('a').consumption('load').time()

        pd.testing.assert_frame_equal(exp_cons, cons)

    def test_aggregate_prod(self):
        # Expected
        index = pd.MultiIndex.from_tuples((('a', 'prod', 0.0), ('a', 'prod', 1.0), ('a', 'prod', 2,0),
                                           ('b', 'prod', 0.0), ('b', 'prod', 1.0), ('b', 'prod', 2,0)),
                                          names=['node', 'name', 't'], )
        exp_cons = pd.DataFrame(data={'avail': [130, 13, 13, 110, 11, 11],
                                      'cost': [10, 10, 10, 20, 20, 20],
                                      'used': [30, 3, 3, 10, 1, 1]}, dtype=float, index=index)

        # Test
        agg = ResultAnalyzer(study=self.study, result=self.result)
        cons = agg.network().scn(0).node(['a', 'b']).production('prod').time()

        pd.testing.assert_frame_equal(exp_cons, cons)

    def test_aggregate_stor(self):
        # Expected
        index = pd.MultiIndex.from_tuples((('b', 'store', 0), ('b', 'store', 1), ('b', 'store', 2)),
                                          names=['node', 'name', 't'], )
        exp_stor = pd.DataFrame(data={'capacity': [10, 1, 1],
                                      'cost_in': [10, 1, 1],
                                      'cost_out': [20, 2, 2],
                                      'eff': [1] * 3,
                                      'flow_in': [30, 3, 3],
                                      'flow_out': [20, 2, 2],
                                      'init_capacity': [0] * 3,
                                      'max_capacity': [100] * 3,
                                      'max_flow_in': [10] * 3,
                                      'max_flow_out': [20] * 3}, index=index)

        # Test
        agg = ResultAnalyzer(study=self.study, result=self.result)
        stor = agg.network().scn(0).node().storage('store').time()
        pd.testing.assert_frame_equal(exp_stor, stor, check_dtype=False)

    def test_aggregate_link(self):
        # Expected
        index = pd.MultiIndex.from_tuples((('b', 0.0), ('b', 1.0), ('b', 2,0),
                                           ('c', 0.0), ('c', 1.0), ('c', 2,0)),
                                          names=['dest', 't'], )
        exp_cons = pd.DataFrame(data={'avail': [110, 11, 11, 120, 12, 12],
                                      'cost': [2, 2, 2, 2, 2, 2],
                                      'used': [10, 1, 1, 20, 2, 2]}, dtype=float, index=index)

        agg = ResultAnalyzer(study=self.study, result=self.result)
        cons = agg.network().scn(0).node('a').link(['b', 'c']).time()

        pd.testing.assert_frame_equal(exp_cons, cons)

    def test_get_elements_inside(self):
        agg = ResultAnalyzer(study=self.study, result=self.result)
        self.assertEqual((2, 1, 0, 2), agg.get_elements_inside('a'))
        self.assertEqual((1, 2, 1, 0), agg.get_elements_inside('b'))

    def test_balance(self):
        agg = ResultAnalyzer(study=self.study, result=self.result)
        np.testing.assert_array_equal([[30, 3, 3], [3, 30, 30]], agg.get_balance(node='a'))
        np.testing.assert_array_equal([[-10, -1, -1], [-1, -10, -10]], agg.get_balance(node='b'))

    def test_cost(self):
        agg = ResultAnalyzer(study=self.study, result=self.result)
        np.testing.assert_array_equal([[200360, 20036, 20036], [20036, 200360, 200360]], agg.get_cost(node='a'))
        np.testing.assert_array_equal([[101300, 10067, 10067], [10067, 101300, 101300]], agg.get_cost(node='b'))

    def test_rac(self):
        agg = ResultAnalyzer(study=self.study, result=self.result)
        np.testing.assert_array_equal([[0, 0, 0], [0, 0, 0]], agg.get_rac())
