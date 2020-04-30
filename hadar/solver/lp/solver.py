#  Copyright (c) 2019-2020, RTE (https://www.rte-france.com)
#  See AUTHORS.txt
#  This Source Code Form is subject to the terms of the Apache License, version 2.0.
#  If a copy of the Apache License, version 2.0 was not distributed with this file, you can obtain one at http://www.apache.org/licenses/LICENSE-2.0.
#  SPDX-License-Identifier: Apache-2.0
#  This file is part of hadar-simulator, a python adequacy library for everyone.

import logging
from functools import reduce

import numpy as np
import multiprocessing
from typing import List, Dict

from ortools.linear_solver.pywraplp import Solver, Variable

from hadar.solver.input import Study
from hadar.solver.lp.domain import LPNode, LPProduction, LPConsumption, LPBorder
from hadar.solver.lp.mapper import InputMapper, OutputMapper
from hadar.solver.output import Result

logger = logging.getLogger(__name__)


class ObjectiveBuilder:
    """
    Build objective cost function.
    """

    def __init__(self, solver: Solver):
        """
        Initiate new objective to minimize inside ortools solver.

        :param solver: ortools solver instance to use
        """
        self.objective = solver.Objective()
        self.objective.SetMinimization()
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

    def add_node(self, node: LPNode):
        """
        Add cost in objective for each node element.

        :param node: node to add
        :return:
        """
        self._add_consumption(node.consumptions)
        self._add_productions(node.productions)
        self._add_borders(node.borders)

    def _add_consumption(self, consumptions: List[LPConsumption]):
        """
        Add consumption cost. That mean we add cost of a loss of consumption.

        :param consumptions: consumption with loss variable and cost
        :return:
        """
        for cons in consumptions:
            self.objective.SetCoefficient(cons.variable, cons.cost)
            self.logger.debug('Add consumption %s into objective', cons.type)

    def _add_productions(self, prods: List[LPProduction]):
        """
        Add production cost. That mean the cost to use a production.

        :param prods: production with cost to use and used quantity variable
        :return:
        """
        for prod in prods:
            self.objective.SetCoefficient(prod.variable, prod.cost)
            self.logger.debug('Add production %s into objective', prod.type)

    def _add_borders(self, borders: List[LPBorder]):
        """
        Add border cost. That mean cost to use a border capacity.

        :param borders: borders with cost to use and used quantity variable
        :return:
        """
        for border in borders:
            self.objective.SetCoefficient(border.variable, border.cost)
            self.logger.debug('Add border %s->%s to objective', border.src, border.dest)

    def build(self):
        pass  # Currently nothing are need at the end. But we keep builder pattern syntax


