import pickle
import unittest
from unittest.mock import MagicMock

from hadar.solver.input import Study, Consumption
from hadar.solver.output import Result, OutputConsumption, OutputNode
from hadar.solver.remote.solver import _solve_remote_wrap


class MockRequest:
    pass


class MockResponse:
    def __init__(self, content, code=200):
        self.content = content
        self.status_code = code

class RemoteSolverTest(unittest.TestCase):

    def setUp(self) -> None:
        self.study = Study(node_names=['a']) \
            .add_on_node('a', data=Consumption(cost=0, quantity=[0], type='load'))

        self.result = Result(nodes={
            'a': OutputNode(consumptions=[OutputConsumption(cost=0, quantity=[0], type='load')],
                            productions=[], borders=[])})

    def test_success(self):
        requests = MockRequest()
        requests.post = MagicMock(return_value=MockResponse(pickle.dumps(self.result)))

        _solve_remote_wrap(study=self.study, url='localhost', token='pwd', rqt=requests)

        requests.post.assert_called_with(data=pickle.dumps(self.study), url='localhost', params={'token': 'pwd'})

    def test_404(self):
        requests = MockRequest()
        requests.post = MagicMock(return_value=MockResponse(content=None, code=404))

        self.assertRaises(ValueError,
                          lambda: _solve_remote_wrap(study=self.study, url='localhost', token='pwd', rqt=requests))

        requests.post.assert_called_with(data=pickle.dumps(self.study), url='localhost', params={'token': 'pwd'})

    def test_403(self):
        requests = MockRequest()
        requests.post = MagicMock(return_value=MockResponse(content=None, code=403))

        self.assertRaises(ValueError,
                          lambda: _solve_remote_wrap(study=self.study, url='localhost', token='pwd', rqt=requests))

        requests.post.assert_called_with(data=pickle.dumps(self.study), url='localhost', params={'token': 'pwd'})

    def test_500(self):
        requests = MockRequest()
        requests.post = MagicMock(return_value=MockResponse(content=None, code=500))

        self.assertRaises(IOError,
                          lambda: _solve_remote_wrap(study=self.study, url='localhost', token='pwd', rqt=requests))

        requests.post.assert_called_with(data=pickle.dumps(self.study), url='localhost', params={'token': 'pwd'})