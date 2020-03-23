from abc import ABC, abstractmethod
from copy import deepcopy
from typing import List, Tuple

import pandas as pd
import numpy as np
from pandas import MultiIndex

from hadar.solver.input import DTO


class Plug(ABC, DTO):
    """
    Abstract class to represent connection between pipeline stage
    """
    def __init__(self, inputs: List[str], outputs: List[str]):
        self.inputs = inputs
        self.outputs = outputs
        self.inputs_no_used = []

    @abstractmethod
    def linkable_to(self, other) -> bool:
        """
        Defined if next stage is linkable with current.

        :param other: other stage to link
        :return: boolean True if linkable False else
        """
        pass

    @abstractmethod
    def __add__(self, other):
        """
        Override add method to add (link) plug with other.

        :param other: other plug to link
        :return: new plug whiched are merge from current and other
        """
        pass


class FreePlug(Plug):
    """
    Plug implementation when stage can use any kind of DataFrame, whatever columns present inside.
    """
    def __init__(self):
        """
        Init Plug.
        """
        Plug.__init__(self, inputs=[], outputs=[])

    def linkable_to(self, other: Plug) -> bool:
        """
        Defined if next stage is linkable with current.
        In this implementation, plug is always linkable

        :param other: other stage to link
        :return: True whatever
        """
        return True

    def __add__(self, other: Plug) -> Plug:
        """
        Override add method to add (link) plug with other.

        :param other: other plug to link
        :return: current plug if next plug is a FreePlug else return other plug
        """
        if not isinstance(other, FreePlug):
            return deepcopy(other)
        return deepcopy(self)


class RestrictedPlug(Plug):
    """
    Implementation where stage expect presence of precise columns.
    """
    def __init__(self, inputs, outputs):
        """
        Init Plug.

        :param inputs: list of column names mandatory inside DataFrame
        :param outputs: list of column names generated by stage
        """
        Plug.__init__(self, inputs=inputs, outputs=outputs)

    def linkable_to(self, next) -> bool:
        """
        Defined if next stage is linkable with current.
        In this implementation, plug is linkable only if input of next stage are present in output of current stage.

        :param next: other stage to link
        :return: True if current output contain mandatory columns for next input else False
        """
        if isinstance(next, FreePlug):
            return True
        return all(e in self.outputs for e in next.inputs)

    def __add__(self, next: Plug) -> Plug:
        """
        Override add method to add (link) plug with other.

        In this implementation, new stage keep inputs of current stage. New outputs are merged with next outputs
        and current output not used by next stage.

        $ [a --> b, \epsilon] + [b --> c] = [a --> c, \epsilon] $

        :param next: other plug to link
        :return: new plug with same input as current plug and merged output
        """
        if isinstance(next, FreePlug):
            return self

        # keep output not used by next pipeline and add next outputs
        next.outputs += [e for e in self.outputs if e not in next.inputs]
        return RestrictedPlug(inputs=self.inputs, outputs=next.outputs)