class AdequacyBuilder:
    """
    Build adequacy flow constraint.
    """
    def __init__(self, solver: Solver, horizon: int, nb_scn: int = 1):
        """
        Initiate.

        :param solver: ortools solver instance to use
        :param horizon: study horizon
        """
        self.horizon = horizon
        self.constraints = [dict() for _ in range(horizon * nb_scn)]
        self.borders = [list() for _ in range(horizon * nb_scn)]
        self.solver = solver
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

    def add_node(self, name: str, t: int, node: LPNode, scn: int, ):
        """
        Add flow constraint for a specific node.

        :param name: node name. Used to differentiate each equation
        :param t: timestamp index
        :param node: node to map constraint
        :param scn: scenario index
        :return:
        """
        i = t + self.horizon * scn

        # Set forced consumption
        load = sum([c.quantity for c in node.consumptions])*1.0
        self.constraints[i][name] = self.solver.Constraint(load, load)

        self._add_consumptions(name, i, node.consumptions)
        self._add_productions(name, i, node.productions)
        self._add_borders(name, i, node.borders)

    def _add_consumptions(self, name: str, i: int, consumptions: List[LPConsumption]):
        """
        Add consumption flow. That mean loss of consumption is set a production to match
        equation in case there are not enough production.

        :param name: node's name
        :param i: index to use to store constraint
        :param consumptions: consumptions with loss as variable
        :return:
        """
        for cons in consumptions:
            self.constraints[i][name].SetCoefficient(cons.variable, 1)
            self.logger.debug('Add lol %s for %s into adequacy constraint', cons.type, name)

    def _add_productions(self, name: str, i: int, productions: List[LPProduction]):
        """
        Add production flow. That mean production use is like a production.

        :param name: node's name
        :param i: index to use to store constraint
        :param productions: productions with production used as variable
        :return:
        """
        for prod in productions:
            self.constraints[i][name].SetCoefficient(prod.variable, 1)
            self.logger.debug('Add prod %s for %s into adequacy constraint', prod.type, name)

    def _add_borders(self, name: str, i: int, borders: List[LPBorder]):
        """
        Add borders. That mean the border export is like a consumption.
        After all node added. The same export, become also an import for destination node.
        Therefore border has to be set like production for destination node.

        :param name: node's name
        :param i: index to use to store constraint
        :param borders: border with export quantity as variable
        :return:
        """
        for bord in borders:
            self.borders[i].append(bord)
            self.constraints[i][name].SetCoefficient(bord.variable, -1)
            self.logger.debug('Add border %s for %s into adequacy constraint', bord.dest, name)

    def build(self):
        """
        Call when all node are added. Apply all import flow for each node.

        :return:
        """
        # Apply import border in adequacy
        for i in range(len(self.constraints)):
            for bord in self.borders[i]:
                self.constraints[i][bord.dest].SetCoefficient(bord.variable, 1)


def _solve_batch(params) -> List[List[Dict[str, LPNode]]]:
    if len(params) == 2: # Runtime
        study, scenarios = params
        solver = Solver('simple_lp_program', Solver.GLOP_LINEAR_PROGRAMMING)

        objective = ObjectiveBuilder(solver=solver)
        adequacy = AdequacyBuilder(solver=solver, horizon=study.horizon)

        in_mapper = InputMapper(solver=solver, study=study)
    else: # Test purpose only
        study, scenarios, solver, objective, adequacy, in_mapper = params

    variables = [[dict() for _ in range(study.horizon)] for _ in range(study.nb_scn)]

    # Build equation
    for scn in scenarios:
        for t in range(0, study.horizon):
            for name, node in study.nodes.items():
                variables[scn][t][name] = in_mapper.get_var(name=name, t=t, scn=scn)

                adequacy.add_node(name=name, t=t, scn=scn, node=variables[scn][t][name])
                objective.add_node(node=variables[scn][t][name])

    objective.build()
    adequacy .build()

    logger.info('Problem build. Start solver')
    solver.EnableOutput()
    solver.Solve()

    logger.info('Solver finish cost=%d', solver.Objective().Value())
    logger.debug(solver.ExportModelAsLpFormat(False).replace('\\', '').replace(',_', ','))

    return variables


def _solve(study: Study, out_mapper=None) -> Result:
    """
    Solve adequacy flow problem with a linear optimizer.

    :param study: study to compute
    :param solver: solver to used
    :param objective: objective builder to use
    :param adequacy: adequacy builder to use
    :return: Result object with optimal solution
    """
    out_mapper = OutputMapper(study) if out_mapper is None else out_mapper

    nb_part = multiprocessing.cpu_count()
    batches = np.array_split(np.arange(study.nb_scn), nb_part)
    pool = multiprocessing.Pool()
    res = pool.map(_solve_batch, ((study, batch) for batch in batches))

    variables = reduce(lambda a, b: a + b if b == list(list(dict())) else a, res)

    for scn in range(0, study.nb_scn):
        for t in range(0, study.horizon):
            for name, node in study.nodes.items():
                out_mapper.set_var(name=name, t=t, scn=scn, vars=variables[scn][t][name])

    return out_mapper.get_result()


def solve_lp(study: Study) -> Result:
    """
    Solve adequacy flow problem with a linear optimizer.

    :param study: study to compute
    :return: Result object with optimal solution
    """
    return _solve(study, OutputMapper(study=study))