class Stage(ABC):
    """
    Abstract method which represent an unit of compute. It can be addition with other to create preprocessing
    pipeline.
    """
    def __init__(self, plug: Plug):
        """
        Init Stage.

        :param plug: plug to use to describe input and output interface used.
        """
        self.next_computes = []
        self.plug = plug

    def __add__(self, other):
        """
        Add stage with other to create pipeline. According to plug specified for each stage,
        some stages can't be linked which other. In this case an error will be raise during adding.

        :param other: other stage to execute after this one.
        :return: same stage with new compute queue to process and new plug configuration.
        """
        if not isinstance(other, Stage):
            raise ValueError('Only addition with other Stage is accepted not with %s' % type(other))

        if not self.plug.linkable_to(other.plug):
            raise ValueError("Pipeline can't be added %s has output %s and %s has input %s" %
                             (self.__class__.__name__, self.plug.outputs, other.__class__.__name__, other.plug.inputs))

        self.plug += other.plug
        self.next_computes.append(other._process_timeline)
        return self

    @abstractmethod
    def _process_timeline(self, timeline: pd.DataFrame) -> pd.DataFrame:
        """
        Method to implement when creating your own state. It take current DataFrame with scenario as first columns index,
        followed by columns type. Time is on index.

        Timeline with scenarios
        +--------+--------+-------+-------+--------+-------+-------+--------+-------+-------+
        |        |            0           |            1           |           ...          |
        +--------+--------+-------+-------+--------+-------+-------+--------+-------+-------+
        |   t    |   a    |   b   |  ...  |   a    |   b   |  ...  |   a    |   b   |  ...  |
        +--------+--------+-------+-------+--------+-------+-------+--------+-------+-------+
        |   0    |        |       |       |        |       |       |        |       |       |
        +--------+--------+-------+-------+--------+-------+-------+--------+-------+-------+
        |   1    |        |       |       |        |       |       |        |       |       |
        +--------+--------+-------+-------+--------+-------+-------+--------+-------+-------+
        |  ...   |        |       |       |        |       |       |        |       |       |
        +--------+--------+-------+-------+--------+-------+-------+--------+-------+-------+

        :param timeline: DataFrame explained above
        :return: new Timeline
        """
        pass

    def compute(self, timeline: pd.DataFrame) -> pd.DataFrame:
        """
        Launch Stage computation and all other stage if stage is linked.

        Timeline without scenarios
        +--------+--------+-------+-------+
        |   t    |   a    |   b   |  ...  |
        +--------+--------+-------+-------+
        |   0    |        |       |       |
        +--------+--------+-------+-------+
        |   1    |        |       |       |
        +--------+--------+-------+-------+
        |  ...   |        |       |       |
        +--------+--------+-------+-------+

        Timeline with scenarios
        +--------+--------+-------+-------+--------+-------+-------+--------+-------+-------+
        |        |            0           |            1           |           ...          |
        +--------+--------+-------+-------+--------+-------+-------+--------+-------+-------+
        |   t    |   a    |   b   |  ...  |   a    |   b   |  ...  |   a    |   b   |  ...  |
        +--------+--------+-------+-------+--------+-------+-------+--------+-------+-------+
        |   0    |        |       |       |        |       |       |        |       |       |
        +--------+--------+-------+-------+--------+-------+-------+--------+-------+-------+
        |   1    |        |       |       |        |       |       |        |       |       |
        +--------+--------+-------+-------+--------+-------+-------+--------+-------+-------+
        |  ...   |        |       |       |        |       |       |        |       |       |
        +--------+--------+-------+-------+--------+-------+-------+--------+-------+-------+

        :param timeline: DataFrame explained above
        :return: new Timeline
        """
        # Add 0th scenarios column if not present.
        if not isinstance(timeline.columns, MultiIndex):
            columns = timeline.columns.values
            timeline.columns = MultiIndex.from_arrays([np.zeros_like(columns), columns])

        timeline = self._process_timeline(timeline.copy())
        for compute in self.next_computes:
            timeline = compute(timeline.copy())

        return timeline


class FocusStage(Stage, ABC):
    """
    Stage focuses on same behaviour for any scenarios.
    """
    def __init__(self, plug):
        """
        Init Stage.

        :param plug: plug to use to describe input and output interface used.
        """
        Stage.__init__(self, plug)

    @abstractmethod
    def _process_scenarios(self, n_scn: int, scenario: pd.DataFrame) -> pd.DataFrame:
        """
        Method to implement to create your own stage. For this stage, you will reveive only this kind of data.
        +--------+--------+-------+-------+
        |   t    |   a    |   b   |  ...  |
        +--------+--------+-------+-------+
        |   0    |        |       |       |
        +--------+--------+-------+-------+
        |   1    |        |       |       |
        +--------+--------+-------+-------+
        |  ...   |        |       |       |
        +--------+--------+-------+-------+

        You don't need to handle if there are scenarios or not. We handle for you. Just implement behaviour to apply
        for every scenario.

        :param n_scn: scenario numero inside Timeline
        :param scenario: slice of one scenario inside Timeline
        :return: new slice with updated data.
        """
        pass

    def _process_timeline(self, timeline: pd.DataFrame) -> pd.DataFrame:
        """
        Implementation to manage stage behaviour independently scenario of not.

        :param timeline:
        :return:
        """
        scenarios = timeline.columns.get_level_values(0).unique()

        n_scn = len(scenarios)
        n_time = timeline.shape[0]
        n_type = len(self.plug.outputs)



        # Create an index for time like
        # [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, ..., n_time-1]
        #  <--- n_type --->  <--- n_type --->  ...
        index_time = np.tile(np.arange(n_scn), (n_type, 1)).T.flatten()

        # Create an index for type like
        # [a, b, c, d, e, f, a, b, c, d, e, f, ..... x n_scn]
        index_type = np.tile(self.plug.outputs, n_scn)

        # Merge index for MultiIndex
        # [[0, a], [0, b], [0, c], ..., [1, a], [1, b], [1, c], ... ]
        index = MultiIndex.from_arrays([index_time, index_type])

        output = pd.DataFrame(data=np.zeros((n_time, n_type * n_scn)), columns=index)
        for scn in timeline.columns.get_level_values(0).unique():
            output[scn] = self._process_scenarios(scn, timeline[scn])
        return output


class Clip(Stage):
    def __init__(self, lower: float = None, upper: float = None):
        Stage.__init__(self, plug=FreePlug())
        self.lower = lower
        self.upper = upper

    def _process_timeline(self, timeline: pd.DataFrame) -> pd.DataFrame:
        return timeline.clip(lower=self.lower, upper=self.upper)